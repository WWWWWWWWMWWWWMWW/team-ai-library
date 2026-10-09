import base64
import json
import subprocess
from pathlib import Path

from tests.core_helpers import dump, governance


def encoded(value):
    content = json.dumps(value).encode() if isinstance(value, dict) else value.encode()
    return {'encoding': 'base64', 'content': base64.b64encode(content).decode()}


class GithubService:
    """Only the external gh boundary is faked; local Git remains real."""
    def __init__(self):
        self.calls = []
        self.private = True
        self.permissions = {'push': True, 'pull': True, 'admin': False}
        self.protected = True
        self.login = 'alice-gh'
        self.head = 'a' * 40
        self.requests = []
        self.issues = []
        self.fail_create = False
        self.create_then_timeout = False
        self.owner = {'login': 'acme', 'type': 'Organization'}
        self.collaborator_pages = []
        self.invitation_pages = [[]]
        self.shared_config = None
        self.members = {'schema_version': 1, 'members': [{'actor_key':'alice','github_login':'alice-gh','role':'contributor'},{'actor_key':'bob','github_login':'bob-gh','role':'contributor'},{'actor_key':'maintainer','github_login':'maintainer-gh','role':'maintainer'}]}
        self.workflow = 'name: Team library submission\non: pull_request_target\npermissions:\n  contents: read\n'

    def __call__(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        if argv[0] != 'gh':
            return subprocess.run(argv, **kwargs)
        value = self._gh(argv)
        return subprocess.CompletedProcess(argv, 0, json.dumps(value) if not isinstance(value, str) else value, '')

    def _gh(self, args):
        if args[1] == 'api':
            endpoint = args[2]
            if endpoint == 'user': return {'login': self.login, 'type': 'User'}
            if '/collaborators?' in endpoint: return self.collaborator_pages
            if '/invitations?' in endpoint: return self.invitation_pages
            if '/contents/library.json' in endpoint: return encoded(self.shared_config)
            if '/contents/governance/members.json' in endpoint: return encoded(self.members)
            if '/contents/.github/workflows/check-submission.yml' in endpoint: return encoded(self.workflow)
            if '/contents/tools/check_submission.py' in endpoint: return encoded('# trusted checker\n')
            if endpoint.endswith('/protection'):
                if not self.protected: raise subprocess.CalledProcessError(1, args, stderr='token secret error')
                return {'enforce_admins': {'enabled': True}, 'required_pull_request_reviews': {'required_approving_review_count': 1, 'dismiss_stale_reviews': True}, 'required_status_checks': {'strict': True, 'checks': []}, 'allow_force_pushes': {'enabled': False}, 'allow_deletions': {'enabled': False}}
            if '/branches/' in endpoint: return {'protected': self.protected, 'commit': {'sha': self.head}}
            return {'private': self.private, 'full_name': 'acme/library', 'permissions': self.permissions, 'owner': self.owner}
        if args[1:3] == ['pr', 'list']:
            if '--head' in args: return [r for r in self.requests if r['headRefName'] == args[args.index('--head') + 1]]
            return self.requests
        if args[1:3] == ['pr', 'view']:
            return next(r for r in self.requests if str(r['number']) == args[3])
        if args[1:3] == ['pr', 'create']:
            if self.fail_create: raise subprocess.CalledProcessError(1, args, stderr='sensitive original')
            body = Path(args[args.index('--body-file') + 1]).read_text()
            branch = args[args.index('--head') + 1]
            r = {'number': len(self.requests) + 1, 'url': 'https://github.com/acme/library/pull/1', 'state': 'OPEN', 'title': args[args.index('--title') + 1], 'body': body, 'author': {'login': self.login}, 'baseRefName': 'main', 'headRefName': branch, 'headRefOid': getattr(self, 'proposal_head', self.head), 'mergeCommit': None, 'mergedAt': None}
            self.requests.append(r)
            if self.create_then_timeout: raise subprocess.TimeoutExpired(args, 1)
            return r['url']
        if args[1:3] == ['issue', 'list']: return self.issues
        if args[1:3] == ['issue', 'view']: return next(r for r in self.issues if str(r['number']) == args[3])
        if args[1:3] == ['issue', 'create']:
            body = Path(args[args.index('--body-file') + 1]).read_text()
            r = {'number': len(self.issues) + 1, 'url': 'https://github.com/acme/library/issues/1', 'state': 'OPEN', 'title': args[args.index('--title') + 1], 'body': body, 'author': {'login': self.login}}
            self.issues.append(r)
            if self.create_then_timeout: raise subprocess.TimeoutExpired(args, 1)
            return r['url']
        raise AssertionError('Unexpected gh command: ' + repr(args))


def config():
    return {'schema_version': 1, 'remote': 'https://github.com/acme/library.git', 'shared_branch': 'main', 'platform': 'github', 'publish_mode': 'request', 'auto_merge': False, 'review_mode': 'manual'}


def owner_trial_config(service):
    """Explicit fixture only for tests exercising the real trial adapter checks."""
    service.login = 'acme'
    service.owner = {'login': 'acme', 'type': 'User'}
    service.permissions = {'pull': True, 'push': True, 'admin': True}
    service.protected = False
    service.members = {'schema_version': 1, 'members': [{'actor_key': 'owner', 'github_login': 'acme', 'role': 'maintainer'}]}
    service.collaborator_pages = [[{'login': 'acme', 'type': 'User', 'permissions': dict(service.permissions)}]]
    value = dict(config(), deployment_mode='owner_trial', review_mode='manual', workspace='.cache/teamlib', target_profiles={})
    service.shared_config = dict(value)
    return value
