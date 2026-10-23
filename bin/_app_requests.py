"""Prepare native host operations; separate Lead identity from runtime verification."""
import os
from uuid import uuid4

from _app_sessions import require_dispatcher, session_id, task_path, guarded_path, pending_writes
from _models import EXECUTOR_ROLES, ccd_agent, ccd_agent_path, resolve_app
from _toml import loads
from _workspace import CONFIG, ROOT, bootstrap


def text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} requires nonempty evidence')
    return value


def require_capabilities(binding, operation):
    required = ('create', 'read', 'wait', 'followup', 'model', 'effort')
    if operation == 'executor':
        required = ('native_executor', 'model', 'effort')
    capabilities = binding['capabilities']
    for name in required:
        capability = capabilities.get(name, {})
        if not capability.get('available'):
            raise ValueError(f'App capability unavailable: {name}; no CLI fallback')
    return capabilities


def model_parameters(owner, operation, role, payload):
    if not isinstance(payload, dict):
        raise ValueError('operation parameters must be a map')
    capabilities = require_capabilities(owner, operation)
    entry = owner['entry']
    model = resolve_app(loads((CONFIG / 'roles.toml').read_text()), role, entry)
    effective = {field: model[field] for field in ('model', 'effort')}
    defaults = payload.get('defaults', {})
    if entry == 'app.ccd' and operation == 'executor':
        inherited = owner.get('configured', owner.get('actual', owner.get('requested', {})))
        for field in effective:
            if effective[field] is None:
                if not isinstance(inherited.get(field), str) or not inherited[field]:
                    raise ValueError('CCD Executor inherits the bound Lead, whose selected ' + field + ' is unknown')
                effective[field] = inherited[field]
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
        if role not in EXECUTOR_ROLES:
            raise ValueError('invalid Executor role')
    entry = owner['entry']
    model, effective, defaults = model_parameters(owner, operation, role, payload)
    agent = None
    if operation == 'executor' and entry == 'app.ccd':
        # CCD's Agent tool only takes model aliases, so the generated agent file pins the real IDs.
        path = ccd_agent_path(role)
        config = loads((CONFIG / 'roles.toml').read_text())
        if not path.is_file() or path.read_text() != ccd_agent(config, role):
            raise ValueError(f'CCD Executor agent {path} is missing or stale; run bin/models, then restart the Lead session')
        agent = path.stem
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
               'host_instructions': ('Create a native independent visible App session with request.prompt. '
                                     'Bind its identity using evidence_level=identity and runtime_verified=false; '
                                     'do not wait for a task action, turn ID or runtime model evidence. '
                                     'Record runtime observations separately after normal execution.'
                                     if operation == 'create' else
                                     'Use the bound Lead native subagent facility. The Executor completes the brief '
                                     'and reports results without a startup handshake or waiting for local binding. '
                                     'The parent records status=completed before optional runtime verification '
                                     'and verifies cwd and actual model/effort after completion.') +
               ' Keep cwd at task. Never substitute CLI or request arguments for runtime evidence.'}
    if operation == 'create' and entry == 'app.ccd':
        request['host_instructions'] = (
            'Create a native independent visible App session with a placeholder only. Set model and effort, '
            'then read them back with get_session. Submit evidence_level=settings with executed=false and '
            'runtime_verified=false, or bind identity only if settings readback is unavailable. '
            'Dispatch request.prompt via read/followup after identity binding. '
            'Host metadata may prove workspace and task cwd. No handshake turn or prompt_id is required. '
            'Never substitute request arguments for host evidence; reuse an existing unresolved creation.')
    if agent:
        request['subagent_type'] = agent
        request['host_instructions'] = (
            f'Use the bound Lead native Agent tool with subagent_type={agent} and no model argument; '
            'the agent file pins model and effort; pass the requested effort explicitly. '
            'The Executor completes the brief with cwd at task and reports results without a startup handshake '
            'or waiting for local binding. The parent records status=completed before runtime verification. '
            'After completion, the parent reads actual model and '
            'effort from the subagent transcript; cwd evidence comes from the executed pwd output. '
            'Never substitute CLI or request arguments for evidence.')
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
    level = payload.get('evidence_level', 'runtime')
    if level not in ('runtime', 'settings', 'identity'):
        raise ValueError('invalid evidence_level')
    identity_only = level == 'identity'
    if identity_only and request['operation'] != 'create':
        raise ValueError('identity evidence is only allowed for Lead create')
    settings_only = level == 'settings'
    if settings_only and (request['operation'] != 'create' or request['entry'] != 'app.ccd'):
        raise ValueError('settings evidence is only allowed for app.ccd Lead create')
    if request['operation'] in ('read', 'wait'):
        return observe_result(state, request, payload)
    if request['operation'] == 'followup':
        return followup_result(state, request, payload)
    status = payload.get('status')
    if status not in ('created', 'completed', 'queued', 'unknown', 'failed'):
        raise ValueError('invalid host receipt status')
    completion_only = status == 'completed'
    if completion_only and (request['operation'] != 'executor' or level != 'runtime'):
        raise ValueError('completion receipt is only allowed for Executor results')
    if request['status'] == 'completed' and (
            status not in ('created', 'completed')
            or payload.get('session') != request['completion']['session']):
        raise ValueError('completed Executor cannot change session or regress to pending execution')
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
    if any(other['id'] != request_id and other.get('completion', {}).get('session') == actual_session
           for other in state['requests'].values()):
        raise ValueError('Executor session is already recorded by another completed request')
    if any(binding.get('session') == actual_session for binding in state['tasks'].values()):
        raise ValueError('created session is already bound to another task')
    if payload.get('workspace') != str(ROOT) or payload.get('cwd') != str(task):
        raise ValueError('receipt workspace and actual task cwd must match request')
    required = ('session', 'workspace', 'cwd')
    if not identity_only:
        required += ('executed',)
        if not completion_only:
            required += ('model', 'effort')
    if request['operation'] == 'create':
        required += ('visible', 'independent')
        if payload.get('visible') is not True or payload.get('independent') is not True:
            raise ValueError('Lead must be a visible independent App session')
    else:
        required += ('native', 'parent_session')
        if payload.get('native') is not True or payload.get('parent_session') != identifier:
            raise ValueError('Executor must be a native subagent of its bound Lead')
        if request.get('subagent_type') and not completion_only:
            required += ('served_model',)
    if completion_only:
        required += ('completed',)
        if (payload.get('executed') is not True or payload.get('runtime_verified') is not False
                or any(field in payload for field in ('actual', 'configured', 'served_model', 'model', 'effort'))):
            raise ValueError('completion receipt records execution separately from runtime model verification')
    elif identity_only:
        if (payload.get('runtime_verified') is not False
                or payload.get('executed', False) is not False
                or any(field in payload for field in ('actual', 'configured', 'served_model', 'model', 'effort'))):
            raise ValueError('identity receipt cannot claim execution or observed model settings')
    elif settings_only:
        if payload.get('executed') is not False or payload.get('runtime_verified') is not False:
            raise ValueError('settings receipt requires executed=false and runtime_verified=false')
        if 'actual' in payload or 'served_model' in payload:
            raise ValueError('settings receipt cannot claim runtime actual or served_model')
        required = tuple(name for name in required if name != 'executed')
    elif payload.get('executed') is not True:
        raise ValueError('first turn has not executed in task cwd')
    elif 'runtime_verified' in payload and payload['runtime_verified'] is not True:
        raise ValueError('runtime receipt cannot deny runtime verification')
    evidence = payload.get('evidence')
    if not isinstance(evidence, dict):
        raise ValueError('created receipt requires individual host observation evidence')
    for name in required:
        text(evidence.get(name), 'observed ' + name)
    if completion_only:
        request.update(status='completed', receipt=payload, completion=payload)
        return request
    selected = None if identity_only else {
        name: text(payload.get(name), 'observed ' + name) for name in ('model', 'effort')}
    if selected is not None and selected != request['effective_request']:
        raise ValueError('observed model/effort does not match resolved target App request')
    if request.get('subagent_type'):
        # CCD transcripts keep the [1m] variant in requestedModel but report the served base ID in message.model.
        served = text(payload.get('served_model'), 'served model')
        if served != selected['model'].removesuffix('[1m]'):
            raise ValueError('served model does not match the requested CCD model')
    request['status'] = 'succeeded'
    request['receipt'] = payload
    verified = {'evidence_level': level, 'runtime_verified': level == 'runtime'}
    if identity_only:
        verified['requested'] = dict(request['effective_request'])
    else:
        verified['configured' if settings_only else 'actual'] = selected
    binding = {'entry': request['entry'], 'capabilities': state['sessions'][identifier]['capabilities'],
               'role': 'lead' if request['operation'] == 'create' else 'executor',
               'task': str(task), **verified, 'request': request_id}
    state['sessions'][actual_session] = binding
    if request['operation'] == 'create':
        state['tasks'][str(task)].update(session=actual_session, state='running', **verified)
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
        request['effective_request_source'] = next(
            field for field in ('configured', 'actual', 'requested') if field in binding)
        request['effective_request'] = dict(binding[request['effective_request_source']])
        request['revalidate'] = {name: observation[name] for name in
                                 ('request_id', 'revision', 'cursor', 'source')}
        request['host_instructions'] = (
            'Read and revalidate the latest native context revision and cursor before sending. '
            'Preserve observed settings when available; for identity-only bindings retain requested values '
            'without waiting for runtime evidence. If context or observed settings changed, do not send; '
            'return stale and read again, recording observed configured or runtime actual settings separately. '
            'Send only this brief to the existing Lead, preserving its selected model and effort. '
            'A send receipt does not verify runtime execution. Never replay an old task or reset user changes.')
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
    if 'configured' in payload and 'actual' in payload:
        raise ValueError('observe configured settings and runtime actual separately')
    settings_field = 'configured' if 'configured' in payload else 'actual' if 'actual' in payload else None
    if settings_field:
        if settings_field == 'configured':
            if request['entry'] != 'app.ccd' or payload.get('runtime_verified') is not False:
                raise ValueError('configured observation requires app.ccd and runtime_verified=false')
        elif ((binding.get('runtime_verified') is False and payload.get('runtime_verified') is not True)
              or ('runtime_verified' in payload and payload['runtime_verified'] is not True)):
            raise ValueError('actual observation requires explicit runtime verification')
        selected = payload[settings_field]
        if not isinstance(selected, dict):
            raise ValueError('observed settings must include model and effort')
        for name in ('model', 'effort'):
            text(selected.get(name), 'observed ' + settings_field + ' ' + name)
            text(evidence.get(name), 'observed ' + settings_field + ' ' + name + ' evidence')
        selected = {name: selected[name] for name in ('model', 'effort')}
        for target in (binding, state['sessions'][request['target_session']]):
            target.pop('actual' if settings_field == 'configured' else 'configured', None)
            target[settings_field] = selected
            target['runtime_verified'] = settings_field == 'actual'
            target['evidence_level'] = 'runtime' if settings_field == 'actual' else 'settings'
    elif payload.get('runtime_verified') is True:
        raise ValueError('runtime verification requires observed actual values')
    observation = {name: payload[name] for name in
                   ('session', 'state', 'revision', 'cursor', 'context', 'source', 'evidence')}
    observation.update(request_id=request['id'], order=request['observation_order'])
    if settings_field:
        observation[settings_field] = selected
        observation['runtime_verified'] = settings_field == 'actual'
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
    if payload.get('runtime_verified') is True or 'actual' in payload:
        raise ValueError('followup send cannot verify runtime actual; use a runtime observation')
    observation = binding.get('observation', {})
    if any(observation.get(name) != value for name, value in request['revalidate'].items()):
        raise ValueError('followup observation is stale; read latest context again')
    for name in ('revision', 'cursor'):
        if payload.get('revalidated_' + name) != request['revalidate'][name]:
            raise ValueError('native context changed before send; do not replay')
    if {name: payload.get(name) for name in ('model', 'effort')} != request['effective_request']:
        raise ValueError('followup changed selected model or effort')
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
