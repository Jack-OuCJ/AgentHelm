"""Prepare native host operations; accept evidence before binding running sessions."""
import os
from uuid import uuid4

from _app_sessions import require_dispatcher, session_id, task_path, guarded_path, pending_writes
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
    if operation in ('read', 'wait', 'followup'):
        return prepare_tracking(state, identifier, operation, task, payload)
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
        try:
            maximum = int(os.environ.get('RESEARCH_MAX_LEADS', '10'))
        except ValueError as error:
            raise ValueError('RESEARCH_MAX_LEADS must be a positive integer') from error
        if maximum < 1:
            raise ValueError('RESEARCH_MAX_LEADS must be a positive integer')
        if sum(binding.get('active', False) for binding in state['tasks'].values()) >= maximum:
            raise ValueError('Lead concurrency limit reached')
        role = 'lead_important' if payload.get('important') is True else 'lead'
    else:
        owner = state['sessions'].get(identifier)
        task_binding = state['tasks'].get(key, {})
        if (owner is None or task_binding.get('session') != identifier
                or task_binding.get('state') != 'running' or not task_binding.get('active')):
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
    if request['operation'] in ('create', 'read', 'wait', 'followup'):
        require_dispatcher(state, identifier)
    elif state['tasks'].get(request['task'], {}).get('session') != identifier:
        raise ValueError('Executor request no longer belongs to the bound Lead')
    if (not isinstance(payload, dict) or type(payload.get('owner_epoch')) is not int
            or any(payload.get(key) != value for key, value in (
            ('request_id', request_id), ('owner_epoch', request['owner_epoch']),
            ('entry', request['entry'])))):
        raise ValueError('receipt must match request_id, owner_epoch and entry')
    if request['operation'] in ('read', 'wait'):
        return observe_result(state, request, payload)
    if request['operation'] == 'followup':
        return followup_result(state, request, payload)
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


def prepare_tracking(state, identifier, operation, task, payload):
    owner = require_dispatcher(state, identifier)
    if not isinstance(payload, dict):
        raise ValueError('operation parameters must be a map')
    task = task_path(task)
    binding = state['tasks'].get(str(task), {})
    if not binding.get('session') or not binding.get('active'):
        raise ValueError('tracking requires an active bound Lead')
    if not owner['capabilities'].get(operation, {}).get('available'):
        raise ValueError(f'App capability unavailable: {operation}; no CLI fallback')
    if owner['entry'] != binding['entry']:
        raise ValueError('cross-App tracking is not supported')
    order = binding.get('observation_counter', 0) + 1
    request = {'id': str(uuid4()), 'operation': operation, 'owner_epoch': state['owner_epoch'],
               'owner_session': identifier, 'caller_session': identifier, 'entry': owner['entry'],
               'workspace': str(ROOT), 'task': str(task), 'target_session': binding['session'],
               'observation_order': order, 'status': 'pending',
               'host_instructions': 'Read the existing bound App session; never recreate it or replay its task. '
                                    'Return latest context, revision and cursor from native observation.'}
    if operation == 'wait':
        request['after_cursor'] = binding.get('observation', {}).get('cursor')
    if operation == 'followup':
        observation = binding.get('observation', {})
        if (not observation or observation.get('state') in ('unknown', 'missing')
                or observation.get('consumed') or observation.get('invalidated')
                or any(payload.get(field) != observation.get(key) for field, key in
                       (('observation', 'request_id'), ('revision', 'revision'), ('cursor', 'cursor')))):
            raise ValueError('followup requires the latest observed context, revision and cursor')
        if pending_writes(state, task):
            raise ValueError('task has an unresolved write request; do not resend')
        request.pop('observation_order')
        request['brief'] = text(payload.get('brief'), 'followup brief')
        request['effective_request'] = dict(binding['actual'])
        request['revalidate'] = {name: observation[name] for name in
                                 ('request_id', 'revision', 'cursor', 'source')}
        request['host_instructions'] = (
            'Read and revalidate the latest native context revision and cursor before sending. '
            'Verify current model and effort before sending. If context or settings changed, do not send; '
            'return stale and read again, recording verified actual settings. Send only this brief to the existing '
            'Lead, preserving its actual model and effort. Never replay an old task or reset user changes.')
    else:
        binding['observation_counter'] = order
    state['requests'][request['id']] = request
    return request


