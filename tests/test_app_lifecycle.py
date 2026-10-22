"""Session tracking and ownership handoff through the public App CLI."""
import json
import subprocess
import unittest

import test_app_requests


class AppLifecycleTests(unittest.TestCase):
    tearDown = test_app_requests.AppRequestTests.tearDown
    run_cmd = test_app_requests.AppRequestTests.run_cmd
    app = test_app_requests.AppRequestTests.app
    prepare = test_app_requests.AppRequestTests.prepare
    receipt = test_app_requests.AppRequestTests.receipt
    receive = test_app_requests.AppRequestTests.receive

    def setUp(self):
        test_app_requests.AppRequestTests.setUp(self)
        self.created = self.prepare()
        self.receive(self.created)
        (self.task / 'STATUS').write_text('running | user task | checking\n')

    def observe(self, operation='read', revision='turn-1', state='idle'):
        request = self.prepare(operation, payload={})
        payload = {'request_id': request['id'], 'owner_epoch': request['owner_epoch'],
                   'entry': request['entry'], 'status': 'observed', 'session': 'lead-1',
                   'workspace': str(self.root), 'cwd': str(self.task), 'state': state,
                   'revision': revision, 'cursor': 'cursor-' + revision,
                   'context': 'User latest instruction: inspect only.', 'source': 'native read',
                   'evidence': {field: 'native readback: ' + field for field in
                                ('session', 'workspace', 'cwd', 'state', 'revision', 'cursor', 'context')}}
        self.receive(request, payload)
        return request, payload

    def test_idle_observation_keeps_task_running_and_show_reports_local_status(self):
        request, _ = self.observe()
        shown = self.app('show', '--session', 'dispatch-1')
        binding = shown['tasks'][str(self.task)]
        self.assertEqual(binding['state'], 'running')
        self.assertTrue(binding['active'])
        self.assertEqual(binding['observation']['state'], 'idle')
        self.assertEqual(binding['observation']['request_id'], request['id'])
        self.assertEqual(binding['task_status']['state'], 'running')
        self.assertEqual(binding['task_status']['raw'], 'running | user task | checking\n')
        self.assertFalse(self.log.exists())

    def test_unknown_and_missing_recover_by_read_without_recreating_or_replaying(self):
        for status in ('unknown', 'missing'):
            request = self.prepare('read', payload={})
            self.assertEqual(request['target_session'], 'lead-1')
            self.assertNotIn('brief', request)
            self.assertNotIn('prompt', request)
            self.receive(request, {'request_id': request['id'], 'owner_epoch': request['owner_epoch'],
                                  'entry': request['entry'], 'status': status, 'session': 'lead-1',
                                  'workspace': str(self.root), 'cwd': str(self.task),
                                  'source': 'native read', 'evidence': 'session currently unavailable'})
            shown = self.app('show', '--session', 'dispatch-1')
            self.assertEqual(shown['tasks'][str(self.task)]['observation']['state'], status)
            self.assertEqual(shown['tasks'][str(self.task)]['session'], 'lead-1')
            self.prepare('create', ok=False)
        request, _ = self.observe('wait', revision='turn-2', state='working')
        self.assertIsNone(request['after_cursor'])

    def followup(self, observation, payload, ok=True):
        return self.prepare('followup', payload={'brief': 'Inspect user latest context; write report.',
                            'observation': observation['id'], 'revision': payload['revision'],
                            'cursor': payload['cursor']}, ok=ok)

    def sent_receipt(self, request):
        return {'request_id': request['id'], 'owner_epoch': request['owner_epoch'],
                'entry': request['entry'], 'status': 'sent', 'session': 'lead-1',
                'workspace': str(self.root), 'cwd': str(self.task), 'sent': True,
                'revalidated_revision': request['revalidate']['revision'],
                'revalidated_cursor': request['revalidate']['cursor'],
                'model': 'desktop-model', 'effort': 'high', 'source': 'native send',
                'evidence': {field: 'native readback: ' + field for field in
                             ('session', 'workspace', 'cwd', 'sent', 'revalidated_revision',
                              'revalidated_cursor', 'model', 'effort')}}

    def test_followup_requires_latest_observation_and_keeps_actual_model(self):
        self.prepare('followup', payload={'brief': 'old message'}, ok=False)
        old, old_payload = self.observe()
        latest, latest_payload = self.observe('wait', revision='turn-2')
        self.followup(old, old_payload, ok=False)
        # New-session defaults must not affect an existing Lead.
        roles = self.root / '.agenthelm/config/roles.toml'
        roles.write_text(roles.read_text() + '\n[app.defaults.codex]\nmodel="foreign"\neffort="low"\n')
        request = self.followup(latest, latest_payload)
        self.assertEqual(request['effective_request'], {'model': 'desktop-model', 'effort': 'high'})
        self.assertNotIn('model_binding', request)
        self.assertEqual(request['revalidate']['source'], 'native read')
        self.assertIn('before sending', request['host_instructions'])
        self.followup(latest, latest_payload, ok=False)
        self.receive(request, self.sent_receipt(request))
        self.followup(latest, latest_payload, ok=False)
        shown = self.app('show', '--session', 'dispatch-1')
        self.assertEqual(shown['tasks'][str(self.task)]['session'], 'lead-1')
        self.assertEqual(shown['sessions']['lead-1']['actual'], {'model': 'desktop-model', 'effort': 'high'})

    def test_explicit_handoff_preserves_lead_and_revokes_old_requests_and_dispatcher(self):
        pending = self.prepare('read', payload={})
        self.app('release', '--session', 'foreign', '--to', 'dispatch-2', ok=False)
        self.app('release', '--session', 'dispatch-1', '--to', 'dispatch-2')
        for identifier in ('dispatch-1', 'dispatch-2', 'foreign'):
            self.app('register', '--entry', 'app.codex', '--session', identifier, ok=False)
        self.app('claim', '--session', 'foreign', '--entry', 'app.codex', ok=False)
        self.app('claim', '--session', 'dispatch-2', '--entry', 'app.ccd', ok=False)
        claimed = self.app('claim', '--session', 'dispatch-2', '--entry', 'app.codex')
        self.assertEqual(claimed['dispatcher'], {'session': 'dispatch-2', 'entry': 'app.codex'})
        self.assertEqual(claimed['owner_epoch'], 2)
        self.assertEqual(claimed['tasks'][str(self.task)]['session'], 'lead-1')
        self.assertIn('lead-1', claimed['sessions'])
        self.receive(pending, {}, ok=False)
        self.prepare('read', payload={}, ok=False)
        self.app('show', '--session', 'dispatch-1', ok=False)
        self.app('release', '--session', 'dispatch-1', '--to', 'dispatch-3', ok=False)
        self.app('capabilities', '--session', 'dispatch-2', payload={
            'entry': 'app.codex', 'source': 'new native inventory', 'capabilities': self.capabilities})
        request = self.prepare('read', session='dispatch-2', payload={})
        self.assertEqual(request['target_session'], 'lead-1')
        self.assertNotIn('brief', request)

    def test_finish_requires_local_done_and_keeps_chat_and_history(self):
        self.app('finish', '--session', 'dispatch-1', '--task', str(self.task), ok=False)
        self.observe(state='done')
        self.app('finish', '--session', 'dispatch-1', '--task', str(self.task), ok=False)
        (self.task / 'STATUS').write_text('done | user task | report verified\n')
        self.app('finish', '--session', 'dispatch-1', '--task', str(self.task))
        shown = self.app('show', '--session', 'dispatch-1')
        binding = shown['tasks'][str(self.task)]
        self.assertFalse(binding['active'])
        self.assertEqual(binding['session'], 'lead-1')
        self.assertEqual(binding['history'][-1]['event'], 'finished')
        self.assertIn('lead-1', shown['sessions'])
        self.assertIn(self.created['id'], shown['requests'])
        self.assertEqual(binding['task_status']['state'], 'done')
        self.prepare('read', payload={}, ok=False)
        self.prepare('executor', session='lead-1', payload={**self.parameters, 'brief': 'late work'}, ok=False)
        self.assertFalse(self.log.exists())

    def test_lead_limit_counts_pending_and_running_and_finished_task_releases_capacity(self):
        first = self.task
        self.env['RESEARCH_MAX_LEADS'] = '1'
        self.task = self.root / 'experiments/002-limited'
        self.task.mkdir()
        (self.task / 'README.md').write_text('# second task')
        error = self.prepare(ok=False)
        self.assertIn('concurrency limit', error.stderr)
        (first / 'STATUS').write_text('done | task | verified')
        self.app('finish', '--session', 'dispatch-1', '--task', str(first))
        pending = self.prepare()
        self.assertEqual(pending['operation'], 'create')
        self.task = self.root / 'experiments/003-limited'
        self.task.mkdir()
        (self.task / 'README.md').write_text('# third task')
        self.assertIn('concurrency limit', self.prepare(ok=False).stderr)

    def test_unresolved_executor_and_followup_block_release_and_finish(self):
        (self.task / 'STATUS').write_text('done | task | verified')
        executor = self.prepare('executor', session='lead-1',
                                payload={**self.parameters, 'brief': 'check result'})
        self.assertIn('unresolved write', self.app('release', '--session', 'dispatch-1',
                      '--to', 'dispatch-2', ok=False).stderr)
        self.assertIn('unresolved write', self.app('finish', '--session', 'dispatch-1',
                      '--task', str(self.task), ok=False).stderr)
        self.receive(executor, {'request_id': executor['id'], 'owner_epoch': 1, 'entry': 'app.codex',
                               'status': 'failed', 'created': False, 'source': 'native host',
                               'evidence': 'subagent rejected before creation'})
        observation, payload = self.observe()
        followup = self.followup(observation, payload)
        unknown = {'request_id': followup['id'], 'owner_epoch': 1, 'entry': 'app.codex',
                   'status': 'unknown', 'session': 'lead-1', 'workspace': str(self.root),
                   'cwd': str(self.task), 'source': 'native host', 'evidence': 'send outcome unknown'}
        self.receive(followup, unknown)
        self.app('release', '--session', 'dispatch-1', '--to', 'dispatch-2', ok=False)
        self.app('finish', '--session', 'dispatch-1', '--task', str(self.task), ok=False)
        self.followup(observation, payload, ok=False)
        self.receive(followup, self.sent_receipt(followup))
        self.app('finish', '--session', 'dispatch-1', '--task', str(self.task))

    def test_new_observation_cannot_be_overwritten_by_late_receipt_or_stale_followup(self):
        first, first_payload = self.observe()
        followup = self.followup(first, first_payload)
        old_read = self.prepare('read', payload={})
        latest, latest_payload = self.observe('wait', revision='turn-3')
        old_payload = dict(first_payload, request_id=old_read['id'])
        self.assertIn('stale observation', self.receive(old_read, old_payload, ok=False).stderr)
        self.assertIn('stale', self.receive(followup, self.sent_receipt(followup), ok=False).stderr)
        stale = {'request_id': followup['id'], 'owner_epoch': 1, 'entry': 'app.codex',
                 'status': 'stale', 'sent': False, 'session': 'lead-1', 'workspace': str(self.root),
                 'cwd': str(self.task), 'source': 'native reread', 'evidence': 'user supplied newer instructions'}
        self.receive(followup, stale)
        self.followup(latest, latest_payload)

    def test_successful_send_requires_a_read_started_after_send_before_another_followup(self):
        observation, payload = self.observe()
        followup = self.followup(observation, payload)
        before_send = self.prepare('read', payload={})
        self.receive(followup, self.sent_receipt(followup))
        self.receive(before_send, dict(payload, request_id=before_send['id']), ok=False)
        fresh, fresh_payload = self.observe(revision='after-send')
        self.followup(fresh, fresh_payload)

    def test_symlinked_status_is_not_followed_for_show_or_finish(self):
        outside = self.base / 'outside-status'
        outside.write_text('done | outside | private')
        (self.task / 'STATUS').unlink()
        (self.task / 'STATUS').symlink_to(outside)
        for command in (('show', '--session', 'dispatch-1'),
                        ('finish', '--session', 'dispatch-1', '--task', str(self.task))):
            error = self.app(*command, ok=False)
            self.assertIn('symbolic link', error.stderr)
            self.assertNotIn('private', error.stdout)
        self.assertEqual(outside.read_text(), 'done | outside | private')

    def test_concurrent_create_obeys_limit_in_same_reservation_transaction(self):
        self.env['RESEARCH_MAX_LEADS'] = '2'
        processes = []
        for name in ('002-left', '003-right'):
            task = self.root / 'experiments' / name
            task.mkdir()
            (task / 'README.md').write_text('# capacity task')
            command = [str(self.root / 'bin/app-session'), 'prepare', '--session', 'dispatch-1',
                       '--operation', 'create', '--task', str(task)]
            processes.append(subprocess.Popen(command, cwd=self.root, env=self.env, text=True,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE))
        outputs = [process.communicate(json.dumps(self.parameters), timeout=15) for process in processes]
        self.assertEqual(sorted(process.returncode for process in processes), [0, 1])
        self.assertTrue(any('concurrency limit' in error for _, error in outputs))
        shown = self.app('show', '--session', 'dispatch-1')
        self.assertEqual(len(shown['tasks']), 2)

    def test_unresolved_create_blocks_handoff_without_losing_original_owner(self):
        self.task = self.root / 'experiments/002-pending'
        self.task.mkdir()
        (self.task / 'README.md').write_text('# pending task')
        self.prepare()
        error = self.app('release', '--session', 'dispatch-1', '--to', 'dispatch-2', ok=False)
        self.assertIn('unresolved write', error.stderr)
        self.assertEqual(self.app('show', '--session', 'dispatch-1')['owner_epoch'], 1)

    def test_verified_manual_model_change_is_preserved_on_followup(self):
        original, payload = self.observe()
        latest = self.prepare('read', payload={})
        manual = dict(payload, request_id=latest['id'], revision='manual-change', cursor='cursor-manual',
                      actual={'model': 'user-chosen-model', 'effort': 'xhigh'})
        manual['evidence'] = {**manual['evidence'], 'model': 'native latest turn model',
                              'effort': 'native latest turn effort'}
        self.receive(latest, manual)
        self.followup(original, payload, ok=False)
        followup = self.followup(latest, manual)
        self.assertEqual(followup['effective_request'], {'model': 'user-chosen-model', 'effort': 'xhigh'})
        receipt = self.sent_receipt(followup)
        receipt.update(model='user-chosen-model', effort='xhigh')
        self.receive(followup, receipt)
        shown = self.app('show', '--session', 'dispatch-1')
        self.assertEqual(shown['sessions']['lead-1']['actual'], manual['actual'])
        self.assertEqual(shown['tasks'][str(self.task)]['actual'], manual['actual'])

    def test_damaged_lifecycle_state_reports_error_without_dispatching_or_reset(self):
        state = self.app('show', '--session', 'dispatch-1')
        target = self.root / '.agenthelm/state/app-sessions.json'
        for changes in ({'observation_counter': True}, {'active': 'yes'}, {'history': {}},
                        {'session': 'unbound-lead'}):
            damaged = json.loads(json.dumps(state))
            damaged['tasks'][str(self.task)].update(changes)
            raw = json.dumps(damaged)
            target.write_text(raw)
            error = self.app('show', '--session', 'dispatch-1', ok=False)
            self.assertIn('damaged App state', error.stderr)
            self.assertEqual(target.read_text(), raw)

    def test_observation_and_followup_require_matching_target_and_native_evidence(self):
        observed, payload = self.observe()
        request = self.prepare('read', payload={})
        for changes in ({'session': 'other-session'}, {'source': ''}, {'evidence': {}},
                        {'actual': {'model': 'manual-model'}},
                        {'actual': {'model': 'manual-model', 'effort': 'high'}}):
            invalid = dict(payload, request_id=request['id'], **changes)
            self.receive(request, invalid, ok=False)
        shown = self.app('show', '--session', 'dispatch-1')
        self.assertEqual(shown['tasks'][str(self.task)]['actual'], {'model': 'desktop-model', 'effort': 'high'})
        followup = self.followup(observed, payload)
        for changes in ({'revalidated_revision': 'user-changed'}, {'revalidated_cursor': 'new-cursor'},
                        {'model': 'unverified-new-model'}, {'effort': 'low'}, {'evidence': {}}):
            self.receive(followup, dict(self.sent_receipt(followup), **changes), ok=False)
        self.receive(followup, self.sent_receipt(followup))


if __name__ == '__main__':
    unittest.main()
