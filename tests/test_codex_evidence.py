"""Read-only Codex evidence checks through the public CLI and an isolated HOME."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
SESSION = '01a16165-fdbd-7153-9596-441937dffabc'


class CodexEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='agenthelm-evidence-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / 'home'
        self.workspace = self.base / 'workspace'
        self.workspace.mkdir()
        self.logs = self.home / '.codex/sessions/2026/10/22'
        self.logs.mkdir(parents=True)
        self.path = self.logs / f'rollout-2026-10-22T10-00-00-{SESSION}.jsonl'
        self.meta = {'id': SESSION, 'cwd': str(self.workspace), 'originator': 'Codex Desktop',
                     'source': 'vscode', 'cli_version': '0.163.0-test', 'secret': 'DO-NOT-READ'}
        self.turn = {'turn_id': 'turn-latest', 'cwd': str(self.workspace),
                     'model': 'actual-model', 'effort': 'high', 'instructions': 'DO-NOT-READ'}

    def record(self, kind, payload):
        return json.dumps({'timestamp': '2026-10-22T00:00:00Z', 'type': kind, 'payload': payload}) + '\n'

    def write_log(self, tail=''):
        self.path.write_text(self.record('session_meta', self.meta)
                             + self.record('event_msg', {'message': 'DO-NOT-READ'})
                             + self.record('turn_context', self.turn) + tail)

    def run_cli(self, *args, ok=True):
        before = {str(path): path.read_bytes() for path in self.home.rglob('*') if path.is_file()}
        result = subprocess.run([sys.executable, str(SOURCE / 'bin/codex-session-evidence'),
                                 '--session', SESSION, '--workspace', str(self.workspace), *args],
                                env=dict(os.environ, HOME=str(self.home), PYTHONDONTWRITEBYTECODE='1'),
                                text=True, capture_output=True, timeout=10)
        after = {str(path): path.read_bytes() for path in self.home.rglob('*') if path.is_file()}
        self.assertEqual(after, before, 'evidence command modified HOME')
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertNotIn('DO-NOT-READ', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        return result

    def test_returns_only_latest_turn_and_whitelisted_source_fields(self):
        self.write_log(self.record('turn_context', {**self.turn, 'turn_id': 'turn-new', 'model': 'new-model'}))
        result = self.run_cli('--turn', 'turn-new')
        self.assertEqual({key: result[key] for key in ('session', 'workspace', 'cwd', 'turn_id', 'model', 'effort')}, {
            'session': SESSION, 'workspace': str(self.workspace), 'cwd': str(self.workspace),
            'turn_id': 'turn-new', 'model': 'new-model', 'effort': 'high'})
        self.assertEqual(result['source'], {'path': str(self.path), 'originator': 'Codex Desktop',
                                           'source': 'vscode', 'cli_version': '0.163.0-test'})
        self.assertEqual(result['locator']['session_meta_line'], 1)
        self.assertEqual(result['locator']['turn_context_line'], 4)
        self.assertEqual(result['locator']['snapshot_bytes'], self.path.stat().st_size)
        self.assertEqual(len(result['locator']['sha256']), 64)
        self.assertNotIn('DO-NOT-READ', json.dumps(result))
        self.assertNotIn('executed', result)
        self.assertNotIn('visible', result)

    def test_rejects_mismatched_session_workspace_and_stale_turn(self):
        cases = (
            ({'id': 'another-session'}, {}, (), 'session'),
            ({'cwd': str(self.base)}, {}, (), 'workspace'),
            ({}, {'cwd': str(self.base)}, (), 'workspace'),
            ({}, {}, ('--turn', 'old-turn'), 'latest turn'),
        )
        for meta, turn, args, message in cases:
            with self.subTest(message=message):
                self.meta.update(meta)
                self.turn.update(turn)
                self.write_log()
                self.assertIn(message, self.run_cli(*args, ok=False).stderr)
                self.meta.update({'id': SESSION, 'cwd': str(self.workspace)})
                self.turn['cwd'] = str(self.workspace)

    def test_turn_in_task_directory_is_valid_workspace_evidence(self):
        task = self.workspace / 'experiments/001-task'
        task.mkdir(parents=True)
        self.meta['cwd'] = str(task)
        self.turn['cwd'] = str(task)
        self.write_log()
        result = self.run_cli()
        self.assertEqual((result['workspace'], result['cwd']), (str(self.workspace), str(task)))

    def test_rejects_ambiguous_missing_and_truncated_records(self):
        self.write_log()
        valid = self.path.read_text()
        for log in (
            self.record('session_meta', self.meta),
            valid + self.record('session_meta', {**self.meta, 'id': 'conflicting-session'}),
            valid.rstrip('\n'),
            valid + '{"type":"event_msg","payload":"DO-NOT-READ"',
            valid + '{"type":"event_msg","payload":}\n',
            valid + '[]\n',
            valid + '{"type":"turn_context","payload":null}\n',
        ):
            with self.subTest(log_length=len(log)):
                self.path.write_text(log)
                self.run_cli(ok=False)
        self.path.write_text(valid)
        duplicate = self.logs / f'rollout-second-{SESSION}.jsonl'
        duplicate.write_text(valid)
        self.assertIn('exactly one', self.run_cli(ok=False).stderr)

    def test_rejects_missing_or_invalid_whitelisted_fields(self):
        original_meta, original_turn = dict(self.meta), dict(self.turn)
        for kind, field in (('meta', 'id'), ('meta', 'cwd'), ('meta', 'originator'),
                            ('meta', 'source'), ('meta', 'cli_version'), ('turn', 'cwd'),
                            ('turn', 'turn_id'), ('turn', 'model'), ('turn', 'effort')):
            with self.subTest(kind=kind, field=field):
                self.meta, self.turn = dict(original_meta), dict(original_turn)
                (self.meta if kind == 'meta' else self.turn).pop(field)
                self.write_log()
                self.run_cli(ok=False)
        for value in (None, False, '', ' ', 'DO-NOT-READ\n'):
            with self.subTest(invalid_type=type(value).__name__):
                self.meta, self.turn = dict(original_meta), dict(original_turn)
                self.turn['model'] = value
                self.write_log()
                self.run_cli(ok=False)

    def test_lead_requires_desktop_source_and_excludes_native_subagents(self):
        for originator, source in (('codex_cli_rs', 'cli'), ('Codex Desktop', 'cli'),
                                   ('other-client', 'vscode'), ('Codex Desktop', {})):
            with self.subTest(originator=originator, source_type=type(source).__name__):
                self.meta.update(originator=originator, source=source)
                self.write_log()
                self.assertIn('Desktop', self.run_cli(ok=False).stderr)
        self.meta.update(originator='Codex Desktop', source='vscode')
        self.write_log()
        self.run_cli('--parent-session', 'parent-1', ok=False)

    def test_executor_requires_exact_native_parent_evidence_and_trims_source(self):
        spawn = {'parent_thread_id': 'parent-1', 'depth': 1, 'agent_path': '/root/executor',
                 'agent_nickname': 'DO-NOT-READ', 'agent_role': 'DO-NOT-READ'}
        self.meta['source'] = {'subagent': {'thread_spawn': spawn}, 'extra': 'DO-NOT-READ'}
        self.write_log()
        result = self.run_cli('--kind', 'executor', '--parent-session', 'parent-1', '--turn', 'turn-latest')
        self.assertEqual(result['source']['source'], {'subagent': {'thread_spawn': {
            'parent_thread_id': 'parent-1', 'depth': 1, 'agent_path': '/root/executor'}}})
        self.assertNotIn('DO-NOT-READ', json.dumps(result))
        self.run_cli(ok=False)
        self.run_cli('--kind', 'executor', ok=False)
        self.run_cli('--kind', 'executor', '--parent-session', 'wrong-parent', ok=False)
        for field, value in (('depth', True), ('depth', 0), ('agent_path', ''),
                             ('parent_thread_id', SESSION)):
            with self.subTest(field=field):
                original = spawn[field]
                spawn[field] = value
                self.write_log()
                self.run_cli('--kind', 'executor', '--parent-session', 'parent-1', ok=False)
                spawn[field] = original

    def test_rejects_path_like_session_ids_and_no_matching_log(self):
        self.write_log()
        for identifier in ('../escape', '/tmp/escape', '..', '*', 'a/b', '', 'missing-session'):
            with self.subTest(identifier=identifier):
                self.run_cli('--session', identifier, ok=False)

    def test_rollout_and_directory_symlinks_are_never_followed(self):
        self.write_log()
        outside = self.base / 'external.jsonl'
        outside.write_bytes(self.path.read_bytes())
        self.path.unlink()
        self.path.symlink_to(outside)
        self.assertIn('symbolic link', self.run_cli(ok=False).stderr)
        self.path.unlink()
        self.path.write_bytes(outside.read_bytes())
        moved = self.base / 'external-logs'
        self.logs.rename(moved)
        self.logs.symlink_to(moved, target_is_directory=True)
        self.assertIn('symbolic link', self.run_cli(ok=False).stderr)

    def test_recorded_cwd_cannot_escape_workspace_through_a_symlink(self):
        linked = self.workspace / 'escape'
        linked.symlink_to(self.base, target_is_directory=True)
        self.turn['cwd'] = str(linked)
        self.write_log()
        self.assertIn('workspace', self.run_cli(ok=False).stderr)

    def test_identical_resume_identity_uses_latest_metadata_and_its_following_turn(self):
        resumed = {**self.meta, 'cli_version': '0.164.0-test'}
        self.write_log(self.record('session_meta', resumed))
        self.run_cli(ok=False)
        with self.path.open('a') as stream:
            stream.write(self.record('turn_context', {**self.turn, 'turn_id': 'resumed-turn'}))
        result = self.run_cli('--turn', 'resumed-turn')
        self.assertEqual(result['source']['cli_version'], '0.164.0-test')
        self.assertEqual((result['locator']['session_meta_line'], result['locator']['turn_context_line']), (4, 5))
        task = self.workspace / 'experiments/001-other-task'
        task.mkdir(parents=True)
        self.write_log(self.record('session_meta', {**self.meta, 'cwd': str(task)})
                       + self.record('turn_context', {**self.turn, 'cwd': str(task)}))
        self.assertIn('ambiguous', self.run_cli(ok=False).stderr)

    def test_forked_executor_accepts_only_declared_parent_history_with_native_turn(self):
        parent_meta = dict(self.meta, id='parent-1')
        self.meta.update(forked_from_id='parent-1', parent_thread_id='parent-1', source={
            'subagent': {'thread_spawn': {'parent_thread_id': 'parent-1', 'depth': 1, 'agent_path': '/root/executor'}}})
        current_meta = self.record('session_meta', self.meta)
        parent_history = self.record('session_meta', parent_meta) + self.record(
            'turn_context', {**self.turn, 'turn_id': 'parent-turn'})
        own_turn = self.record('turn_context', self.turn)
        self.path.write_text(current_meta + parent_history + own_turn)
        result = self.run_cli('--kind', 'executor', '--parent-session', 'parent-1', '--turn', 'turn-latest')
        self.assertEqual(result['source']['forked_from_id'], 'parent-1')
        self.assertEqual(result['locator']['session_meta_line'], 1)
        self.assertIn('native read_thread', result['requirements']['turn_source'])
        self.run_cli('--kind', 'executor', '--parent-session', 'parent-1', ok=False)
        self.run_cli('--kind', 'executor', '--parent-session', 'parent-1', '--turn', 'parent-turn', ok=False)
        for replacement in (
            current_meta + self.record('session_meta', dict(parent_meta, id='third-session')) + own_turn,
            self.record('session_meta', {key: value for key, value in self.meta.items() if key != 'forked_from_id'})
            + parent_history + own_turn,
            self.record('session_meta', {**self.meta, 'parent_thread_id': 'other-parent'}) + parent_history + own_turn,
        ):
            with self.subTest(log_length=len(replacement)):
                self.path.write_text(replacement)
                self.run_cli('--kind', 'executor', '--parent-session', 'parent-1', '--turn', 'turn-latest', ok=False)


if __name__ == '__main__':
    unittest.main()
