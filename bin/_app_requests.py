"""Prepare native host operations; accept evidence before binding running sessions."""
from uuid import uuid4

from _app_sessions import require_dispatcher, session_id, task_path, guarded_path
from _models import resolve_app
from _toml import loads
from _workspace import CONFIG, ROOT, bootstrap


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} requires nonempty evidence')
    return value


def require_capabilities(binding, operation):
    required = ('create', 'read', 'wait', 'followup', 'model', 'effort', 'verify_model')
    if operation == 'executor':
        required = ('native_executor', 'model', 'effort', 'verify_model')
    capabilities = binding['capabilities']
    for name in required:
        capability = capabilities.get(name, {})
        if not capability.get('available'):
            raise ValueError(f'App capability unavailable: {name}; no CLI fallback')
    fields = capabilities['verify_model'].get('fields', [])
    if not isinstance(fields, list) or not {'model', 'effort'}.issubset(fields):
        raise ValueError('verify_model must read back model and effort')
    return capabilities


def model_parameters(owner, operation, role, payload):
    if not isinstance(payload, dict):
        raise ValueError('operation parameters must be a map')
    capabilities = require_capabilities(owner, operation)
    entry = owner['entry']
    model = resolve_app(loads((CONFIG / 'roles.toml').read_text()), role, entry)
    effective = {field: model[field] for field in ('model', 'effort')}
    defaults = payload.get('defaults', {})
    if any(value is None for value in effective.values()):
        if not isinstance(defaults, dict):
            raise ValueError('App defaults must include model, effort, source and evidence')
        text(defaults.get('source'), 'App default source')
        text(defaults.get('evidence'), 'App default resolution')
        for field in effective:
            if effective[field] is None:
                effective[field] = text(defaults.get(field), 'App default ' + field)
    models = capabilities['model'].get('values', [])
    combinations = capabilities['effort'].get('combinations', {})
    if not isinstance(models, list) or effective['model'] not in models:
        raise ValueError('requested model unavailable in target App')
    if (not isinstance(combinations, dict)
            or not isinstance(combinations.get(effective['model']), list)
            or effective['effort'] not in combinations[effective['model']]):
        raise ValueError('requested model/effort combination unavailable in target App')
    return model, effective, defaults


def prepare(state, identifier, operation, task, payload):
    if operation not in ('create', 'executor'):
        raise ValueError('unsupported App operation')
    if not isinstance(payload, dict):
        raise ValueError('operation parameters must be a map')
    if not state['dispatcher']:
        raise ValueError('App operation requires an active Dispatcher')
    task = task_path(task)
    key = str(task)
    if operation == 'create':
        owner = require_dispatcher(state, identifier)
        if key in state['tasks']:
            raise ValueError('task already has a Lead or pending create request')
        role = 'lead_important' if payload.get('important') is True else 'lead'
    else:
        owner = state['sessions'].get(identifier)
        task_binding = state['tasks'].get(key, {})
        if (owner is None or task_binding.get('session') != identifier
                or task_binding.get('state') != 'running'):
            raise ValueError('native Executor requires the bound running Lead session')
        role = payload.get('role', 'fact')
        if role not in ('fact', 'hard', 'chore', 'writing', 'visual', 'simplify', 'aesthetic'):
            raise ValueError('invalid Executor role')
    entry = owner['entry']
    model, effective, defaults = model_parameters(owner, operation, role, payload)
    if operation == 'create':
        brief = guarded_path(task / 'README.md').read_text()
        prompt = bootstrap('lead', task, entry=entry) + '\n任务卡：\n' + brief
    else:
        brief = text(payload.get('brief'), 'Executor brief')
        prompt = bootstrap('executor (' + role + ')', task, entry=entry) + '\n委派任务：\n' + brief
    request = {'id': str(uuid4()), 'operation': operation, 'owner_epoch': state['owner_epoch'],
               'owner_session': state['dispatcher']['session'], 'caller_session': identifier,
               'entry': entry, 'workspace': str(ROOT), 'task': key, 'role': role,
               'model_binding': model, 'effective_request': effective, 'defaults': defaults,
               'prompt': prompt, 'brief': brief, 'status': 'pending',
               'host_instructions': ('Use native independent visible App session creation and execute the first turn.'
                                     if operation == 'create' else
                                     'Use the bound Lead native subagent facility and execute the brief.') +
               ' Keep cwd at task. Read back actual model and effort. Never substitute CLI or request arguments for evidence.'}
    state['requests'][request['id']] = request
    if operation == 'create':
        state['tasks'][key] = {'state': 'pending', 'request': request['id'], 'entry': entry,
                               'active': True}
    return request


