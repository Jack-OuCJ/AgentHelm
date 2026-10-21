"""Board integration contracts using an offline lark-cli double, never the real service."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import test_workspace

FAKE_CLI = r'''
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
assert args[:1]==['base']
assert args[args.index('--profile')+1]=='profile-hb'
assert args[args.index('--as')+1]=='user'
action=args[1]
path=Path(os.environ['FAKE_BOARD'])
state=json.loads(path.read_text()) if path.exists() else {'rows':{},'creates':0,'updates':0}
mode=os.environ.get('FAKE_MODE','')
def flag(name): return args[args.index(name)+1]
def save(): path.write_text(json.dumps(state))
def fail():
 print(json.dumps({'ok':False,'error':{'type':'network','subtype':'test_failure'}}),file=sys.stderr)
 raise SystemExit(1)
if mode=='offline': fail()
if action in ('+record-list','+record-get'):
 fields=[args[i+1] for i,a in enumerate(args) if a=='--field-id']
 rows=[]
 for ident,value in state['rows'].items():
  if action=='+record-get' and ident!=flag('--record-id'): continue
  if action=='+record-list':
   key,operator,expected=json.loads(flag('--filter-json'))['conditions'][0]
   assert operator=='=='
   if value.get(key)!=expected: continue
  rows.append({'record_id':ident,**{'label-'+f:value.get(f) for f in fields}})
 output=Path(flag('--output'));output.parent.mkdir(parents=True,exist_ok=True)
 output.write_text(''.join(json.dumps(row)+'\n' for row in rows))
 manifest={'manifest_version':'v1','has_more':mode=='truncated','records_count':len(rows),
           'columns':{'label-'+f:{'field_id':f} for f in fields}}
 output.with_suffix('.manifest.json').write_text(json.dumps(manifest))
 print(json.dumps(manifest))
elif action=='+record-batch-create':
 body=json.loads(flag('--json'))
 assert len(body['create_records'])==1
 state['creates']+=1;ident='rec-'+str(state['creates'])
 state['rows'][ident]=body['create_records'][0];save()
 if mode=='lost-create-reply': fail()
 print(json.dumps({'ok':True,'data':{'record_id_list':[ident]}}))
elif action=='+record-batch-update':
 body=json.loads(flag('--json'))
 for ident,fields in body['update_records'].items():
  if ident in state['rows'] and mode!='drop-update': state['rows'][ident].update(fields)
 state['updates']+=1;save()
 print(json.dumps({'ok':True,'data':{}}))
else: raise SystemExit('Unexpected action: '+action)
'''


class FeishuBoardTests(unittest.TestCase):
    run_cmd = test_workspace.WorkspaceTests.run_cmd
    tearDown = test_workspace.WorkspaceTests.tearDown

    def setUp(self):
        test_workspace.WorkspaceTests.setUp(self)
        script = self.fakebin / 'lark-cli'
        script.write_text('#!' + sys.executable + '\n' + FAKE_CLI)
        script.chmod(0o755)
        self.remote = self.base / 'remote.json'
        self.env['FAKE_BOARD'] = str(self.remote)
        self.fields = {key:'fld_'+key for key in ('key','task_id','title','workspace','status',
                                                'summary','lead','updated','conclusion','cost')}
        self.config = {'backend':'feishu','base_token':'base-test','table_id':'tbl-test',
                       'profile':'profile-hb','workspace_id':'workspace-test','fields':self.fields,
                       'statuses':{'running':'进行中','needs-input':'待输入','blocked':'阻塞','done':'完成'}}
        (self.root / '.agenthelm/config/board.json').write_text(json.dumps(self.config))
        self.task = self.root / 'experiments/001-board'
        self.task.mkdir()
        (self.task / 'README.md').write_text('# Board\n- id: 001-board\n- question: Track progress\n')

    def remote_state(self):
        return json.loads(self.remote.read_text())

    def test_statuses_update_one_record_and_conclusion(self):
        for state in self.config['statuses']:
            self.run_cmd('bin/status', state, 'quote " ; | progress\nnext', cwd=self.task)
            remote = self.remote_state()
            self.assertEqual(remote['creates'],1)
            row = remote['rows']['rec-1']
            self.assertEqual(row[self.fields['status']],[self.config['statuses'][state]])
            self.assertEqual(row[self.fields['summary']], 'quote " ; ｜ progress next')
            self.assertEqual(row[self.fields['title']], 'Track progress')
        with (self.task / 'README.md').open('a') as handle:
            handle.write('\n## Conclusion (2026-10-21)\n- **Tendency**: verified\n- **Confidence**: high\n')
        self.run_cmd('bin/board-sync','--all')
        self.assertIn('verified',self.remote_state()['rows']['rec-1'][self.fields['conclusion']])
        self.assertFalse((self.task / '.feishu-pending').exists())

    def test_offline_keeps_local_status_and_retry_clears_marker(self):
        failed_env = dict(self.env,FAKE_MODE='offline')
        result = self.run_cmd('bin/status','running','Local progress',cwd=self.task,env=failed_env)
        self.assertIn('local update succeeded',result.stderr)
        self.assertIn('Local progress',(self.task / 'STATUS').read_text())
        self.assertIn('001-board',(self.root / 'BOARD.md').read_text())
        self.assertTrue((self.task / '.feishu-pending').exists())
        self.assertIn('飞书待同步',(self.root / 'BOARD.md').read_text())
        self.run_cmd('bin/board-sync',self.task,env=failed_env,ok=False)
        self.run_cmd('bin/board-sync',self.task)
        self.assertFalse((self.task / '.feishu-pending').exists())
        self.assertNotIn('飞书待同步',(self.root / 'BOARD.md').read_text())
        self.assertEqual(self.remote_state()['creates'],1)

    def test_unknown_create_result_is_reconciled_before_retry(self):
        self.run_cmd('bin/status','running','Create reply lost',cwd=self.task,
                     env=dict(self.env,FAKE_MODE='lost-create-reply'))
        self.assertTrue((self.task / '.feishu-pending').exists())
        self.run_cmd('bin/board-sync',self.task)
        self.assertEqual(self.remote_state()['creates'],1)
        self.assertEqual(self.remote_state()['updates'],1)

    def test_duplicates_and_incomplete_queries_do_not_create(self):
        (self.task / 'STATUS').write_text('running | 001-board | Check |\n')
        key=self.fields['key']
        self.remote.write_text(json.dumps({'rows':{'rec-a':{key:'workspace-test:001-board'},
                         'rec-b':{key:'workspace-test:001-board'}},'creates':0,'updates':0}))
        self.run_cmd('bin/board-sync',self.task,ok=False)
        self.assertEqual(self.remote_state()['updates'],0)
        self.run_cmd('bin/board-sync',self.task,ok=False,env=dict(self.env,FAKE_MODE='truncated'))
        self.assertEqual(self.remote_state()['creates'],0)

    def test_success_without_applied_update_is_not_reported_verified(self):
        self.run_cmd('bin/status','running','Before',cwd=self.task)
        result=self.run_cmd('bin/status','done','After',cwd=self.task,
                            env=dict(self.env,FAKE_MODE='drop-update'))
        self.assertIn('readback does not match',result.stderr)
        self.assertTrue((self.task / '.feishu-pending').exists())
        self.assertEqual(self.remote_state()['rows']['rec-1'][self.fields['summary']],'Before')

    def test_parallel_sync_serializes_record_creation(self):
        (self.task / 'STATUS').write_text('running | 001-board | Parallel |\n')
        command=[str(self.root / 'bin/board-sync'),str(self.task)]
        processes=[subprocess.Popen(command,cwd=self.root,env=self.env,text=True,
                                    stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
        for process in processes:
            stdout,stderr=process.communicate(timeout=15)
            self.assertEqual(process.returncode,0,stdout+stderr)
        self.assertEqual(self.remote_state()['creates'],1)
        self.assertEqual(self.remote_state()['updates'],1)


if __name__=='__main__': unittest.main()
