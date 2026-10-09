"""Package a read-only offline page using one validated shared snapshot."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from .catalog import build_catalog, KINDS, LABELS
from .contracts import TeamLibError, ensure_no_symlinks, _open_regular, read_json
from .package import scan_text, validate_release

MARKER='<!-- teamlib-local-web: generated -->'
TEMPLATE=Path(__file__).resolve().parents[2]/'templates/local-web-shell.html'
TEXT_EXTENSIONS={'.md','.txt','.rst','.csv','.json'}
MAX_TEXT_BYTES=128*1024
MAX_PAGE_BYTES=5*1024*1024


def build_web_record(snapshot, catalog):
    """Recheck bindings before adding any displayed text; never read checkout bodies."""
    expected=build_catalog(snapshot,pending=catalog.get('pending_requests'),
                           pending_status=catalog.get('pending_status','not_checked'))
    if expected != catalog:
        raise TeamLibError('STATUS_UNVERIFIED','Web data must match the same approved catalog snapshot.')
    record=deepcopy(catalog)
    record['generated_at']=datetime.now(timezone.utc).isoformat(timespec='seconds')
    record['kinds']=dict(KINDS); record['labels']=dict(LABELS)
    root=ensure_no_symlinks(Path(snapshot['root']))
    members=read_json(root/'governance/members.json').get('members',[])
    names={}
    names_path=root/'docs/contributor-names.json'
    if names_path.exists():
        registry=read_json(names_path)
        if set(registry)!={'schema_version','names'} or registry['schema_version']!=1 or not isinstance(registry['names'],dict):
            raise TeamLibError('INVALID_PACKAGE','Contributor display name registry is invalid.')
        for login,name in registry['names'].items():
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*',login) or not isinstance(name,str) or not name.strip() or name!=name.strip() or len(name)>80 or any(ord(c)<32 for c in name) or login.casefold() in names:
                raise TeamLibError('INVALID_PACKAGE','Contributor display name is invalid or duplicated.')
            names[login.casefold()]=name
    record['member_labels']={row['actor_key']:names.get(row['github_login'].casefold(),row['github_login']) for row in members
                             if isinstance(row,dict) and isinstance(row.get('actor_key'),str)
                             and isinstance(row.get('github_login'),str)}
    policy=read_json(root/'governance/policy.json')
    for row in record['releases']:
        prefix=f"entries/{row['id']}/releases/{row['version']}/"
        folder=ensure_no_symlinks(root/prefix)
        manifest=validate_release(folder,policy=policy)
        with _open_regular(folder/'manifest.json') as stream:
            digest=hashlib.sha256(stream.read()).hexdigest()
        if digest != row['manifest_sha256']:
            raise TeamLibError('STATUS_UNVERIFIED','Web manifest changed while packaging.')
        inventory={prefix+item['path']:item for item in manifest['files']}
        materials=[]
        for path in dict.fromkeys([row['readme'],*row['entrypoints']]):
            item=inventory[path]
            material={'path':path,'sha256':item['sha256'],'size':item['size'],'displayable':False}
            # Read a bounded eligible file only. Scripts and binary formats remain references.
            if Path(path).suffix.lower() not in TEXT_EXTENSIONS:
                material['reason']='这类入口不在网页内展示，由 AI 按准确版本获取完整材料；网页不执行脚本。'
            elif item['size']>MAX_TEXT_BYTES:
                material['reason']='说明超过网页单文件展示上限，未截断或改写；让 AI 获取完整材料。'
            else:
                with _open_regular(root/path) as stream: raw=stream.read(MAX_TEXT_BYTES+1)
                if len(raw)!=item['size'] or hashlib.sha256(raw).hexdigest()!=item['sha256']:
                    raise TeamLibError('STATUS_UNVERIFIED','Web material changed while packaging.')
                try: text=raw.decode('utf-8')
                except UnicodeError: text=None
                if text is None or any(ord(char)<32 and char not in '\r\n\t' for char in text):
                    material['reason']='此入口不是可安全展示的 UTF-8 文本，请让 AI 核对并获取完整材料。'
                else:
                    scan_text(text,'local_web_material')
                    material.update(displayable=True,text=text)
            materials.append(material)
        row['materials']=materials
        # This label is grounded in the actual source declaration, never guessed from ID.
        row['is_example']='内置示例' in row['source'].get('reference','')
    return record


def render_web(record, *, template=TEMPLATE):
    shell=ensure_no_symlinks(template).read_text(encoding='utf-8')
    if shell.count('__TEAMLIB_DATA__') != 1:
        raise TeamLibError('INVALID_PACKAGE','Local web template must contain exactly one data slot.')
    encoded=json.dumps(record,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    # Escape even inside a JSON script block: HTML tokenization precedes JSON decoding.
    for character,escaped in [('&',r'\u0026'),('<',r'\u003c'),('>',r'\u003e'),('\u2028',r'\u2028'),('\u2029',r'\u2029')]:
        encoded=encoded.replace(character,escaped)
    page=MARKER+'\n'+shell.replace('__TEAMLIB_DATA__',encoded)
    if len(page.encode('utf-8'))>MAX_PAGE_BYTES:
        raise TeamLibError('INVALID_PACKAGE','Local web page exceeds its safe output budget.')
    scan_text(page,'local_web_html')
    return page
