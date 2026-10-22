"""App role bindings through the public model CLI."""
import json
import unittest

import test_workspace


class AppModelTests(unittest.TestCase):
    setUp = test_workspace.WorkspaceTests.setUp
    tearDown = test_workspace.WorkspaceTests.tearDown
    run_cmd = test_workspace.WorkspaceTests.run_cmd

    def configure(self, text):
        path = self.root / '.agenthelm/config/roles.toml'
        path.write_text(text)

    def resolve(self, role='lead', entry='app.codex'):
        return json.loads(self.run_cmd('bin/models', 'resolve', role, '--entry', entry).stdout)

    def test_absent_app_binding_uses_native_defaults_without_cli_candidates(self):
        self.configure('[roles.lead]\ncandidates = ["unknown:ignored"]\n')
        self.assertEqual(self.resolve(), {
            'entry': 'app.codex', 'role': 'lead', 'model': None, 'effort': None,
            'sources': {'model': 'native-default', 'effort': 'native-default'},
        })

    def test_role_and_app_defaults_resolve_each_field_independently(self):
        self.configure('''
[roles.lead]
[app.defaults.codex]
model = "desktop-model"
effort = "high"
[roles.lead.app.codex]
effort = "low"
[app.defaults.ccd]
model = "ccd-model"
''')
        codex = self.resolve()
        self.assertEqual((codex['model'], codex['effort'], codex['sources']), (
            'desktop-model', 'low', {'model': 'app.defaults.codex', 'effort': 'roles.lead.app.codex'}))
        ccd = self.resolve(entry='app.ccd')
        self.assertEqual((ccd['model'], ccd['effort'], ccd['sources']), (
            'ccd-model', None, {'model': 'app.defaults.ccd', 'effort': 'native-default'}))

    def test_explicit_default_resets_app_defaults_for_each_field(self):
        self.configure('''
[roles.lead]
[app.defaults.codex]
model = "desktop-model"
effort = "high"
[roles.lead.app.codex]
model = "default"
effort = "default"
''')
        result = self.resolve()
        self.assertEqual((result['model'], result['effort'], result['sources']), (
            None, None, {'model': 'roles.lead.app.codex', 'effort': 'roles.lead.app.codex'}))

    def test_invalid_app_configuration_is_rejected(self):
        for suffix in (
            '[app]\ndefaults = true',
            '[app.defaults.other]\nmodel = "x"',
            '[app.defaults.codex]\nmodel = 42',
            '[app.defaults.codex]\neffort = false',
            '[app.defaults.codex]\nmodel = ""',
            '[app.defaults.codex]\nmodel = "  "',
            '[roles.lead.app]\ncodex = true',
            '[roles.lead.app.other]\nmodel = "x"',
            '[roles.lead.app.codex]\nreasoning = "high"',
        ):
            with self.subTest(suffix=suffix):
                self.configure('[roles.lead]\n' + suffix + '\n')
                result = self.run_cmd('bin/models', 'resolve', 'lead', '--entry', 'app.codex', ok=False)
                self.assertIn('models:', result.stderr)
                self.assertNotIn('Traceback', result.stderr)

    def test_generated_model_table_shows_app_bindings_and_keeps_cli_commands(self):
        path = self.root / '.agenthelm/config/roles.toml'
        path.write_text(path.read_text() + '''
[roles.lead.app.codex]
model = "desktop-model"
effort = "host-effort"
''')
        self.assertEqual(self.run_cmd('bin/models', 'get', 'hard').stdout.strip(), 'codex default')
        result = self.run_cmd('bin/models').stdout
        self.assertIn('| Role | App entry | Requested model | Model source | Requested effort | Effort source |', result)
        self.assertIn('| lead | app.codex | desktop-model | roles.lead.app.codex | host-effort | roles.lead.app.codex |', result)
        self.assertIn('| lead | app.ccd | default | app.defaults.ccd | default | app.defaults.ccd |', result)
        self.assertIn('`codex exec`', result)
        self.assertNotIn('codex exec -m desktop-model', result)

    def test_ccd_executor_without_binding_inherits_lead_instead_of_app_defaults(self):
        self.configure('''
[roles.lead]
[roles.chore]
[app.defaults.ccd]
model = "ccd-model"
effort = "high"
''')
        chore = self.resolve('chore', 'app.ccd')
        self.assertEqual((chore['model'], chore['effort'], chore['sources']), (
            None, None, {'model': 'lead-inherit', 'effort': 'lead-inherit'}))
        lead = self.resolve('lead', 'app.ccd')
        self.assertEqual((lead['model'], lead['sources']['model']), ('ccd-model', 'app.defaults.ccd'))
        codex = self.resolve('chore', 'app.codex')
        self.assertEqual(codex['sources']['model'], 'native-default')

    def test_models_writes_ccd_executor_agents_pinning_model_and_effort(self):
        path = self.root / '.agenthelm/config/roles.toml'
        path.write_text(path.read_text() + '''
[roles.hard.app.ccd]
model = "anthropic/gateway-opus[1m]"
effort = "low"
''')
        result = self.run_cmd('bin/models').stdout
        self.assertIn('| chore | app.ccd | inherit | lead-inherit | inherit | lead-inherit |', result)
        agents = self.root / '.claude/agents'
        hard = (agents / 'agenthelm-hard.md').read_text()
        self.assertIn('name: agenthelm-hard\n', hard)
        self.assertIn('model: anthropic/gateway-opus[1m]\neffort: low\n---', hard)
        self.assertIn('不创建下层代理', hard)
        chore = (agents / 'agenthelm-chore.md').read_text()
        self.assertIn('model: inherit\n---', chore)
        self.assertNotIn('effort:', chore)
        self.assertEqual(sorted(item.name for item in agents.iterdir()), [
            f'agenthelm-{role}.md' for role in
            sorted(('aesthetic', 'chore', 'fact', 'hard', 'simplify', 'visual', 'writing'))])

    def test_unsafe_ccd_agent_values_are_rejected(self):
        path = self.root / '.agenthelm/config/roles.toml'
        original = path.read_text()
        for value in ('bad: value', 'model # note', 'a\\nb'):
            with self.subTest(value=value):
                path.write_text(original + f'\n[roles.hard.app.ccd]\nmodel = "{value}"\n')
                result = self.run_cmd('bin/models', ok=False)
                self.assertIn('roles.hard.app.ccd.model', result.stderr)

    def test_resolve_rejects_unknown_role_entry_and_missing_configuration(self):
        self.run_cmd('bin/models', 'resolve', 'missing', '--entry', 'app.codex', ok=False)
        self.run_cmd('bin/models', 'resolve', 'lead', '--entry', 'cli.codex', ok=False)
        (self.root / '.agenthelm/config/roles.toml').unlink()
        result = self.run_cmd('bin/models', 'resolve', 'lead', '--entry', 'app.codex', ok=False)
        self.assertIn('roles.toml', result.stderr)

    def test_existing_cli_rejects_invalid_app_configuration(self):
        path = self.root / '.agenthelm/config/roles.toml'
        path.write_text(path.read_text().replace('model = "default"', 'model = false', 1))
        result = self.run_cmd('bin/models', 'get', 'lead', ok=False)
        self.assertIn('app.defaults.ccd.model', result.stderr)

    def test_cli_executor_keeps_candidate_and_command_compatibility(self):
        task = self.root / 'experiments/001-model-compatibility'
        task.mkdir(parents=True)
        self.run_cmd('bin/run-executor', task, '--role', 'hard', input='只读任务；输出一行。')
        executed = json.loads(self.log.read_text().splitlines()[-1])
        self.assertEqual((executed['cli'], executed['cwd'], executed['argv'][0]),
                         ('codex', str(task), 'exec'))
        self.assertNotIn('--model', executed['argv'])
        self.assertNotIn('-m', executed['argv'])


if __name__ == '__main__':
    unittest.main()
