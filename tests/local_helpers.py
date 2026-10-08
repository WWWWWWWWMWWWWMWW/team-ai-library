import json
import subprocess
from pathlib import Path


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def release(root, capability='alice/root', version='1.0.0', dependencies=None, text='safe'):
    import hashlib
    folder = root / 'entries' / capability / 'releases' / version
    (folder / 'payload').mkdir(parents=True, exist_ok=True)
    (folder / 'README.md').write_text(text, encoding='utf-8')
    (folder / 'payload' / 'instructions.txt').write_text('instructions', encoding='utf-8')
    files = [{'path': str(p.relative_to(folder)), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'size': p.stat().st_size} for p in sorted(folder.rglob('*')) if p.is_file() and p.name != 'manifest.json']
    manifest = dict(schema_version=1, id=capability, version=version, entrypoints=['payload/instructions.txt'], scope=dict(inputs=['text'], outputs=['text'], includes=['planning'], excludes=['production']), compatibility=dict(os=['macos'], runtimes={}, tools=['codex'], capabilities=['filesystem']), effects=['read_only'], dependencies=dependencies or [], files=files)
    (folder / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True), encoding='utf-8')
    entry = root / 'entries' / capability
    (entry / 'meta.json').write_text(json.dumps(dict(schema_version=1, id=capability, title='Example', kind='prompt', summary='Example', tags=[], aliases=[], author_key='alice', owner_key='alice', source={'type':'original','reference':'local authored material'})))
    state = dict(schema_version=1,recommended_version=version, withdrawn_versions=[], reviews=[], verification=[], owner_key='alice')
    (entry / 'state.json').write_text(json.dumps(state))
    return dict(id=capability, version=version, manifest_sha256=hashlib.sha256((folder/'manifest.json').read_bytes()).hexdigest())


def repository(root):
    root.mkdir()
    git(root, 'init', '-b', 'shared')
    git(root, 'config', 'user.name', 'Fixture')
    git(root, 'config', 'user.email', 'fixture@example.invalid')
    release(root)
    (root/'governance').mkdir()
    (root/'governance'/'revocations.json').write_text(json.dumps(dict(schema_version=1, revocations=[])))
    git(root, 'add', '.')
    git(root, 'commit', '-m', 'isolated fixture')
    remote = root.parent / 'remote.git'
    subprocess.run(['git', 'clone', '--bare', str(root), str(remote)], check=True, capture_output=True)
    git(root, 'remote', 'add', 'origin', str(remote))
    workspace = root.parent / 'workspace'
    return dict(schema_version=1, remote=str(remote), shared_branch='shared', platform='local', workspace=str(workspace), publish_mode='request', auto_merge=False, target_profiles={}), workspace


def publish(root):
    git(root, 'add', '.')
    git(root, 'commit', '-m', 'fixture change')
    git(root, 'push', 'origin', 'shared')


def context():
    return dict(task_scope=dict(inputs=['text'], outputs=['text'], includes=['planning'], excludes=[]), environment=dict(os='macos', tools=['codex'], capabilities=['filesystem'], runtimes={}), effects_authorized=['read_only'])
