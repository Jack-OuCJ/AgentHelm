"""Download, select and register domain skills without writing user configuration."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from _workspace import ROOT, STATE, owned, write

DEFAULT_SOURCE = 'https://github.com/K-Dense-AI/scientific-agent-skills.git'


def hashes(directory):
    result = {}
    for path in sorted(directory.rglob('*')):
        if path.is_symlink():
            raise ValueError('symlinks are not supported in skill content: ' + str(path))
        if path.is_file():
            result[str(path.relative_to(directory))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def metadata(path):
    content = path.read_text()
    header = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', content, re.S)
    if not header:
        raise ValueError('missing frontmatter: ' + str(path))
    front = header[1]
    fields = {}
    for key in ('name', 'description'):
        match = re.search(r'(?m)^' + key + r':[ \t]*([^\n]*)(?:\n((?:[ \t]+[^\n]*\n?)*))', front)
        if not match:
            raise ValueError('missing ' + key + ': ' + str(path))
        value = match[1].strip()
        if value in ('>', '|', '>-', '|-'):
            value = ' '.join((match[2] or '').split())
        else:
            value = value.strip('\"\'')
        if not value:
            raise ValueError('empty ' + key + ': ' + str(path))
        fields[key] = value
    if fields['name'] != path.parent.name or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', fields['name']) or len(fields['name']) > 64:
        raise ValueError('skill name must match its directory in kebab-case: ' + str(path))
    return fields['description'].replace('|', '\\|').replace('\n', ' ')


def git(*args):
    result = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false', *args],
                            check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            stdin=subprocess.DEVNULL, timeout=120)
    return result.stdout.strip()


def install(args):
    STATE.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='skills-download-', dir=STATE) as temporary:
        revision = None
        if args.source:
            source = Path(args.source).expanduser().resolve()
            if not source.is_dir():
                raise ValueError('source directory does not exist: ' + str(source))
            origin = str(source)
        else:
            source = Path(temporary) / 'source'
            origin = DEFAULT_SOURCE
            try:
                git('clone', '--depth', '1', '--', origin, str(source))
                if args.ref:
                    git('-C', str(source), 'fetch', '--depth', '1', 'origin', args.ref)
                    git('-C', str(source), 'checkout', '--detach', 'FETCH_HEAD')
                revision = git('-C', str(source), 'rev-parse', 'HEAD')
            except (subprocess.SubprocessError, OSError) as error:
                raise ValueError('download failed; no skills installed: ' + str(error)) from error
        skills = {}
        descriptions = {}
        for path in sorted(source.rglob('SKILL.md')):
            if '.git' in path.relative_to(source).parts:
                continue
            parts = path.relative_to(source).parts
            if any(source.joinpath(*parts[:i]).is_symlink() for i in range(1, len(parts) + 1)):
                raise ValueError('symlinked skill source: ' + str(path))
            name = path.parent.name
            if name in skills:
                raise ValueError('duplicate skill directory: ' + name)
            descriptions[name] = metadata(path)
            skills[name] = path.parent
        if not skills:
            raise ValueError('source contains no skills')
        print('来源：' + origin + ((' @ ' + revision) if revision else ''))
        if args.list or not (args.skill or args.all):
            for name in skills:
                print(name + ' | ' + descriptions[name])
            print('未安装。使用 --skill <名称>（可重复），或明确使用 --all。')
            return
        selected = sorted(skills if args.all else set(args.skill))
        unknown = set(selected) - skills.keys()
        if unknown:
            raise ValueError('unknown skills: ' + ', '.join(sorted(unknown)))
        library = owned(ROOT / 'skills-library')
        manifest = owned(STATE / 'skills-library.json')
        previous = json.loads(manifest.read_text()) if manifest.exists() else {'skills': {}}
        records = previous['skills']
        folders = {'claude': ('.claude/skills',), 'codex': ('.agents/skills',),
                   'both': ('.agents/skills', '.claude/skills'), 'none': ()}[args.agent]
        licenses = sorted(p for p in source.glob('LICENSE*') if p.is_file())
        if not licenses:
            raise ValueError('source must include a root LICENSE file')
        # Preflight the complete selection and every write before installing anything.
        plans = []
        for name in selected:
            destination = owned(library / name)
            expected = hashes(skills[name])
            if destination.is_symlink():
                raise ValueError('existing skill directory is a symlink: ' + str(destination))
            if destination.exists():
                if name not in records or hashes(destination) != records[name]['hashes']:
                    raise ValueError('preserve existing or locally modified skill: ' + str(destination))
            links = []
            for folder in folders:
                link = owned(ROOT / folder / name)
                if (link.exists() or link.is_symlink()) and not (link.is_symlink() and link.resolve() == destination):
                    raise ValueError('preserve existing skill entry: ' + str(link))
                links.append(link)
            plans.append((name, destination, expected, links))
        for license_path in licenses:
            target = owned(library / license_path.name)
            if license_path.is_symlink() or (target.exists() and target.read_bytes() != license_path.read_bytes()):
                raise ValueError('license conflict: ' + str(target))
        catalog = owned(library / 'CATALOG.md')
        if catalog.exists() and not catalog.is_file():
            raise ValueError('catalog is not a file: ' + str(catalog))
        for name, destination, expected, links in plans:
            action = '保留' if destination.exists() and hashes(destination) == expected else '安装/更新'
            print(action + '：' + name)
            for link in links:
                print('  注册：' + str(link.relative_to(ROOT)))
        if args.dry_run:
            print('预览完成，未安装。')
            return
        for name, destination, expected, links in plans:
            if not destination.exists() or hashes(destination) != expected:
                staged = Path(temporary) / 'staged' / name
                staged.parent.mkdir(exist_ok=True)
                shutil.copytree(skills[name], staged)
                if hashes(staged) != expected:
                    raise ValueError('source changed during copy: ' + name)
                destination.parent.mkdir(parents=True, exist_ok=True)
                backup = Path(temporary) / 'previous' / name
                backup.parent.mkdir(exist_ok=True)
                if destination.exists():
                    destination.rename(backup)
                try:
                    staged.rename(destination)
                except OSError:
                    if backup.exists():
                        backup.rename(destination)
                    raise
            for link in links:
                link.parent.mkdir(parents=True, exist_ok=True)
                if not link.is_symlink():
                    link.symlink_to(os.path.relpath(destination, link.parent), target_is_directory=True)
            records[name] = {'source': origin, 'revision': revision, 'hashes': expected,
                             'description': descriptions[name]}
        for license_path in licenses:
            shutil.copy2(license_path, library / license_path.name)
        rows = ['# 已安装领域技能', '', 'Skill | Description', '--- | ---']
        rows.extend(name + ' | ' + record['description'] for name, record in sorted(records.items()))
        write(catalog, '\n'.join(rows) + '\n')
        write(manifest, json.dumps({'skills': records}, ensure_ascii=False, indent=2) + '\n')
        print(f'已安装/注册 {len(selected)} 个技能；仅当前工作区。依赖未安装，未启动 agent。')
