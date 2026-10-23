#!/usr/bin/env python3
"""Plan/apply/check a one-time, statically-mapped migration out of claudedocs/.

Scope: this tool only understands the fixed claudedocs/ -> {experiments/*/artifacts,
docs/design, docs/validation} mapping agreed for AgentHelm task 008. It is not a
general-purpose file migration framework. See
experiments/008-workspace-layout/findings/implementation-migration-fact.md for the
interface contract.

Python 3.9/3.10 compatible, standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
import unicodedata
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Static mapping (must not change targets; see brief-implement-migration.md)
# ---------------------------------------------------------------------------

# category -> frozen (evidence packages must never be re-hashed differently;
# top-level docs may later have their relative links edited by the Lead).
CATEGORY_FROZEN = {
    "top-level": False,
    "evidence-ccd": True,
    "evidence-008": True,
}

# Single-file entries directly under claudedocs/ (the "14 top-level files").
TOP_LEVEL_FILES: Dict[str, str] = {
    "agenthelm-intro.html": "experiments/002-agenthelm-intro/artifacts/agenthelm-intro.html",
    "metagpt-harness.html": "experiments/003-metagpt-harness/artifacts/metagpt-harness.html",
    "helpflow-deep-dive.html": "experiments/004-helpflow-deep-dive/artifacts/helpflow-deep-dive.html",
    "funcsea-architecture.html": "experiments/005-funcsea-architecture/artifacts/funcsea-architecture.html",
    "atoms-architecture.html": "experiments/006-atoms-architecture/artifacts/atoms-architecture.html",
    "2026-10-22-workspace-layout-summary.md": "experiments/008-workspace-layout/artifacts/2026-10-22-workspace-layout-summary.md",
    "2026-10-22-codex-app-smoke-validation.md": "experiments/007-codex-app-dispatch-smoke/artifacts/2026-10-22-codex-app-smoke-validation.md",
    "2026-10-21-aris-autoresearch-agenthelm-plan.md": "docs/design/2026-10-21-aris-autoresearch-agenthelm-plan.md",
    "2026-10-22-app-mode-design.md": "docs/design/2026-10-22-app-mode-design.md",
    "2026-10-22-app-mode-spec.md": "docs/design/2026-10-22-app-mode-spec.md",
    "swiss-deck-controls-spec.md": "docs/design/swiss-deck-controls-spec.md",
    "2026-10-22-app-host-capabilities.md": "docs/validation/2026-10-22-app-host-capabilities.md",
    "2026-10-22-app-mode-validation.md": "docs/validation/2026-10-22-app-mode-validation.md",
    "2026-10-22-ccd-app-acceptance.md": "docs/validation/2026-10-22-ccd-app-acceptance.md",
}

# Directory entries under claudedocs/evidence/: copied recursively, byte-for-byte,
# frozen forever (no link-editing allowed, unlike the top-level files above).
EVIDENCE_DIRS: List[Tuple[str, str, str]] = [
    # (source_dir_rel_to_claudedocs, target_dir_rel_to_root, category)
    ("evidence/ccd-app-20261022", "docs/validation/evidence/ccd-app-20261022", "evidence-ccd"),
    (
        "evidence/008-workspace-layout",
        "experiments/008-workspace-layout/findings/evidence/008-workspace-layout",
        "evidence-008",
    ),
]

CLAUDEDOCS = "claudedocs"
DEFAULT_MANIFEST_REL = "experiments/008-workspace-layout/findings/layout-migration.json"
DEFAULT_BACKUP_ROOT_REL = ".agenthelm/state/backups/008-layout-migration"
MANIFEST_VERSION = 1

# Phases, in forward order. "planned" is the only phase from which `plan` may
# regenerate the manifest without --force.
PHASES = ["planned", "backed_up", "copied", "sources_removed", "applied"]


class MigrationError(Exception):
    """Raised for any precondition or integrity failure. Caller prints and exits 1."""


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _mode_octal(path: Path) -> str:
    return oct(stat.S_IMODE(path.lstat().st_mode))[2:].zfill(3)


def _is_special_or_symlink(path: Path) -> bool:
    st = path.lstat()
    if stat.S_ISLNK(st.st_mode):
        return True
    if not stat.S_ISREG(st.st_mode):
        return True
    return False


def _ensure_within(path: Path, root: Path, label: str) -> Path:
    """Resolve path and ensure it stays inside root. Raises MigrationError otherwise.

    This is the sole guard against path traversal / HOME escape: every write
    target (manifest, backups, copy targets) must resolve under the given root.
    """
    resolved_root = root.resolve()
    candidate = path if path.is_absolute() else resolved_root / path
    if '..' in candidate.parts:
        raise MigrationError("路径含 ..: {}".format(candidate))
    try:
        candidate.relative_to(resolved_root)
    except ValueError:
        raise MigrationError("{} 在 root 外: {}".format(label, candidate))
    _no_symlink_in_parents(candidate, resolved_root)
    if candidate.is_symlink():
        raise MigrationError("拒绝 symlink: {}".format(candidate))
    # Resolve without requiring existence (Path.resolve(strict=False) is fine on
    # 3.6+; default strict=False already).
    resolved = candidate.resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        raise MigrationError(
            "{} 解析后逃出 root 边界: {} (root={})".format(label, resolved, resolved_root)
        )
    return resolved


def _no_symlink_in_parents(path: Path, root: Path) -> None:
    """Reject if any existing path component between root and path's parent is a
    symlink. Does not require the leaf to exist."""
    resolved_root = root.resolve()
    rel = path.relative_to(resolved_root) if path.is_absolute() else path
    cur = resolved_root
    for part in rel.parts[:-1]:
        cur = cur / part
        if cur.exists() and cur.is_symlink():
            raise MigrationError("路径穿过 symlink 目录: {}".format(cur))


def _normalize_key(rel_posix: str) -> str:
    """Case-fold + NFC-normalize a relative path for collision detection on
    case-insensitive / normalization-insensitive filesystems (e.g. macOS)."""
    return unicodedata.normalize("NFC", rel_posix).casefold()


def _git_category(root: Path, rel_posix: str) -> str:
    """Best-effort tracked/ignored/untracked classification. Informational only;
    never gates migration safety. Returns "unknown" if git is unavailable."""
    try:
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", rel_posix],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if tracked.returncode == 0:
            return "tracked"
        ignored = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "-q", "--", rel_posix],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if ignored.returncode == 0:
            return "ignored"
        return "untracked"
    except (OSError, FileNotFoundError):
        return "unknown"


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_name(path.name + ".tmp-{}".format(uuid.uuid4().hex[:8]))
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8")
    os.replace(str(tmp), str(path))


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z") or time.strftime("%Y-%m-%dT%H:%M:%S")


# ---------------------------------------------------------------------------
# Discovery (plan-time): expand the static mapping against the real tree and
# fail loudly on anything the mapping does not already know about.
# ---------------------------------------------------------------------------


def discover_entries(root: Path) -> List[dict]:
    claudedocs = _ensure_within(root / CLAUDEDOCS, root, "source directory")
    if not claudedocs.is_dir():
        raise MigrationError("{} 不存在或不是目录".format(claudedocs))

    entries: List[dict] = []
    seen_sources = set()

    # 1) known top-level files
    top_level_children = sorted(
        p.name for p in claudedocs.iterdir() if p.name != "evidence"
    )
    unknown = [n for n in top_level_children if n not in TOP_LEVEL_FILES]
    if unknown:
        raise MigrationError(
            "claudedocs/ 下出现未登记的顶层条目，先 fail: {}".format(sorted(unknown))
        )
    missing = [n for n in TOP_LEVEL_FILES if not (claudedocs / n).exists()]
    if missing:
        raise MigrationError(
            "claudedocs/ 缺少映射要求的顶层文件: {}".format(sorted(missing))
        )
    for name, target_rel in sorted(TOP_LEVEL_FILES.items()):
        src = claudedocs / name
        if _is_special_or_symlink(src):
            raise MigrationError("拒绝 symlink/特殊文件: {}".format(src))
        source_rel = "{}/{}".format(CLAUDEDOCS, name)
        seen_sources.add(source_rel)
        entries.append(_build_entry(root, source_rel, target_rel, "top-level"))

    # 2) evidence directories, recursively, byte-for-byte, frozen
    evidence_root = claudedocs / "evidence"
    known_evidence_dirnames = {Path(src).name for src, _tgt, _cat in EVIDENCE_DIRS}
    if evidence_root.is_dir():
        actual_evidence_children = sorted(p.name for p in evidence_root.iterdir())
        unknown_evidence = [n for n in actual_evidence_children if n not in known_evidence_dirnames]
        if unknown_evidence:
            raise MigrationError(
                "claudedocs/evidence/ 下出现未登记的条目，先 fail: {}".format(sorted(unknown_evidence))
            )
    for src_dir_rel, tgt_dir_rel, category in EVIDENCE_DIRS:
        src_dir = _ensure_within(claudedocs / src_dir_rel, root, "evidence directory")
        if not src_dir.is_dir():
            raise MigrationError("映射要求的证据目录缺失: {}".format(src_dir))
        for file_path in sorted(src_dir.rglob("*")):
            _ensure_within(file_path, root, "evidence source")
            if file_path.is_dir():
                continue
            if _is_special_or_symlink(file_path):
                raise MigrationError("拒绝 symlink/特殊文件: {}".format(file_path))
            rel_within = file_path.relative_to(src_dir).as_posix()
            source_rel = "{}/{}/{}".format(CLAUDEDOCS, src_dir_rel, rel_within)
            target_rel = "{}/{}".format(tgt_dir_rel, rel_within)
            seen_sources.add(source_rel)
            entries.append(_build_entry(root, source_rel, target_rel, category))

    _check_normalization_collisions(entries)
    return entries


def _build_entry(root: Path, source_rel: str, target_rel: str, category: str) -> dict:
    src = root / source_rel
    st = src.lstat()
    return {
        "source": source_rel,
        "target": target_rel,
        "category": category,
        "frozen": CATEGORY_FROZEN[category],
        "git_status": _git_category(root, source_rel),
        "mode": _mode_octal(src),
        "size": st.st_size,
        "sha256": _sha256_file(src),
        "copied": False,
        "target_verified": False,
        "source_removed": False,
        "post_edit": None,
    }


def _check_normalization_collisions(entries: List[dict]) -> None:
    seen: Dict[str, str] = {}
    for e in entries:
        for label, rel in (("source", e["source"]), ("target", e["target"])):
            key = _normalize_key(rel)
            tagged = "{}:{}".format(label, rel)
            if key in seen and seen[key] != tagged:
                raise MigrationError(
                    "大小写/Unicode 归一化碰撞: {} 与 {}".format(seen[key], tagged)
                )
            seen[key] = tagged


# ---------------------------------------------------------------------------
# Manifest I/O
# ---------------------------------------------------------------------------


def _load_manifest(path: Path) -> dict:
    if not path.exists():
        raise MigrationError("manifest 不存在: {}".format(path))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MigrationError("manifest 不是合法 JSON: {} ({})".format(path, exc))
    if data.get("version") != MANIFEST_VERSION:
        raise MigrationError("manifest version 不受支持: {}".format(data.get("version")))
    if data.get("phase") not in PHASES:
        raise MigrationError("manifest phase 未知: {}".format(data.get("phase")))
    return data


def _mapped(source: str) -> Tuple[str, str]:
    if not isinstance(source, str):
        raise MigrationError('source 必须为字符串')
    parts = Path(source).parts
    if Path(source).is_absolute() or any(part in ('', '.', '..') for part in source.split('/')):
        raise MigrationError("非法 source: {}".format(source))
    prefix = CLAUDEDOCS + '/'
    if source.startswith(prefix):
        relative = source[len(prefix):]
        if relative in TOP_LEVEL_FILES:
            return TOP_LEVEL_FILES[relative], 'top-level'
        for old, new, category in EVIDENCE_DIRS:
            if relative.startswith(old + '/'):
                return new + relative[len(old):], category
    raise MigrationError("source 不属于静态映射: {}".format(source))


def _validate_manifest(root: Path, path: Path) -> dict:
    path = _ensure_within(path, root, 'manifest')
    if not path.is_file() or _is_special_or_symlink(path):
        raise MigrationError("manifest 不是普通文件: {}".format(path))
    data = _load_manifest(path)
    if data.get('root') != str(root.resolve()):
        raise MigrationError('manifest root 与当前 root 不一致')
    entries = data.get('entries')
    if not isinstance(entries, list) or not entries:
        raise MigrationError('manifest entries 必须为非空数组')
    seen = set()
    for entry in entries:
        try:
            source = entry['source']
            target, category = _mapped(source)
            if source in seen or entry['target'] != target or entry['category'] != category:
                raise MigrationError('manifest 重复条目或映射被修改: ' + source)
            if entry['frozen'] is not CATEGORY_FROZEN[category]:
                raise MigrationError('manifest frozen 被修改: ' + source)
            if not isinstance(entry['sha256'], str) or len(entry['sha256']) != 64 or any(
                    c not in '0123456789abcdef' for c in entry['sha256']):
                raise MigrationError('manifest 哈希非法: ' + source)
            int(entry['mode'], 8)
            seen.add(source)
            _ensure_within(root / source, root, 'source')
            _ensure_within(root / target, root, 'target')
        except (KeyError, TypeError, ValueError) as error:
            raise MigrationError('manifest 条目非法: {}'.format(error)) from error
    required = {CLAUDEDOCS + '/' + name for name in TOP_LEVEL_FILES}
    if not required.issubset(seen):
        raise MigrationError('manifest 缺少顶层映射')
    _check_normalization_collisions(entries)
    if data.get('backup_dir'):
        _ensure_within(Path(data['backup_dir']), root, 'backup directory')
    return data


def _verify(path: Path, entry: dict, root: Path, expected=None) -> None:
    _ensure_within(path, root, 'verification')
    if not path.exists() or _is_special_or_symlink(path):
        raise MigrationError('文件缺失或非普通文件: {}'.format(path))
    if _sha256_file(path) != (expected or entry['sha256']) or _mode_octal(path) != entry['mode']:
        raise MigrationError('文件 hash/mode 校验失败: {}'.format(path))


def _remaining_sources(root: Path) -> set:
    base = root / CLAUDEDOCS
    _ensure_within(base, root, 'source directory')
    found = set()
    if base.exists():
        for directory, folders, files in os.walk(base, followlinks=False):
            for name in folders + files:
                p = Path(directory) / name
                _ensure_within(p, root, 'remaining source')
                if not p.is_dir():
                    if _is_special_or_symlink(p):
                        raise MigrationError('source 非普通文件: {}'.format(p))
                    found.add(p.relative_to(root).as_posix())
    return found


def _save_manifest(path: Path, data: dict) -> None:
    data["updated_at"] = _now()
    _atomic_write_json(path, data)


def _append_step(manifest: dict, action: str, **extra) -> None:
    step = {"ts": _now(), "action": action}
    step.update(extra)
    manifest.setdefault("steps", []).append(step)


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------


def cmd_plan(root: Path, manifest_path: Path, force: bool) -> int:
    manifest_path = _ensure_within(manifest_path, root, 'manifest')
    if manifest_path.exists():
        try:
            existing = _load_manifest(manifest_path)
        except MigrationError as exc:
            raise MigrationError(
                "既有 manifest 无法解析，拒绝覆盖（可手动删除或换 --manifest）: {}".format(exc)
            )
        if existing.get("phase") != "planned" and not force:
            raise MigrationError(
                "既有 manifest 已进入 phase={}（非 planned），拒绝覆盖；"
                "需要重新规划请显式传 --force".format(existing.get("phase"))
            )

    entries = discover_entries(root)
    manifest = {
        "version": MANIFEST_VERSION,
        "phase": "planned",
        "root": str(root.resolve()),
        "run_id": uuid.uuid4().hex[:12],
        "created_at": _now(),
        "updated_at": _now(),
        "backup_dir": None,
        "entries": entries,
        "steps": [],
    }
    _append_step(manifest, "plan", entry_count=len(entries))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(manifest_path, manifest)

    by_cat: Dict[str, int] = {}
    for e in entries:
        by_cat[e["category"]] = by_cat.get(e["category"], 0) + 1
    print("plan: {} entries -> {}".format(len(entries), manifest_path))
    for cat, count in sorted(by_cat.items()):
        print("  {}: {}".format(cat, count))
    return 0


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------


def _resolve_backup_dir(root: Path, backup_arg: Optional[str], run_id: str) -> Path:
    if backup_arg:
        base = Path(backup_arg)
        candidate = base if base.is_absolute() else root / base
    else:
        candidate = root / DEFAULT_BACKUP_ROOT_REL / run_id
    return _ensure_within(candidate, root, "backup_dir")


def _rmdir_empty_ancestors(root: Path, entries: List[dict]) -> None:
    claudedocs_root = (root / CLAUDEDOCS).resolve()
    dirs = set()
    for e in entries:
        p = (root / e["source"]).parent.resolve()
        while True:
            try:
                p.relative_to(claudedocs_root)
            except ValueError:
                break
            dirs.add(p)
            if p == claudedocs_root:
                break
            p = p.parent
    for d in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        try:
            d.rmdir()
        except OSError:
            pass  # not empty (or already gone) -- never rmtree


def cmd_apply(root: Path, manifest_path: Path, backup_arg: Optional[str]) -> int:
    manifest = _validate_manifest(root, manifest_path)
    phase = manifest['phase']
    entries = manifest['entries']
    remaining = _remaining_sources(root)
    expected_sources = {e['source'] for e in entries if not e['source_removed']}
    # A recorded removal may have completed just before its checkpoint was saved.
    for e in entries:
        if e.get('removing') and e['source'] not in remaining:
            if not manifest.get('backup_dir'):
                raise MigrationError('缺少恢复备份')
            _verify(root / e['target'], e, root)
            _verify(Path(manifest['backup_dir']) / e['source'], e, root)
            e['source_removed'] = True
            expected_sources.discard(e['source'])
    if remaining != expected_sources:
        raise MigrationError('source 集合与计划不一致: extra={} missing={}'.format(
            sorted(remaining - expected_sources), sorted(expected_sources - remaining)))
    if phase == 'applied':
        return cmd_check(root, manifest_path, False)

    # Verify every existing source and every previously created target before mutation.
    for e in entries:
        src, tgt = root / e['source'], root / e['target']
        if not e['source_removed']:
            _verify(src, e, root)
        if e['copied']:
            _verify(tgt, e, root)
        elif tgt.exists() or tgt.is_symlink():
            # Recovery only recognizes the exact file identity created by this run.
            identity = e.get('target_identity')
            st = tgt.lstat()
            if not identity or identity != [st.st_dev, st.st_ino]:
                raise MigrationError('target 已存在，冲突: ' + e['target'])
            try:
                _verify(tgt, e, root)
            except MigrationError:
                # A partial file from this run is disposable only while the source is intact.
                _verify(src, e, root)
                tgt.unlink()
                e.pop('target_identity', None)
            else:
                e['copied'], e['target_verified'] = True, True
        _ensure_within(tgt, root, 'target')

    # ---- Backup (fresh, once) ----
    backup_dir_str = manifest.get("backup_dir")
    if backup_dir_str is None:
        backup_dir = _resolve_backup_dir(root, backup_arg, manifest["run_id"])
        backup_dir.mkdir(parents=True, exist_ok=False)
        for e in entries:
            src = root / e["source"]
            dst = backup_dir / e["source"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            if _sha256_file(dst) != e["sha256"]:
                raise MigrationError("备份校验失败: {}".format(e["source"]))
        manifest["backup_dir"] = str(backup_dir)
        manifest["phase"] = "backed_up"
        _append_step(manifest, "apply:backup", backup_dir=str(backup_dir))
        _save_manifest(manifest_path, manifest)
        phase = "backed_up"
    else:
        backup_dir = Path(backup_dir_str)

    # ---- Copy phase ----
    if phase == "backed_up":
        copied_this_run: List[dict] = []
        for e in entries:
            if e["copied"]:
                continue
            src = root / e["source"]
            tgt = root / e["target"]
            try:
                tgt.parent.mkdir(parents=True, exist_ok=True)
                _ensure_within(tgt, root, 'copy target')
                with tgt.open('xb') as destination:
                    st = os.fstat(destination.fileno())
                    e['target_identity'] = [st.st_dev, st.st_ino]
                    _save_manifest(manifest_path, manifest)
                    with src.open('rb') as source:
                        shutil.copyfileobj(source, destination)
                    destination.flush()
                    os.fsync(destination.fileno())
                shutil.copystat(src, tgt)
                _verify(tgt, e, root)
                _verify(src, e, root)
            except Exception:
                if tgt.exists() and e.get('target_identity') == [tgt.lstat().st_dev, tgt.lstat().st_ino]:
                    tgt.unlink()
                    e.pop('target_identity', None)
                for done in copied_this_run:
                    done_tgt = root / done['target']
                    if done_tgt.exists() and done.get('target_identity') == [
                            done_tgt.lstat().st_dev, done_tgt.lstat().st_ino]:
                        done_tgt.unlink()
                    done.pop('target_identity', None)
                    done['copied'] = False
                    done['target_verified'] = False
                _append_step(
                    manifest, "apply:copy-failed", rolled_back=len(copied_this_run), failed_entry=e["target"]
                )
                _save_manifest(manifest_path, manifest)
                raise
            e["copied"] = True
            e["target_verified"] = True
            copied_this_run.append(e)
            _save_manifest(manifest_path, manifest)
        manifest["phase"] = "copied"
        _append_step(manifest, "apply:copy", count=len(copied_this_run))
        _save_manifest(manifest_path, manifest)
        phase = "copied"

    # ---- Remove verified sources, one at a time ----
    if phase == "copied":
        for e in entries:
            if not e['source_removed']:
                _verify(root / e['source'], e, root)
            _verify(root / e['target'], e, root)
            _verify(backup_dir / e['source'], e, root)
        for e in entries:
            if e["source_removed"]:
                continue
            src = root / e["source"]
            e['removing'] = True
            _save_manifest(manifest_path, manifest)
            _verify(src, e, root)
            _verify(root / e['target'], e, root)
            src.unlink()
            e["source_removed"] = True
            _save_manifest(manifest_path, manifest)
        _rmdir_empty_ancestors(root, entries)
        manifest["phase"] = "sources_removed"
        _append_step(manifest, "apply:remove-sources", count=len(entries))
        _save_manifest(manifest_path, manifest)
        phase = "sources_removed"

    if phase == "sources_removed":
        manifest["phase"] = "applied"
        _append_step(manifest, "apply:done")
        _save_manifest(manifest_path, manifest)
        phase = "applied"

    print("apply: phase={}".format(phase))
    return 0


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------


def cmd_check(root: Path, manifest_path: Path, accept_link_edits: bool) -> int:
    manifest = _validate_manifest(root, manifest_path)
    entries = manifest["entries"]
    problems: List[str] = []
    accepted: List[str] = []
    now = _now()
    backup_dir = manifest.get("backup_dir")
    remaining = _remaining_sources(root)
    expected = {e['source'] for e in entries if not e['source_removed']}
    if remaining != expected:
        problems.append('source 集合与记录不一致')

    for e in entries:
        src = root / e["source"]
        tgt = root / e["target"]
        effective_expected = e["sha256"]
        post = e.get("post_edit")
        if post:
            effective_expected = post["sha256"]

        if e["source_removed"] or e["copied"]:
            cur_path, cur_label = tgt, "target"
            if e["copied"] and not e["source_removed"] and src.exists():
                if _sha256_file(src) != e["sha256"]:
                    problems.append("{}: apply 未完成期间 source 被改动".format(e["source"]))
        else:
            cur_path, cur_label = src, "source"

        if not cur_path.exists():
            problems.append("{}: {} 缺失，文件丢失".format(e["source"], cur_label))
            continue
        if _is_special_or_symlink(cur_path):
            problems.append("{}: {} 变成 symlink/特殊文件".format(e["source"], cur_label))
            continue

        cur_hash = _sha256_file(cur_path)
        if _mode_octal(cur_path) != e['mode']:
            problems.append('{}: 文件 mode 已变化'.format(e['source']))
        if cur_hash == effective_expected:
            pass
        elif e["frozen"]:
            problems.append(
                "{}: frozen 条目哈希变动，禁止接受（原={} 现={}）".format(
                    e["source"], effective_expected, cur_hash
                )
            )
        elif accept_link_edits:
            e["post_edit"] = {"pre_sha256": effective_expected, "sha256": cur_hash, "recorded_at": now}
            accepted.append(e["source"])
        else:
            problems.append(
                "{}: 顶层条目哈希变动，未用 --accept-link-edits 确认（原={} 现={}）".format(
                    e["source"], effective_expected, cur_hash
                )
            )

        if backup_dir:
            backup_path = _ensure_within(Path(backup_dir) / e['source'], root, 'backup file')
            try:
                _verify(backup_path, e, root)
            except MigrationError as error:
                problems.append('{}: 备份校验失败 ({})'.format(e['source'], error))

    if problems:
        print("check: FAIL ({} problems)".format(len(problems)))
        for p in problems:
            print("  - {}".format(p))
        return 1
    if accepted:
        _append_step(manifest, 'check:accept-link-edits', entries=accepted)
        _save_manifest(manifest_path, manifest)
    print(
        "check: OK ({} entries, phase={}, accepted_links={})".format(
            len(entries), manifest["phase"], len(accepted)
        )
    )
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _default_root() -> Path:
    return Path(__file__).resolve().parents[3]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=None, help="workspace root (default: derived from script location)")
    p.add_argument("--manifest", default=None, help="manifest path (default: {})".format(DEFAULT_MANIFEST_REL))
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("plan", help="discover the static mapping and write a fresh manifest")
    sp.add_argument("--force", action="store_true", help="overwrite a manifest even if phase != planned")

    sa = sub.add_parser("apply", help="execute backup -> copy -> verify -> remove-sources from a planned manifest")
    sa.add_argument("--backup", default=None, help="backup directory (relative to root, or absolute within root)")

    sc = sub.add_parser("check", help="verify current state against the manifest")
    sc.add_argument(
        "--accept-link-edits",
        action="store_true",
        help="record a new hash for a non-frozen top-level entry whose content changed (e.g. link edits)",
    )

    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve() if args.root else _default_root()
    manifest_path = (
        Path(args.manifest) if args.manifest else root / DEFAULT_MANIFEST_REL
    )
    if not manifest_path.is_absolute():
        manifest_path = root / manifest_path

    try:
        if args.cmd == "plan":
            return cmd_plan(root, manifest_path, args.force)
        if args.cmd == "apply":
            return cmd_apply(root, manifest_path, args.backup)
        if args.cmd == "check":
            return cmd_check(root, manifest_path, args.accept_link_edits)
        raise MigrationError("未知命令: {}".format(args.cmd))
    except MigrationError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