def result(state, identifier, request_id, payload):
    request = state['requests'].get(request_id)
    if request is None:
        raise ValueError('unknown host request')
    if request['status'] in ('succeeded', 'failed'):
        raise ValueError('request already resolved')
    if (not state['dispatcher'] or request['owner_epoch'] != state['owner_epoch']
            or request['owner_session'] != state['dispatcher']['session']):
        raise ValueError('stale host request ownership')
    if identifier != request['caller_session']:
        raise ValueError('request belongs to a different session')
    if request['operation'] == 'create':
        require_dispatcher(state, identifier)
    elif state['tasks'].get(request['task'], {}).get('session') != identifier:
        raise ValueError('Executor request no longer belongs to the bound Lead')
    if (not isinstance(payload, dict) or type(payload.get('owner_epoch')) is not int
            or any(payload.get(key) != value for key, value in (
            ('request_id', request_id), ('owner_epoch', request['owner_epoch']),
            ('entry', request['entry'])))):
        raise ValueError('receipt must match request_id, owner_epoch and entry')
    status = payload.get('status')
    if status not in ('created', 'queued', 'unknown', 'failed'):
        raise ValueError('invalid host receipt status')
    task = task_path(request['task'])
    if status in ('queued', 'unknown', 'failed'):
        text(payload.get('source'), 'host outcome source')
        text(payload.get('evidence'), 'host outcome')
        if status == 'failed' and payload.get('created') is False:
            request['status'] = 'failed'
            if request['operation'] == 'create':
                del state['tasks'][str(task)]
        else:
            request['status'] = status if status != 'failed' else 'unknown'
        request['receipt'] = payload
        return request
    actual_session = session_id(payload.get('session'))
    if actual_session == state['dispatcher']['session'] or actual_session == identifier:
        raise ValueError('created session must be independent from Dispatcher and caller')
    if actual_session in state['sessions']:
        raise ValueError('created session is already bound')
    if any(binding.get('session') == actual_session for binding in state['tasks'].values()):
        raise ValueError('created session is already bound to another task')
    if payload.get('workspace') != str(ROOT) or payload.get('cwd') != str(task):
        raise ValueError('receipt workspace and actual task cwd must match request')
    required = ('session', 'workspace', 'cwd', 'executed', 'model', 'effort')
    if request['operation'] == 'create':
        required += ('visible', 'independent')
        if payload.get('visible') is not True or payload.get('independent') is not True:
            raise ValueError('Lead must be a visible independent App session')
    else:
        required += ('native', 'parent_session')
        if payload.get('native') is not True or payload.get('parent_session') != identifier:
            raise ValueError('Executor must be a native subagent of its bound Lead')
    if payload.get('executed') is not True:
        raise ValueError('first turn has not executed in task cwd')
    evidence = payload.get('evidence')
    if not isinstance(evidence, dict):
        raise ValueError('created receipt requires individual host observation evidence')
    for name in required:
        text(evidence.get(name), 'observed ' + name)
    actual = {name: text(payload.get(name), 'actual ' + name) for name in ('model', 'effort')}
    if actual != request['effective_request']:
        raise ValueError('actual model/effort does not match resolved target App request')
    request['status'] = 'succeeded'
    request['receipt'] = payload
    binding = {'entry': request['entry'], 'capabilities': state['sessions'][identifier]['capabilities'],
               'role': 'lead' if request['operation'] == 'create' else 'executor',
               'task': str(task), 'actual': actual, 'request': request_id}
    state['sessions'][actual_session] = binding
    if request['operation'] == 'create':
        state['tasks'][str(task)].update(session=actual_session, state='running', actual=actual)
    return request
