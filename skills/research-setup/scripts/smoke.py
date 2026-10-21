#!/usr/bin/env python3
"""Offline checks with a disposable HOME; does not install optional components."""
import json
import importlib.util
import io
import re
import runpy
import sys
from unittest.mock import patch
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

source = Path(__file__).resolve().parents[3]


def run(command, env, cwd, expected=0, input=None):
    result = subprocess.run([str(arg) for arg in command], env=env, cwd=cwd, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, input=input, timeout=30)
    assert result.returncode == expected, result.stdout
    return result.stdout


def snapshot(root):
    return {str(p.relative_to(root)): ('link', os.readlink(p)) if p.is_symlink() else ('file', p.read_bytes())
            for p in root.rglob('*') if p.is_file() or p.is_symlink()}


with tempfile.TemporaryDirectory(prefix='research-smoke-', dir='/tmp') as temporary:
    home = Path(temporary)
    env = dict(os.environ, HOME=str(home), PYTHONDONTWRITEBYTECODE='1')
    kit = home / 'research space'
    deploy = source / 'skills/research-setup/scripts/deploy'
    run([deploy, kit, '--role', 'dispatcher', '--rules-remote', '', '--env', 'cli-plain'], env, home)
    first = snapshot(home)
    assert (kit / 'rules/claude-global.md').read_text() in (home / '.codex/AGENTS.md').read_text(), 'Codex-only AGENTS.md misses the global rules'
    run([deploy, kit, '--rules-remote', ''], env, home)
    assert first == snapshot(home), 'Repeated deployment changed files'
    print('smoke: repeated deploy unchanged, Codex AGENTS.md carries shared rules')
    config = home / '.claude/settings.json'
    original = {'permissions': {'allow': ['Read']}, 'hooks': {'SessionStart': [
        {'hooks': [{'type': 'command', 'command': 'echo existing'}]}], 'Stop': []}}
    config.write_text(json.dumps(original))
    merge = kit / 'skills/research-setup/scripts/merge-hooks'
    run([merge], env, home)
    assert json.loads(config.read_text()) == original
    run([merge, '--apply'], env, home)
    first = snapshot(home)
    run([merge, '--apply'], env, home)
    assert first == snapshot(home), 'Repeated hook merge changed files'
    settings = json.loads(config.read_text())
    assert settings['permissions'] == original['permissions']
    assert len(settings['hooks']['SessionStart']) == 2
    assert list(config.parent.glob('settings.json.backup.*'))
    print('smoke: hook preview, backup, preservation and idempotence ok')
    task = kit / 'experiments/demo-task'
    task.mkdir()
    (task / 'README.md').write_text('# Demo\n- id: demo-task\n- question: Does local status work?\n\n## Conclusion\nObserved locally.\n')
    (kit / 'TODO.md').write_text('- Review demo\n')
    for state in ('running', 'needs-input', 'blocked', 'done'):
        tendency, confidence = ('**Tendency:**', '**Confidence:**') if state in ('running', 'blocked') else ('**Tendency**:', '**Confidence**:')
        with (task / 'README.md').open('a') as stream:
            stream.write(f'\n## Conclusion (2026-01-01, {state})\n- {tendency} {state} evidence\n- {confidence} high — offline fixture\n')
        run([kit / 'bin/status', state, 'Checked locally'], env, task)
        run([kit / 'bin/kb', 'index', '--check'], env, kit)
        assert f'{state} evidence | high — offline fixture' in (kit / 'INDEX.md').read_text()
    with (task / 'README.md').open('a') as stream:
        stream.write('\n## 结论（2026-01-02，中文）\n- **倾向：**本地证据\n- **把握：**高\n')
        stream.write('\n## 结论（2026-01-02，中文）\n- **倾向**：本地证据\n- **把握**：高\n')
    run([kit / 'bin/kb', 'index'], env, kit)
    assert '本地证据 | 高 | 2026-01-02' in (kit / 'INDEX.md').read_text()
    board = (kit / 'BOARD.md').read_text()
    assert 'done | demo-task' in board and 'Review demo' in board
    assert not (task / '.notion-pending').exists()
    run([kit / 'bin/kb', 'lint'], env, kit)
    run([kit / 'bin/kb', 'index', '--check'], env, kit)
    (task / 'results.jsonl').write_text('{}\n[]\nnull\ninvalid\n')
    output = run([kit / 'bin/kb', 'lint', '--brief'], env, kit, expected=1)
    assert '4 error(s)' in output and len(output.splitlines()) == 4
    (task / 'results.jsonl').write_text(json.dumps({'command': 'true', 'exit_code': 0, 'artifact': 'output.txt'}) + '\n')
    run([kit / 'bin/kb', 'lint'], env, kit)
    (task / 'results.jsonl').unlink()
    for command in ('rules-pull', 'rules-push'):
        run([kit / 'bin' / command], env, kit)
    rules = kit / 'rules/claude-global.md'
    original_rules = rules.read_text()
    rules.write_text(original_rules + '\n`bin/missing-fixture` and `templates/missing-fixture.md`\n')
    output = run([kit / 'bin/kb', 'lint'], env, kit, expected=1)
    assert 'missing path: bin/missing-fixture' in output and 'missing path: templates/missing-fixture.md' in output
    rules.write_text(original_rules)
    card = kit / 'cards/budget-fixture.md'
    card.write_text('# Budget\n- id: budget-fixture\n- topic: budget\n- sources: fixture\n- date: 2026-01-01\n- valid_for: test\n' + '\n' * 151)
    assert 'warning: budget' in run([kit / 'bin/kb', 'lint'], env, kit)
    card.unlink()
    kb = runpy.run_path(str(kit / 'bin/kb'))
    def limited_walk(directory):
        yield str(directory), [], ['README.md']
        raise AssertionError('done-directory scan continued after reaching the byte limit')
    with patch.dict(kb['lint'].__globals__, DONE_BYTES=0), patch('os.walk', limited_walk), patch('sys.stdout', new_callable=io.StringIO) as output:
        assert kb['lint']() == 0
        assert 'cleanup task directory' in output.getvalue()
    print('smoke: every status refreshes index; bilingual conclusions, result errors, path errors and budget warnings ok')
    scan = home / 'scan'
    scan.mkdir()
    terms = home / '.config/research/scrub-terms.txt'
    terms.write_text('private-fixture-word\n')
    bad = scan / 'fixture.txt'
    fake = 'sk-' + 'A' * 20
    bad.write_text(fake + '\nprivate-fixture-word\n')
    output = run([kit / 'bin/scrub-check', scan], env, home, expected=1)
    assert 'fixture.txt:1:' in output and 'fixture.txt:2:' in output and fake not in output
    run(['git', 'init', '-q', str(scan)], env, home)
    run(['git', 'add', 'fixture.txt'], env, scan)
    git_env = dict(env, GIT_AUTHOR_NAME='Test', GIT_COMMITTER_NAME='Test',
                   GIT_AUTHOR_EMAIL='test' + '@' + 'example.invalid',
                   GIT_COMMITTER_EMAIL='test' + '@' + 'example.invalid')
    run(['git', 'commit', '-qm', 'Fixture'], git_env, scan)
    bad.unlink()
    run(['git', 'add', '-u'], env, scan)
    run(['git', 'commit', '-qm', 'Remove fixture'], git_env, scan)
    output = run([kit / 'bin/scrub-check', scan], env, home, expected=1)
    assert 'git-log.patch:' in output and fake not in output
    external_git = home / 'external-history.git'
    (scan / '.git').rename(external_git)
    output = run([kit / 'bin/scrub-check', scan, '--git-dir', external_git], env, home, expected=1)
    assert 'git-log.patch:' in output and fake not in output
    print('smoke: private terms, fake key and removed-secret history detected without disclosure')
    output = run([kit / 'bin/install-component', 'herdr', '--dry-run'], env, kit)
    assert 'URL: https://' in output and not (home / '.local/bin/herdr').exists()
    print('smoke: herdr dry-run writes nothing')
    sections = {
        'cli-herdr': '## Runtime environment: terminal CLI with herdr',
        'cli-plain': '## Runtime environment: terminal CLI without a multiplexer',
        'app': '## Runtime environment: desktop app (Claude app or Codex app)',
    }
    plain = None
    for environment, heading in sections.items():
        env_home = home / environment
        env_home.mkdir()
        env_env = dict(os.environ, HOME=str(env_home), PYTHONDONTWRITEBYTECODE='1')
        env_kit = env_home / 'research'
        run([deploy, env_kit, '--role', 'dispatcher', '--rules-remote', '', '--env', environment],
            env_env, env_home)
        agents = (env_home / '.claude/AGENTS.md').read_text()
        assert heading in agents
        assert all(other == heading or other not in agents for other in sections.values())
        if environment == 'cli-plain':
            plain = (env_env, env_kit)
    print('smoke: each env writes only its own AGENTS.md section')
    assert plain is not None
    env_env, env_kit = plain
    task = env_kit / 'experiments/plain-task'
    task.mkdir(parents=True)
    output = run([env_kit / 'bin/spawn-lead', task], env_env, env_kit.parent)
    assert str(task) in output and 'clipboard' not in output
    print('smoke: spawn-lead prints the task path for cli-plain without copying')
    output = run([env_kit / 'bin/new-task', 'new-fixture', '--important', '--kind', 'codex'], env_env, env_kit,
                 input='# New task\n- id: <task-id>\n- question: Offline creation?\nPre-authorized: yes\n')
    new_task = env_kit / 'experiments/001-new-fixture'
    assert new_task.is_dir() and (new_task / 'findings').is_dir()
    assert 'running | 001-new-fixture | Lead reading task card' in (new_task / 'STATUS').read_text()
    assert '- id: 001-new-fixture' in (new_task / 'README.md').read_text() and 'pre-authorized' in output
    (env_kit / 'experiments/archive/009-old').mkdir(parents=True)
    run([env_kit / 'bin/new-task', 'after-archive'], env_env, env_kit, input='# Archived numbering test\n')
    assert (env_kit / 'experiments/010-after-archive').exists()
    for name, stdin in (('empty-input', ''), ('blank-input', ' \n\t ')):
        run([env_kit / 'bin/new-task', name], env_env, env_kit, input=stdin)
        created = next((env_kit / 'experiments').glob('*-' + name))
        assert (created / 'README.md').read_text() == (env_kit / 'templates/task-card.md').read_text().replace('<task-id>', created.name)
    status = env_kit / 'bin/status'
    status_source = status.read_text()
    status.write_text('#!/bin/sh\nexit 1\n')
    output = run([env_kit / 'bin/new-task', 'offline-status'], env_env, env_kit, input='')
    assert 'Lead task:' in output and 'offline-status' in output
    status.write_text(status_source)
    print('smoke: new-task cli-plain creates numbered cards, findings, status and prompt; archive IDs counted')

    models = kit / 'bin/models'
    assert 'copy ' in run([models], env, kit)
    model_config = home / '.config/research/roles.toml'
    shutil.copy2(kit / 'templates/roles.toml.example', model_config)
    module_spec = importlib.util.spec_from_file_location('smoke_toml', kit / 'bin/_toml.py')
    toml = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(toml)
    parsed = toml.loads(model_config.read_text())
    toml.tomllib = None
    assert toml.loads(model_config.read_text()) == parsed
    output = run([models], env, kit)
    assert all(name in output for name in parsed['roles']) and 'Research:' in output
    selected = parsed['roles']['lead']['candidates'][0]
    assert run([models, 'get', 'lead'], env, kit).strip() == selected.replace(':', ' ')
    original_config = model_config.read_text()
    assert '# Candidates:' in original_config
    missing_effort = selected.rsplit(':', 1)[0]
    model_config.write_text(original_config.replace(selected, missing_effort))
    output = run([models], env, kit, expected=1)
    assert 'Role lead:' in output and 'requires effort' in output
    model_config.write_text(original_config)
    probes = original_config.replace("check = 'claude --version'", "check = 'python3 --version'").replace("check = 'codex --version'", "check = 'python3 --version'")
    model_config.write_text(probes)
    output = run([models, 'check'], env, kit)
    assert 'claude: exit=0' in output and 'codex: exit=0' in output
    assert model_config.read_text() == probes
    model_config.write_text(original_config)
    local = home / '.claude/local.md'
    local.write_text('Local machine fixture.\n')
    run([models], env, kit)
    assert model_config.read_text() == original_config
    agents = (home / '.codex/AGENTS.md').read_text()
    assert agents.index('Local machine fixture.') < agents.index('Generated by bin/models')
    assert (home / '.config/research/models.md').read_text() in agents
    output = run([kit / 'bin/spawn-lead', task, '--important'], env, kit)
    assert parsed['roles']['lead_important']['candidates'][0].split(':')[1] in output
    output = run([kit / 'bin/spawn-lead', task, '--kind', 'codex'], env, kit)
    assert 'Lead selection:' not in output
    legacy_roles = home / '.config/research/roles'
    legacy_roles.write_text('kind=codex\nmodel=legacy-model\neffort=high\n')
    no_leads = re.sub(r'(?ms)^\[roles\.lead(?:_important)?\]\n.*?(?=^\[|\Z)', '', original_config)
    model_config.write_text(no_leads)
    for flags in ([], ['--important']):
        output = run([kit / 'bin/spawn-lead', task] + flags, env, kit)
        assert 'Lead selection: codex legacy-model effort=high' in output
    legacy_roles.unlink()
    output = run([kit / 'bin/spawn-lead', task], env, kit)
    assert 'Lead task:' in output and 'Lead selection:' not in output
    model_config.write_text(original_config)
    legacy_roles.write_text('kind=codex\nmodel=legacy-model\neffort=high\n')
    model_config.rename(model_config.with_suffix('.saved'))
    assert 'codex legacy-model' in run([kit / 'bin/spawn-lead', task], env, kit)
    model_config.with_suffix('.saved').rename(model_config)
    print('smoke: roles example, older-Python TOML reader, get/check, effort validation, comment preservation, automatic sync and Lead overrides/fallbacks ok')

    task = kit / 'experiments/demo-task'
    memory = task / 'memory/MEMORY.md'
    memory.parent.mkdir()
    memory.write_text('- Task-specific memory fixture\n')
    hook = kit / 'bin/lead-watch-start'
    event = {'cwd': str(task), 'source': 'compact', 'session_id': 'fixture-session'}
    for count in range(1, 4):
        output = run([hook], env, kit, input=json.dumps(event))
        assert 'Task-specific memory fixture' in output and 'done | demo-task' in output
        assert '本地证据' in output
        assert ('consider /clear' in output) == (count >= 3)
    assert 'needs-input evidence' in output and 'running evidence' not in output and '## Conclusion |' not in output
    event['source'] = 'clear'
    run([hook], env, kit, input=json.dumps(event))
    assert not (task / '.compactions').exists()
    event['cwd'] = str(memory.parent)
    assert not run([hook], env, kit, input=json.dumps(event))
    for index in range(4):
        finished = kit / f'experiments/finished-{index}'
        finished.mkdir()
        status = finished / 'STATUS'
        status.write_text(f'done | finished-{index} | fixture |\n')
        os.utime(status, (index + 1, index + 1))
    output = run([hook], env, kit, input=json.dumps({'cwd': str(kit)}))
    assert 'Review demo' in output and 'finished-3' in output and 'finished-0' not in output
    print('smoke: task handoff, last five conclusions, memory, compact reminder/reset and dispatcher latest-three context ok')

    assert 'routers.toml' in run([kit / 'bin/build-routers'], env, kit)
    library = home / 'router-library'
    skill = library / 'fixture-skill/SKILL.md'
    skill.parent.mkdir(parents=True)
    skill.write_text('---\nname: fixture-skill\ndescription: >\n  Fixture skill description.\n---\n# Fixture\n')
    router_config = home / '.config/research/routers.toml'
    router_config.write_text(f'library = {json.dumps(str(library))}\noutput = {json.dumps(str(home / "routers"))}\nprefix = "route-"\n[routers.fixture]\ntitle = "Fixture"\ndescription = "Use for fixture work."\nskills = ["fixture-skill"]\n')
    run([kit / 'bin/build-routers'], env, kit)
    assert 'Fixture skill description.' in (home / 'routers/route-fixture/SKILL.md').read_text()
    manual = home / 'routers/route-manual'
    manual.mkdir()
    (manual / 'SKILL.md').write_text('User-owned router.\n')
    router_config.write_text(router_config.read_text().replace('[routers.fixture]', '[routers.renamed]'))
    run([kit / 'bin/build-routers'], env, kit)
    assert not (home / 'routers/route-fixture').exists()
    assert 'Generated by bin/build-routers' in (home / 'routers/route-renamed/SKILL.md').read_text()
    assert (manual / 'SKILL.md').read_text() == 'User-owned router.\n'
    with router_config.open('a') as stream:
        stream.write('[routers.duplicate]\ntitle = "Duplicate"\ndescription = "Duplicate fixture"\nskills = ["fixture-skill"]\n')
    assert 'duplicates=' in run([kit / 'bin/build-routers'], env, kit, expected=1)
    assert (home / 'routers/route-renamed/SKILL.md').exists()
    print('smoke: configured routers and catalog generated; duplicate coverage rejected')

    fakebin = home / 'fakebin'
    fakebin.mkdir()
    cron = fakebin / 'crontab'
    cron.write_text('#!/bin/sh\ntouch "$HOME/cron-was-called"\n')
    cron.chmod(0o755)
    private = home / '.local/share/research-rules'
    private.mkdir(parents=True)
    run(['git', 'init', '-q', str(private)], env, kit)
    run(['git', 'remote', 'add', 'origin', str(home / 'fixture-remote')], env, private)
    (home / '.config/research/rules-remote').write_text(str(home / 'fixture-remote'))
    cron_env = dict(env, PATH=str(fakebin) + os.pathsep + env.get('PATH', ''))
    cron_env.pop('RULES_CRON', None)
    run([kit / 'bin/install-rules'], cron_env, kit)
    assert not (home / 'cron-was-called').exists()
    extra = kit / 'rules-extra.md'
    if (kit / 'templates/research-extra.md').exists():
        extra.write_text('Existing extra rules fixture.\n')
        run([kit / 'bin/install-rules'], cron_env, kit)
        assert extra.read_text() == (kit / 'templates/research-extra.md').read_text()
        assert extra.with_name('rules-extra.md.before-agenthelm').read_text() == 'Existing extra rules fixture.\n'
    print('smoke: temporary HOME skips cron even with a remote; extra rules rendered with backup')

    remote = home / 'sync-remote.git'
    run(['git', 'init', '-q', '--bare', '--initial-branch=main', remote], git_env, home)
    run(['git', 'remote', 'set-url', 'origin', remote], git_env, private)
    (home / '.config/research/rules-remote').write_text(str(remote))
    (private / 'rules').mkdir()
    conflict = private / 'rules/conflict.md'
    conflict.write_text('Base rule.\n')
    run(['git', 'add', '.'], git_env, private)
    run(['git', 'commit', '-qm', 'Base'], git_env, private)
    run(['git', 'branch', '-M', 'main'], git_env, private)
    run(['git', 'push', '-qu', 'origin', 'main'], git_env, private)
    peer = home / 'sync-peer'
    run(['git', 'clone', '-q', remote, peer], git_env, home)
    (peer / 'rules/conflict.md').write_text('Remote rule.\n')
    run(['git', 'commit', '-qam', 'Remote change'], git_env, peer)
    run(['git', 'push', '-q'], git_env, peer)
    conflict.write_text('Local rule.\n')
    run(['git', 'commit', '-qam', 'Local change'], git_env, private)
    before = run(['git', 'rev-parse', 'HEAD'], git_env, private)
    assert 'failed' in run([kit / 'bin/rules-pull'], git_env, kit)
    assert run(['git', 'rev-parse', 'HEAD'], git_env, private) == before
    assert conflict.read_text() == 'Local rule.\n' and not (private / '.git/rebase-merge').exists()
    run([kit / 'bin/rules-push'], git_env, kit, expected=1)
    assert run(['git', 'rev-parse', 'HEAD'], git_env, private) == before
    run([kit / 'bin/rules-sync'], git_env, kit, expected=1)
    assert (home / '.local/state/rules-sync.status').exists()
    rebase = private / '.git/rebase-merge'
    rebase.mkdir()
    assert 'skipped' in run([kit / 'bin/rules-pull'], git_env, kit)
    rebase.rmdir()
    run(['git', 'reset', '--hard', 'origin/main'], git_env, private)
    (private / 'rules/new-rule.md').write_text('New rule.\n')
    gate = private / 'rules/gate.md'
    gate.write_text('`bin/missing-gate-fixture`\n')
    output = run([kit / 'bin/rules-push'], git_env, kit, expected=1)
    assert 'missing path: bin/missing-gate-fixture' in output
    assert (kit / 'rules/gate.md').read_text() == gate.read_text()
    gate.unlink()
    (kit / 'rules/gate.md').unlink()
    (task / 'results.jsonl').write_text('{}\n')
    run([kit / 'bin/rules-push'], git_env, kit)
    (task / 'results.jsonl').unlink()
    run([kit / 'bin/rules-sync'], git_env, kit)
    assert not (home / '.local/state/rules-sync.status').exists()
    assert (kit / 'rules/new-rule.md').read_text() == 'New rule.\n'
    print('smoke: real local Git rebase conflicts abort without losing commits; manual rebase skipped; weekly failure/success recorded')


    notion = home / '.config/research/notion.env'
    notion.write_text('NOTION_DB=fixture\nNOTION_TOKEN=fixture\n')
    identity = home / '.config/research/machine'
    identity.write_text('fixture-machine')
    calls = []
    machine_kind = 'select'
    def notion_api(request, timeout):
        method, path = request.method, request.full_url.split('/v1/')[1]
        body = json.loads(request.data) if request.data else None
        calls.append((method, path, body))
        if path == 'databases/fixture':
            result = {'properties': {'Machine': {'type': machine_kind}}}
        elif path.endswith('/query'):
            assert body['filter'] == {'and': [
                {'property': 'Name', 'title': {'equals': task.name}},
                {'or': [{'property': 'Machine', machine_kind: {'equals': 'fixture-machine'}},
                        {'property': 'Machine', machine_kind: {'is_empty': True}}]}]}
            result = {'results': [{'id': 'fixture-page', 'properties': {'Machine': {machine_kind: None if machine_kind == 'select' else []}}}]}
        elif method == 'GET':
            result = {'results': [{'id': 'old-block'}]}
        else:
            result = {}
        return io.StringIO(json.dumps(result))
    for machine_kind in ('select', 'rich_text'):
        calls.clear()
        with patch.dict(os.environ, env), patch.object(sys, 'argv', ['notion-sync', str(task)]), patch('urllib.request.urlopen', notion_api):
            runpy.run_path(str(kit / 'bin/notion-sync'), run_name='__main__')
        properties = next(body['properties'] for method, path, body in calls if path == 'pages/fixture-page')
        expected = {'name': 'fixture-machine'} if machine_kind == 'select' else [{'text': {'content': 'fixture-machine'}}]
        assert properties['Machine'][machine_kind] == expected
        assert not any(method == 'POST' and path == 'pages' for method, path, _ in calls)
    assert any(method == 'DELETE' and path == 'blocks/old-block' for method, path, _ in calls)
    children = [body for method, path, body in calls if method == 'PATCH' and path.endswith('/children')]
    assert '本地证据' in json.dumps(children, ensure_ascii=False) and 'done evidence' not in json.dumps(children)
    with patch.dict(os.environ, env), patch.object(sys, 'argv', ['notion-sync', str(task)]), patch('urllib.request.urlopen', side_effect=TimeoutError):
        try:
            runpy.run_path(str(kit / 'bin/notion-sync'), run_name='__main__')
        except SystemExit as error:
            assert error.code == 1
    assert (task / '.notion-pending').exists() and 'done | demo-task' in (task / 'STATUS').read_text()
    print('smoke: mocked Notion replaces latest conclusion, writes optional Machine and retains STATUS plus pending marker on failure')

print('smoke: ok (temporary HOME removed)')