def observe_result(state, request, payload):
    task_path(request['task'])
    binding = state['tasks'][request['task']]
    if (payload.get('session') != request['target_session']
            or payload.get('workspace') != request['workspace'] or payload.get('cwd') != request['task']):
        raise ValueError('observation must match the bound session, workspace and cwd')
    observation = binding.get('observation', {})
    if request['observation_order'] <= max(observation.get('order', 0), binding.get('observation_floor', 0)):
        raise ValueError('stale observation cannot replace newer context')
    status = payload.get('status')
    if status in ('unknown', 'missing'):
        text(payload.get('source'), 'observation source')
        text(payload.get('evidence'), 'unavailable session observation')
        observation = {name: payload[name] for name in ('session', 'source', 'evidence')}
        observation.update(request_id=request['id'], order=request['observation_order'],
                           state=status, revision=None, cursor=None)
        binding['observation'] = observation
        state['sessions'][request['target_session']]['observation'] = observation
        request.update(status='succeeded', receipt=payload)
        return request
    if status != 'observed':
        raise ValueError('invalid observation receipt status')
    if payload.get('state') not in ('idle', 'working', 'blocked', 'done', 'unknown', 'missing'):
        raise ValueError('invalid observed session state')
    text(payload.get('source'), 'observation source')
    evidence = payload.get('evidence')
    if not isinstance(evidence, dict):
        raise ValueError('observation requires individual evidence')
    for name in ('session', 'workspace', 'cwd', 'state', 'revision', 'cursor', 'context'):
        text(evidence.get(name), 'observed ' + name)
    for name in ('revision', 'cursor', 'context'):
        text(payload.get(name), name)
    if 'actual' in payload:
        actual = payload['actual']
        if not isinstance(actual, dict):
            raise ValueError('observed actual settings must include model and effort')
        for name in ('model', 'effort'):
            text(actual.get(name), 'observed actual ' + name)
            text(evidence.get(name), 'observed actual ' + name + ' evidence')
        actual = {name: actual[name] for name in ('model', 'effort')}
        binding['actual'] = actual
        state['sessions'][request['target_session']]['actual'] = actual
    observation = {name: payload[name] for name in
                   ('session', 'state', 'revision', 'cursor', 'context', 'source', 'evidence')}
    observation.update(request_id=request['id'], order=request['observation_order'])
    if 'actual' in payload:
        observation['actual'] = actual
    binding['observation'] = observation
    state['sessions'][request['target_session']]['observation'] = observation
    request.update(status='succeeded', receipt=payload)
    return request


def followup_result(state, request, payload):
    task_path(request['task'])
    binding = state['tasks'][request['task']]
    if (payload.get('session') != request['target_session']
            or payload.get('workspace') != request['workspace'] or payload.get('cwd') != request['task']):
        raise ValueError('followup receipt must match the bound session, workspace and cwd')
    text(payload.get('source'), 'followup source')
    status = payload.get('status')
    if status in ('queued', 'unknown', 'failed', 'stale'):
        text(payload.get('evidence'), 'followup outcome')
        if status in ('failed', 'stale') and payload.get('sent') is False:
            request['status'] = 'failed'
            observation = binding.get('observation', {})
            if observation.get('request_id') == request['revalidate']['request_id']:
                observation['invalidated'] = True
        else:
            request['status'] = 'queued' if status == 'queued' else 'unknown'
        request['receipt'] = payload
        return request
    if status != 'sent' or payload.get('sent') is not True:
        raise ValueError('followup requires evidence of actual native send')
    observation = binding.get('observation', {})
    if any(observation.get(name) != value for name, value in request['revalidate'].items()):
        raise ValueError('followup observation is stale; read latest context again')
    for name in ('revision', 'cursor'):
        if payload.get('revalidated_' + name) != request['revalidate'][name]:
            raise ValueError('native context changed before send; do not replay')
    if {name: payload.get(name) for name in ('model', 'effort')} != request['effective_request']:
        raise ValueError('followup changed actual model or effort')
    evidence = payload.get('evidence')
    if not isinstance(evidence, dict):
        raise ValueError('followup requires individual native send evidence')
    for name in ('session', 'workspace', 'cwd', 'sent', 'revalidated_revision',
                 'revalidated_cursor', 'model', 'effort'):
        text(evidence.get(name), 'followup observed ' + name)
    request.update(status='succeeded', receipt=payload)
    observation['consumed'] = True
    binding['observation_floor'] = binding.get('observation_counter', 0)
    binding.setdefault('history', []).append({'event': 'followup', 'request': request['id']})
    return request
