"""Project route registration and migration preserve installed skills and user entries."""
from pathlib import Path
import re
import unittest
from urllib.parse import unquote

import test_skills
import test_workspace


class RouterRegistrationTests(unittest.TestCase):
    run_cmd = test_workspace.WorkspaceTests.run_cmd
    install = test_skills.SkillInstallTests.install
    tearDown = test_workspace.WorkspaceTests.tearDown

    def setUp(self):
        test_skills.SkillInstallTests.setUp(self)
        self.install('--all', '--agent', 'both')
        self.config = self.root / '.agenthelm/config/routers.toml'
        self.config.write_text('''library = "../../skills-library"
output = "../../.agenthelm/routers"
prefix = "route-"
[routers.research]
title = "研究"
description = "研究任务"
skills = ["alpha", "beta"]
[routers.data]
title = "数据"
description = "数据任务"
skills = ["source"]
''')

    def migrate(self, *args, **kwargs):
        return self.run_cmd('bin/build-routers', '--agent', 'both', '--replace-leaf-links',
                            *args, **kwargs)

    def test_preview_migration_and_repeat_preserve_skills_and_unrelated_entries(self):
        unrelated = self.root / '.claude/skills/user-skill'
        unrelated.mkdir()
        (unrelated / 'SKILL.md').write_text('user content')
        before = test_workspace.snapshot(self.root)
        self.migrate('--dry-run')
        self.assertEqual(test_workspace.snapshot(self.root), before)
        skill_trees = {name: test_workspace.snapshot(self.root / 'skills-library' / name)
                       for name in ('alpha', 'beta', 'source')}
        manifest_before = (self.root / '.agenthelm/state/skills-library.json').read_bytes()
        self.migrate()
        for name, contents in skill_trees.items():
            self.assertEqual(test_workspace.snapshot(self.root / 'skills-library' / name), contents)
        self.assertEqual((self.root / '.agenthelm/state/skills-library.json').read_bytes(), manifest_before)
        self.assertEqual((unrelated / 'SKILL.md').read_text(), 'user content')
        for folder in ('.agents/skills', '.claude/skills'):
            for name in skill_trees:
                self.assertFalse((self.root / folder / name).is_symlink())
            for name in ('route-research', 'route-data'):
                link = self.root / folder / name
                self.assertTrue(link.is_symlink())
                self.assertEqual(link.resolve(), self.root / '.agenthelm/routers' / name)
            self.assertEqual((self.root / folder / 'research-setup').resolve(),
                             self.root / 'skills/research-setup')
        before_repeat = test_workspace.snapshot(self.root)
        self.migrate()
        self.assertEqual(test_workspace.snapshot(self.root), before_repeat)

    def test_conflicting_route_entry_aborts_before_generation_or_leaf_removal(self):
        conflict = self.root / '.claude/skills/route-data'
        conflict.mkdir()
        (conflict / 'SKILL.md').write_text('manual route')
        before = test_workspace.snapshot(self.root)
        self.migrate(ok=False)
        self.assertEqual(test_workspace.snapshot(self.root), before)

    def test_nonmatching_leaf_entry_is_preserved_without_partial_migration(self):
        leaf = self.root / '.claude/skills/beta'
        leaf.unlink()
        leaf.symlink_to(self.root / 'skills/research-setup')
        before = test_workspace.snapshot(self.root)
        self.migrate(ok=False)
        self.assertEqual(test_workspace.snapshot(self.root), before)

    def test_replacement_requires_installer_manifest_and_explicit_target(self):
        self.run_cmd('bin/build-routers', '--replace-leaf-links', ok=False)
        (self.root / '.agenthelm/state/skills-library.json').unlink()
        before = test_workspace.snapshot(self.root)
        self.migrate(ok=False)
        self.assertEqual(test_workspace.snapshot(self.root), before)

    def test_project_registration_cannot_follow_symlink_to_home(self):
        folder = self.root / '.claude/skills'
        for link in folder.iterdir():
            link.unlink()
        folder.rmdir()
        folder.symlink_to(self.home / '.agents/skills')
        before = test_workspace.snapshot(self.root)
        self.migrate(ok=False)
        self.assertEqual(test_workspace.snapshot(self.root), before)

    def test_router_output_cannot_write_into_installed_skill_library(self):
        self.config.write_text(self.config.read_text().replace('../../.agenthelm/routers', '../../skills-library'))
        before = test_workspace.snapshot(self.root)
        self.migrate(ok=False)
        self.assertEqual(test_workspace.snapshot(self.root), before)

    def test_output_file_or_catalog_directory_conflict_is_detected_before_writes(self):
        output = self.root / '.agenthelm/routers'
        output.mkdir()
        (output / 'route-data').write_text('manual output file')
        before = test_workspace.snapshot(self.root)
        self.migrate(ok=False)
        self.assertEqual(test_workspace.snapshot(self.root), before)
        (output / 'route-data').unlink()
        catalog = self.root / 'skills-library/CATALOG.md'
        catalog.unlink()
        catalog.mkdir()
        before = test_workspace.snapshot(self.root)
        self.migrate(ok=False)
        self.assertEqual(test_workspace.snapshot(self.root), before)

    def test_rebuild_removes_only_obsolete_generated_route_links(self):
        self.migrate()
        self.config.write_text(self.config.read_text().replace('[routers.data]', '[routers.storage]'))
        self.migrate()
        for folder in ('.agents/skills', '.claude/skills'):
            self.assertFalse((self.root / folder / 'route-data').is_symlink())
            self.assertTrue((self.root / folder / 'route-storage').is_symlink())
        self.assertFalse((self.root / '.agenthelm/routers/route-data').exists())

    def test_relative_links_survive_workspace_move_and_symlink_entrypoints(self):
        self.migrate()
        original = self.root
        moved = self.base / 'moved workspace'
        self.root.rename(moved)
        self.root = moved
        documents = [moved / 'skills-library/CATALOG.md']
        for folder in ('.agenthelm/routers', '.agents/skills', '.claude/skills'):
            documents.extend(moved / folder / name / 'SKILL.md'
                             for name in ('route-data', 'route-research'))
        before = {str(p.relative_to(moved)): p.read_text() for p in documents}
        for document in documents:
            content = document.read_text()
            self.assertNotIn(str(original), content)
            self.assertNotIn(str(moved), content)
            urls = re.findall(r'\[[^\]]+\]\(([^)]+)\)', content)
            self.assertTrue(urls, str(document))
            for url in urls:
                relative = Path(unquote(url))
                self.assertFalse(relative.is_absolute(), url)
                target = (document.resolve().parent / relative).resolve()
                self.assertTrue(target.is_file(), str(target))
                self.assertIn(moved, target.parents)
        self.run_cmd('bin/build-routers', '--agent', 'both')
        self.assertEqual({str(p.relative_to(moved)): p.read_text() for p in documents}, before)


if __name__ == '__main__':
    unittest.main()
