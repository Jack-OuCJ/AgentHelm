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


def restored_session(session=None, entry=None, task=None):
    """Read App role ownership for restoration; never register a new session."""
    from _app_sessions import load_state, session_id, task_path
    state = load_state()
    if entry is not None and entry not in ('app.codex', 'app.ccd', 'cli.claude', 'cli.codex'):
        raise ValueError('unknown runtime entry')
    if session is not None:
        session_id(session)
    binding = state['sessions'].get(session)
    if binding:
        if entry is not None and entry != binding['entry']:
            raise ValueError('entry conflicts with bound session')
        if state['dispatcher'] and state['dispatcher']['session'] == session:
            if task is not None:
                raise ValueError('Dispatcher session cannot restore a Lead task')
            role, bound_task = 'dispatcher', None
        elif binding.get('role') in ('lead', 'executor'):
            role = binding['role']
            bound_task = task_path(binding['task'])
            if task is not None and task != bound_task:
                raise ValueError('session belongs to a different task')
        else:
            role, bound_task = '只读观察者（无 Dispatcher 权限）', None
            if task is not None:
                raise ValueError('session is not the bound Lead or Executor')
        return {'entry': binding['entry'], 'session': session, 'role': role, 'task': bound_task}
    environment, _ = runtime_environment(entry)
    if (environment == 'app' or (task is not None and str(task) in state['tasks'])):
        raise ValueError('unregistered App session: verify native identity and bind it explicitly')
    if task is None and (state['dispatcher'] or state.get('handoff')):
        return {'entry': entry, 'session': None,
                'role': '只读观察者（未绑定，无 Dispatcher 权限）', 'task': None}
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
    if entry is None and session is not None:
        entry = runtime_entry(session=session)
    environment, instructions = runtime_environment(entry)
    return (f'工作区根目录：{ROOT}\n当前角色：{role}\n'
            f'开始前读取 {ROOT / "AGENTS.md"} 和 '
            f'{ROOT / "skills/agenthelm-workflow/SKILL.md"}，按角色加载对应规则。\n'
            + f'运行入口：{entry or ("app（未绑定）" if environment == "app" else environment)}\n'
            + f'会话标识：{session or "待宿主确认"}\n'
            + (f'任务目录：{task}\n' if task else '')
            + f'当前运行环境：{environment}；环境说明来源：{instructions}\n'
            + instructions.read_text().strip() + '\n'
            + (f'App 宿主操作前读取 {ROOT / "skills/agenthelm-workflow/references/app-host.md"}。\n'
               if environment == 'app' else '')
            + '沿用用户既有全局规则和权限；只操作当前任务明确授权的文件。\n'
            + '不得修改用户 HOME 中的规则、skills、插件、配置或凭据；不得绕过权限审批。\n'
            + (memory_context(task if role == 'lead' else None) if role in ('dispatcher', 'lead') else ''))


def memory_context(task):
    """Memory catalog for a Dispatcher or Lead; failures stay diagnostics, never startup errors."""
    try:
        from _memory import context  # imported at call time: _memory imports this module
        return context(task)
    except Exception as error:  # identity and STATUS restoration must not depend on memory health
        return f'## 记忆索引\n诊断：记忆目录不可用（{type(error).__name__}: {error}）；身份与 STATUS 恢复继续。\n'
