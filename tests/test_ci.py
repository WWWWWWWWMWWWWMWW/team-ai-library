import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from tests.core_helpers import dump,governance,entry,state
from tools.teamlib.contracts import TeamLibError
from tools.check_ci import prepare_context
from tools.check_submission import infer_proposal_kind
from tools.teamlib.policy import check_change
from tests.git_helpers import create_remote,publish_fixture
from tools.teamlib.snapshots import open_snapshot


class CITests(unittest.TestCase):
    def fixture(self,root):
        governance(root)
        dump(root/'governance/members.json',{'schema_version':1,'members':[{'actor_key':'alice','github_login':'alice-gh','role':'contributor'}]})
        dump(root/'library.json',{'shared_branch':'team'})
        row={'number':12,'user':{'login':'alice-gh','type':'User'},'base':{'ref':'team','sha':'a'*40,'repo':{'full_name':'company/library'}},'head':{'sha':'b'*40,'repo':{'full_name':'company/library'}}}
        return {'repository':{'full_name':'company/library'},'pull_request':row,'number':12},row

    def test_platform_author_mapped_from_base_not_candidate(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve();event,row=self.fixture(root)
            context=prepare_context(root,event,row)
            self.assertEqual(context['actor_key'],'alice')
            self.assertEqual(context['role'],'contributor')
            self.assertEqual(context['head_commit'],'b'*40)

    def test_changed_head_or_foreign_repo_cannot_reuse_check(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve();event,row=self.fixture(root)
            other=dict(row,head={'sha':'c'*40,'repo':{'full_name':'company/library'}})
            with self.assertRaises(TeamLibError):prepare_context(root,event,other)
            event,row=self.fixture(root);row['head']['repo']['full_name']='outsider/fork'
            with self.assertRaises(TeamLibError):prepare_context(root,event,row)

    def test_real_tracked_hidden_workflow_is_still_rejected(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve();work,remote,config=create_remote(root)
            base=Path(open_snapshot(config,root/'cache')['root'])
            entry(work/'entries/alice/new',identifier='alice/new')
            (work/'.github/workflows').mkdir(parents=True)
            (work/'.github/workflows/added.yml').write_text('malicious workflow data')
            (work/'.gitattributes').write_text('.gitattributes export-ignore\n.github export-ignore\n')
            publish_fixture(work)
            candidate=Path(open_snapshot(config,root/'cache')['root'])
            self.assertTrue((candidate/'.github/workflows/added.yml').exists())
            decision=check_change(base,candidate,{'actor_key':'alice','role':'contributor','proposal_author':'alice'})
            self.assertFalse(decision['allowed'])

    def test_actual_state_diff_routes_maintainer_and_rejects_contributor(self):
        with TemporaryDirectory() as d:
            root=Path(d).resolve();base=root/'base';base.mkdir();governance(base)
            entry(base/'entries/alice/demo');candidate=root/'candidate';shutil.copytree(base,candidate)
            dump(candidate/'entries/alice/demo/state.json',state(version=None))
            kind=infer_proposal_kind(base,candidate)
            self.assertEqual(kind,'governance')
            allowed=check_change(base,candidate,{'actor_key':'maintainer','role':'maintainer','proposal_author':'maintainer','proposal_kind':kind})
            denied=check_change(base,candidate,{'actor_key':'alice','role':'contributor','proposal_author':'alice','proposal_kind':kind})
            self.assertTrue(allowed['allowed'],allowed)
            self.assertFalse(denied['allowed'])

    def test_ci_api_targets_configured_github_host_despite_environment(self):
        import json,os,subprocess
        from unittest.mock import patch
        from tools.check_ci import _api
        def hosted(argv,**kwargs):
            host=argv[argv.index('--hostname')+1] if '--hostname' in argv else os.environ.get('GH_HOST','github.com')
            kwargs['stdout'].write(json.dumps({'host':host}).encode())
            return subprocess.CompletedProcess(argv,0)
        with patch.dict(os.environ,{'GH_HOST':'enterprise.invalid'}),patch('tools.check_ci.subprocess.run',side_effect=hosted):
            self.assertEqual(json.loads(_api('repos/company/library'))['host'],'github.com')
