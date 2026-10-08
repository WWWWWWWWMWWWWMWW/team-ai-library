"""Complete release inventory and pre-network inspection. Never executes payload."""
import os
import json
import re
import stat
from pathlib import Path
from .contracts import TeamLibError, read_json, hash_file, validate_record, validate_version, safe_relative, ensure_no_symlinks, _open_regular, _pairs

DEFAULT_LIMITS = {'max_file_bytes': 5 * 1024 * 1024, 'max_release_bytes': 20 * 1024 * 1024, 'max_files': 500, 'opaque_shares': []}
SECRET_PATTERNS = [
    re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|ASIA[A-Z0-9]{16})\b'),
    re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b'),
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----'),
    re.compile(r'(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|token)\b["\']?\s*[:=]\s*["\']?([A-Za-z0-9_+/=-]{8,})'),
    re.compile(r'https?://[^\s/:]+:[^\s/@]+@'),
    re.compile(r'\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b'),
]
OPAQUE_EXTENSIONS = {'.png','.jpg','.jpeg','.gif','.webp','.pdf','.mp3','.mp4','.mov','.wav','.woff','.woff2','.ttf','.bin','.exe','.dylib','.so','.dll'}
ARCHIVES = {'.zip','.gz','.bz2','.xz','.tar','.7z','.rar','.jar','.whl'}
PLACEHOLDERS = {'REDACTED','PLACEHOLDER','EXAMPLE_VALUE','YOUR_TOKEN','YOUR_API_KEY','CHANGEME','NOT_A_SECRET'}


def _scan_raw(text, location):
    """Reusable for request titles/branch names/history; errors omit matched text."""
    if not isinstance(text, str):
        raise TeamLibError('INVALID_PACKAGE', 'Outbound text must be a string.')
    for pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            if match.lastindex and match.group(1).upper() in PLACEHOLDERS: continue
            raise TeamLibError('INVALID_PACKAGE', 'Secret-like outbound text was blocked.', {'category':'secret_like_text','location':location})


def scan_json(value, location='json_material'):
    """Check decoded JSON keys, scalar strings, and key/value associations."""
    stack=[value]
    while stack:
        item=stack.pop()
        if isinstance(item,dict):
            for key, child in item.items():
                _scan_raw(key,location)
                stack.append(child)
        elif isinstance(item,list): stack.extend(item)
        elif isinstance(item,str): _scan_raw(item,location)
    try: canonical=json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    except (ValueError,TypeError,RecursionError):
        raise TeamLibError('INVALID_PACKAGE','Outbound JSON could not be checked.') from None
    _scan_raw(canonical,location)


