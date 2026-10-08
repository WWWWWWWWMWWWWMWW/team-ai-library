import hashlib
import json
from pathlib import Path


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def meta(owner='alice', identifier='alice/demo'):
    return {'schema_version': 1, 'id': identifier, 'title': 'Demo', 'kind': 'skill', 'summary': 'Example', 'tags': [], 'aliases': [], 'author_key': identifier.split('/')[0], 'owner_key': owner, 'source': {'type': 'original', 'reference': 'local authored material'}}


def manifest(identifier='alice/demo', version='1.0.0'):
    return {'schema_version': 1, 'id': identifier, 'version': version, 'entrypoints': ['payload/SKILL.md'], 'scope': {'inputs': ['text'], 'outputs': ['text'], 'includes': ['documentation'], 'excludes': ['production']}, 'compatibility': {'os': ['any'], 'runtimes': {}, 'tools': ['AI'], 'capabilities': ['filesystem.read']}, 'effects': ['read_only'], 'dependencies': [], 'files': []}


def state(owner='alice', version='1.0.0'):
    return {'schema_version': 1, 'owner_key': owner, 'recommended_version': version, 'withdrawn_versions': [], 'reviews': [], 'verification': []}


def release(root, identifier='alice/demo', version='1.0.0'):
    root = Path(root)
    (root / 'payload').mkdir(parents=True, exist_ok=True)
    (root / 'README.md').write_text('A shareable example\n', encoding='utf-8')
    (root / 'payload' / 'SKILL.md').write_text('Read the supplied text.\n', encoding='utf-8')
    record = manifest(identifier, version)
    record['files'] = [{'path': str(p.relative_to(root).as_posix()), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'size': p.stat().st_size} for p in sorted(root.rglob('*')) if p.is_file()]
    dump(root / 'manifest.json', record)
    return record


def entry(root, owner='alice', identifier='alice/demo', version='1.0.0'):
    root = Path(root)
    dump(root / 'meta.json', meta(owner, identifier))
    dump(root / 'state.json', state(owner, version))
    release(root / 'releases' / version, identifier, version)
    return root


def governance(root, maintainers=('maintainer',), members=('alice', 'bob')):
    root = Path(root)
    dump(root / 'governance' / 'members.json', {'schema_version': 1, 'members': [{'actor_key': name, 'github_login': name, 'role': 'maintainer' if name in maintainers else 'contributor'} for name in list(maintainers) + list(members)]})
    dump(root / 'governance' / 'policy.json', {'schema_version': 1, 'max_file_bytes': 5 * 1024 * 1024, 'max_release_bytes': 20 * 1024 * 1024, 'max_files': 500, 'opaque_shares': []})
    dump(root / 'governance' / 'revocations.json', {'schema_version': 1, 'revocations': []})
