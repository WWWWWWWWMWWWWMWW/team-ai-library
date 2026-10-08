"""Generate synthetic offline pages for browser regression checks, never shared entries."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sys
from tests.core_helpers import entry, release, dump, state, governance
from tools.teamlib.catalog import build_catalog
from tools.teamlib.local_web import build_web_record, render_web
from tools.teamlib.contracts import hash_file


def fixtures(output):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory() as temp:
        root=Path(temp).resolve(); governance(root)
        where=entry(root/'entries/alice/demo')
        def material(folder,text):
            path=folder/'README.md'; path.write_text(text)
            manifest=json.loads((folder/'manifest.json').read_text())
            for item in manifest['files']:
                if item['path']=='README.md': item.update(size=path.stat().st_size,sha256=hash_file(path))
            dump(folder/'manifest.json',manifest)
        material(where/'releases/1.0.0','旧版专属词 测试说明\n</script><script>window.webInjected=true</script>\n<img src="https://example.test/should-not-load">')
        release(where/'releases/2.0.0',version='2.0.0')
        dump(where/'state.json',state(version='2.0.0'))
        meta=json.loads((where/'meta.json').read_text()); meta.update(title='多版本测试能力',summary='用于浏览器验收的合成材料',aliases=['测试能力']); dump(where/'meta.json',meta)
        meta['source']={'type':'adapted','reference':'合成改编样例','license':'仅限合成验收','derived_from':{'repository':'https://github.com/example/original.git','id':'bob/original','version':'3.0.0','manifest_sha256':'d'*64,'source_commit':'c'*40}}; dump(where/'meta.json',meta)
        for slug,availability in [('withdrawn','withdrawn'),('revoked','revoked'),('blocked','blocked_dependency')]:
            item=entry(root/f'entries/alice/{slug}',identifier=f'alice/{slug}')
            meta=json.loads((item/'meta.json').read_text()); meta['title']={'withdrawn':'撤回测试能力','revoked':'作废测试能力','blocked':'依赖停用测试能力'}[slug]; dump(item/'meta.json',meta)
            if availability=='withdrawn':
                status=state(version=None); status['withdrawn_versions']=['1.0.0']; dump(item/'state.json',status)
        dump(root/'governance/revocations.json',{'schema_version':1,'revocations':[{'id':'alice/revoked','version':'1.0.0','reason':'合成测试材料作废'}]})
        manifest_path=root/'entries/alice/blocked/releases/1.0.0/manifest.json'
        manifest=json.loads(manifest_path.read_text()); manifest['dependencies']=[{'id':'alice/withdrawn','version':'1.0.0','manifest_sha256':hash_file(root/'entries/alice/withdrawn/releases/1.0.0/manifest.json')}]; dump(manifest_path,manifest)
        status=state(version='2.0.0'); digest=hash_file(where/'releases/2.0.0/manifest.json')
        status['verification']=[{'id':'alice/demo','version':'2.0.0','manifest_sha256':digest,'date':'2026-10-08','tool':'合成工具 1.0','environment':{'os':'macos'},'business_scope':'合成样例中的审查','result':result,'evidence':['合成通过记录' if result=='passed' else '合成失败记录']} for result in ('passed','failed')]
        dump(where/'state.json',status)
        snapshot={'root':str(root),'source_commit':'a'*40,'repository':'https://github.com/example/team.git','shared_branch':'main'}
        pending=[{'number':3,'kind':'publication','ids':['bob/pending'],'head_commit':'b'*40,'url':'https://github.com/example/team/pull/3'},
                 {'number':4,'kind':'maintenance','ids':[],'head_commit':'c'*40,'url':'https://github.com/example/team/pull/4'}]
        def save(name,pending_status='available'):
            catalog=build_catalog(snapshot,pending=pending if pending_status=='available' else [],pending_status=pending_status)
            (output/name).write_text(render_web(build_web_record(snapshot,catalog)),encoding='utf-8')
        save('versions.html')
        dump(where/'state.json',state(version=None)); save('no-recommendation.html')
        save('pending-unavailable.html','unavailable')
        for child in (root/'entries').iterdir():
            import shutil
            shutil.rmtree(child)
        save('empty.html')
    return output


if __name__=='__main__': print(fixtures(sys.argv[1]))
