"""Paths and guarded writes for this checkout; never manage user configuration."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent


def owned(path):
    path = Path(path).absolute()
    try:
        path.relative_to(ROOT)
        path.resolve().relative_to(ROOT)
    except ValueError:
        raise SystemExit(f'workspace: refusing path outside {ROOT}: {path}')
    return path


CONFIG = owned(ROOT / '.agenthelm/config')
STATE = owned(ROOT / '.agenthelm/state')


def write(path, content):
    path = owned(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text() != content:
        path.write_text(content)


def register_skill(name):
    target = owned(ROOT / 'skills' / name)
    for directory in ('.agents/skills', '.claude/skills'):
        link = owned(ROOT / directory / name)
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink() and link.resolve() == target:
            continue
        if link.exists() or link.is_symlink():
            raise SystemExit(f'workspace: existing skill entry requires manual resolution: {link}')
        link.symlink_to(os.path.relpath(target, link.parent), target_is_directory=True)


def task_directory(path):
    path = owned(Path(path).expanduser().resolve())
    if path.parent != ROOT / 'experiments' or not path.is_dir():
        raise SystemExit('workspace: task must be an existing experiments/<task> directory')
    return path


def runtime_entry(entry=None, session=None, task=None):
    """Explicit session bindings take precedence over workspace CLI defaults."""
    from _app_sessions import ENTRIES, load_state, session_id
    state = load_state()
    if session is not None:
        session_id(session)
        binding = state['sessions'].get(session)
        if binding is None:
            raise ValueError('unknown session binding; register the App Dispatcher explicitly')
        if entry is not None and entry != binding['entry']:
            raise ValueError('entry conflicts with bound session')
        return binding['entry']
    if task is not None and str(task) in state['tasks']:
        raise ValueError('App task requires an explicitly bound --session')
    if entry is not None:
        if entry not in (*ENTRIES, 'cli.claude', 'cli.codex'):
            raise ValueError('unknown runtime entry')
        if entry in ENTRIES:
            raise ValueError('App entry requires an explicitly bound --session')
        return entry
    environment, _ = runtime_environment()
    if environment == 'app':
        raise ValueError('App environment requires an explicitly bound --session')
    return None


def runtime_environment(entry=None, session=None):
    if session is not None:
        entry = runtime_entry(entry, session)
    path = CONFIG / 'env'
    environment = ('app' if entry and entry.startswith('app.') else
                   path.read_text().strip() if path.exists() else 'cli-plain')
    if entry and entry.startswith('cli.') and environment == 'app':
        environment = 'cli-plain'
    if environment not in ('cli-herdr', 'cli-plain', 'app'):
        raise SystemExit(f'workspace: unknown environment in {path}: {environment}')
    instructions = ROOT / 'rules' / f'env-{environment}.md'
    if not instructions.is_file():
        raise SystemExit(f'workspace: missing environment instructions: {instructions}; '
                         f'run {ROOT / "bin/install-rules"}')
    return environment, instructions


def bootstrap(role, task=None, entry=None, session=None):
    environment, instructions = runtime_environment(entry, session)
    return (f'工作区根目录：{ROOT}\n当前角色：{role}\n'
            f'开始前读取 {ROOT / "AGENTS.md"} 和 '
            f'{ROOT / "skills/agenthelm-workflow/SKILL.md"}，按角色加载对应规则。\n'
            + (f'任务目录：{task}\n' if task else '')
            + f'当前运行环境：{environment}；环境说明来源：{instructions}\n'
            + instructions.read_text().strip() + '\n'
            + '沿用用户既有全局规则和权限；只操作当前任务明确授权的文件。\n'
            + '不得修改用户 HOME 中的规则、skills、插件、配置或凭据；不得绕过权限审批。\n')
