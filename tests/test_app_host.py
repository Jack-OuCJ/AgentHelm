"""App entry and restoration through public CLIs, with no real host calls."""
import json
import unittest

import test_app_sessions


class AppHostTests(unittest.TestCase):
    setUp = test_app_sessions.AppSessionTests.setUp
    tearDown = test_app_sessions.AppSessionTests.tearDown
    run_cmd = test_app_sessions.AppSessionTests.run_cmd
    app = test_app_sessions.AppSessionTests.app

    def bind_lead(self):
        self.task = self.root / 'experiments/001-app'
        self.task.mkdir()
        (self.task / 'README.md').write_text('# Authorized task')
        self.app('register', '--entry', 'app.codex', '--session', 'owner')
        capabilities = {name: {'available': True, 'source': 'fake host inventory'} for name in
                        ('create', 'read', 'wait', 'followup', 'model', 'effort',
                         'verify_model', 'native_executor')}
        capabilities['verify_model']['fields'] = ['model', 'effort']
        capabilities['model']['values'] = ['native-model']
        capabilities['effort']['combinations'] = {'native-model': ['high']}
        self.app('capabilities', '--session', 'owner', payload={
            'entry': 'app.codex', 'source': 'fake inventory', 'capabilities': capabilities})
        request = self.app('prepare', '--session', 'owner', '--operation', 'create', '--task', self.task,
                           payload={'defaults': {'model': 'native-model', 'effort': 'high',
                                                 'source': 'fake settings', 'evidence': 'default read'}})
        self.app('result', '--session', 'owner', '--request', request['id'], payload={
            'request_id': request['id'], 'owner_epoch': 1, 'entry': 'app.codex', 'status': 'created',
            'session': 'lead', 'workspace': str(self.root), 'cwd': str(self.task),
            'visible': True, 'independent': True, 'executed': True, 'model': 'native-model', 'effort': 'high',
            'evidence': {name: 'fake host observation' for name in
                         ('session', 'workspace', 'cwd', 'visible', 'independent', 'executed', 'model', 'effort')}})

    def test_bound_lead_reload_uses_app_entry_in_a_cli_default_workspace(self):
        self.bind_lead()
        output = self.run_cmd('bin/lead-reload', self.task, 'resume', '--session', 'lead')
        self.assertIn('当前角色：lead', output.stdout)
        self.assertIn('运行入口：app.codex', output.stdout)
        self.assertIn('会话标识：lead', output.stdout)
        self.assertIn('当前运行环境：app', output.stdout)
        self.assertNotIn('Runtime environment: terminal CLI', output.stdout)
        self.run_cmd('bin/lead-reload', self.task, '--session', 'owner', ok=False)
        self.run_cmd('bin/lead-reload', self.task, '--session', 'unknown', ok=False)
        self.assertFalse(self.log.exists())

    def test_session_start_restores_bound_app_roles_without_promoting_unknown_root_sessions(self):
        self.bind_lead()
        for cwd in (self.task, self.root):
            output = self.run_cmd('bin/lead-watch-start', input=json.dumps({
                'cwd': str(cwd), 'session_id': 'lead', 'source': 'resume'}))
            self.assertIn('当前角色：lead', output.stdout)
            self.assertIn('会话标识：lead', output.stdout)
            self.assertIn('运行入口：app.codex', output.stdout)
            self.assertNotIn('当前角色：dispatcher', output.stdout)
        owner = self.run_cmd('bin/lead-watch-start', input=json.dumps({
            'cwd': str(self.root), 'session_id': 'owner'}))
        self.assertIn('当前角色：dispatcher', owner.stdout)
        for event in ({'cwd': str(self.root)}, {'cwd': str(self.root), 'session_id': 'other'},
                      {'cwd': str(self.root), 'session_id': 'other', 'entry': 'app.codex'}):
            output = self.run_cmd('bin/lead-watch-start', input=json.dumps(event))
            self.assertNotIn('当前角色：dispatcher', output.stdout)
        self.assertFalse(self.log.exists())

    def test_app_executor_print_is_a_non_executable_preview_without_pending_request(self):
        self.bind_lead()
        before = self.app('show', '--session', 'owner')
        output = self.run_cmd('bin/run-executor', self.task, '--session', 'lead', '--print',
                              '--app-params', json.dumps({'defaults': {'model': 'native-model', 'effort': 'high',
                                                                       'source': 'fake settings', 'evidence': 'read'}}),
                              input='只读任务目录。')
        preview = json.loads(output.stdout)
        self.assertTrue(preview['preview'])
        self.assertFalse(preview['executable'])
        self.assertNotIn('id', preview)
        self.assertEqual(self.app('show', '--session', 'owner'), before)
        self.assertFalse(self.log.exists())

    def test_explicit_cli_dispatch_entry_chooses_the_requested_cli_and_rejects_conflict(self):
        self.run_cmd('bin/dispatch', '--entry', 'cli.codex')
        commands = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual(commands[-1]['cli'], 'codex')
        self.run_cmd('bin/dispatch', '--entry', 'cli.codex', '--kind', 'claude', ok=False)
        self.assertEqual(len(self.log.read_text().splitlines()), len(commands))

    def test_handoff_restores_old_owner_as_observer_and_keeps_lead_entry(self):
        self.bind_lead()
        self.app('release', '--session', 'owner', '--to', 'replacement')
        self.run_cmd('bin/dispatch', ok=False)
        self.run_cmd('bin/dispatch', '--entry', 'app.codex', '--session', 'owner', ok=False)
        during = self.run_cmd('bin/lead-watch-start', input=json.dumps({'cwd': str(self.root)}))
        self.assertNotIn('当前角色：dispatcher', during.stdout)
        self.app('claim', '--session', 'replacement', '--entry', 'app.codex')
        old = self.run_cmd('bin/lead-watch-start', input=json.dumps({
            'cwd': str(self.root), 'session_id': 'owner'}))
        self.assertIn('只读观察者', old.stdout)
        self.assertNotIn('当前角色：dispatcher', old.stdout)
        self.run_cmd('bin/dispatch', '--session', 'owner', '--print', ok=False)
        lead = self.run_cmd('bin/lead-reload', self.task, '--session', 'lead')
        self.assertIn('运行入口：app.codex', lead.stdout)
        self.assertFalse(self.log.exists())

    def test_unregistered_app_root_hook_and_ccd_capability_gap_do_not_start_cli(self):
        (self.root / '.agenthelm/config/env').write_text('app\n')
        unbound = self.run_cmd('bin/lead-watch-start', input=json.dumps({'cwd': str(self.root)}))
        self.assertIn('unregistered App session', unbound.stdout)
        self.assertNotIn('当前角色：dispatcher', unbound.stdout)
        self.run_cmd('bin/dispatch', '--entry', 'app.ccd', '--session', 'ccd')
        task = self.root / 'experiments/001-ccd'
        task.mkdir()
        (task / 'README.md').write_text('# task')
        failure = self.run_cmd('bin/spawn-lead', task, '--session', 'ccd', ok=False)
        self.assertIn('capability unavailable: create', failure.stderr)
        self.assertEqual(self.app('show', '--session', 'ccd')['tasks'], {})
        self.assertFalse(self.log.exists())

    def test_native_executor_hook_restores_its_own_role_and_entry(self):
        self.bind_lead()
        request = self.app('prepare', '--session', 'lead', '--operation', 'executor', '--task', self.task,
                           payload={'brief': '只读任务目录', 'defaults': {'model': 'native-model', 'effort': 'high',
                                                                      'source': 'fake settings', 'evidence': 'readback'}})
        self.app('result', '--session', 'lead', '--request', request['id'], payload={
            'request_id': request['id'], 'owner_epoch': 1, 'entry': 'app.codex', 'status': 'created',
            'session': 'executor', 'workspace': str(self.root), 'cwd': str(self.task), 'native': True,
            'parent_session': 'lead', 'executed': True, 'model': 'native-model', 'effort': 'high',
            'evidence': {name: 'fake native observation' for name in
                         ('session', 'workspace', 'cwd', 'native', 'parent_session', 'executed', 'model', 'effort')}})
        output = self.run_cmd('bin/lead-watch-start', input=json.dumps({
            'cwd': str(self.task), 'session_id': 'executor'}))
        self.assertIn('当前角色：executor', output.stdout)
        self.assertNotIn('当前角色：lead', output.stdout)
        self.assertIn('会话标识：executor', output.stdout)
        self.assertIn('运行入口：app.codex', output.stdout)
        self.assertFalse(self.log.exists())

    def test_dispatch_app_registration_prints_target_and_session_without_cli(self):
        output = self.run_cmd('bin/dispatch', '--entry', 'app.codex', '--session', 'desktop-1')
        self.assertIn('运行入口：app.codex', output.stdout)
        self.assertIn('会话标识：desktop-1', output.stdout)
        self.assertIn('app-host.md', output.stdout)
        self.assertEqual(self.app('show', '--session', 'desktop-1')['dispatcher']['session'], 'desktop-1')
        self.assertFalse(self.log.exists())


    def test_app_print_is_read_only_preview_without_registering_or_taking_ownership(self):
        directory = self.root / '.agenthelm/state'
        before = test_app_sessions.test_workspace.snapshot(directory) if directory.exists() else {}
        preview = self.run_cmd('bin/dispatch', '--entry', 'app.codex', '--session', 'preview', '--print')
        self.assertIn('未注册，无调度权限', preview.stdout)
        self.assertFalse(self.log.exists())
        self.assertEqual(test_app_sessions.test_workspace.snapshot(directory) if directory.exists() else {}, before)
        self.app('register', '--entry', 'app.codex', '--session', 'owner')
        self.run_cmd('bin/dispatch', '--entry', 'app.codex', '--session', 'other', '--print')
        self.assertEqual(self.app('show', '--session', 'owner')['dispatcher']['session'], 'owner')

    def test_active_app_dispatcher_blocks_a_second_legacy_cli_dispatcher(self):
        self.app('register', '--entry', 'app.codex', '--session', 'owner')
        error = self.run_cmd('bin/dispatch', ok=False)
        self.assertIn('Dispatcher conflict', error.stderr)
        preview = self.run_cmd('bin/dispatch', '--print')
        self.assertIn('只读观察者', preview.stdout)
        self.assertNotIn('当前角色：dispatcher', preview.stdout)
        self.assertFalse(self.log.exists())


if __name__ == '__main__':
    unittest.main()