def scan_text(text, location='text'):
    """Scan raw text and valid JSON, including JSON fragments in request prose."""
    _scan_raw(text,location)
    decoder=json.JSONDecoder(object_pairs_hook=_pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    index=0
    starts=re.compile(r'[\[{"]')
    try:
        while index < len(text):
            match=starts.search(text,index)
            if match is None: break
            index=match.start()
            try: value,end=decoder.raw_decode(text,index)
            except (json.JSONDecodeError,ValueError): index+=1; continue
            scan_json(value,location)
            index=end
    except RecursionError:
        raise TeamLibError('INVALID_PACKAGE','Outbound JSON exceeds supported nesting.') from None


def _limits(policy=None):
    path = Path(__file__).resolve().parents[2] / 'governance' / 'policy.json'
    policy = (read_json(path) if path.exists() else dict(DEFAULT_LIMITS)) if policy is None else policy
    for key in ('max_file_bytes','max_release_bytes','max_files'):
        if type(policy.get(key)) is not int or policy[key] <= 0:
            raise TeamLibError('INVALID_PACKAGE', 'Trusted package limits are invalid.')
    return policy


def tree_files(root):
    root = ensure_no_symlinks(root)
    if not root.is_dir(): raise TeamLibError('INVALID_PACKAGE', 'Material root must be a directory.')
    paths = []
    case_names = set()
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            rel = path.relative_to(root).as_posix()
            safe_relative(rel)
            folded = rel.casefold()
            if folded in case_names:
                raise TeamLibError('INVALID_PACKAGE', 'Case-colliding material paths were blocked.')
            case_names.add(folded)
            if path.is_symlink(): raise TeamLibError('INVALID_PACKAGE', 'Symbolic link material was blocked.')
            mode = path.lstat().st_mode
            if not stat.S_ISREG(mode) and not stat.S_ISDIR(mode):
                raise TeamLibError('INVALID_PACKAGE', 'Special filesystem material was blocked.')
            if stat.S_ISREG(mode): paths.append(path)
    return sorted(paths, key=lambda p:p.relative_to(root).as_posix())


def build_inventory(release_root, *, policy=None):
    root = ensure_no_symlinks(release_root)
    policy = _limits(policy); rows = []; total = 0; count = 0
    for path in tree_files(root):
        rel = path.relative_to(root).as_posix()
        size = path.stat().st_size
        if size > policy['max_file_bytes']:
            raise TeamLibError('INVALID_PACKAGE', 'Package file exceeds its size limit.', {'category':'file_size'})
        total += size; count += 1
        if rel == 'manifest.json': continue
        if rel != 'README.md' and not rel.startswith('payload/'):
            raise TeamLibError('INVALID_PACKAGE', 'Release contains material outside README/payload.')
        rows.append({'path':rel,'sha256':hash_file(path),'size':size})
    if total > policy['max_release_bytes'] or count > policy['max_files']:
        raise TeamLibError('INVALID_PACKAGE', 'Release exceeds its material budget.', {'category':'release_size'})
    if not any(row['path']=='README.md' for row in rows):
        raise TeamLibError('INVALID_PACKAGE', 'Release README is missing.')
    return rows


def validate_release(release_root, *, policy=None):
    root = ensure_no_symlinks(release_root)
    manifest_path=ensure_no_symlinks(root/'manifest.json')
    if not manifest_path.is_file(): raise TeamLibError('INVALID_PACKAGE', 'Release manifest is missing.')
    if manifest_path.stat().st_size > _limits(policy)['max_file_bytes']:
        raise TeamLibError('INVALID_PACKAGE', 'Manifest exceeds its size limit.')
    record = read_json(root/'manifest.json'); validate_record('manifest',record)
    if record['files'] != build_inventory(root, policy=policy):
        raise TeamLibError('INVALID_PACKAGE', 'Release inventory does not match actual material.')
    paths = {row['path'] for row in record['files']}
    if not set(record['entrypoints']) <= paths:
        raise TeamLibError('INVALID_PACKAGE', 'Entrypoint material is missing.')
    return record


def scan_file(path, *, policy=None, location=None):
    policy = _limits(policy)
    path = ensure_no_symlinks(path)
    location = location or 'material'
    if path.stat().st_size > policy['max_file_bytes']:
        raise TeamLibError('INVALID_PACKAGE', 'Outbound file exceeds its size limit.', {'category':'file_size','location':location})
    if path.suffix.lower() in ARCHIVES:
        raise TeamLibError('INVALID_PACKAGE', 'Opaque archives must be safely expanded before sharing.', {'category':'opaque_archive','location':location})
    with _open_regular(path) as file: content = file.read(policy['max_file_bytes'] + 1)
    archive_magic = (b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08', b'\x1f\x8b', b'BZh', b'\xfd7zXZ\x00', b'7z\xbc\xaf\x27\x1c', b'Rar!\x1a\x07', b'\x28\xb5\x2f\xfd')
    if content.startswith(archive_magic) or content[257:262] == b'ustar':
        raise TeamLibError('INVALID_PACKAGE', 'Opaque archives must be safely expanded before sharing.', {'category':'opaque_archive','location':location})
    scan_text(content.decode('utf-8', errors='replace'), location)
    try:
        text = content.decode('utf-8')
        opaque = '\x00' in text or path.suffix.lower() in OPAQUE_EXTENSIONS
    except UnicodeError:
        opaque = True; text = None
    if opaque:
        digest = hash_file(path)
        approvals = policy.get('opaque_shares', [])
        members_path = Path(__file__).resolve().parents[2] / 'governance' / 'members.json'
        maintainers = policy.get('_trusted_maintainers')
        if maintainers is None:
            maintainers = [row['actor_key'] for row in read_json(members_path).get('members',[]) if isinstance(row,dict) and row.get('role') == 'maintainer'] if members_path.exists() else []
        approved = any(isinstance(row,dict) and row.get('sha256') == digest and row.get('scope') and row.get('approved_by') in maintainers for row in approvals)
        if not approved:
            raise TeamLibError('INVALID_PACKAGE', 'Opaque material needs a trusted sharing approval.', {'category':'opaque_unapproved','location':location})
    else: scan_text(text,location)


def validate_outbound(entry_root, commit_message, body_file, *, policy=None):
    root = ensure_no_symlinks(entry_root); policy = _limits(policy)
    scan_text(commit_message,'commit_message'); scan_file(body_file,policy=policy,location='request_body')
    paths = tree_files(root)
    if len(paths) > policy['max_files'] * max(1, len(list((root/'releases').glob('*')))) + 2:
        raise TeamLibError('INVALID_PACKAGE', 'Outbound entry contains too many files.')
    for path in paths:
        # Never include untrusted path strings in diagnostics: filenames themselves may contain secrets.
        scan_text(path.relative_to(root).as_posix(),'material_path')
        scan_file(path,policy=policy,location='entry_material')
    result = validate_entry(root, policy=policy)
    return {'allowed':True,'state':'prepared','checks':{'inventory':True,'outbound_scan':True},'release_count':result['release_count']}


def validate_entry(entry_root, *, policy=None):
    root = ensure_no_symlinks(entry_root)
    paths = tree_files(root)
    meta=read_json(root/'meta.json'); state=read_json(root/'state.json')
    validate_record('meta',meta); validate_record('state',state)
    if meta['owner_key'] != state['owner_key']:
        raise TeamLibError('INVALID_PACKAGE', 'Discovery owner must match canonical state owner.')
    allowed_files={'meta.json','state.json'}; versions={}; releases=root/'releases'
    if not releases.is_dir(): raise TeamLibError('INVALID_PACKAGE', 'Entry release directory is missing.')
    for release in sorted(releases.iterdir()):
        validate_version(release.name)
        manifest = validate_release(release, policy=policy)
        if manifest['id'] != meta['id'] or manifest['version'] != release.name:
            raise TeamLibError('INVALID_PACKAGE', 'Release identity does not match its entry.')
        versions[release.name]=manifest
        allowed_files.update('releases/'+release.name+'/'+p.relative_to(release).as_posix() for p in tree_files(release))
    if not versions or {p.relative_to(root).as_posix() for p in paths} != allowed_files:
        raise TeamLibError('INVALID_PACKAGE', 'Entry contains missing or unexpected material.')
    if state['recommended_version'] is not None and state['recommended_version'] not in versions:
        raise TeamLibError('INVALID_PACKAGE', 'Recommended version is missing.')
    if not set(state['withdrawn_versions']) <= versions.keys():
        raise TeamLibError('INVALID_PACKAGE', 'Withdrawn version is missing.')
    for binding in state['verification'] + state['reviews']:
        version=binding['version']
        if binding['id'] != meta['id'] or version not in versions or binding['manifest_sha256'] != hash_file(releases/version/'manifest.json'):
            raise TeamLibError('INVALID_PACKAGE', 'Review or verification binding does not match material.')
    return {'meta':meta,'entry_state':state,'releases':versions,'release_count':len(versions)}
