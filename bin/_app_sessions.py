"""Workspace-local App bindings and serialized, atomic state transactions."""
from contextlib import contextmanager
from copy import deepcopy
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
        if (str(path) != task or path.parent != ROOT / 'experiments' or not isinstance(binding, dict)
                or binding.get('entry') not in ENTRIES or type(binding.get('active')) is not bool
                or any(type(binding[field]) is not int or binding[field] < 0 for field in
                       ('observation_counter', 'observation_floor') if field in binding)
                or ('history' in binding and not isinstance(binding['history'], list))):
            raise ValueError('damaged App state: invalid task binding')
        if 'session' in binding and (not isinstance(binding['session'], str)
                or binding['session'] not in state['sessions']
                or state['sessions'][binding['session']]['entry'] != binding['entry']):
            raise ValueError('damaged App state: unbound task session')
    for identifier, request in state['requests'].items():
        if (not isinstance(request, dict) or request.get('id') != identifier
                or request.get('operation') not in ('create', 'executor', 'read', 'wait', 'followup')
                or request.get('status') not in ('pending', 'queued', 'unknown', 'succeeded', 'failed')
                or request.get('workspace') != str(ROOT) or request.get('entry') not in ENTRIES
                or type(request.get('owner_epoch')) is not int or request['owner_epoch'] < 1
                or not isinstance(request.get('task'), str)
                or guarded_path(request['task']).parent != ROOT / 'experiments'):
            raise ValueError('damaged App state: invalid host request')
    dispatcher = state.get('dispatcher')
    if dispatcher is not None:
        if (not isinstance(dispatcher, dict) or not isinstance(dispatcher.get('session'), str)
                or dispatcher['session'] not in state['sessions'] or state['owner_epoch'] < 1
                or dispatcher.get('entry') != state['sessions'][dispatcher['session']]['entry']):
            raise ValueError('damaged App state: invalid Dispatcher binding')
    handoff = state.get('handoff')
    if handoff is not None:
        if (not isinstance(handoff, dict) or dispatcher is not None
                or handoff.get('entry') not in ENTRIES
                or type(handoff.get('owner_epoch')) is not int
                or handoff.get('owner_epoch') != state['owner_epoch']
                or not isinstance(handoff.get('from'), str) or not isinstance(handoff.get('to'), str)):
            raise ValueError('damaged App state: invalid handoff')
        session_id(handoff['from'])
        session_id(handoff['to'])
    if 'handoff_history' in state and not isinstance(state['handoff_history'], list):
        raise ValueError('damaged App state: invalid handoff history')
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


def pending_writes(state, task=None):
    return [request for request in state['requests'].values()
            if request['operation'] in ('create', 'executor', 'followup')
            and request['status'] not in ('succeeded', 'failed')
            and (task is None or request['task'] == str(task))]


def register(state, identifier, entry):
    session_id(identifier)
    if entry not in ENTRIES:
        raise ValueError('unsupported App entry')
    if state.get('handoff'):
        raise ValueError('pending handoff must be claimed by its designated session')
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


def task_status(task):
    path = guarded_path(task_path(task) / 'STATUS')
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return {'state': 'unknown', 'source': str(path), 'raw': None}
    with os.fdopen(descriptor) as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('task STATUS must be a regular file')
        raw = stream.read()
    return {'state': raw.split('|', 1)[0].strip(), 'source': str(path), 'raw': raw}


def show(state, identifier):
    require_dispatcher(state, identifier)
    output = deepcopy(state)
    for task, binding in output['tasks'].items():
        binding['task_status'] = task_status(task)
    return output


def release(state, identifier, target):
    owner = require_dispatcher(state, identifier)
    session_id(target)
    if target == identifier:
        raise ValueError('handoff target must be another session')
    if pending_writes(state):
        raise ValueError('handoff blocked by unresolved write request')
    if target in state['sessions'] and state['sessions'][target]['entry'] != owner['entry']:
        raise ValueError('cross-App handoff is not supported')
    state['owner_epoch'] += 1
    state['handoff'] = {'from': identifier, 'to': target, 'entry': owner['entry'],
                        'owner_epoch': state['owner_epoch']}
    state['dispatcher'] = None
    return state


def claim(state, identifier, entry):
    session_id(identifier)
    handoff = state.get('handoff')
    if (not handoff or state['dispatcher'] is not None or handoff['to'] != identifier
            or handoff['entry'] != entry):
        raise ValueError('claim requires an explicit same-App handoff to this session')
    binding = state['sessions'].get(identifier)
    if binding is not None and binding['entry'] != entry:
        raise ValueError('cross-App handoff is not supported')
    state['sessions'].setdefault(identifier, {'entry': entry, 'capabilities': {}})
    state['dispatcher'] = {'session': identifier, 'entry': entry}
    state.setdefault('handoff_history', []).append(handoff)
    del state['handoff']
    return state


def finish(state, identifier, task):
    require_dispatcher(state, identifier)
    task = task_path(task)
    binding = state['tasks'].get(str(task), {})
    if not binding.get('session'):
        raise ValueError('finish requires a bound Lead')
    if pending_writes(state, task):
        raise ValueError('finish blocked by unresolved write request')
    observed = task_status(task)
    if observed['state'] != 'done':
        raise ValueError('finish requires local task STATUS=done; session state is insufficient')
    if binding['active']:
        binding['active'] = False
        binding.setdefault('history', []).append({'event': 'finished', 'task_status': observed})
    return binding


def resume(state, identifier, task, reason):
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('resume requires a nonempty user authorization reason')
    if not state['dispatcher']:
        raise ValueError('resume requires an active Dispatcher')
    task = task_path(task)
    binding = state['tasks'].get(str(task), {})
    lead = state['sessions'].get(binding.get('session'), {})
    if (binding.get('state') != 'running' or lead.get('role') != 'lead'
            or lead.get('task') != str(task)):
        raise ValueError('resume requires an existing bound Lead')
    if identifier != state['dispatcher']['session'] and identifier != binding['session']:
        raise ValueError('resume requires the current Dispatcher or this task bound Lead')
    if state['dispatcher']['entry'] != binding['entry']:
        raise ValueError('cross-App resume is not supported')
    if binding['active']:
        return binding
    if pending_writes(state, task):
        raise ValueError('resume blocked by unresolved write request')
    try:
        maximum = int(os.environ.get('RESEARCH_MAX_LEADS', '10'))
    except ValueError as error:
        raise ValueError('RESEARCH_MAX_LEADS must be a positive integer') from error
    if maximum < 1:
        raise ValueError('RESEARCH_MAX_LEADS must be a positive integer')
    if sum(item.get('active', False) for item in state['tasks'].values()) >= maximum:
        raise ValueError('Lead concurrency limit reached')
    binding['active'] = True
    binding['observation_floor'] = binding.get('observation_counter', 0)
    for target in (binding, lead):
        if target.get('observation'):
            target['observation']['invalidated'] = True
    binding.setdefault('history', []).append({
        'event': 'resumed', 'session': identifier, 'owner_epoch': state['owner_epoch'],
        'reason': reason.strip()})
    return binding
