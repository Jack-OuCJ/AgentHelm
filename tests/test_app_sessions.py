"""App session behavior through the public workspace CLI."""
import json
import shutil
import subprocess
import unittest

import test_workspace


class AppSessionTests(unittest.TestCase):
    setUp = test_workspace.WorkspaceTests.setUp
    tearDown = test_workspace.WorkspaceTests.tearDown
    run_cmd = test_workspace.WorkspaceTests.run_cmd

    def app(self, *args, payload=None, ok=True):
        result = self.run_cmd('bin/app-session', *args,
                              input=json.dumps(payload) if payload is not None else None, ok=ok)
        return json.loads(result.stdout) if ok else result

    def test_registered_dispatcher_keeps_entry_and_workspace_defaults(self):
        original = (self.root / '.agenthelm/config/env').read_text()
        self.app('register', '--entry', 'app.codex', '--session', 'dispatch-1')
        result = self.app('show', '--session', 'dispatch-1')
        self.assertEqual(result['dispatcher'], {'session': 'dispatch-1', 'entry': 'app.codex'})
        self.assertEqual(result['sessions']['dispatch-1']['entry'], 'app.codex')
        self.assertEqual(result['owner_epoch'], 1)
        self.assertEqual((self.root / '.agenthelm/config/env').read_text(), original)

    def test_ccd_capability_gaps_keep_individual_sources(self):
        self.app('register', '--entry', 'app.ccd', '--session', 'ccd-1')
        payload = {'entry': 'app.ccd', 'source': 'host tool inventory', 'capabilities': {
            'create': {'available': False, 'source': 'start_session absent'},
            'read': {'available': True, 'source': 'read_session tool'}}}
        self.app('capabilities', '--session', 'ccd-1', payload=payload)
        shown = self.app('show', '--session', 'ccd-1')
        binding = shown['sessions']['ccd-1']
        self.assertEqual(binding['capabilities'], payload['capabilities'])
        self.assertEqual(binding['capability_source'], 'host tool inventory')

    def test_repeated_registration_is_idempotent_and_cannot_take_ownership(self):
        first = self.app('register', '--entry', 'app.codex', '--session', 'dispatch-1')
        again = self.app('register', '--entry', 'app.codex', '--session', 'dispatch-1')
        self.assertEqual(first, again)
        conflict = self.app('register', '--entry', 'app.codex', '--session', 'dispatch-2', ok=False)
        self.assertIn('conflict', conflict.stderr)
        self.app('register', '--entry', 'app.ccd', '--session', 'dispatch-1', ok=False)
        self.app('show', '--session', 'dispatch-2', ok=False)
        self.assertEqual(self.app('show', '--session', 'dispatch-1'), first)

    def test_concurrent_registration_has_exactly_one_dispatcher(self):
        processes = [subprocess.Popen([str(self.root / 'bin/app-session'), 'register', '--entry',
                                      'app.codex', '--session', identifier], cwd=self.root,
                                     env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True) for identifier in ('first', 'second')]
        outputs = [process.communicate(timeout=15) for process in processes]
        self.assertEqual(sorted(process.returncode for process in processes), [0, 1])
        winner = next(json.loads(output[0])['dispatcher']['session']
                      for process, output in zip(processes, outputs) if process.returncode == 0)
        self.assertEqual(self.app('show', '--session', winner)['owner_epoch'], 1)

    def test_capability_registration_rejects_wrong_entry_and_missing_evidence(self):
        self.app('register', '--entry', 'app.codex', '--session', 'dispatch-1')
        for payload in (
                {'entry': 'app.ccd', 'source': 'inventory', 'capabilities': {}},
                {'entry': 'app.codex', 'source': 'inventory', 'capabilities': {'read': True}},
                {'entry': 'app.codex', 'source': 'inventory', 'capabilities': {
                    'read': {'available': True}}}):
            self.app('capabilities', '--session', 'dispatch-1', payload=payload, ok=False)
        self.assertEqual(self.app('show', '--session', 'dispatch-1')['sessions']['dispatch-1']
                         ['capabilities'], {})

    def test_damaged_state_with_escaped_task_is_not_read_or_replaced(self):
        state = self.app('register', '--entry', 'app.codex', '--session', 'dispatch-1')
        state['tasks'][str(self.home)] = {'session': 'foreign'}
        target = self.root / '.agenthelm/state/app-sessions.json'
        target.write_text(json.dumps(state))
        before = target.read_bytes()
        self.app('show', '--session', 'dispatch-1', ok=False)
        self.app('register', '--entry', 'app.codex', '--session', 'dispatch-1', ok=False)
        self.assertEqual(target.read_bytes(), before)

    def test_damaged_state_is_reported_without_automatic_reset(self):
        valid = self.app('register', '--entry', 'app.codex', '--session', 'dispatch-1')
        target = self.root / '.agenthelm/state/app-sessions.json'
        invalid_capability = json.loads(json.dumps(valid))
        invalid_capability['sessions']['dispatch-1']['capabilities'] = {'read': {'available': 'yes'}}
        for damaged in ('{', json.dumps({**valid, 'owner_epoch': True}),
                        json.dumps({key: value for key, value in valid.items() if key != 'dispatcher'}),
                        json.dumps(invalid_capability)):
            target.write_text(damaged)
            result = self.app('register', '--entry', 'app.codex', '--session', 'dispatch-1', ok=False)
            self.assertIn('damaged App state', result.stderr)
            self.assertEqual(target.read_text(), damaged)

    def test_state_files_and_parent_links_are_never_followed(self):
        state_directory = self.root / '.agenthelm/state'
        state_directory.mkdir(exist_ok=True)
        outside = self.base / 'outside'
        outside.mkdir()
        sentinel = outside / 'sentinel'
        sentinel.write_text('preserve')
        for name in ('app-sessions.json', 'app-sessions.lock'):
            link = state_directory / name
            if link.exists():
                link.unlink()
            link.symlink_to(sentinel)
            result = self.app('register', '--entry', 'app.codex', '--session', 'dispatch-1', ok=False)
            self.assertIn('symbolic link', result.stderr)
            self.assertEqual(sentinel.read_text(), 'preserve')
            link.unlink()
        shutil.rmtree(state_directory)
        state_directory.symlink_to(outside, target_is_directory=True)
        self.app('register', '--entry', 'app.codex', '--session', 'dispatch-1', ok=False)
        self.assertEqual(list(outside.iterdir()), [sentinel])


if __name__ == '__main__':
    unittest.main()
