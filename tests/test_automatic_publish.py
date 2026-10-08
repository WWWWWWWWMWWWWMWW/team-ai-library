import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.platform_helpers import GithubService, owner_trial_config
from tools.teamlib.contracts import TeamLibError


class AutomaticPublishTests(unittest.TestCase):
    def setUp(self):
        from tools.teamlib import platform
        self.platform = platform
        self.service = GithubService()
        self.config = owner_trial_config(self.service)
        self.config.update(review_mode='automatic', auto_merge=True)
        self.service.shared_config = dict(self.config)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        body = Path(self.temp.name) / 'body.md'
        body.write_text('自动检查后入库\n<!-- teamlib-operation: ' + 'a' * 32 + ' -->\n')
        # Seed the external PR, retaining real parsing and provenance checks.
        self.service._gh(['gh','pr','create','--head','teamlib/'+'a'*32,'--title','上传测试能力','--body-file',str(body)])
        row = self.service.requests[0]
        self.expected = dict(platform._safe_request('acme/library', row), head_commit=row['headRefOid'], source_branch=row['headRefName'])
        self.check = {'name':'team-library-policy','status':'completed','conclusion':'success',
                      'app':{'slug':'github-actions'},'details_url':'https://github.com/acme/library/actions/runs/7/job/8'}
        self.merges = []
        self.changed = False
        self.mutate_during_check = False
        original = self.service._gh
        def gh(args):
            if args[1]=='api' and '/check-runs' in args[2]:
                if self.mutate_during_check: self.service.requests[0]['headRefOid']='b'*40
                return {'total_count':1,'check_runs':[self.check]}
            if args[1]=='api' and '/actions/runs/7' in args[2]:
                return {'event':'pull_request_target','path':'.github/workflows/check-submission.yml',
                        'head_sha':self.expected['head_commit'],'status':'completed','conclusion':'success',
                        'repository':{'full_name':'acme/library'}}
            if args[1:3]==['pr','merge']:
                self.merges.append(args)
                self.assertEqual(args[args.index('--match-head-commit')+1],self.service.requests[0]['headRefOid'])
                self.service.requests[0].update(state='MERGED',mergedAt='2026-10-08T00:00:00Z',mergeCommit={'oid':'c'*40})
                return ''
            return original(args)
        self.service._gh = gh
        p = patch.object(platform,'run_command',self.service); p.start(); self.addCleanup(p.stop)

    def test_legacy_owner_trial_baseline_without_policy_fields_is_automatic(self):
        config = dict(self.config, auto_merge=False)
        config.pop('review_mode')
        self.service.shared_config = dict(config)
        result = self.platform.doctor_platform(config)
        self.assertFalse(result['manual_review_required'])
        self.assertTrue(result['auto_merge'])

    def test_current_policy_automatically_merges_checked_exact_request(self):
        result = self.platform.merge_checked_request(self.config,self.expected)
        self.assertEqual(result['platform_state'],'MERGED')
        self.assertFalse(result['manual_review_required'])
        self.assertEqual(len(self.merges),1)

    def test_pending_failed_missing_or_impostor_check_does_not_merge(self):
        original=copy.deepcopy(self.check)
        for change in [{'status':'in_progress','conclusion':None},{'conclusion':'failure'},
                       {'name':'unrelated'},{'app':{'slug':'other'}},
                       {'details_url':'https://github.com/foreign/repo/actions/runs/7/job/8'}]:
            self.check=dict(original,**change)
            with self.subTest(change=change), self.assertRaises(TeamLibError):
                self.platform.merge_checked_request(self.config,self.expected)
        self.assertEqual(self.merges,[])

    def test_changed_title_body_or_head_cannot_reuse_old_checks(self):
        original=copy.deepcopy(self.service.requests[0])
        for change in [{'title':'换了内容'},{'body':'换了内容'},{'headRefOid':'b'*40}]:
            self.service.requests[0]=dict(original,**change)
            with self.subTest(change=change), self.assertRaises(TeamLibError):
                self.platform.merge_checked_request(self.config,self.expected)
        self.assertEqual(self.merges,[])

    def test_head_changed_while_reading_checks_does_not_merge(self):
        self.mutate_during_check=True
        with self.assertRaises(TeamLibError): self.platform.merge_checked_request(self.config,self.expected)
        self.assertEqual(self.merges,[])

    def test_local_automatic_switch_cannot_override_shared_policy(self):
        self.service.shared_config.update(review_mode='manual',auto_merge=False)
        with self.assertRaises(TeamLibError): self.platform.merge_checked_request(self.config,self.expected)
        self.assertEqual(self.merges,[])

    def test_legacy_manual_policy_does_not_merge(self):
        self.config.update(review_mode='manual',auto_merge=False)
        self.service.shared_config=dict(self.config)
        with self.assertRaises(TeamLibError): self.platform.merge_checked_request(self.config,self.expected)
        self.assertEqual(self.merges,[])
