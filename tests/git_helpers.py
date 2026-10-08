"""Isolated real Git fixtures; never use a company remote or user checkout."""
import os
import subprocess
from pathlib import Path
from tests.core_helpers import entry, governance, dump


def git(cwd, *args, check=True):
    env = dict(os.environ, GIT_AUTHOR_NAME='Fixture', GIT_AUTHOR_EMAIL='fixture@example.invalid',
               GIT_COMMITTER_NAME='Fixture', GIT_COMMITTER_EMAIL='fixture@example.invalid')
    return subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.autocrlf=false',
                           '-c', 'core.attributesFile=/dev/null', *args], cwd=cwd,
                          env=env, capture_output=True, text=True, check=check)


def create_remote(root):
    root = Path(root).resolve()
    work = root / 'author'
    work.mkdir()
    git(work, 'init', '--initial-branch=team')
    entry(work / 'entries/alice/demo')
    governance(work)
    dump(work/'governance/revocations.json', {'schema_version': 1, 'revocations': []})
    git(work, 'add', '.')
    git(work, 'commit', '-m', 'Fixture capability')
    remote = root / 'team remote.git'
    git(root, 'clone', '--bare', str(work), str(remote))
    git(work, 'remote', 'add', 'origin', str(remote))
    config = {'schema_version': 1, 'remote': str(remote), 'shared_branch': 'team',
              'platform': 'local', 'workspace': str(root/'cache'), 'publish_mode': 'request',
              'auto_merge': False, 'target_profiles': {}}
    return work, remote, config


def publish_fixture(work, message='Fixture change'):
    git(work, 'add', '.')
    git(work, 'commit', '-m', message)
    git(work, 'push', 'origin', 'team')
    return git(work, 'rev-parse', 'HEAD').stdout.strip()
