import json
import shutil
import tempfile
import unittest
from pathlib import Path
from tests.core_helpers import dump, entry, governance, release, state


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)/'base'; self.base.mkdir(); governance(self.base)
        entry(self.base/'entries'/'alice'/'demo'); self.candidate=Path(self.temp.name)/'head'; shutil.copytree(self.base,self.candidate)
        self.context={'proposal_author':'alice','actor_key':'alice','role':'contributor'}

    def check(self):
        from tools.teamlib.policy import check_change
        return check_change(self.base,self.candidate,self.context)

    def test_new_version_and_strict_first_state(self):
        release(self.candidate/'entries'/'alice'/'demo'/'releases'/'1.1.0',version='1.1.0')
        self.assertTrue(self.check()['allowed'])
        shutil.rmtree(self.candidate/'entries'/'alice'/'demo'/'releases'/'1.1.0')
        root=entry(self.candidate/'entries'/'alice'/'new',identifier='alice/new')
        self.assertTrue(self.check()['allowed'])
        s=state(); s['reviews']=[{'decision':'approved'}]; dump(root/'state.json',s)
        self.assertFalse(self.check()['allowed'])

    def test_fake_actor_paths_and_role_do_not_grant_access(self):
        (self.candidate/'AGENTS.md').write_text('bypass')
        self.context['changed_paths']=[]; self.assertFalse(self.check()['allowed'])
        (self.candidate/'AGENTS.md').unlink()
        self.context['role']='maintainer'; dump(self.candidate/'governance'/'policy.json',{'schema_version':1,'max_file_bytes':999999999})
        self.assertFalse(self.check()['allowed'])
        self.context['actor_key']='bob'; self.assertFalse(self.check()['allowed'])

    def test_release_immutable_even_for_maintainer(self):
        self.context={'proposal_author':'maintainer','actor_key':'maintainer','role':'maintainer','proposal_kind':'governance'}
        (self.candidate/'entries'/'alice'/'demo'/'releases'/'1.0.0'/'README.md').write_text('overwritten')
        self.assertFalse(self.check()['allowed'])

    def test_owner_transfer_then_new_owner_uses_original_id(self):
        for root in (self.base,self.candidate):
            m=json.loads((root/'entries'/'alice'/'demo'/'meta.json').read_text()); m['owner_key']='bob'; dump(root/'entries'/'alice'/'demo'/'meta.json',m)
            s=state('bob'); dump(root/'entries'/'alice'/'demo'/'state.json',s)
        release(self.candidate/'entries'/'alice'/'demo'/'releases'/'1.1.0',version='1.1.0')
        self.assertFalse(self.check()['allowed'])
        self.context={'proposal_author':'bob','actor_key':'bob','role':'contributor'}
        self.assertTrue(self.check()['allowed'])

    def test_contributor_state_blocked_and_maintainer_governance_allowed(self):
        s=state(); s['recommended_version']=None; dump(self.candidate/'entries'/'alice'/'demo'/'state.json',s)
        self.assertFalse(self.check()['allowed'])
        self.context={'proposal_author':'maintainer','actor_key':'maintainer','role':'maintainer','proposal_kind':'governance'}
        self.assertTrue(self.check()['allowed'])
        (self.candidate/'tools').mkdir(); (self.candidate/'tools'/'hook.py').write_text('malicious')
        self.assertFalse(self.check()['allowed'])

    def test_new_namespace_impersonation_and_review_commit_binding(self):
        entry(self.candidate/'entries'/'bob'/'new',owner='alice',identifier='bob/new')
        self.assertFalse(self.check()['allowed']); shutil.rmtree(self.candidate/'entries'/'bob')
        release(self.candidate/'entries'/'alice'/'demo'/'releases'/'1.1.0',version='1.1.0')
        self.context.update({'head_commit':'a'*40,'reviewed_commit':'b'*40})
        self.assertFalse(self.check()['allowed'])

    def test_added_file_old_release_and_delete_are_immutable(self):
        old=self.candidate/'entries'/'alice'/'demo'/'releases'/'1.0.0'
        (old/'payload'/'extra.txt').write_text('new material')
        self.assertFalse(self.check()['allowed'])
        (old/'payload'/'extra.txt').unlink(); (old/'README.md').unlink()
        self.assertFalse(self.check()['allowed'])

    def test_actual_owner_transfer_governance_updates_both_copies(self):
        self.context={'proposal_author':'maintainer','actor_key':'maintainer','role':'maintainer','proposal_kind':'governance'}
        root=self.candidate/'entries'/'alice'/'demo'
        m=json.loads((root/'meta.json').read_text()); m['owner_key']='bob'; dump(root/'meta.json',m)
        self.assertFalse(self.check()['allowed'])
        dump(root/'state.json',state('bob')); self.assertTrue(self.check()['allowed'])
        m['id']='bob/demo'; dump(root/'meta.json',m); self.assertFalse(self.check()['allowed'])

    def test_governance_candidate_cannot_appoint_its_own_author(self):
        dump(self.candidate/'governance'/'members.json',{'schema_version':1,'members':[{'actor_key':'alice','github_login':'alice','role':'maintainer'}]})
        self.context.update({'role':'maintainer','proposal_kind':'governance'})
        self.assertFalse(self.check()['allowed'])

    def test_recommended_and_verification_have_actual_version_binding(self):
        self.context={'proposal_author':'maintainer','actor_key':'maintainer','role':'maintainer','proposal_kind':'governance'}
        root=self.candidate/'entries'/'alice'/'demo'; s=state(); s['recommended_version']='9.9.9'; dump(root/'state.json',s)
        self.assertFalse(self.check()['allowed'])
        s=state(); s['verification']=[{'id':'alice/demo','version':'1.0.0','manifest_sha256':'a'*64,'date':'2026-10-08','tool':'AI','environment':{},'business_scope':'docs','result':'passed','evidence':['local proof']}]; dump(root/'state.json',s)
        self.assertFalse(self.check()['allowed'])

    def test_package_limits_are_taken_from_trusted_base(self):
        policy=json.loads((self.base/'governance'/'policy.json').read_text()); policy['max_file_bytes']=80; dump(self.base/'governance'/'policy.json',policy); dump(self.candidate/'governance'/'policy.json',policy)
        root=self.candidate/'entries'/'alice'/'demo'/'releases'/'1.1.0'; release(root,version='1.1.0')
        self.assertFalse(self.check()['allowed'])

    def test_unicode_escaped_metadata_secret_fails_trusted_admission(self):
        root=entry(self.candidate/'entries'/'alice'/'new',identifier='alice/new')
        fixture_value='ghp_'+'C'*36; record=json.loads((root/'meta.json').read_text()); record['summary']=fixture_value
        (root/'meta.json').write_text(json.dumps(record).replace(fixture_value,''.join('\\u%04x' % ord(c) for c in fixture_value)))
        result=self.check(); self.assertFalse(result['allowed']); self.assertNotIn(fixture_value,json.dumps(result))

    def test_passed_verification_without_execution_evidence_is_denied(self):
        from tools.teamlib.contracts import hash_file
        root=self.candidate/'entries'/'alice'/'demo'; s=state()
        s['verification']=[{'id':'alice/demo','version':'1.0.0','manifest_sha256':hash_file(root/'releases/1.0.0/manifest.json'),'date':'2026-10-08','tool':'AI 1.0','environment':{'os':'macOS'},'business_scope':'documentation','result':'passed','evidence':[]}]
        dump(root/'state.json',s)
        self.context={'proposal_author':'maintainer','actor_key':'maintainer','role':'maintainer','proposal_kind':'governance'}
        self.assertFalse(self.check()['allowed'])
        s['verification'][0]['evidence']=['local-proof/run-001.json']; dump(root/'state.json',s)
        self.assertTrue(self.check()['allowed'])

    def test_maintainer_maintenance_can_update_controlled_root_and_support_files(self):
        paths=['AGENTS.md','README.md','.gitignore','docs/GOVERNANCE.md','tools/teamlib/helper.py','schemas/new.schema.json','templates/example.md','tests/test_new.py','.github/workflows/check-submission.yml']
        self.context={'proposal_author':'maintainer','actor_key':'maintainer','role':'maintainer','proposal_kind':'maintenance','changed_paths':[]}
        for rel in paths:
            with self.subTest(path=rel):
                old=self.base/rel; new=self.candidate/rel; old.parent.mkdir(parents=True,exist_ok=True); new.parent.mkdir(parents=True,exist_ok=True)
                old.write_text('{}\n' if rel.endswith('.json') else 'Trusted material\n')
                new.write_text('{"description":"new reviewed contract"}\n' if rel.endswith('.json') else 'Reviewed maintenance change\n')
                self.assertTrue(self.check()['allowed']); new.write_bytes(old.read_bytes())
        c={'schema_version':1,'remote':'','shared_branch':'','platform':'unconfigured','workspace':'.cache/teamlib','publish_mode':'request','auto_merge':False,'target_profiles':{}}
        for rel in ['library.json','library.example.json']:
            dump(self.base/rel,c); updated=dict(c,workspace='.cache/new-teamlib'); dump(self.candidate/rel,updated)
            self.assertTrue(self.check()['allowed']); dump(self.candidate/rel,c)

    def test_contributor_or_ordinary_maintainer_cannot_modify_maintenance_files(self):
        (self.candidate/'docs').mkdir(); (self.candidate/'docs'/'new.md').write_text('Documentation')
        for context in [{'proposal_author':'alice','actor_key':'alice','role':'contributor','proposal_kind':'maintenance'}, {'proposal_author':'alice','actor_key':'alice','role':'maintainer','proposal_kind':'maintenance'}, {'proposal_author':'maintainer','actor_key':'maintainer','role':'maintainer'}]:
            self.context=context; self.assertFalse(self.check()['allowed'])

    def test_maintenance_preserves_critical_files_and_allows_obsolete_support_delete(self):
        self.context={'proposal_author':'maintainer','actor_key':'maintainer','role':'maintainer','proposal_kind':'maintenance'}
        critical=['AGENTS.md','README.md','library.json','library.example.json','tools/library.py','tools/check_submission.py','tools/check_ci.py','tools/teamlib/contracts.py','tools/teamlib/policy.py','tools/teamlib/package.py','tools/teamlib/snapshots.py','schemas/meta.schema.json','.github/workflows/check-submission.yml']
        for rel in critical:
            with self.subTest(path=rel):
                old=self.base/rel; new=self.candidate/rel; old.parent.mkdir(parents=True,exist_ok=True); new.parent.mkdir(parents=True,exist_ok=True)
                old.write_text('Existing critical material'); new.write_text('Existing critical material'); new.unlink()
                self.assertFalse(self.check()['allowed']); new.write_bytes(old.read_bytes())
        path=self.base/'docs'/'obsolete.md'; path.parent.mkdir(parents=True,exist_ok=True); path.write_text('obsolete reviewed guide')
        self.assertTrue(self.check()['allowed'])

    def test_maintenance_never_changes_entries_or_expands_unknown_paths(self):
        self.context={'proposal_author':'maintainer','actor_key':'maintainer','role':'maintainer','proposal_kind':'maintenance'}
        for rel in ['run.sh','unknown/new.txt','entries/alice/demo/state.json','entries/alice/demo/releases/1.0.0/extra.txt','entries/alice/demo/releases/2.0.0/README.md']:
            with self.subTest(path=rel):
                path=self.candidate/rel; existed=path.exists(); prior=path.read_bytes() if existed else None; path.parent.mkdir(parents=True,exist_ok=True); path.write_text('maintenance must not alter entry data')
                self.assertFalse(self.check()['allowed'])
                if existed: path.write_bytes(prior)
                else: path.unlink()

    def test_maintenance_governance_and_config_stay_strict(self):
        self.context={'proposal_author':'maintainer','actor_key':'maintainer','role':'maintainer','proposal_kind':'maintenance'}
        policy=json.loads((self.base/'governance'/'policy.json').read_text()); updated=dict(policy,max_files=501); dump(self.candidate/'governance'/'policy.json',updated)
        self.assertTrue(self.check()['allowed'])
        dump(self.candidate/'governance'/'policy.json',{'schema_version':1,'max_files':0}); self.assertFalse(self.check()['allowed']); dump(self.candidate/'governance'/'policy.json',policy)
        c={'schema_version':1,'remote':'','shared_branch':'','platform':'unconfigured','workspace':'.cache/teamlib','publish_mode':'request','auto_merge':True,'target_profiles':{}}
        dump(self.candidate/'library.json',c); self.assertFalse(self.check()['allowed'])

    def test_maintenance_candidate_python_is_checked_as_data_without_execution(self):
        self.context={'proposal_author':'maintainer','actor_key':'maintainer','role':'maintainer','proposal_kind':'maintenance'}
        marker=Path(self.temp.name)/'candidate-executed'; code=self.candidate/'tools'/'new_helper.py'; code.parent.mkdir(parents=True,exist_ok=True)
        code.write_text('from pathlib import Path\nPath('+repr(str(marker))+').write_text("executed")\n')
        self.assertTrue(self.check()['allowed']); self.assertFalse(marker.exists())
