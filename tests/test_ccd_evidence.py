"""Read-only CCD evidence checks through the public CLI and an isolated HOME."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
SESSION = 'local_c41874d4-6f29-47e5-8695-dbded5c4f337'
CLI = '3485e4d9-3965-459a-a448-d0936a51237a'
MODEL = 'anthropic/claude-ccr-sol[1m]'


class CcdEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='agenthelm-ccd-evidence-test-')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()
        self.workspace = self.home / 'workspace'
        self.workspace.mkdir()
        self.task = str(self.workspace / 'experiments/008-task')
        records = self.home / 'Library/Application Support/Claude-3p/claude-code-sessions/a/b'
        records.mkdir(parents=True)
        (records / f'{SESSION}.json').write_text(json.dumps(
            {'sessionId': SESSION, 'cliSessionId': CLI, 'cwd': self.task, 'secret': 'DO-NOT-READ'}))
        self.project = self.home / '.claude/projects/-work'
        self.project.mkdir(parents=True)
        self.transcript = self.project / f'{CLI}.jsonl'

    def user(self, prompt):
        return {'type': 'user', 'promptId': prompt, 'timestamp': '2026-10-22T12:59:00Z', 'message': {'content': 'DO-NOT-READ'}}

    def assistant(self, model, effort, at, ref='r'):
        at = {'t0': '2026-10-22T13:00:00Z', 't1': '2026-10-22T13:00:01Z', 't2': '2026-10-22T13:00:02Z'}.get(at, at)
        return {'sessionId': CLI, 'cwd': self.task, 'entrypoint': 'claude-desktop-3p',
                'type': 'assistant', 'requestedModel': model, 'effort': effort, 'timestamp': at,
                'requestRef': ref, 'message': {'model': model.removesuffix('[1m]')}}

    def tool(self, stdout):
        return {'type': 'user', 'toolUseResult': {'stdout': stdout}}

    def write(self, path, rows):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))

    def run_cli(self, *args, ok=True):
        before = {str(path): path.read_bytes() for path in self.home.rglob('*') if path.is_file()}
        result = subprocess.run([sys.executable, str(SOURCE / 'bin/ccd-session-evidence'), '--session', SESSION, '--workspace', str(self.workspace), *args],
                                env=dict(os.environ, HOME=str(self.home), PYTHONDONTWRITEBYTECODE='1'),
                                text=True, capture_output=True, timeout=10)
        after = {str(path): path.read_bytes() for path in self.home.rglob('*') if path.is_file()}
        self.assertEqual(after, before, 'evidence command modified HOME')
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertNotIn('Traceback', result.stderr)
        self.assertNotIn('DO-NOT-READ', result.stdout + result.stderr)
        return result

    def test_reports_only_the_requested_turn_and_its_cwd_line(self):
        self.write(self.transcript, [
            self.user('placeholder'), self.assistant('anthropic/claude-ccr-opus[1m]', 'high', 't0'),
            self.user('first'), self.assistant(MODEL, 'max', 't1', 'ref-1'),
            self.tool(self.task + '\n["a"]'), self.assistant(MODEL, 'max', 't2')])
        result = self.run_cli('--prompt-id', 'first', '--cwd', self.task)
        self.assertEqual((result['requested_model'], result['effort'], result['served_model']),
                         (MODEL, 'max', 'anthropic/claude-ccr-sol'))
        self.assertEqual({k: result['turn'][k] for k in ('prompt_id', 'first_line', 'last_line', 'assistant_records', 'first_request_ref', 'started_at')}, {'prompt_id': 'first', 'first_line': 4, 'last_line': 6,
                                          'assistant_records': 2, 'first_request_ref': 'ref-1',
                                          'started_at': '2026-10-22T12:59:00+00:00'})
        self.assertEqual(result['cwd'], {'path': self.task, 'line': 5})
        self.assertEqual(result['transcript']['path'], str(self.transcript))
        self.assertEqual(len(result['transcript']['sha256']), 64)

    def test_rejects_a_turn_that_mixes_models(self):
        self.write(self.transcript, [self.user('first'), self.assistant(MODEL, 'max', 't1'),
                                     self.assistant('anthropic/claude-ccr-opus[1m]', 'max', 't2')])
        failure = self.run_cli('--prompt-id', 'first', ok=False)
        self.assertIn('mixes model or effort', failure.stderr)

    def test_requires_cwd_stdout_inside_the_turn(self):
        self.write(self.transcript, [self.user('placeholder'), self.tool(self.task),
                                     self.assistant(MODEL, 'max', 't0'),
                                     self.user('first'), self.assistant(MODEL, 'max', 't1')])
        failure = self.run_cli('--prompt-id', 'first', '--cwd', self.task, ok=False)
        self.assertIn('expected cwd', failure.stderr)

    def test_reads_native_subagent_transcript_and_agent_type(self):
        subagents = self.project / CLI / 'subagents'
        self.write(self.transcript, [self.user('lead'), self.assistant(MODEL, 'max', 't0')])
        self.write(subagents / 'agent-a1.jsonl', [{**self.assistant(MODEL, 'high', 't1'), 'agentId': 'a1', 'isSidechain': True}])
        (subagents / 'agent-a1.meta.json').write_text(json.dumps({'agentType': 'agenthelm-hard'}))
        result = self.run_cli('--agent', 'a1')
        self.assertEqual(result['agent']['agent_type'], 'agenthelm-hard')
        self.assertIn('sha256', result['agent']['source'])
        self.assertEqual(result['effort'], 'high')

    def test_adds_gateway_counts_for_the_turn_window(self):
        self.write(self.transcript, [self.user('first'), self.assistant(MODEL, 'max', '2026-10-22T13:00:00Z'),
                                     self.assistant(MODEL, 'max', '2026-10-22T13:01:00Z'),
                                     {**self.user('next'), 'timestamp': '2026-10-22T13:02:00Z'}])
        database = self.home / '.claude-code-router/app-data/usage.sqlite'
        database.parent.mkdir(parents=True)
        connection = sqlite3.connect(database)
        connection.execute('create table usage_events (created_at text, provider text, model text, status_code int)')
        connection.executemany('insert into usage_events values (?, ?, ?, ?)', [
            ('2026-10-22T20:59:30+08:00', 'ouapi', 'sol', 200), ('2026-10-22T13:00:40Z', 'ouapi', 'sol', 500),
            ('2026-10-22T14:00:00Z', 'nclaude', 'opus', 200)])
        connection.commit()
        connection.close()
        result = self.run_cli('--prompt-id', 'first', '--gateway')
        self.assertEqual(result['gateway']['counts'], [{'provider': 'ouapi', 'model': 'sol', 'requests': 2, 'ok': 1}])

    def test_rejects_new_user_body_without_prompt_boundary(self):
        for missing in (None, ''):
            self.write(self.transcript, [self.user('first'), self.assistant(MODEL, 'max', 't1'),
                {'type': 'user', 'promptId': missing, 'message': {'content': 'new task'}},
                self.assistant(MODEL, 'max', 't2')])
            self.assertIn('turn boundary', self.run_cli('--prompt-id', 'first', ok=False).stderr)

    def test_rejects_malformed_json_without_echoing_contents(self):
        cases = ['[]\n', 'null\n', '{"type":"user","secret":NaN}\n',
                 '{"type":"user","type":"assistant"}\n', '{"secret":"DO-NOT-READ"}\n']
        for raw in cases:
            with self.subTest(raw=raw):
                self.transcript.write_text(raw)
                self.run_cli('--prompt-id', 'first', ok=False)

    def test_rejects_partial_line_missing_fields_and_wrong_origin(self):
        good = self.assistant(MODEL, 'max', 't1')
        for field, value in [('effort', None), ('message', []), ('sessionId', 'wrong'),
                             ('entrypoint', 'cli'), ('requestedModel', []), ('cwd', '/outside')]:
            with self.subTest(field=field):
                self.write(self.transcript, [self.user('first'), {**good, field: value}])
                self.run_cli('--prompt-id', 'first', ok=False)
        self.write(self.transcript, [self.user('first'), good])
        with self.transcript.open('a') as stream:
            stream.write('{"partial":')
        self.assertIn('incomplete transcript', self.run_cli('--prompt-id', 'first', ok=False).stderr)

    def test_rejects_symlink_file_and_parent_directory(self):
        self.write(self.transcript, [self.user('first'), self.assistant(MODEL, 'max', 't1')])
        target = self.home / 'external.jsonl'
        self.transcript.rename(target)
        self.transcript.symlink_to(target)
        self.run_cli('--prompt-id', 'first', ok=False)
        self.transcript.unlink()
        target.rename(self.transcript)
        moved = self.home / 'moved-project'
        self.project.rename(moved)
        self.project.symlink_to(moved, target_is_directory=True)
        self.run_cli('--prompt-id', 'first', ok=False)

    def test_rejects_session_record_and_agent_metadata_links_or_nonobjects(self):
        record = next(self.home.glob('Library/**/' + SESSION + '.json'))
        original = record.read_bytes()
        record.write_text('[]')
        self.run_cli('--prompt-id', 'first', ok=False)
        record.write_bytes(original)
        target = self.home / 'record.json'
        record.rename(target)
        record.symlink_to(target)
        self.run_cli('--prompt-id', 'first', ok=False)
        record.unlink()
        target.rename(record)
        self.write(self.transcript, [self.user('lead'), self.assistant(MODEL, 'max', 't0')])
        agent = self.project / CLI / 'subagents/agent-a1.jsonl'
        self.write(agent, [{**self.assistant(MODEL, 'high', 't1'), 'agentId': 'a1', 'isSidechain': True}])
        meta = agent.with_suffix('.meta.json')
        meta.write_text('[]')
        self.run_cli('--agent', 'a1', ok=False)
        meta.unlink()
        meta.symlink_to(record)
        self.run_cli('--agent', 'a1', ok=False)

    def test_gateway_rejects_link_and_active_wal(self):
        self.write(self.transcript, [self.user('first'), self.assistant(MODEL, 'max', 't1')])
        database = self.home / '.claude-code-router/app-data/usage.sqlite'
        database.parent.mkdir(parents=True)
        database.symlink_to(self.transcript)
        self.run_cli('--prompt-id', 'first', '--gateway', ok=False)
        database.unlink()
        Path(str(database) + '-wal').write_bytes(b'active')
        self.assertIn('WAL', self.run_cli('--prompt-id', 'first', '--gateway', ok=False).stderr)

    def test_gateway_rechecks_sidecars_after_database_capture(self):
        import runpy
        from unittest.mock import patch
        module = runpy.run_path(str(SOURCE / 'bin/ccd-session-evidence'))
        real_snapshot = module['gateway'].__globals__['snapshot']
        database = self.home / '.claude-code-router/app-data/usage.sqlite'
        database.parent.mkdir(parents=True)
        database.write_bytes(b'database')
        def concurrent_snapshot(path, newline=False):
            captured = real_snapshot(path, newline)
            if path == database:
                Path(str(database) + '-wal').write_bytes(b'new transaction')
            return captured
        with patch.dict(module['gateway'].__globals__, snapshot=concurrent_snapshot):
            with self.assertRaisesRegex(ValueError, 'WAL'):
                module['gateway'](self.home, 'start', 'end')

    def test_snapshot_detects_in_place_change(self):
        import runpy
        from unittest.mock import patch
        from types import SimpleNamespace
        module = runpy.run_path(str(SOURCE / 'bin/ccd-session-evidence'))
        self.transcript.write_text('{}\n')
        real_stat = os.fstat
        calls = 0
        def changing_stat(fd):
            nonlocal calls
            actual = real_stat(fd)
            calls += 1
            return SimpleNamespace(st_mode=actual.st_mode, st_size=actual.st_size,
                                   st_mtime_ns=actual.st_mtime_ns + calls, st_ctime_ns=actual.st_ctime_ns)
        with patch('os.fstat', side_effect=changing_stat):
            with self.assertRaisesRegex(ValueError, 'changed while reading'):
                module['snapshot'](self.transcript)

    def test_rejects_missing_selector_and_unknown_turn(self):
        self.write(self.transcript, [self.user('first'), self.assistant(MODEL, 'max', 't1')])
        self.assertIn('exactly one', self.run_cli(ok=False).stderr)
        self.assertIn('no assistant records', self.run_cli('--prompt-id', 'other', ok=False).stderr)


if __name__ == '__main__':
    unittest.main()
