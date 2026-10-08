import json
import tempfile
import unittest
from pathlib import Path
from tests.core_helpers import manifest, meta, state


class ContractTests(unittest.TestCase):
    def test_valid_version_and_leading_zero_rejected(self):
        from tools.teamlib.contracts import validate_version, TeamLibError
        validate_version('1.10.0')
        for value in ['01.0.0', 'latest', '1.0', '1.0.0-beta', True]:
            with self.subTest(value=value), self.assertRaises(TeamLibError):
                validate_version(value)

    def test_required_shapes_unknown_fields_and_binding(self):
        from tools.teamlib.contracts import validate_record, TeamLibError
        for kind, record in [('meta', meta()), ('manifest', manifest()), ('state', state())]:
            validate_record(kind, record)
        for kind, record in [('manifest', manifest()), ('meta', meta()), ('state', state())]:
            record['verified'] = True
            with self.assertRaises(TeamLibError):
                validate_record(kind, record)
        broken = manifest(); del broken['scope']
        with self.assertRaises(TeamLibError): validate_record('manifest', broken)
        broken = meta(); broken['author_key'] = 'bob'
        with self.assertRaises(TeamLibError): validate_record('meta', broken)
        broken = state(); broken['withdrawn_versions'] = ['1.0.0']
        with self.assertRaises(TeamLibError): validate_record('state', broken)
        broken = state(); broken['verification'] = [{'result': 'verified'}]
        with self.assertRaises(TeamLibError): validate_record('state', broken)

    def test_json_atomic_roundtrip_and_no_symlinks(self):
        from tools.teamlib.contracts import read_json, write_json, hash_file, TeamLibError
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); p = root / 'record.json'
            write_json(p, {'schema_version': 1}); self.assertEqual(read_json(p), {'schema_version': 1})
            self.assertEqual(len(hash_file(p)), 64)
            q = root / 'link.json'; q.symlink_to(p)
            for fn in (read_json, hash_file):
                with self.assertRaises(TeamLibError): fn(q)
            with self.assertRaises(TeamLibError): write_json(q, {'changed': True})
            p.write_text('{"a":1,'+'"a":2}')
            with self.assertRaises(TeamLibError): read_json(p)

    def test_inventory_portable_and_digest_constraints(self):
        from tools.teamlib.contracts import validate_record, TeamLibError
        for path in ['../fixture_value', '/tmp/a', 'payload\\file', 'payload/./file', 'payload//file', 'payload/C:drive', 'payload/CON']:
            broken = manifest(); broken['entrypoints'] = [path]
            with self.subTest(path=path), self.assertRaises(TeamLibError): validate_record('manifest', broken)
        broken = manifest(); broken['dependencies'] = [{'id':'alice/demo','version':'1.0.0','manifest_sha256':'short'}]
        with self.assertRaises(TeamLibError): validate_record('manifest', broken)

    def test_adaptation_requires_exact_original_binding(self):
        from tools.teamlib.contracts import validate_record, TeamLibError
        m=meta(); m['source']={'type':'adapted','reference':'some source'}
        with self.assertRaises(TeamLibError): validate_record('meta',m)

    def test_receipt_and_run_require_accurate_material_sources(self):
        from tools.teamlib.contracts import validate_record, TeamLibError
        receipt={'schema_version':1,'installation_id':'example','repository':'/private/tmp/library.git','shared_branch':'approved','source_commit':'a'*40,'id':'alice/demo','version':'1.0.0','manifest_sha256':'b'*64,'dependency_lock':[],'target':'/private/tmp/target','baseline':'/private/tmp/baseline','files':[],'local_changes':[],'installed_at':'2026-10-08T12:00:00Z','receipt_path':'/private/tmp/receipt.json','releases':[{'id':'alice/demo','version':'1.0.0','manifest_sha256':'b'*64,'path':'releases/alice/demo/1.0.0'}],'baseline_files':[]}
        validate_record('receipt',receipt)
        for key in ['source_commit','manifest_sha256','baseline']:
            broken=dict(receipt); broken.pop(key)
            with self.assertRaises(TeamLibError): validate_record('receipt',broken)
        run={'schema_version':1,'run_id':'example','started_at':'2026-10-08T12:00:00Z','finished_at':'2026-10-08T12:01:00Z','sources':[{'repository':'local','id':'alice/demo','version':'1.0.0','manifest_sha256':'b'*64,'source_commit':'a'*40}],'task_goal':'write docs','environment':{},'result':'unverified','artifacts':[],'change_summary':'no changes','unverified':['business validity']}
        validate_record('run',run); run['sources'][0].pop('manifest_sha256')
        with self.assertRaises(TeamLibError): validate_record('run',run)

    def test_receipt_release_paths_baseline_and_lock_cannot_diverge(self):
        from tools.teamlib.contracts import validate_record, TeamLibError
        base={'schema_version':1,'installation_id':'example','repository':'local','shared_branch':'approved','source_commit':'a'*40,'id':'alice/demo','version':'1.0.0','manifest_sha256':'b'*64,'dependency_lock':[],'target':'/private/tmp/target','baseline':'/private/tmp/baseline','files':[],'local_changes':[],'installed_at':'2026-10-08T12:00:00Z','receipt_path':'/private/tmp/receipt.json','releases':[{'id':'alice/demo','version':'1.0.0','manifest_sha256':'b'*64,'path':'releases/alice/demo/1.0.0'}],'baseline_files':[]}
        for mode in ['release_path','baseline_path','root_hash','dependency_lock']:
            import copy
            record=copy.deepcopy(base)
            if mode=='release_path': record['releases'][0]['path']='../outside'
            if mode=='baseline_path': record['baseline_files']=[{'path':'../outside','sha256':'c'*64,'size':1}]
            if mode=='root_hash': record['releases'][0]['manifest_sha256']='c'*64
            if mode=='dependency_lock': record['dependency_lock']=[{'id':'alice/other','version':'1.0.0','manifest_sha256':'d'*64}]
            with self.subTest(mode=mode), self.assertRaises(TeamLibError): validate_record('receipt',record)

    def test_executed_verification_requires_evidence_date_versioned_tool_and_environment(self):
        from tools.teamlib.contracts import validate_record, read_json, _schema_check, TeamLibError
        import copy
        row={'id':'alice/demo','version':'1.0.0','manifest_sha256':'b'*64,'date':'2026-10-08','tool':'AI 1.0','environment':{'os':'macOS'},'business_scope':'documentation','result':'passed','evidence':['local-proof/run-001.json']}
        record=state(); record['verification']=[row]; validate_record('state',record)
        schema=read_json(Path(__file__).resolve().parents[1]/'schemas/state.schema.json')
        for change in [{'evidence':[]},{'evidence':['  ']},{'environment':{}},{'environment':{'os':''}},{'tool':'AI'},{'tool':' '},{'date':'yesterday'},{'date':'2026-02-31'}]:
            broken=copy.deepcopy(record); broken['verification'][0].update(change)
            with self.subTest(change=change), self.assertRaises(TeamLibError): validate_record('state',broken)
            with self.subTest(schema_change=change), self.assertRaises(TeamLibError): _schema_check(schema,broken)
        failed=copy.deepcopy(record); failed['verification'][0].update(result='failed',evidence=[])
        with self.assertRaises(TeamLibError): validate_record('state',failed)
        unverified=copy.deepcopy(record); unverified['verification'][0].update(result='unverified',evidence=[],environment={})
        validate_record('state',unverified)

    def test_schema_and_runtime_agree_on_basic_portable_paths(self):
        from tools.teamlib.contracts import validate_record, read_json, _schema_check, TeamLibError
        schema=read_json(Path(__file__).resolve().parents[1]/'schemas/manifest.schema.json')
        for path in ['../private','/private/file','payload\\file','payload/./file','payload//file','payload/C:drive','payload/CON','payload/con.md','payload/a.','payload/a ']:
            record=manifest(); record['entrypoints']=[path]
            with self.subTest(path=path), self.assertRaises(TeamLibError): _schema_check(schema,record)
            with self.assertRaises(TeamLibError): validate_record('manifest',record)
