import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.platform_helpers import GithubService, config, encoded, owner_trial_config
from tools.teamlib.contracts import TeamLibError


class OwnerTrialTests(unittest.TestCase):
    def setUp(self):
        from tools.teamlib import platform
        self.platform = platform
        self.service = GithubService()
        self.config = owner_trial_config(self.service)
        self.patch = patch.object(platform, 'run_command', self.service)
        self.patch.start(); self.addCleanup(self.patch.stop)

    def test_single_owner_trial_can_create_review_request_without_claiming_protection(self):
        result = self.platform.doctor_platform(self.config)
        self.assertEqual(result['deployment_mode'], 'owner_trial')
        self.assertTrue(result['owner_trial']); self.assertFalse(result['protected'])
        self.assertFalse(result['approval_required']); self.assertFalse(result['hard_gate_enforced'])
        self.assertTrue(result['manual_review_required']); self.assertEqual(result['role'], 'maintainer')
        self.assertTrue(result['permissions']['push']); self.assertTrue(result['permissions']['admin'])
        with tempfile.TemporaryDirectory() as d:
            body=Path(d)/'body.md'; body.write_text('Please review.\n<!-- teamlib-operation: '+'a'*32+' -->\n')
            created=self.platform.create_request(self.config,'teamlib/'+'a'*32,'Safe title',body)
            self.assertEqual(created['state'],'submitted'); self.assertTrue(created['owner_trial'])
            self.assertFalse(created['hard_gate_enforced']); self.assertTrue(created['manual_review_required'])
            self.assertTrue(self.platform.create_request(self.config,'teamlib/'+'a'*32,'Safe title',body)['owner_trial'])
        calls=[args for args,_ in self.service.calls if args[1]=='api']
        for endpoint in ('/collaborators?affiliation=all&per_page=100','/invitations?per_page=100'):
            matching=[args for args in calls if endpoint in args[2]]
            self.assertTrue(matching)
            self.assertTrue(all('--paginate' in args and '--slurp' in args for args in matching))
        self.assertFalse(any('/protection' in args[2] for args in calls))

    def test_trial_reports_actual_branch_protection(self):
        self.service.protected=True
        self.assertTrue(self.platform.doctor_platform(self.config)['protected'])

    def test_trial_is_rechecked_on_every_write_gate(self):
        self.platform.doctor_platform(self.config)
        self.service.invitation_pages=[[{'id':1}]]
        with self.assertRaises(TeamLibError): self.platform.doctor_platform(self.config)

    def test_direct_trial_config_is_complete_strict_data(self):
        for change in [{'auto_merge':0},{'extra':True},{'workspace':None},{'schema_version':True}]:
            with self.subTest(change=change), self.assertRaises(TeamLibError):
                self.platform.doctor_platform(dict(self.config,**change))
        for key in ('workspace','target_profiles','publish_mode','auto_merge'):
            incomplete=dict(self.config); del incomplete[key]
            with self.subTest(missing=key), self.assertRaises(TeamLibError): self.platform.doctor_platform(incomplete)

    def test_local_workspace_profile_differences_cannot_contain_credentials(self):
        local=dict(self.config,workspace='password'+'=FictitiousCredential12345')
        with self.assertRaises(TeamLibError): self.platform.doctor_platform(local)

    def test_unknown_branch_protection_data_is_not_reported_as_unprotected(self):
        original=self.service._gh
        for protected in (None,0,'false'):
            def bad_branch(args):
                value=original(args)
                if args[1]=='api' and '/branches/' in args[2]: value['protected']=protected
                return value
            with self.subTest(protected=protected), patch.object(self.service,'_gh',bad_branch), self.assertRaises(TeamLibError):
                self.platform.doctor_platform(self.config)

    def test_trial_governance_and_failed_request_results_keep_manual_review_status(self):
        from tests.core_helpers import dump
        with tempfile.TemporaryDirectory() as d:
            payload=Path(d)/'payload.json'
            dump(payload,{'operation_id':'b'*32,'id':'owner/demo','version':'1.0.0','reason':'Scope no longer applies'})
            first=self.platform.create_governance_request(self.config,'withdrawal',payload)
            second=self.platform.create_governance_request(self.config,'withdrawal',payload)
            self.assertTrue(first['owner_trial']); self.assertTrue(second['manual_review_required'])
            body=Path(d)/'body.md'; body.write_text('Please review.\n<!-- teamlib-operation: '+'a'*32+' -->\n')
            self.service.fail_create=True
            failed=self.platform.create_request(self.config,'teamlib/'+'a'*32,'Safe title',body)
            self.assertEqual(failed['state'],'prepared'); self.assertTrue(failed['owner_trial'])

    def test_trial_governance_body_exposes_review_boundary_and_roundtrips_on_retry(self):
        from tests.core_helpers import dump
        with tempfile.TemporaryDirectory() as d:
            payload=Path(d)/'payload.json'
            dump(payload,{'operation_id':'b'*32,'id':'owner/demo','version':'1.0.0','reason':'Scope no longer applies'})
            created=self.platform.create_governance_request(self.config,'withdrawal',payload)
            document=json.loads(self.platform._OPERATION.sub('',self.service.issues[0]['body']).strip())
            self.assertEqual(document['deployment'],{'deployment_mode':'owner_trial','owner_trial':True,'hard_gate_enforced':False,'manual_review_required':True})
            retry=self.platform.create_governance_request(self.config,'withdrawal',payload)
            self.assertEqual(retry['request_id'],created['request_id']); self.assertEqual(len(self.service.issues),1)
            read=self.platform.get_governance_request(self.config,created['request_id'])
            self.assertEqual(read['kind'],'withdrawal'); self.assertEqual(read['payload']['id'],'owner/demo')

    def test_owner_identity_and_permissions_fail_closed(self):
        baseline=copy.deepcopy(self.service.__dict__)
        for attribute,value in [('private',False),('owner',{'login':'acme','type':'Organization'}),('owner',{'login':'different','type':'User'}),('owner',{}),('login','different'),('permissions',{'pull':True,'push':True,'admin':False}),('permissions',{'pull':True,'push':False,'admin':True}),('permissions',{'pull':True,'push':'true','admin':True})]:
            self.service.__dict__.update(copy.deepcopy(baseline)); setattr(self.service,attribute,value)
            with self.subTest(attribute=attribute,value=value), self.assertRaises(TeamLibError): self.platform.doctor_platform(self.config)

    def test_collaborator_pages_reject_every_additional_actor_and_bad_data(self):
        owner=copy.deepcopy(self.service.collaborator_pages[0][0])
        for pages in [[], {}, [None], [owner], [[]], [[owner],[{'login':'bob','type':'User','permissions':{'pull':True}}]], [[owner],[{'login':'helper','type':'Bot'}]], [[owner],[owner]], [[dict(owner,type='Bot')]], [[dict(owner,login='other')]], [[dict(owner,permissions={'pull':True,'push':True,'admin':False})]]]:
            self.service.collaborator_pages=pages
            with self.subTest(pages=pages), self.assertRaises(TeamLibError): self.platform.doctor_platform(self.config)

    def test_invitation_pages_must_be_complete_and_empty(self):
        for pages in [[], {}, [None], [[{'id':1}]], [[],[{'id':2}]]]:
            self.service.invitation_pages=pages
            with self.subTest(pages=pages), self.assertRaises(TeamLibError): self.platform.doctor_platform(self.config)

    def test_api_and_pagination_failures_block_before_remote_write(self):
        original=self.service._gh
        for fragment in ('/collaborators?','/invitations?','/contents/library.json'):
            def broken(args):
                if args[1]=='api' and fragment in args[2]: raise subprocess.TimeoutExpired(args,1)
                return original(args)
            with self.subTest(fragment=fragment), patch.object(self.service,'_gh',broken), self.assertRaises(TeamLibError):
                self.platform.doctor_platform(self.config)
        self.assertFalse(any(args[1:3]==['pr','create'] for args,_ in self.service.calls))

    def test_trusted_mapping_must_have_only_the_owner_maintainer(self):
        owner=copy.deepcopy(self.service.members['members'][0])
        for rows in [[],[dict(owner,role='contributor')],[dict(owner,github_login='other')],[owner,dict(owner,actor_key='reader',github_login='reader')],[owner,owner],[dict(owner,extra=True)]]:
            self.service.members={'schema_version':1,'members':rows}
            with self.subTest(rows=rows), self.assertRaises(TeamLibError): self.platform.doctor_platform(self.config)
        self.service.members={'schema_version':True,'members':[owner]}
        with self.assertRaises(TeamLibError): self.platform.doctor_platform(self.config)

    def test_shared_config_must_match_security_fields_and_be_strict(self):
        baseline=copy.deepcopy(self.service.shared_config)
        for change in [{'remote':'git@github.com:acme/library.git'},{'shared_branch':'other'},{'platform':'local'},{'publish_mode':'direct'},{'auto_merge':True},{'deployment_mode':'protected'},{'deployment_mode':'unknown'},{'extra':'value'},{'schema_version':True},{'target_profiles':{'demo':{'path':'install','unknown':'data'}}}]:
            self.service.shared_config=dict(baseline,**change)
            with self.subTest(change=change), self.assertRaises(TeamLibError): self.platform.doctor_platform(self.config)
        self.service.shared_config=dict(baseline); del self.service.shared_config['deployment_mode']
        with self.assertRaises(TeamLibError): self.platform.doctor_platform(self.config)

    def test_shared_workspace_profiles_may_differ_without_credentials(self):
        self.service.shared_config.update(workspace='.cache/other',target_profiles={'demo':{'path':'installed/demo','tool':'codex'}})
        self.assertTrue(self.platform.doctor_platform(self.config)['owner_trial'])
        self.service.shared_config['target_profiles']['demo']['tool']='password'+'=FictitiousCredential12345'
        with self.assertRaises(TeamLibError): self.platform.doctor_platform(self.config)

    def test_shared_config_duplicate_keys_non_json_and_constants_are_rejected(self):
        baseline=json.dumps(self.service.shared_config)
        original=self.service._gh
        for text in [baseline[:-1]+',"deployment_mode":"owner_trial"}',baseline.replace('false','NaN'), 'raise Exception("must never execute")']:
            def bad_json(args):
                if args[1]=='api' and '/contents/library.json' in args[2]: return encoded(text)
                return original(args)
            with self.subTest(text_kind=text[:20]), patch.object(self.service,'_gh',bad_json), self.assertRaises(TeamLibError):
                self.platform.doctor_platform(self.config)

    def test_trial_read_gate_still_accepts_other_registered_readers_without_push(self):
        self.service.login='reader'
        self.service.members['members'].append({'actor_key':'reader','github_login':'reader','role':'contributor'})
        self.service.permissions={'pull':True,'push':False,'admin':False}
        self.assertEqual(self.platform.doctor_read(self.config)['actor_key'],'reader')
        with self.assertRaises(TeamLibError): self.platform.doctor_platform(self.config)
        self.assertFalse(any('/collaborators?' in args[2] for args,_ in self.service.calls if args[1]=='api'))

    def test_protected_default_cannot_be_enabled_by_shared_trial(self):
        for mode in ({},{'deployment_mode':'protected'}):
            protected=dict(self.config,**mode)
            if not mode: del protected['deployment_mode']
            with self.assertRaises(TeamLibError): self.platform.doctor_platform(protected)

    def test_direct_adapter_rejects_unknown_trial_modes_and_non_github(self):
        for change in [{'deployment_mode':'unexpected'},{'deployment_mode':None},{'platform':'local'},{'platform':'unconfigured'},{'publish_mode':'direct'},{'auto_merge':True}]:
            with self.subTest(change=change), self.assertRaises(TeamLibError): self.platform.doctor_platform(dict(self.config,**change))
