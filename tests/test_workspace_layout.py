"""Tests for scripts/migrate-workspace-layout.py.

Everything runs against a hand-built temporary fixture root; the real repo's
claudedocs/ is never touched or copied. See
experiments/008-workspace-layout/findings/implementation-migration-fact.md for
the tool's interface contract.
"""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "migrate-workspace-layout.py"

_spec = importlib.util.spec_from_file_location("migrate_workspace_layout", SCRIPT_PATH)
migrate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migrate)

EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def _git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root)] + list(args),
        check=True,
        capture_output=True,
        text=True,
    )


def build_fixture(root: Path, tracked_count: int = 3) -> None:
    """Build a small representative workspace: claudedocs/ with the 14 known
    top-level files, both evidence directories (with nested structure and a
    zero-byte file), and a real .git repo classifying some files as tracked
    and the rest as ignored -- mirroring the real repo's claudedocs/ pattern.
    """
    claudedocs = root / "claudedocs"
    claudedocs.mkdir(parents=True)
    top_level_names = sorted(migrate.TOP_LEVEL_FILES.keys())
    for name in top_level_names:
        (claudedocs / name).write_text("content of {}\n".format(name), encoding="utf-8")

    ccd = claudedocs / "evidence" / "ccd-app-20261022"
    (ccd / "experiments" / "001-ccd-lead-smoke" / "findings").mkdir(parents=True)
    (ccd / "scripts").mkdir(parents=True)
    (ccd / "01-start-session.json").write_text('{"a": 1}\n', encoding="utf-8")
    (ccd / "11-followup3-request.json").write_text("", encoding="utf-8")  # zero-byte, like real evidence
    (ccd / "experiments" / "001-ccd-lead-smoke" / "findings" / "x.json").write_text(
        '{"x": 1}\n', encoding="utf-8"
    )
    (ccd / "scripts" / "ah_rev.py").write_text("# stub\n", encoding="utf-8")

    e008 = claudedocs / "evidence" / "008-workspace-layout"
    e008.mkdir(parents=True)
    (e008 / "created-receipt.json").write_text('{"ok": true}\n', encoding="utf-8")
    (e008 / "create-request.json").write_text('{"req": true}\n', encoding="utf-8")

    (root / ".gitignore").write_text("claudedocs/\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    force_add = ["claudedocs/" + n for n in top_level_names[:tracked_count]]
    _git(root, "add", "-f", *force_add)
    _git(root, "add", ".gitignore")


class WorkspaceLayoutTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()
        build_fixture(self.root)
        self.manifest_path = self.root / "manifest.json"

    def tearDown(self):
        self._tmp.cleanup()

    # -- helpers -----------------------------------------------------------

    def plan(self, force=False):
        return migrate.cmd_plan(self.root, self.manifest_path, force)

    def apply(self, backup=None):
        return migrate.cmd_apply(self.root, self.manifest_path, backup)

    def check(self, accept_link_edits=False):
        return migrate.cmd_check(self.root, self.manifest_path, accept_link_edits)

    def load_manifest(self):
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def entries_by_source(self):
        return {e["source"]: e for e in self.load_manifest()["entries"]}


class PlanTests(WorkspaceLayoutTestCase):
    def test_plan_discovers_full_static_mapping(self):
        self.plan()
        manifest = self.load_manifest()
        self.assertEqual(manifest["phase"], "planned")
        entries = manifest["entries"]

        expected_top = len(migrate.TOP_LEVEL_FILES)
        top = [e for e in entries if e["category"] == "top-level"]
        ccd = [e for e in entries if e["category"] == "evidence-ccd"]
        e008 = [e for e in entries if e["category"] == "evidence-008"]

        self.assertEqual(len(top), expected_top)
        self.assertEqual(len(ccd), 4)  # fixture's ccd evidence file count
        self.assertEqual(len(e008), 2)
        self.assertTrue(all(not e["frozen"] for e in top))
        self.assertTrue(all(e["frozen"] for e in ccd + e008))

        for e in top:
            self.assertEqual(
                migrate.TOP_LEVEL_FILES[Path(e["source"]).name], e["target"]
            )

    def test_plan_classifies_git_status(self):
        self.plan()
        by_source = self.entries_by_source()
        top_level_names = sorted(migrate.TOP_LEVEL_FILES.keys())
        tracked_sources = {"claudedocs/" + n for n in top_level_names[:3]}
        for source, entry in by_source.items():
            expected = "tracked" if source in tracked_sources else "ignored"
            self.assertEqual(entry["git_status"], expected, source)

    def test_plan_records_zero_byte_file_correctly(self):
        self.plan()
        by_source = self.entries_by_source()
        entry = by_source["claudedocs/evidence/ccd-app-20261022/11-followup3-request.json"]
        self.assertEqual(entry["size"], 0)
        self.assertEqual(entry["sha256"], EMPTY_SHA256)

    def test_plan_fails_on_unregistered_top_level_file(self):
        (self.root / "claudedocs" / "mystery.md").write_text("surprise\n", encoding="utf-8")
        with self.assertRaises(migrate.MigrationError) as ctx:
            self.plan()
        self.assertIn("mystery.md", str(ctx.exception))
        self.assertFalse(self.manifest_path.exists())

    def test_plan_fails_on_unregistered_evidence_entry(self):
        (self.root / "claudedocs" / "evidence" / "stray-dir").mkdir()
        (self.root / "claudedocs" / "evidence" / "stray-dir" / "f.txt").write_text(
            "x", encoding="utf-8"
        )
        with self.assertRaises(migrate.MigrationError) as ctx:
            self.plan()
        self.assertIn("stray-dir", str(ctx.exception))

    def test_plan_fails_on_symlink_source(self):
        top_name = sorted(migrate.TOP_LEVEL_FILES.keys())[0]
        target_file = self.root / "claudedocs" / top_name
        other = self.root / "claudedocs" / "evidence" / "008-workspace-layout" / "created-receipt.json"
        target_file.unlink()
        os.symlink(other, target_file)
        with self.assertRaises(migrate.MigrationError) as ctx:
            self.plan()
        self.assertIn("symlink", str(ctx.exception))

    def test_plan_refuses_to_overwrite_non_planned_manifest_without_force(self):
        self.plan()
        manifest = self.load_manifest()
        manifest["phase"] = "backed_up"  # simulate progress past "planned"
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        with self.assertRaises(migrate.MigrationError) as ctx:
            self.plan(force=False)
        self.assertIn("force", str(ctx.exception))

        # --force bypasses the guard and regenerates a fresh "planned" manifest.
        self.plan(force=True)
        self.assertEqual(self.load_manifest()["phase"], "planned")

    def test_plan_allows_overwrite_while_still_planned(self):
        self.plan()
        self.plan()  # no exception: still "planned", safe to regenerate


class ApplyHappyPathTests(WorkspaceLayoutTestCase):
    def test_apply_moves_every_entry_and_cleans_up(self):
        self.plan()
        before = self.entries_by_source()
        self.apply()

        manifest = self.load_manifest()
        self.assertEqual(manifest["phase"], "applied")
        self.assertIsNotNone(manifest["backup_dir"])
        backup_dir = Path(manifest["backup_dir"])
        self.assertTrue(backup_dir.is_dir())

        for source, entry in before.items():
            src = self.root / source
            tgt = self.root / entry["target"]
            self.assertFalse(src.exists(), source)
            self.assertTrue(tgt.exists(), entry["target"])
            self.assertEqual(migrate._sha256_file(tgt), entry["sha256"])
            self.assertEqual(migrate._mode_octal(tgt), entry["mode"])

            backup_copy = backup_dir / source
            self.assertTrue(backup_copy.exists())
            self.assertEqual(migrate._sha256_file(backup_copy), entry["sha256"])

        # claudedocs/ only ever held migrated files in this fixture, so it
        # (and its now-empty evidence subdirectories) must be rmdir'd away.
        self.assertFalse((self.root / "claudedocs").exists())

        zero_byte_target = self.root / before[
            "claudedocs/evidence/ccd-app-20261022/11-followup3-request.json"
        ]["target"]
        self.assertEqual(zero_byte_target.stat().st_size, 0)

    def test_check_passes_after_clean_apply(self):
        self.plan()
        self.apply()
        self.assertEqual(self.check(), 0)

    def test_rerun_apply_after_success_is_a_no_op(self):
        self.plan()
        self.apply()
        manifest_before = self.load_manifest()
        self.assertEqual(self.apply(), 0)
        self.assertEqual(self.load_manifest(), manifest_before)

    def test_check_before_apply_validates_sources(self):
        self.plan()
        self.assertEqual(self.check(), 0)  # phase=planned, checks sources

        top_name = sorted(migrate.TOP_LEVEL_FILES.keys())[0]
        (self.root / "claudedocs" / top_name).write_text("tampered\n", encoding="utf-8")
        self.assertEqual(self.check(), 1)


class ApplyRejectionTests(WorkspaceLayoutTestCase):
    def test_apply_rejects_target_conflict(self):
        self.plan()
        entry = next(iter(self.entries_by_source().values()))
        conflict_path = self.root / entry["target"]
        conflict_path.parent.mkdir(parents=True, exist_ok=True)
        conflict_path.write_text("already here\n", encoding="utf-8")

        with self.assertRaises(migrate.MigrationError) as ctx:
            self.apply()
        self.assertIn("冲突", str(ctx.exception))

        manifest = self.load_manifest()
        self.assertIsNone(manifest["backup_dir"])  # preflight failed before backup
        for source in self.entries_by_source():
            self.assertTrue((self.root / source).exists(), source)  # no source lost

    def test_apply_rejects_source_hash_change_after_plan(self):
        self.plan()
        top_name = sorted(migrate.TOP_LEVEL_FILES.keys())[0]
        tampered = self.root / "claudedocs" / top_name
        tampered.write_text("changed after plan\n", encoding="utf-8")

        with self.assertRaises(migrate.MigrationError) as ctx:
            self.apply()
        self.assertIn(top_name, str(ctx.exception))
        self.assertIsNone(self.load_manifest()["backup_dir"])

    def test_apply_rejects_permission_change_after_plan(self):
        self.plan()
        top_name = sorted(migrate.TOP_LEVEL_FILES.keys())[0]
        changed = self.root / "claudedocs" / top_name
        os.chmod(changed, 0o600)
        try:
            with self.assertRaises(migrate.MigrationError) as ctx:
                self.apply()
            self.assertIn(top_name, str(ctx.exception))
        finally:
            os.chmod(changed, 0o644)

    def test_apply_rejects_symlink_parent_for_target(self):
        self.plan()
        real_dir = self.root / "real-experiments-dir"
        real_dir.mkdir()
        os.symlink(real_dir, self.root / "experiments", target_is_directory=True)

        with self.assertRaises(migrate.MigrationError) as ctx:
            self.apply()
        self.assertIn("symlink", str(ctx.exception))

        for source in self.entries_by_source():
            self.assertTrue((self.root / source).exists(), source)
        self.assertIsNone(self.load_manifest()["backup_dir"])


class ApplyFailureRecoveryTests(WorkspaceLayoutTestCase):
    def test_copy_failure_rolls_back_this_run_only_and_retry_succeeds(self):
        self.plan()
        before = self.entries_by_source()
        real_sha256 = migrate._sha256_file
        poison_rel_target = migrate.TOP_LEVEL_FILES["metagpt-harness.html"]

        def poisoned_sha256(path):
            if str(path).endswith(poison_rel_target) and self.root.as_posix() in str(path):
                return "0" * 64
            return real_sha256(path)

        with mock.patch.object(migrate, "_sha256_file", side_effect=poisoned_sha256):
            with self.assertRaises(migrate.MigrationError) as ctx:
                self.apply()
        self.assertIn("校验失败", str(ctx.exception))

        manifest = self.load_manifest()
        self.assertEqual(manifest["phase"], "backed_up")  # never advanced to "copied"
        self.assertIsNotNone(manifest["backup_dir"])  # backup from before copy loop stays

        for source, entry in before.items():
            self.assertTrue((self.root / source).exists(), source)  # no source lost
            self.assertFalse(entry["copied"], source)
            tgt = self.root / entry["target"]
            # every target attempted in the failed run was rolled back
            self.assertFalse(tgt.exists(), entry["target"])

        # retry with the real hash function: should complete cleanly this time.
        self.apply()
        self.assertEqual(self.load_manifest()["phase"], "applied")
        for source, entry in before.items():
            self.assertFalse((self.root / source).exists())
            self.assertTrue((self.root / entry["target"]).exists())


class CheckLinkEditTests(WorkspaceLayoutTestCase):
    def test_frozen_hash_change_always_fails_check(self):
        self.plan()
        self.apply()
        entries = self.entries_by_source()
        frozen_entry = next(e for e in entries.values() if e["frozen"])
        tgt = self.root / frozen_entry["target"]
        tgt.write_text("tampered evidence\n", encoding="utf-8")

        self.assertEqual(self.check(accept_link_edits=False), 1)
        # --accept-link-edits must NOT be able to launder a frozen change.
        self.assertEqual(self.check(accept_link_edits=True), 1)
        manifest = self.load_manifest()
        changed_entry = next(e for e in manifest["entries"] if e["target"] == frozen_entry["target"])
        self.assertIsNone(changed_entry["post_edit"])

    def test_top_level_hash_change_requires_accept_flag_then_is_recorded(self):
        self.plan()
        self.apply()
        entries = self.entries_by_source()
        top_entry = next(e for e in entries.values() if not e["frozen"])
        tgt = self.root / top_entry["target"]
        original_sha = top_entry["sha256"]
        tgt.write_text("edited relative links\n", encoding="utf-8")
        new_sha = migrate._sha256_file(tgt)

        self.assertEqual(self.check(accept_link_edits=False), 1)
        manifest = self.load_manifest()
        unchanged_entry = next(e for e in manifest["entries"] if e["target"] == top_entry["target"])
        self.assertIsNone(unchanged_entry["post_edit"])

        self.assertEqual(self.check(accept_link_edits=True), 0)
        manifest = self.load_manifest()
        recorded = next(e for e in manifest["entries"] if e["target"] == top_entry["target"])
        self.assertEqual(recorded["post_edit"]["sha256"], new_sha)
        self.assertEqual(recorded["post_edit"]["pre_sha256"], original_sha)

        # a later plain check (no flag) stays green against the recorded hash.
        self.assertEqual(self.check(accept_link_edits=False), 0)

    def test_accept_flag_only_covers_top_level_in_a_mixed_batch(self):
        self.plan()
        self.apply()
        entries = self.entries_by_source()
        top_entry = next(e for e in entries.values() if not e["frozen"])
        frozen_entry = next(e for e in entries.values() if e["frozen"])
        (self.root / top_entry["target"]).write_text("link fix\n", encoding="utf-8")
        (self.root / frozen_entry["target"]).write_text("evidence tampering\n", encoding="utf-8")

        self.assertEqual(self.check(accept_link_edits=True), 1)  # frozen still fails the batch
        manifest = self.load_manifest()
        top_after = next(e for e in manifest["entries"] if e["target"] == top_entry["target"])
        frozen_after = next(e for e in manifest["entries"] if e["target"] == frozen_entry["target"])
        self.assertIsNone(top_after["post_edit"])  # a failed batch publishes no accepted edits
        self.assertIsNone(frozen_after["post_edit"])  # frozen entry never recorded


class SafetyHelperTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name).resolve()

    def tearDown(self):
        self._tmp.cleanup()

    def test_ensure_within_rejects_path_traversal(self):
        with self.assertRaises(migrate.MigrationError):
            migrate._ensure_within(Path("../../etc/passwd"), self.root, "test")

    def test_resolve_backup_dir_rejects_escape(self):
        with self.assertRaises(migrate.MigrationError):
            migrate._resolve_backup_dir(self.root, "../outside", "run1")

    def test_resolve_backup_dir_accepts_relative_within_root(self):
        backup = migrate._resolve_backup_dir(self.root, "custom/backup", "run1")
        backup.relative_to(self.root.resolve())  # raises ValueError if escaped

    def test_normalization_collision_detected(self):
        entries = [
            {"source": "a/Foo.md", "target": "b/Foo.md"},
            {"source": "a/foo.md", "target": "b/other.md"},
        ]
        with self.assertRaises(migrate.MigrationError):
            migrate._check_normalization_collisions(entries)

    def test_no_collision_for_distinct_names(self):
        entries = [
            {"source": "a/one.md", "target": "b/one.md"},
            {"source": "a/two.md", "target": "b/two.md"},
        ]
        migrate._check_normalization_collisions(entries)  # must not raise


