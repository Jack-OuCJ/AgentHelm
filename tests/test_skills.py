"""Domain skill installation contracts; network and agents are never invoked."""
import json
import unittest

import test_workspace


class SkillInstallTests(unittest.TestCase):
    run_cmd = test_workspace.WorkspaceTests.run_cmd

    def setUp(self):
        test_workspace.WorkspaceTests.setUp(self)
        self.source = self.base / 'library-source'
        self.source.mkdir()
        (self.source / 'LICENSE').write_text('MIT fixture license\n')
        for name in ('alpha', 'beta', 'source'):
            skill = self.source / 'skills' / name
            (skill / 'references').mkdir(parents=True)
            (skill / 'SKILL.md').write_text(
                f'---\nname: {name}\ndescription: >-\n  {name} domain\n  research workflow\n---\n# Test\n')
            (skill / 'references/context.md').write_text(name + ' reference\n')
        self.source_before = test_workspace.snapshot(self.source)

    def tearDown(self):
        test_workspace.WorkspaceTests.tearDown(self)

    def install(self, *args, **kwargs):
        if '--agent' not in args:
            args = (*args, '--agent', 'both')
        return self.run_cmd('bin/install-component', 'skills-library', '--source', self.source,
                            *args, **kwargs)

    def test_catalog_preview_and_explicit_selection(self):
        result = self.install()
        self.assertIn('alpha | alpha domain research workflow', result.stdout)
        self.assertIn('beta |', result.stdout)
        self.install('--skill', 'alpha', '--dry-run')
        self.assertFalse((self.root / 'skills-library').exists())
        self.assertFalse((self.root / '.agenthelm/state/skills-library.json').exists())
        self.install('--skill', 'alpha')
        library = self.root / 'skills-library'
        self.assertEqual((library / 'alpha/references/context.md').read_text(), 'alpha reference\n')
        self.assertFalse((library / 'beta').exists())
        self.assertEqual((library / 'LICENSE').read_text(), 'MIT fixture license\n')
        for folder in ('.agents/skills', '.claude/skills'):
            self.assertEqual((self.root / folder / 'alpha').resolve(), library / 'alpha')
        self.assertEqual(test_workspace.snapshot(self.source), self.source_before)
        manifest = json.loads((self.root / '.agenthelm/state/skills-library.json').read_text())
        self.assertEqual(set(manifest['skills']), {'alpha'})
        self.assertEqual(manifest['skills']['alpha']['source'], str(self.source))

    def test_all_agents_idempotence_and_upstream_refresh(self):
        self.install('--all', '--agent', 'none')
        self.assertFalse((self.root / '.agents/skills/alpha').exists())
        self.assertFalse((self.root / '.claude/skills/alpha').exists())
        self.install('--all', '--agent', 'codex')
        before = test_workspace.snapshot(self.root / 'skills-library')
        self.install('--all', '--agent', 'codex')
        self.assertEqual(test_workspace.snapshot(self.root / 'skills-library'), before)
        self.assertFalse((self.root / '.claude/skills/alpha').exists())
        self.install('--skill', 'alpha', '--agent', 'claude')
        self.assertTrue((self.root / '.claude/skills/alpha').is_symlink())
        (self.source / 'skills/alpha/references/context.md').write_text('new upstream reference\n')
        self.install('--skill', 'alpha')
        self.assertEqual((self.root / 'skills-library/alpha/references/context.md').read_text(),
                         'new upstream reference\n')
        self.assertTrue((self.root / 'skills-library/beta/SKILL.md').exists())

    def test_local_changes_and_unmanaged_content_are_preserved(self):
        self.install('--skill', 'alpha')
        target = self.root / 'skills-library/alpha/references/context.md'
        target.write_text('local user work\n')
        result = self.install('--all', ok=False)
        self.assertIn('locally modified', result.stderr)
        self.assertEqual(target.read_text(), 'local user work\n')
        self.assertFalse((self.root / 'skills-library/beta').exists())
        target.write_text('alpha reference\n')
        (self.root / 'skills-library/beta').mkdir()
        self.install('--all', ok=False)
        self.assertEqual(list((self.root / 'skills-library/beta').iterdir()), [])

    def test_complete_preflight_preserves_existing_skill_entries(self):
        existing = self.root / '.claude/skills/beta'
        existing.mkdir()
        (existing / 'SKILL.md').write_text('manual user skill')
        self.install('--all', ok=False)
        self.assertFalse((self.root / 'skills-library').exists())
        self.assertFalse((self.root / '.agents/skills/alpha').exists())
        self.assertEqual((existing / 'SKILL.md').read_text(), 'manual user skill')

    def test_symlink_escapes_and_skill_symlinks_are_rejected(self):
        folder = self.root / '.claude/skills'
        for entry in folder.iterdir():
            entry.unlink()
        folder.rmdir()
        folder.symlink_to(self.home / '.agents/skills')
        self.install('--all', ok=False)
        self.assertFalse((self.root / 'skills-library').exists())
        folder.unlink()
        folder.mkdir()
        (self.source / 'skills/alpha/references/escape').symlink_to(self.home / '.agents/AGENTS.md')
        self.install('--all', ok=False)
        self.assertFalse((self.root / 'skills-library').exists())

    def test_invalid_selection_metadata_and_duplicate_names_do_not_install(self):
        self.install('--skill', '../escape', ok=False)
        self.install('--skill', 'alpha', '--all', ok=False)
        self.install('--skill', 'alpha', '--list', ok=False)
        original = (self.source / 'skills/alpha/SKILL.md').read_text()
        (self.source / 'skills/alpha/SKILL.md').write_text('no frontmatter')
        self.install('--all', ok=False)
        (self.source / 'skills/alpha/SKILL.md').write_text(original.replace('name: alpha', 'name: renamed'))
        self.install('--all', ok=False)
        (self.source / 'skills/alpha/SKILL.md').write_text(original)
        other = self.source / 'other/alpha'
        other.mkdir(parents=True)
        (other / 'SKILL.md').write_text(original)
        self.install('--all', ok=False)
        self.assertFalse((self.root / 'skills-library').exists())

    def test_official_download_uses_workspace_temporary_directory_and_records_revision(self):
        script = self.fakebin / 'git'
        script.write_text('#!' + test_workspace.sys.executable + '\n' + '''
import json,os,shutil,sys
from pathlib import Path
args=sys.argv[1:]
with open(os.environ['TEST_LOG'], 'a') as f: f.write(json.dumps(args)+'\\n')
if 'clone' in args:
 target=Path(args[-1]);assert target.parent.parent==Path(os.environ['TEST_ROOT'])/'.agenthelm/state'
 shutil.copytree(os.environ['TEST_SOURCE'],target)
elif 'rev-parse' in args: print('a'*40)
elif 'fetch' in args or 'checkout' in args: pass
else: raise SystemExit(1)
''')
        script.chmod(0o755)
        env = dict(self.env, TEST_ROOT=str(self.root), TEST_SOURCE=str(self.source))
        self.run_cmd('bin/install-component', 'skills-library', '--skill', 'alpha', '--ref',
                     'a' * 40, '--agent', 'both', env=env)
        manifest = json.loads((self.root / '.agenthelm/state/skills-library.json').read_text())
        self.assertEqual(manifest['skills']['alpha']['revision'], 'a' * 40)
        self.assertEqual(list((self.root / '.agenthelm/state').glob('skills-download-*')), [])
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertTrue(any('fetch' in call and 'a' * 40 in call for call in calls))
        self.assertTrue(all('core.hooksPath=/dev/null' in call for call in calls))

    def test_download_failure_does_not_install(self):
        script = self.fakebin / 'git'
        script.write_text('#!/bin/sh\nexit 1\n')
        script.chmod(0o755)
        result = self.run_cmd('bin/install-component', 'skills-library', '--all', '--agent', 'both', ok=False)
        self.assertIn('download failed', result.stderr)
        self.assertFalse((self.root / 'skills-library').exists())
        self.assertEqual(list((self.root / '.agenthelm/state').glob('skills-download-*')), [])

    def test_install_requires_explicit_registration_choice(self):
        result = self.run_cmd('bin/install-component', 'skills-library', '--source', self.source,
                              '--all', ok=False)
        self.assertIn('注册方式', result.stderr)
        self.assertFalse((self.root / 'skills-library').exists())


if __name__ == '__main__':
    unittest.main()
