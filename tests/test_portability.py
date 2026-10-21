"""Relocation contracts use fake agent CLIs and a disposable HOME."""
import json
import shlex
import subprocess
import unittest

import test_workspace


class PortabilityTests(unittest.TestCase):
    setUp = test_workspace.WorkspaceTests.setUp
    tearDown = test_workspace.WorkspaceTests.tearDown
    run_cmd = test_workspace.WorkspaceTests.run_cmd

    def run_hook(self, cwd, project=None):
        data = json.loads((self.root / '.claude/settings.json').read_text())
        commands = [hook['command'] for entry in data['hooks']['SessionStart']
                    for hook in entry['hooks'] if 'agenthelm-session-start' in hook.get('command', '')]
        self.assertEqual(len(commands), 1)
        env = dict(self.env)
        env.pop('CLAUDE_PROJECT_DIR', None)
        if project is not None:
            env['CLAUDE_PROJECT_DIR'] = str(project)
        result = subprocess.run(commands[0], shell=True, cwd=self.base, env=env, text=True,
                                input=json.dumps({'cwd': str(cwd), 'source': 'startup'}),
                                capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_moved_workspace_runs_hooks_dispatch_tasks_models_and_maintenance(self):
        (self.root / '.agenthelm/config/env').write_text('cli-plain\n')
        self.run_cmd('bin/new-task', 'move', input='# Test\n- id: <task-id>\n- question: Move\n')
        original = self.root
        self.root = self.base / '移动工作区 with spaces'
        original.rename(self.root)
        task = self.root / 'experiments/001-move'
        (task / 'memory').mkdir()
        (task / 'memory/MEMORY.md').write_text('Saved portable decision\n')
        hook_before = (self.root / '.claude/settings.json').read_text()
        self.assertNotIn(str(original), hook_before)
        self.assertIn(str(self.root), self.run_hook(self.root, self.root))
        self.assertIn('Saved portable decision', self.run_hook(task / 'findings', task))
        self.assertIn('Saved portable decision', self.run_hook(task / 'findings'))
        self.assertEqual(self.run_hook(self.home, self.root), '')
        self.assertEqual(self.run_hook(self.home), '')
        dispatcher = self.run_cmd('bin/dispatch', '--print', cwd=self.base).stdout
        self.assertIn(str(self.root / 'AGENTS.md'), dispatcher)
        self.assertNotIn(str(original), dispatcher)
        executor = self.run_cmd('bin/run-executor', task, '--role', 'hard', '--print',
                                input='只读取任务目录。', cwd=self.base).stdout
        self.assertIn(str(task), executor)
        self.assertNotIn(str(original), executor)
        self.run_cmd('bin/status', 'running', 'Moved successfully', cwd=task)
        self.run_cmd('bin/models')
        self.run_cmd('bin/kb', 'index', '--check')
        self.run_cmd('bin/kb', 'lint')
        self.run_cmd('skills/research-setup/scripts/deploy', self.root, cwd=self.base)
        self.assertEqual((self.root / '.claude/settings.json').read_text(), hook_before)
        install_dir = self.root / '.agenthelm/config/install-dir'
        self.assertEqual(install_dir.read_text(), '../..\n')
        self.assertEqual((install_dir.parent / install_dir.read_text().strip()).resolve(), self.root)
        for folder in ('.agents/skills', '.claude/skills'):
            for link in (self.root / folder).iterdir():
                self.assertFalse(link.readlink().is_absolute())
                self.assertTrue((link / 'SKILL.md').is_file())
        (self.root / '.agenthelm/config/env').write_text('cli-herdr\n')
        self.run_cmd('bin/new-task', 'after-move', input='# Test\n- id: <task-id>\n- question: Launch\n')
        commands = [json.loads(line) for line in self.log.read_text().splitlines()]
        created = [row for row in commands if row['argv'][:2] == ['tab', 'create']][-1]
        launched = [row for row in commands if row['argv'][:2] == ['agent', 'prompt']][-1]
        self.assertIn(str(self.root / 'experiments/002-after-move'), created['argv'])
        self.assertIn(str(self.root), launched['argv'][-1])
        self.assertNotIn(str(original), launched['argv'][-1])

    def test_legacy_absolute_hooks_are_migrated_without_overwriting_other_settings(self):
        settings = self.root / '.claude/settings.json'
        old_command = shlex.quote(str(self.root / 'bin/lead-watch-start'))
        obsolete_command = shlex.quote(str(self.base / 'former workspace/bin/lead-watch-start'))
        manual = {'matcher': 'resume', 'hooks': [{'type': 'command', 'command': 'echo retained'}]}
        data = {'env': {'KEEP': 'user-value'}, 'hooks': {'SessionStart': [
            {'matcher': 'startup|resume|clear|compact', 'hooks': [
                {'type': 'command', 'command': old_command, 'timeout': 10},
                {'type': 'command', 'command': obsolete_command, 'timeout': 10}]}, manual]}}
        settings.write_text(json.dumps(data))
        self.run_cmd('skills/research-setup/scripts/merge-hooks')
        once = settings.read_text()
        self.run_cmd('skills/research-setup/scripts/merge-hooks')
        self.assertEqual(settings.read_text(), once)
        after = json.loads(once)
        self.assertEqual(after['env'], data['env'])
        self.assertIn(manual, after['hooks']['SessionStart'])
        commands = [hook['command'] for entry in after['hooks']['SessionStart'] for hook in entry['hooks']]
        self.assertEqual(len(commands), 2)
        self.assertNotIn(old_command, commands)
        self.assertNotIn(obsolete_command, commands)
        self.assertIn(str(self.root), self.run_hook(self.root))


if __name__ == '__main__':
    unittest.main()