class IntegrityRegressionTests(WorkspaceLayoutTestCase):
    def test_apply_rejects_new_source_after_plan(self):
        self.plan()
        (self.root / 'claudedocs/evidence/008-workspace-layout/new.json').write_text('{}')
        with self.assertRaises(migrate.MigrationError):
            self.apply()
        self.assertIsNone(self.load_manifest()['backup_dir'])

    def test_manifest_cannot_redirect_source_or_target(self):
        for key in ('source', 'target'):
            self.plan(force=True)
            manifest = self.load_manifest()
            manifest['entries'][0][key] = '../../outside'
            self.manifest_path.write_text(json.dumps(manifest))
            with self.assertRaises(migrate.MigrationError):
                self.apply()

    def test_plan_refuses_symlink_evidence_directory(self):
        source = self.root / 'claudedocs/evidence/008-workspace-layout'
        source.rename(source.with_name('saved'))
        source.symlink_to(source.with_name('saved'), target_is_directory=True)
        with self.assertRaises(migrate.MigrationError):
            self.plan()

    def test_copy_checkpoint_interrupt_can_resume(self):
        self.plan()
        real_save = migrate._save_manifest
        interrupted = [False]
        def save(path, manifest):
            real_save(path, manifest)
            if any(e.get('target_identity') and not e['copied'] for e in manifest['entries']) and not interrupted[0]:
                interrupted[0] = True
                raise KeyboardInterrupt()
        with mock.patch.object(migrate, '_save_manifest', side_effect=save):
            with self.assertRaises(KeyboardInterrupt):
                self.apply()
        self.apply()
        self.assertEqual(self.check(), 0)

    def test_deletion_checkpoint_interrupt_can_resume(self):
        self.plan()
        real_save = migrate._save_manifest
        def save(path, manifest):
            if any(e['source_removed'] for e in manifest['entries']):
                raise KeyboardInterrupt()
            real_save(path, manifest)
        with mock.patch.object(migrate, '_save_manifest', side_effect=save):
            with self.assertRaises(KeyboardInterrupt):
                self.apply()
        self.apply()
        self.assertEqual(self.check(), 0)

    def test_changed_source_is_not_deleted_after_copy(self):
        self.plan()
        real_save = migrate._save_manifest
        source = self.root / self.load_manifest()['entries'][0]['source']
        def save(path, manifest):
            real_save(path, manifest)
            if manifest['phase'] == 'copied':
                source.write_text('changed while copying')
        with mock.patch.object(migrate, '_save_manifest', side_effect=save):
            with self.assertRaises(migrate.MigrationError):
                self.apply()
        self.assertEqual(source.read_text(), 'changed while copying')
        self.assertTrue(all((self.root / e['source']).exists() for e in self.load_manifest()['entries']))

    def test_check_rejects_changed_mode(self):
        self.plan()
        self.apply()
        target = self.root / self.load_manifest()['entries'][0]['target']
        target.chmod(0o600)
        self.assertEqual(self.check(), 1)

    def test_manifest_path_outside_root_is_refused(self):
        with self.assertRaises(migrate.MigrationError):
            migrate.cmd_plan(self.root, self.root.parent / 'outside-manifest.json', False)


class CliTests(WorkspaceLayoutTestCase):
    def test_main_plan_subcommand(self):
        rc = migrate.main(
            ["--root", str(self.root), "--manifest", str(self.manifest_path), "plan"]
        )
        self.assertEqual(rc, 0)
        self.assertTrue(self.manifest_path.exists())

    def test_main_reports_error_without_raising(self):
        (self.root / "claudedocs" / "mystery.md").write_text("x\n", encoding="utf-8")
        rc = migrate.main(
            ["--root", str(self.root), "--manifest", str(self.manifest_path), "plan"]
        )
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
