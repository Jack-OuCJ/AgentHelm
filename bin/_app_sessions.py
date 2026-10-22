"""Workspace-local App bindings and serialized, atomic state transactions."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import stat
import tempfile

from _workspace import ROOT

STATE_DIRECTORY = ROOT / '.agenthelm/state'
STATE_FILE = STATE_DIRECTORY / 'app-sessions.json'
ENTRIES = ('app.codex', 'app.ccd')
REQUIRED_CAPABILITIES = ('create', 'read', 'wait', 'followup', 'model', 'effort',
                         'verify_model', 'native_executor')


def guarded_path(path):
    path = Path(os.path.abspath(path))
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        raise ValueError(f'path outside workspace: {path}')
    current = ROOT
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            raise ValueError(f'symbolic link is not allowed: {current}')
    return path


def task_path(path):
    path = guarded_path(Path(path).expanduser())
    if path.parent != ROOT / 'experiments' or not path.is_dir():
        raise ValueError('task must be an existing experiments/<task> directory')
    return path


def session_id(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 256 or any(
            ord(character) < 32 for character in value):
        raise ValueError('session must be a nonempty identifier without control characters')
    return value


def initial_state():
    return {'version': 1, 'workspace': str(ROOT), 'owner_epoch': 0, 'dispatcher': None,
            'sessions': {}, 'tasks': {}, 'requests': {}}


def validate_capabilities(capabilities):
    if not isinstance(capabilities, dict):
        raise ValueError('capabilities must be a map')
    for name, capability in capabilities.items():
        if (name not in REQUIRED_CAPABILITIES or not isinstance(capability, dict)
                or type(capability.get('available')) is not bool
                or not isinstance(capability.get('source'), str) or not capability['source'].strip()
                or ('verified' in capability and type(capability['verified']) is not bool)):
            raise ValueError(f'capability {name} requires available boolean and individual source')


def validate_state(state):
    if (not isinstance(state, dict) or state.get('version') != 1
            or type(state.get('version')) is not int or 'dispatcher' not in state
            or state.get('workspace') != str(ROOT)
            or type(state.get('owner_epoch')) is not int or state['owner_epoch'] < 0
            or any(not isinstance(state.get(key), dict) for key in ('sessions', 'tasks', 'requests'))):
        raise ValueError('damaged App state: invalid schema or workspace')
    for identifier, binding in state['sessions'].items():
        session_id(identifier)
        if (not isinstance(binding, dict) or binding.get('entry') not in ENTRIES
                or not isinstance(binding.get('capabilities'), dict)):
            raise ValueError('damaged App state: invalid session binding')
        try:
            validate_capabilities(binding['capabilities'])
        except ValueError as error:
            raise ValueError(f'damaged App state: {error}') from error
    for task, binding in state['tasks'].items():
        path = guarded_path(task)
        if path.parent != ROOT / 'experiments' or not isinstance(binding, dict):
            raise ValueError('damaged App state: invalid task binding')
    dispatcher = state.get('dispatcher')
    if dispatcher is not None:
        if (not isinstance(dispatcher, dict) or not isinstance(dispatcher.get('session'), str)
                or dispatcher['session'] not in state['sessions'] or state['owner_epoch'] < 1
                or dispatcher.get('entry') != state['sessions'][dispatcher['session']]['entry']):
            raise ValueError('damaged App state: invalid Dispatcher binding')
    return state


def load_state():
    path = guarded_path(STATE_FILE)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return initial_state()
    with os.fdopen(descriptor) as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('damaged App state: expected regular file')
        try:
            return validate_state(json.load(stream))
        except (json.JSONDecodeError, UnicodeError) as error:
            raise ValueError(f'damaged App state: {error}') from error


def save_state(state):
    validate_state(state)
    guarded_path(STATE_FILE)
    descriptor, temporary = tempfile.mkstemp(prefix='.app-sessions-', dir=STATE_DIRECTORY)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        guarded_path(STATE_FILE)
        os.replace(temporary, STATE_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def transaction(readonly=False):
    directory = guarded_path(STATE_DIRECTORY)
    directory.mkdir(parents=True, exist_ok=True)
    lock = guarded_path(directory / 'app-sessions.lock')
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(descriptor, 'r+') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('App state lock must be a regular file')
        fcntl.flock(stream, fcntl.LOCK_EX)
        state = load_state()
        yield state
        if not readonly:
            save_state(state)


def require_dispatcher(state, identifier):
    if not state['dispatcher'] or state['dispatcher']['session'] != identifier:
        raise ValueError('session is not the active Dispatcher')
    return state['sessions'][identifier]


def register(state, identifier, entry):
    session_id(identifier)
    if entry not in ENTRIES:
        raise ValueError('unsupported App entry')
    if state['dispatcher'] is not None and state['dispatcher'] != {'session': identifier, 'entry': entry}:
        raise ValueError('Dispatcher conflict: explicit handoff is required')
    binding = state['sessions'].get(identifier)
    if binding and binding['entry'] != entry:
        raise ValueError('session entry cannot change')
    if state['dispatcher'] is None:
        state['owner_epoch'] += 1
        state['dispatcher'] = {'session': identifier, 'entry': entry}
    state['sessions'].setdefault(identifier, {'entry': entry, 'capabilities': {}})
    return state


def record_capabilities(state, identifier, payload):
    binding = require_dispatcher(state, identifier)
    if not isinstance(payload, dict) or payload.get('entry') != binding['entry']:
        raise ValueError('capabilities must name the bound App entry')
    source = payload.get('source')
    capabilities = payload.get('capabilities')
    if not isinstance(source, str) or not source.strip() or not isinstance(capabilities, dict):
        raise ValueError('capabilities require a source and capability map')
    validate_capabilities(capabilities)
    binding['capabilities'] = capabilities
    binding['capability_source'] = source
    return binding
