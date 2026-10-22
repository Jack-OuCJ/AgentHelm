"""Host request protocol through public App and role-start CLIs."""
import json
import subprocess
import unittest

import test_app_sessions


class AppRequestTests(unittest.TestCase):
    tearDown = test_app_sessions.AppSessionTests.tearDown
    run_cmd = test_app_sessions.AppSessionTests.run_cmd
    app = test_app_sessions.AppSessionTests.app

    def setUp(self):
        test_app_sessions.AppSessionTests.setUp(self)
        self.task = self.root / 'experiments/001-app'
        (self.task / 'findings').mkdir(parents=True)
        (self.task / 'README.md').write_text('# Task\n可写：findings；验收：检查报告。\n')
        self.app('register', '--entry', 'app.codex', '--session', 'dispatch-1')
        self.capabilities = {name: {'available': True, 'source': 'fake host inventory'} for name in
                             ('create', 'read', 'wait', 'followup', 'model', 'effort',
                              'verify_model', 'native_executor')}
        self.capabilities['verify_model']['fields'] = ['model', 'effort']
        self.capabilities['model']['values'] = ['desktop-model']
        self.capabilities['effort']['combinations'] = {'desktop-model': ['high']}
        self.app('capabilities', '--session', 'dispatch-1', payload={
            'entry': 'app.codex', 'source': 'fake tool inventory', 'capabilities': self.capabilities})
        self.parameters = {'defaults': {'model': 'desktop-model', 'effort': 'high',
                                       'source': 'fake App settings', 'evidence': 'settings readback'}}

    def prepare(self, operation='create', session='dispatch-1', payload=None, ok=True):
        return self.app('prepare', '--session', session, '--operation', operation,
                        '--task', str(self.task), payload=self.parameters if payload is None else payload, ok=ok)

    def receipt(self, request, status='created', session='lead-1'):
        return {'request_id': request['id'], 'owner_epoch': request['owner_epoch'],
                'entry': 'app.codex', 'status': status, 'session': session,
                'workspace': str(self.root), 'cwd': str(self.task), 'visible': True,
                'independent': True, 'executed': True, 'model': 'desktop-model', 'effort': 'high',
                'evidence': {name: 'fake host readback: ' + name for name in
                             ('session', 'workspace', 'cwd', 'visible', 'independent',
                              'executed', 'model', 'effort', 'native', 'parent_session')}}

    def receive(self, request, receipt=None, ok=True):
        return self.app('result', '--session', request['caller_session'], '--request', request['id'],
                        payload=self.receipt(request) if receipt is None else receipt, ok=ok)

    def test_host_receipt_binds_a_real_visible_executed_lead_and_effective_model(self):
        request = self.prepare()
        self.receive(request)
        state = self.app('show', '--session', 'dispatch-1')
        binding = state['tasks'][str(self.task)]
        self.assertEqual(binding['session'], 'lead-1')
        self.assertEqual(binding['state'], 'running')
        self.assertEqual(binding['actual'], {'model': 'desktop-model', 'effort': 'high'})
        self.assertEqual(state['sessions']['lead-1']['entry'], 'app.codex')
        self.assertEqual(state['requests'][request['id']]['status'], 'succeeded')
        self.assertIn('already', self.receive(request, ok=False).stderr)

    def test_bad_receipts_keep_pending_and_block_duplicate_creation(self):
        request = self.prepare()
        for changes in ({'request_id': 'foreign'}, {'owner_epoch': 2}, {'entry': 'app.ccd'},
                        {'session': 'dispatch-1'}, {'visible': False}, {'independent': False},
                        {'workspace': str(self.home)}, {'cwd': str(self.root)},
                        {'executed': False}, {'model': 'parent-model'}, {'effort': 'low'},
                        {'evidence': {'model': 'request arguments'}}):
            receipt = self.receipt(request)
            receipt.update(changes)
            self.receive(request, receipt, ok=False)
            shown = self.app('show', '--session', 'dispatch-1')
            self.assertEqual(shown['requests'][request['id']]['status'], 'pending')
            self.assertEqual(shown['tasks'][str(self.task)]['state'], 'pending')
        self.prepare(ok=False)
        self.receive(request)

    def test_unknown_and_queued_outcomes_recover_without_duplicate_creation(self):
        request = self.prepare()
        for status in ('queued', 'unknown', 'failed'):
            receipt = {'request_id': request['id'], 'owner_epoch': 1, 'entry': 'app.codex',
                       'status': status, 'source': 'native host', 'evidence': 'outcome not final'}
            self.receive(request, receipt)
            self.prepare(ok=False)
        self.receive(request)

    def test_confirmed_no_session_failure_allows_a_new_request(self):
        request = self.prepare()
        self.receive(request, {'request_id': request['id'], 'owner_epoch': 1, 'entry': 'app.codex',
                               'status': 'failed', 'created': False,
                               'source': 'native host', 'evidence': 'creation rejected before start'})
        retry = self.prepare()
        self.assertNotEqual(request['id'], retry['id'])

    def test_capability_and_default_evidence_gaps_stop_before_pending_write(self):
        for capability in ('create', 'read', 'wait', 'followup', 'model', 'effort', 'verify_model'):
            capabilities = json.loads(json.dumps(self.capabilities))
            capabilities[capability]['available'] = False
            self.app('capabilities', '--session', 'dispatch-1', payload={
                'entry': 'app.codex', 'source': 'fake inventory', 'capabilities': capabilities})
            self.assertIn(capability, self.prepare(ok=False).stderr)
        self.app('capabilities', '--session', 'dispatch-1', payload={
            'entry': 'app.codex', 'source': 'fake inventory', 'capabilities': self.capabilities})
        for payload in ({}, {'defaults': {'model': 'desktop-model', 'effort': 'high'}},
                        {'defaults': {'model': 'foreign', 'effort': 'high', 'source': 'settings', 'evidence': 'read'}},
                        {'defaults': {'model': 'desktop-model', 'effort': 'low', 'source': 'settings', 'evidence': 'read'}}):
            self.prepare(payload=payload, ok=False)
        self.assertEqual(self.app('show', '--session', 'dispatch-1')['tasks'], {})

    def test_bound_app_session_overrides_herdr_at_lead_entry(self):
        result = self.run_cmd('bin/spawn-lead', self.task, '--session', 'dispatch-1',
                              '--app-params', json.dumps(self.parameters))
        request = json.loads(result.stdout)
        self.assertEqual(request['entry'], 'app.codex')
        self.assertEqual(request['operation'], 'create')
        self.assertFalse(self.log.exists())
        self.assertIn('pending', self.run_cmd('bin/spawn-lead', self.task, '--session',
                      'dispatch-1', '--app-params', json.dumps(self.parameters), ok=False).stderr)

    def test_new_task_uses_bound_app_and_stays_unstarted_until_receipt(self):
        output = self.run_cmd('bin/new-task', 'new-app', '--session', 'dispatch-1',
                              '--app-params', json.dumps(self.parameters), input='# New card')
        request = json.loads(output.stdout)
        self.assertEqual(request['task'], str(self.root / 'experiments/002-new-app'))
        self.assertIn('# New card', request['prompt'])
        status = self.root / 'experiments/002-new-app/STATUS'
        self.assertFalse(status.exists() and status.read_text().startswith('running'))
        self.assertFalse(self.log.exists())

    def test_native_executor_runs_only_under_bound_lead_and_verifies_its_parameters(self):
        request = self.prepare()
        self.receive(request)
        self.prepare('executor', payload={**self.parameters, 'brief': 'write report'}, ok=False)
        output = self.run_cmd('bin/run-executor', self.task, '--session', 'lead-1', '--role', 'hard',
                              '--app-params', json.dumps(self.parameters), input='只写 findings；检查报告。')
        executor = json.loads(output.stdout)
        self.assertEqual(executor['operation'], 'executor')
        self.assertEqual(executor['caller_session'], 'lead-1')
        self.assertEqual(executor['role'], 'hard')
        self.assertIn('只写 findings；检查报告。', executor['prompt'])
        receipt = self.receipt(executor, session='native-1')
        receipt.update(native=True, parent_session='lead-1')
        self.receive(executor, receipt)
        shown = self.app('show', '--session', 'dispatch-1')
        self.assertEqual(shown['sessions']['native-1']['role'], 'executor')
        self.assertEqual(shown['tasks'][str(self.task)]['session'], 'lead-1')
        self.assertFalse(self.log.exists())

    def test_app_entry_errors_do_not_fall_back_to_cli_or_create_a_task(self):
        for args in (('--app-params', json.dumps(self.parameters)), ('--entry', 'app.codex'), ('--session', 'unknown'),
                     ('--entry', 'app.ccd', '--session', 'dispatch-1'),
                     ('--session', 'dispatch-1', '--kind', 'codex')):
            self.run_cmd('bin/new-task', 'rejected', *args, input='# card', ok=False)
            self.run_cmd('bin/spawn-lead', self.task, *args, ok=False)
        self.assertFalse((self.root / 'experiments/002-rejected').exists())
        self.assertFalse(self.log.exists())
        self.prepare()
        self.run_cmd('bin/spawn-lead', self.task, ok=False)
        self.run_cmd('bin/run-executor', self.task, input='brief', ok=False)
        self.assertFalse(self.log.exists())

    def test_missing_native_executor_capability_and_wrong_parent_are_rejected(self):
        self.capabilities['native_executor']['available'] = False
        self.app('capabilities', '--session', 'dispatch-1', payload={
            'entry': 'app.codex', 'source': 'inventory', 'capabilities': self.capabilities})
        request = self.prepare()
        self.receive(request)
        failure = self.prepare('executor', session='lead-1',
                               payload={**self.parameters, 'brief': 'brief'}, ok=False)
        self.assertIn('native_executor', failure.stderr)

    def test_executor_cannot_inherit_parent_for_unresolved_app_defaults(self):
        request = self.prepare()
        self.receive(request)
        failure = self.prepare('executor', session='lead-1', payload={'brief': 'brief'}, ok=False)
        self.assertIn('App default', failure.stderr)
        request = self.prepare('executor', session='lead-1', payload={**self.parameters, 'brief': 'brief'})
        receipt = self.receipt(request, session='executor-1')
        receipt.update(native=True, parent_session='dispatch-1')
        self.receive(request, receipt, ok=False)
        receipt['parent_session'] = 'lead-1'
        self.receive(request, receipt)

    def test_symlinked_task_card_is_not_read_as_delegation_context(self):
        outside = self.base / 'private-card'
        outside.write_text('private task material')
        (self.task / 'README.md').unlink()
        (self.task / 'README.md').symlink_to(outside)
        error = self.prepare(ok=False)
        self.assertIn('symbolic link', error.stderr)
        self.assertEqual(self.app('show', '--session', 'dispatch-1')['tasks'], {})

    def test_concurrent_create_preparations_reserve_exactly_one_lead(self):
        command = [str(self.root / 'bin/app-session'), 'prepare', '--session', 'dispatch-1',
                   '--operation', 'create', '--task', str(self.task)]
        processes = [subprocess.Popen(command, cwd=self.root, env=self.env, text=True,
                                      stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE) for _ in range(2)]
        outputs = [process.communicate(json.dumps(self.parameters), timeout=15) for process in processes]
        self.assertEqual(sorted(process.returncode for process in processes), [0, 1])
        self.assertEqual(len(self.app('show', '--session', 'dispatch-1')['requests']), 1)
        self.assertTrue(any('pending' in error for _, error in outputs))

    def test_one_real_session_cannot_bind_two_tasks(self):
        first = self.prepare()
        self.receive(first)
        self.task = self.root / 'experiments/002-second'
        self.task.mkdir()
        (self.task / 'README.md').write_text('# second task')
        second = self.prepare()
        self.assertIn('already bound', self.receive(second, ok=False).stderr)
        self.assertEqual(self.app('show', '--session', 'dispatch-1')['tasks'][str(self.task)]['state'], 'pending')

    def test_new_task_does_not_create_card_when_app_defaults_cannot_be_resolved(self):
        self.run_cmd('bin/new-task', 'missing-defaults', '--session', 'dispatch-1', input='# card', ok=False)
        self.assertFalse((self.root / 'experiments/002-missing-defaults').exists())

    def test_explicit_cli_entry_can_start_without_app_binding_under_app_workspace_default(self):
        (self.root / '.agenthelm/config/env').write_text('app\n')
        output = self.run_cmd('bin/spawn-lead', self.task, '--entry', 'cli.codex')
        self.assertIn('当前运行环境：cli-plain', output.stdout)
        self.assertFalse(self.log.exists())

    def test_prepare_create_is_complete_and_does_not_start_cli_or_claim_running(self):
        request = self.prepare()
        self.assertEqual(request['operation'], 'create')
        self.assertEqual(request['entry'], 'app.codex')
        self.assertEqual(request['workspace'], str(self.root))
        self.assertEqual(request['task'], str(self.task))
        self.assertEqual(request['owner_epoch'], 1)
        self.assertEqual(request['model_binding']['model'], None)
        self.assertEqual(request['effective_request'], {'model': 'desktop-model', 'effort': 'high'})
        self.assertIn(str(self.root / 'AGENTS.md'), request['prompt'])
        self.assertIn('可写：findings；验收：检查报告。', request['prompt'])
        self.assertIn('native', request['host_instructions'])
        shown = self.app('show', '--session', 'dispatch-1')
        self.assertEqual(shown['tasks'][str(self.task)]['state'], 'pending')
        self.assertFalse(self.log.exists())
        self.assertFalse((self.task / 'STATUS').exists())
        self.assertIn('pending', self.prepare(ok=False).stderr)


