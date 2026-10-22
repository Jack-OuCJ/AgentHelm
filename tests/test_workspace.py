"""Offline integration checks. All subprocess agents and Herdr are fake executables."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]


def snapshot(path):
    result = {}
    for base, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            item = Path(base) / name
            relative = str(item.relative_to(path))
            result[relative] = ('link', os.readlink(item)) if item.is_symlink() else (
                ('file', hashlib.sha256(item.read_bytes()).hexdigest()) if item.is_file() else ('dir',))
    return result


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='agenthelm-workspace-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'workspace'
        shutil.copytree(SOURCE, self.root, ignore=shutil.ignore_patterns(
            '.git', '.agenthelm', '.agents', '.claude', 'skills-library', '__pycache__', 'experiments',
            'cards', 'reports', 'rules', 'INDEX.md', 'BOARD.md', 'EXPERIMENTS.md', 'rules-extra.md'))
        self.home = self.base / 'home'
        (self.home / '.agents/skills/existing').mkdir(parents=True)
        (self.home / '.agents/AGENTS.md').write_text('global rules sentinel\n')
        (self.home / '.agents/skills/existing/SKILL.md').write_text('skill sentinel\n')
        (self.home / '.claude').mkdir()
        (self.home / '.claude/CLAUDE.md').symlink_to('../.agents/AGENTS.md')
        (self.home / '.claude/settings.json').write_text('{"hooks":{"SessionStart":[]}}\n')
        (self.home / '.codex').mkdir()
        (self.home / '.codex/AGENTS.md').symlink_to('../.agents/AGENTS.md')
        self.before = snapshot(self.home)
        self.fakebin = self.base / 'fakebin'
        self.fakebin.mkdir()
        self.log = self.base / 'commands.jsonl'
        stub = ("#!" + sys.executable + "\nimport json,os,sys\n"
                "with open(os.environ['TEST_LOG'],'a') as f: f.write(json.dumps({'cli':os.path.basename(sys.argv[0]),'argv':sys.argv[1:],'cwd':os.getcwd()},ensure_ascii=False)+'\\n')\n"
                "if sys.argv[1:3] == ['tab','create']: print(json.dumps({'result':{'root_pane':{'pane_id':'fake-pane'}}}))\n"
                "elif sys.argv[1:3] == ['tab','list']: print(json.dumps({'result':{'tabs':[]}}))\n"
                "elif sys.argv[1:3] == ['agent','list']: print(json.dumps({'result':{'agents':[]}}))\n")
        for name in ('herdr', 'claude', 'codex'):
            target = self.fakebin / name
            target.write_text(stub)
            target.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.fakebin) + os.pathsep + os.environ['PATH'],
                        PYTHONDONTWRITEBYTECODE='1', HERDR_ENV='1', TEST_LOG=str(self.log))
        self.run_cmd('skills/research-setup/scripts/deploy', str(self.root), '--env', 'cli-herdr')

    def tearDown(self):
        self.assertEqual(snapshot(self.home), self.before, 'global configuration was modified')

    def run_cmd(self, command, *args, input=None, ok=True, cwd=None, env=None):
        result = subprocess.run([str(self.root / command), *map(str,args)], cwd=cwd or self.root,
                                input=input, text=True, capture_output=True, env=env or self.env, timeout=15)
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_deploy_idempotent_and_project_hooks_preserved(self):
        settings = self.root / '.claude/settings.json'
        data = json.loads(settings.read_text())
        data['env'] = {'EXISTING_PROJECT_VALUE': 'keep'}
        data['hooks']['SessionStart'].append({'hooks': [{'type': 'command', 'command': 'existing-hook'}]})
        settings.write_text(json.dumps(data))
        self.run_cmd('skills/research-setup/scripts/deploy', self.root)
        self.run_cmd('skills/research-setup/scripts/deploy', self.root)
        after = json.loads(settings.read_text())
        self.assertEqual(after['env'], data['env'])
        hooks = [hook['command'] for entry in after['hooks']['SessionStart'] for hook in entry['hooks']]
        self.assertEqual(len(hooks), 2)
        for folder in ('.agents/skills', '.claude/skills'):
            for name in ('agenthelm-workflow', 'research-setup'):
                self.assertEqual((self.root / folder / name).resolve(), self.root / 'skills' / name)
        self.assertNotIn('claude:sonnet', (self.root / '.agenthelm/config/models.md').read_text())

    def test_herdr_lead_and_executor_bootstrap(self):
        card = '# Test\n- id: <task-id>\n- question: Test workspace startup\n'
        self.run_cmd('bin/new-task', 'example', input=card)
        task = self.root / 'experiments/001-example'
        commands = [json.loads(row) for row in self.log.read_text().splitlines()]
        starts = [row for row in commands if row['argv'][:2] == ['agent', 'start']]
        self.assertEqual(len(starts), 1)
        self.assertNotIn('--model', starts[0]['argv'])
        tabs = [row for row in commands if row['argv'][:2] == ['tab', 'create']]
        self.assertEqual(tabs[0]['argv'][tabs[0]['argv'].index('--cwd') + 1], str(task))
        prompt = [row['argv'][-1] for row in commands if row['argv'][:2] == ['agent', 'prompt']][0]
        self.assertIn(str(self.root / 'AGENTS.md'), prompt)
        self.assertIn(str(self.root / 'skills/agenthelm-workflow/SKILL.md'), prompt)
        self.run_cmd('bin/run-executor', task, '--role', 'hard', input='只读任务文件；输出一行；不得修改其他文件。')
        commands = [json.loads(row) for row in self.log.read_text().splitlines()]
        executor = commands[-1]
        self.assertEqual(executor['cli'], 'codex')
        self.assertEqual(executor['cwd'], str(task))
        self.assertEqual(executor['argv'][0], 'exec')
        self.assertIn('当前角色：executor (hard)', executor['argv'][-1])
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', executor['argv'])

    def test_hook_restores_context_and_ignores_other_workspaces(self):
        self.run_cmd('bin/lead-watch-start', input=json.dumps({'cwd':str(self.root),'source':'startup'}))
        task = self.root / 'experiments/001-hook'
        (task / 'findings').mkdir(parents=True)
        (task / 'STATUS').write_text('running | hook test')
        (task / 'memory').mkdir()
        (task / 'memory/MEMORY.md').write_text('Saved decision: keep scope')
        result = self.run_cmd('bin/lead-watch-start', input=json.dumps({'cwd':str(task / 'findings'),'source':'compact','session_id':'test-session'}))
        self.assertIn('Saved decision: keep scope', result.stdout)
        self.assertEqual((task / '.compactions').read_text(), 'test-session\n1\n')
        result = self.run_cmd('bin/lead-watch-start', input=json.dumps({'cwd':str(self.home),'source':'startup'}))
        self.assertEqual(result.stdout, '')

    def test_outside_paths_and_symlink_writes_rejected(self):
        self.run_cmd('skills/research-setup/scripts/deploy', self.home, ok=False)
        self.run_cmd('bin/spawn-lead', self.home, ok=False)
        # A root entry symlink must never be followed into user rules.
        target = self.root / 'AGENTS.md'
        target.unlink()
        target.symlink_to(self.home / '.agents/AGENTS.md')
        self.run_cmd('bin/kb', 'sync-agents', ok=False)
        target.unlink()
        self.run_cmd('bin/kb', 'sync-agents')
        link = self.root / '.claude/skills/agenthelm-workflow'
        link.unlink()
        link.symlink_to(self.home / '.agents/skills/existing')
        self.run_cmd('bin/kb', 'sync-agents', ok=False)

    def test_manual_entry_not_overwritten(self):
        target = self.root / 'AGENTS.md'
        target.write_text('manual rules')
        self.run_cmd('bin/install-rules', ok=False)
        self.assertEqual(target.read_text(), 'manual rules')

    def test_routers_only_use_workspace_and_preserve_manual_skills(self):
        library = self.root / 'skills-library'
        (library / 'demo').mkdir(parents=True)
        (library / 'demo/SKILL.md').write_text('---\nname: demo\ndescription: Example skill\n---\n# Demo\n')
        config = self.root / '.agenthelm/config/routers.toml'
        def configure(output='../../skills', skills='["demo"]'):
            config.write_text('library="../../skills-library"\noutput="' + output + '"\nprefix="route-"\n[routers.demo]\ntitle="Demo"\ndescription="Example tasks"\nskills=' + skills + '\n')
        configure()
        self.run_cmd('bin/build-routers')
        router = self.root / 'skills/route-demo/SKILL.md'
        self.assertIn('../../skills-library/demo/SKILL.md', router.read_text())
        self.run_cmd('bin/build-routers')
        configure(skills='[]')
        self.assertIn('missing=', self.run_cmd('bin/build-routers', ok=False).stderr)
        configure(output=str(self.home / '.agents/skills'))
        self.run_cmd('bin/build-routers', ok=False)
        configure()
        router.write_text('manual skill')
        self.run_cmd('bin/build-routers', ok=False)
        self.assertEqual(router.read_text(), 'manual skill')

    def test_index_lint_and_inactive_global_helpers(self):
        task = self.root / 'experiments/002-results'
        task.mkdir()
        (task / 'README.md').write_text('# Result\n- id: 002-results\n- question: Does it work?\n\n## Conclusion (2026-10-21)\n- **Tendency**: works\n- **Confidence**: high\n')
        (task / 'results.jsonl').write_text('{"command":"check","exit_code":0,"artifact":"log.txt"}\n')
        self.run_cmd('bin/status', 'done', 'checked', cwd=task)
        self.run_cmd('bin/kb', 'index', '--check')
        self.run_cmd('bin/kb', 'lint')
        self.assertIn('002-results', (self.root / 'INDEX.md').read_text())
        (task / 'results.jsonl').write_text('{"fake":true}\n')
        self.assertIn('invalid result record', self.run_cmd('bin/kb', 'lint', ok=False).stdout)
        for command in ('rules-pull','rules-push','rules-sync','rgit'):
            self.run_cmd('bin/' + command)
        self.run_cmd('bin/install-component', 'ponytail', ok=False)
        self.run_cmd('bin/install-component', 'herdr')

    def test_herdr_requires_context_and_dispatch_prints_only(self):
        other_env = dict(self.env, HERDR_ENV='0')
        self.run_cmd('bin/new-task', 'no-herdr', input='', ok=False, env=other_env)
        self.assertFalse((self.root / 'experiments/001-no-herdr').exists())
        result = self.run_cmd('bin/dispatch', '--print')
        self.assertIn(str(self.root / 'AGENTS.md'), result.stdout)
        self.assertFalse(self.log.exists())


if __name__ == '__main__':
    unittest.main()
