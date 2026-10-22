"""Offline contracts for shared rules and environment-specific context."""
import json
import unittest

import test_workspace


class RuntimeRulesTests(unittest.TestCase):
    setUp = test_workspace.WorkspaceTests.setUp
    tearDown = test_workspace.WorkspaceTests.tearDown
    run_cmd = test_workspace.WorkspaceTests.run_cmd

    def test_environment_context_reaches_all_roles_and_restore_paths(self):
        task = self.root / 'experiments/001-environment'
        task.mkdir()
        environments = ('cli-herdr', 'cli-plain', 'app')
        for environment in environments:
            with self.subTest(environment=environment):
                (self.root / '.agenthelm/config/env').write_text(environment + '\n')
                instructions = self.root / 'rules' / f'env-{environment}.md'
                expected = instructions.read_text().strip()
                template = self.root / 'templates' / instructions.name
                marker = f'未同步的环境模板修改：{environment}'
                template.write_text(template.read_text() + '\n' + marker + '\n')
                if environment == 'app':
                    previous_commands = self.log.read_text() if self.log.exists() else ''
                    self.run_cmd('bin/spawn-lead', task, ok=False)
                    self.run_cmd('bin/run-executor', task, '--print', input='只读任务目录。', ok=False)
                    self.run_cmd('bin/app-session', 'register', '--entry', 'app.codex', '--session', 'dispatcher')
                    capabilities = {name: {'available': True, 'source': 'fake native host'} for name in
                                    ('create', 'read', 'wait', 'followup', 'model', 'effort',
                                     'verify_model', 'native_executor')}
                    capabilities['verify_model']['fields'] = ['model', 'effort']
                    capabilities['model']['values'] = ['native-model']
                    capabilities['effort']['combinations'] = {'native-model': ['high']}
                    self.run_cmd('bin/app-session', 'capabilities', '--session', 'dispatcher',
                                 input=json.dumps({'entry': 'app.codex', 'source': 'fake host inventory',
                                                   'capabilities': capabilities}))
                    parameters = json.dumps({'defaults': {'model': 'native-model', 'effort': 'high',
                                                          'source': 'fake App settings', 'evidence': 'readback'}})
                    (task / 'README.md').write_text('# Read task directory')
                    request = json.loads(self.run_cmd('bin/spawn-lead', task, '--session', 'dispatcher',
                                                     '--app-params', parameters).stdout)
                    lead = request['prompt']
                    self.run_cmd('bin/app-session', 'result', '--session', 'dispatcher', '--request', request['id'],
                                 input=json.dumps({'request_id': request['id'], 'owner_epoch': 1,
                                                   'entry': 'app.codex', 'status': 'created', 'session': 'lead',
                                                   'workspace': str(self.root), 'cwd': str(task),
                                                   'visible': True, 'independent': True, 'executed': True,
                                                   'model': 'native-model', 'effort': 'high',
                                                   'evidence': {name: 'fake native observation' for name in
                                                                ('session', 'workspace', 'cwd', 'visible',
                                                                 'independent', 'executed', 'model', 'effort')}}))
                    executor = json.loads(self.run_cmd('bin/run-executor', task, '--session', 'lead',
                                                      '--app-params', parameters, input='只读任务目录。').stdout)['prompt']
                    self.assertEqual(self.log.read_text() if self.log.exists() else '', previous_commands)
                else:
                    executor = self.run_cmd('bin/run-executor', task, '--print', input='只读任务目录。').stdout
                    lead = self.run_cmd('bin/spawn-lead', task).stdout
                contexts = [
                    self.run_cmd('bin/dispatch', '--print', *(['--session', 'dispatcher'] if environment == 'app' else [])).stdout,
                    executor,
                    self.run_cmd('bin/lead-reload', task, 'resume', *(['--session', 'lead'] if environment == 'app' else [])).stdout,
                    self.run_cmd('bin/lead-watch-start', input=json.dumps({
                        'cwd': str(self.root), **({'session_id': 'dispatcher'} if environment == 'app' else {})})).stdout,
                    self.run_cmd('bin/lead-watch-start', input=json.dumps({
                        'cwd': str(task), **({'session_id': 'lead'} if environment == 'app' else {})})).stdout,
                ]
                if environment == 'cli-herdr':
                    commands = [json.loads(row) for row in self.log.read_text().splitlines()]
                    lead = [row['argv'][-1] for row in commands
                            if row['argv'][:2] == ['agent', 'prompt']][-1]
                contexts.append(lead)
                for context in contexts:
                    self.assertIn(f'当前运行环境：{environment}', context)
                    self.assertIn(str(instructions), context)
                    self.assertIn(expected, context)
                    self.assertNotIn(str(template), context)
                    self.assertNotIn(marker, context)
                    for other in environments:
                        if other != environment:
                            other_instructions = self.root / 'rules' / f'env-{other}.md'
                            self.assertNotIn(other_instructions.read_text().strip(), context)

    def test_missing_env_defaults_to_plain_without_launching_agents(self):
        (self.root / '.agenthelm/config/env').unlink()
        task = self.root / 'experiments/001-default'
        task.mkdir()
        expected = (self.root / 'rules/env-cli-plain.md').read_text().strip()
        for command, args in [('bin/dispatch', ('--print',)), ('bin/spawn-lead', (task,))]:
            context = self.run_cmd(command, *args).stdout
            self.assertIn('当前运行环境：cli-plain', context)
            self.assertIn(expected, context)
        self.assertFalse(self.log.exists())

    def test_invalid_environment_or_missing_installed_rules_stops_before_launch(self):
        task = self.root / 'experiments/001-invalid'
        task.mkdir()
        config = self.root / '.agenthelm/config/env'
        for environment in ('unknown', '../../outside', ''):
            with self.subTest(environment=environment):
                config.write_text(environment + '\n')
                for command, args in [('bin/dispatch', ('--print',)), ('bin/spawn-lead', (task,))]:
                    result = self.run_cmd(command, *args, ok=False)
                    self.assertIn('unknown environment', result.stderr)
        config.write_text('cli-herdr\n')
        instructions = self.root / 'rules/env-cli-herdr.md'
        instructions.unlink()
        self.assertTrue((self.root / 'templates/env-cli-herdr.md').is_file())
        for command, args in [('bin/dispatch', ('--print',)), ('bin/spawn-lead', (task,))]:
            result = self.run_cmd(command, *args, ok=False)
            self.assertIn('missing environment instructions', result.stderr)
            self.assertIn(str(instructions), result.stderr)
            self.assertIn(str(self.root / 'bin/install-rules'), result.stderr)
        self.assertFalse(self.log.exists())

    def test_shared_rule_reference_is_consistent_after_install(self):
        template = self.root / 'templates/claude-global.md'
        installed = self.root / 'rules/claude-global.md'
        self.assertEqual(installed.read_text(), template.read_text())
        for relative in ('templates/research-AGENTS.md', 'rules/research-workflow.md',
                         'skills/agenthelm-workflow/references/lead.md',
                         'skills/agenthelm-workflow/references/dispatcher.md'):
            content = (self.root / relative).read_text()
            self.assertIn('`rules/claude-global.md`', content)
            self.assertNotIn('`templates/claude-global.md`', content)

    def test_role_and_environment_references_use_installed_rules(self):
        executor = (self.root / 'skills/agenthelm-workflow/references/executor.md').read_text()
        self.assertIn('`rules/executor-agents.md`', executor)
        self.assertNotIn('`templates/executor-agents.md`', executor)
        workflow = (self.root / 'skills/agenthelm-workflow/SKILL.md').read_text()
        for environment in ('cli-herdr', 'cli-plain', 'app'):
            self.assertIn(f'`rules/env-{environment}.md`', workflow)
            self.assertNotIn(f'`templates/env-{environment}.md`', workflow)

    def test_install_updates_all_rules_only_after_sync_and_is_idempotent(self):
        config_before = test_workspace.snapshot(self.root / '.agenthelm/config')
        mapping = (
            ('claude-global.md', 'rules/claude-global.md'),
            ('executor-agents.md', 'rules/executor-agents.md'),
            ('env-cli-herdr.md', 'rules/env-cli-herdr.md'),
            ('env-cli-plain.md', 'rules/env-cli-plain.md'),
            ('env-app.md', 'rules/env-app.md'),
            ('research-AGENTS.md', 'rules/research-workflow.md'),
            ('research-extra.md', 'rules-extra.md'),
        )
        for source, destination in mapping:
            template = self.root / 'templates' / source
            installed = self.root / destination
            original = installed.read_text()
            self.assertEqual(original, template.read_text())
            template.write_text(original + f'\n同步测试标记：{source}\n')
            self.assertEqual(installed.read_text(), original)
        marker = '同步测试标记：env-cli-herdr.md'
        self.assertNotIn(marker, self.run_cmd('bin/dispatch', '--print').stdout)
        self.run_cmd('bin/install-rules')
        for source, destination in mapping:
            self.assertEqual((self.root / destination).read_text(),
                             (self.root / 'templates' / source).read_text())
        self.assertIn(marker, self.run_cmd('bin/dispatch', '--print').stdout)
        before = test_workspace.snapshot(self.root / 'rules')
        self.run_cmd('bin/install-rules')
        self.assertEqual(test_workspace.snapshot(self.root / 'rules'), before)
        self.assertEqual(test_workspace.snapshot(self.root / '.agenthelm/config'), config_before)

    def test_task_creation_still_uses_task_card_template(self):
        (self.root / '.agenthelm/config/env').write_text('cli-plain\n')
        template = self.root / 'templates/task-card.md'
        template.write_text(template.read_text() + '\n任务卡模板测试标记\n')
        self.run_cmd('bin/new-task', 'template-card', input='')
        task = self.root / 'experiments/001-template-card'
        self.assertEqual((task / 'README.md').read_text(),
                         template.read_text().replace('<task-id>', task.name))
        self.assertFalse(self.log.exists())

    def test_lint_reports_missing_installed_shared_rules(self):
        (self.root / 'rules/claude-global.md').unlink()
        result = self.run_cmd('bin/kb', 'lint', ok=False)
        self.assertIn('missing path: rules/claude-global.md', result.stdout)


if __name__ == '__main__':
    unittest.main()
