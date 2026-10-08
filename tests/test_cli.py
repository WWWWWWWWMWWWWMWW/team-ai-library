import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from tests.core_helpers import entry,dump
from tests.git_helpers import create_remote


REPO=Path(__file__).resolve().parents[1]


def cli(*args):
    result=subprocess.run([sys.executable,str(REPO/'tools/library.py'),*map(str,args)],cwd=REPO,capture_output=True,text=True)
    return result,json.loads(result.stdout)


class CLITests(unittest.TestCase):
    def test_local_validate_needs_no_remote_and_does_not_execute_payload(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve();where=entry(root/'entry')
            result,row=cli('validate','--entry',where)
            self.assertEqual(result.returncode,0,row)
            self.assertEqual(row['state'],'prepared')
            self.assertEqual(row['operation'],'validate')

    def test_missing_configuration_is_blocked_json_not_traceback(self):
        with TemporaryDirectory() as d:
            result,row=cli('doctor','--config',Path(d)/'missing.json')
            self.assertEqual(result.returncode,2)
            self.assertEqual(row['code'],'CONFIG_MISSING')
            self.assertNotIn('Traceback',result.stderr)

    def test_invalid_arguments_do_not_echo_unknown_private_text(self):
        fixture_value='private-test-value-that-must-not-be-echoed'
        result,row=cli('search','--private-value',fixture_value)
        self.assertEqual(result.returncode,2)
        self.assertNotIn(fixture_value,result.stdout+result.stderr)

    def test_real_local_git_search_fetch_install_and_reuse(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve();work,remote,config=create_remote(root)
            config['target_profiles']={'trial':{'path':str(root/'installed'),'tool':'library-directory'}}
            path=root/'config.json';dump(path,config)
            result,row=cli('search','--config',path,'--query','Demo')
            self.assertEqual(result.returncode,0,row)
            self.assertEqual(row['data']['results'][0]['id'],'alice/demo')
            dest=root/'download'
            result,row=cli('fetch','--config',path,'--id','alice/demo','--version','1.0.0','--dest',dest)
            self.assertEqual(result.returncode,0,row);self.assertEqual(row['state'],'downloaded')
            self.assertTrue((dest/'download.json').exists())
            result,row=cli('install','--config',path,'--id','alice/demo','--version','1.0.0','--target','trial')
            self.assertEqual(result.returncode,0,row);self.assertEqual(row['state'],'installed')
            self.assertEqual(row['data']['installation_type'],'library-directory')
            self.assertFalse(row['data']['native_discovery_verified'])
            selection=root/'selection.json';context=root/'context.json'
            dump(selection,{'receipt_path':row['data']['receipt_path']})
            dump(context,{'task_scope':{'inputs':['text'],'outputs':['text'],'includes':['documentation'],'excludes':[]},'environment':{'os':'any','runtimes':{},'tools':['AI'],'capabilities':['filesystem.read']},'effects_authorized':['read_only']})
            result,row=cli('check-reuse','--config',path,'--selection',selection,'--context',context)
            self.assertEqual(result.returncode,0,row)
            self.assertEqual(row['state'],'prepared')
            self.assertFalse(row['data']['execution_authorized'])
            self.assertFalse(row['data']['business_verified'])

    def test_unknown_install_profile_blocks_without_touching_target(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve();work,remote,config=create_remote(root);path=root/'config.json';dump(path,config)
            result,row=cli('install','--config',path,'--id','alice/demo','--version','1.0.0','--target','unknown')
            self.assertEqual(result.returncode,2)
            self.assertEqual(row['code'],'CONFIG_MISSING')

    def test_unconfigured_example_does_not_claim_platform_ready(self):
        result,row=cli('doctor','--config',REPO/'library.example.json')
        self.assertEqual(result.returncode,2)
        self.assertEqual(row['code'],'CONFIG_MISSING')

    def test_connected_privacy_gate_blocks_doctor_search_fetch_and_install(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch
        from tools import library
        from tools.teamlib.contracts import TeamLibError
        with TemporaryDirectory() as d:
            root=Path(d).resolve()
            config={'schema_version':1,'remote':'https://github.com/company/library.git','shared_branch':'team','platform':'github','workspace':str(root/'cache'),'publish_mode':'request','auto_merge':False,'target_profiles':{'trial':{'path':str(root/'installed'),'tool':'library-directory'}}}
            path=root/'config.json';dump(path,config)
            commands=[['doctor'],['search','--query','Demo'],['fetch','--id','alice/demo','--version','1.0.0','--dest',str(root/'download')],['install','--id','alice/demo','--version','1.0.0','--target','trial']]
            for args in commands:
                with self.subTest(operation=args[0]),patch('tools.teamlib.platform.doctor_read',side_effect=TeamLibError('SCOPE_DENIED','Private membership not verified')):
                    output=io.StringIO()
                    with redirect_stdout(output):status=library.main(args+['--config',str(path)])
                    row=json.loads(output.getvalue())
                    self.assertEqual(status,2)
                    self.assertEqual(row['state'],'blocked')
                    self.assertEqual(row['code'],'SCOPE_DENIED')
            self.assertFalse((root/'cache').exists())
            self.assertFalse((root/'installed').exists())

    def test_doctor_reports_read_success_when_publishing_gate_is_missing(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch
        from tools import library
        from tools.teamlib.contracts import TeamLibError
        with TemporaryDirectory() as d:
            root=Path(d).resolve();_,_,config=create_remote(root);config['platform']='github'
            config['remote']='https://github.com/company/library.git';path=root/'config.json';dump(path,config)
            output=io.StringIO()
            with patch('tools.teamlib.snapshots.open_snapshot',return_value={'source_commit':'a'*40}),patch('tools.teamlib.platform.doctor_platform',side_effect=TeamLibError('SCOPE_DENIED','Protection unavailable')),redirect_stdout(output):
                status=library.main(['doctor','--config',str(path)])
            row=json.loads(output.getvalue());self.assertEqual(status,2)
            self.assertTrue(row['data']['readable']);self.assertFalse(row['data']['can_publish'])
            self.assertEqual(row['state'],'blocked');self.assertEqual(row['code'],'SCOPE_DENIED')

    def test_doctor_pull_only_account_does_not_claim_publishing_access(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch
        from tools import library
        with TemporaryDirectory() as d:
            root=Path(d).resolve();_,_,config=create_remote(root);config['platform']='github'
            config['remote']='https://github.com/company/library.git';path=root/'config.json';dump(path,config)
            output=io.StringIO()
            with patch('tools.teamlib.snapshots.open_snapshot',return_value={'source_commit':'a'*40}),patch('tools.teamlib.platform.doctor_platform',return_value={'permissions':{'pull':True,'push':False,'admin':False}}),redirect_stdout(output):
                status=library.main(['doctor','--config',str(path)])
            row=json.loads(output.getvalue());self.assertEqual(status,2)
            self.assertTrue(row['data']['readable']);self.assertFalse(row['data']['can_publish'])
            self.assertEqual(row['code'],'SCOPE_DENIED')

    def test_doctor_owner_trial_explicitly_reports_no_server_gate(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch
        from tools import library
        with TemporaryDirectory() as d:
            root=Path(d).resolve();_,_,config=create_remote(root);config['platform']='github'
            config['remote']='https://github.com/company/library.git';path=root/'config.json';dump(path,config)
            output=io.StringIO()
            checks={'permissions':{'pull':True,'push':True,'admin':True},'deployment_mode':'owner_trial','owner_trial':True,'protected':False,'hard_gate_enforced':False,'manual_review_required':True}
            with patch('tools.teamlib.snapshots.open_snapshot',return_value={'source_commit':'a'*40}),patch('tools.teamlib.platform.doctor_platform',return_value=checks),redirect_stdout(output):
                status=library.main(['doctor','--config',str(path)])
            row=json.loads(output.getvalue());self.assertEqual(status,0)
            self.assertTrue(row['data']['can_publish']);self.assertEqual(row['data']['deployment_mode'],'owner_trial')
            self.assertFalse(row['data']['hard_gate_enforced']);self.assertTrue(row['data']['manual_review_required'])