class CcdExecutorTests(unittest.TestCase):
    tearDown = test_app_sessions.AppSessionTests.tearDown
    run_cmd = test_app_sessions.AppSessionTests.run_cmd
    app = test_app_sessions.AppSessionTests.app

    def setUp(self):
        test_app_sessions.AppSessionTests.setUp(self)
        self.task = self.root / 'experiments/001-ccd'
        (self.task / 'findings').mkdir(parents=True)
        (self.task / 'README.md').write_text('# Task\n可写：findings；验收：检查报告。\n')
        roles = self.root / '.agenthelm/config/roles.toml'
        roles.write_text(roles.read_text() + '\n[roles.hard.app.ccd]\nmodel = "gateway/opus"\neffort = "low"\n')
        self.run_cmd('bin/models')
        self.app('register', '--entry', 'app.ccd', '--session', 'dispatch-1')
        capabilities = {name: {'available': True, 'source': 'fake CCD inventory'} for name in
                        ('create', 'read', 'wait', 'followup', 'model', 'effort',
                         'verify_model', 'native_executor')}
        capabilities['verify_model']['fields'] = ['model', 'effort']
        capabilities['model']['values'] = ['gateway/opus', 'gateway/opus[1m]', 'gateway/lead']
        capabilities['effort']['combinations'] = {'gateway/opus': ['low', 'high'], 'gateway/opus[1m]': ['low'],
                                                  'gateway/lead': ['high']}
        self.app('capabilities', '--session', 'dispatch-1', payload={
            'entry': 'app.ccd', 'source': 'fake tool inventory', 'capabilities': capabilities})
        lead = self.app('prepare', '--session', 'dispatch-1', '--operation', 'create', '--task', str(self.task),
                        payload={'defaults': {'model': 'gateway/lead', 'effort': 'high',
                                              'source': 'fake CCD settings', 'evidence': 'settings readback'}})
        self.receive(lead, self.receipt(lead, 'lead-1', 'gateway/lead', 'high',
                                        visible=True, independent=True))

    def receipt(self, request, session, model, effort, **fields):
        return {'request_id': request['id'], 'owner_epoch': request['owner_epoch'], 'entry': 'app.ccd',
                'status': 'created', 'session': session, 'workspace': str(self.root), 'cwd': str(self.task),
                'executed': True, 'model': model, 'effort': effort, **fields,
                'evidence': {name: 'fake transcript readback: ' + name for name in
                             ('session', 'workspace', 'cwd', 'visible', 'independent',
                              'executed', 'model', 'effort', 'native', 'parent_session', 'served_model')}}

    def receive(self, request, receipt, ok=True):
        return self.app('result', '--session', request['caller_session'], '--request', request['id'],
                        payload=receipt, ok=ok)

    def executor(self, role, ok=True):
        result = self.run_cmd('bin/run-executor', self.task, '--session', 'lead-1', '--role', role,
                              input='只写 findings；检查报告。', ok=ok)
        return json.loads(result.stdout) if ok else result

    def test_configured_role_requests_its_generated_agent_and_exact_ids(self):
        request = self.executor('hard')
        self.assertEqual(request['subagent_type'], 'agenthelm-hard')
        self.assertEqual(request['effective_request'], {'model': 'gateway/opus', 'effort': 'low'})
        self.assertIn('subagent_type=agenthelm-hard and no model argument', request['host_instructions'])
        for model, effort in (('gateway/lead', 'low'), ('gateway/opus', 'high'), ('opus', 'low')):
            receipt = self.receipt(request, 'native-1', model, effort, native=True, parent_session='lead-1',
                                   served_model='gateway/opus')
            self.receive(request, receipt, ok=False)
        receipt = self.receipt(request, 'native-1', 'gateway/opus', 'low', native=True, parent_session='lead-1')
        self.assertIn('served model', self.receive(request, receipt, ok=False).stderr)
        receipt['served_model'] = 'gateway/lead'
        self.receive(request, receipt, ok=False)
        receipt['served_model'] = 'gateway/opus'
        self.receive(request, receipt)
        shown = self.app('show', '--session', 'dispatch-1')
        self.assertEqual(shown['sessions']['native-1']['actual'], {'model': 'gateway/opus', 'effort': 'low'})

    def test_1m_role_matches_requested_variant_and_served_base_model(self):
        roles = self.root / '.agenthelm/config/roles.toml'
        roles.write_text(roles.read_text() + '\n[roles.chore.app.ccd]\nmodel = "gateway/opus[1m]"\neffort = "low"\n')
        self.run_cmd('bin/models')
        agent = (self.root / '.claude/agents/agenthelm-chore.md').read_text()
        self.assertIn('model: gateway/opus[1m]\neffort: low\n', agent)
        request = self.executor('chore')
        self.assertEqual(request['effective_request'], {'model': 'gateway/opus[1m]', 'effort': 'low'})
        fields = dict(native=True, parent_session='lead-1')
        for model, served in (('gateway/opus', 'gateway/opus'), ('gateway/opus[1m]', 'gateway/opus[1m]'),
                              ('gateway/opus[1m]', 'gateway/lead')):
            receipt = self.receipt(request, 'native-1', model, 'low', served_model=served, **fields)
            self.receive(request, receipt, ok=False)
        receipt = self.receipt(request, 'native-1', 'gateway/opus[1m]', 'low', served_model='gateway/opus', **fields)
        self.receive(request, receipt)

    def test_unconfigured_role_inherits_bound_lead_actual_values(self):
        request = self.executor('chore')
        self.assertEqual(request['subagent_type'], 'agenthelm-chore')
        self.assertEqual(request['effective_request'], {'model': 'gateway/lead', 'effort': 'high'})
        self.assertEqual(request['model_binding']['sources'], {'model': 'lead-inherit', 'effort': 'lead-inherit'})

    def test_missing_or_stale_agent_file_stops_before_a_request_is_recorded(self):
        agent = self.root / '.claude/agents/agenthelm-hard.md'
        agent.write_text(agent.read_text().replace('effort: low', 'effort: high'))
        self.assertIn('stale', self.executor('hard', ok=False).stderr)
        agent.unlink()
        self.assertIn('bin/models', self.executor('hard', ok=False).stderr)
        requests = self.app('show', '--session', 'dispatch-1')['requests']
        self.assertEqual([request['operation'] for request in requests.values()], ['create'])
        self.run_cmd('bin/models')
        self.executor('hard')


if __name__ == '__main__':
    unittest.main()
