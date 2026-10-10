#!/usr/bin/env python3
"""Read-only GitHub CI: materialize candidates as data and run trusted base policy."""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.teamlib.contracts import TeamLibError,read_json,write_json
from tools.teamlib.snapshots import _git,export_tree


def prepare_context(base,event,current_pr):
    repo=event.get('repository',{}).get('full_name')
    if not isinstance(repo,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):
        raise TeamLibError('SCOPE_DENIED','Repository identity is invalid.')
    prior=event.get('pull_request',{})
    if type(event.get('number')) is not int or current_pr.get('number')!=event['number']:
        raise TeamLibError('SCOPE_DENIED','Request identity does not match the event.')
    config=read_json(Path(base)/'library.json')
    if current_pr.get('base',{}).get('ref')!=config.get('shared_branch'):
        raise TeamLibError('SCOPE_DENIED','Request does not target the configured shared branch.')
    for side in ('base','head'):
        row=current_pr.get(side,{})
        if row.get('repo',{}).get('full_name')!=repo:
            raise TeamLibError('SCOPE_DENIED','External fork submissions are outside the first release scope.')
        sha=row.get('sha')
        if not isinstance(sha,str) or not re.fullmatch(r'[0-9a-f]{40}',sha) or sha!=prior.get(side,{}).get('sha'):
            raise TeamLibError('STATUS_UNVERIFIED','Request content changed; a fresh check is required.')
    actor=current_pr.get('user',{})
    if actor.get('type')!='User':raise TeamLibError('SCOPE_DENIED','Submission needs an individual author.')
    members=read_json(Path(base)/'governance/members.json')
    matches=[r for r in members.get('members',[]) if isinstance(r,dict) and r.get('github_login','').casefold()==actor.get('login','').casefold()]
    if len(matches)!=1:raise TeamLibError('SCOPE_DENIED','Author has no unique approved identity mapping.')
    row=matches[0]
    return {'actor_key':row['actor_key'],'role':row['role'],'proposal_author':row['actor_key'],
            'base_commit':current_pr['base']['sha'],'head_commit':current_pr['head']['sha']}


def materialize_candidate(repo,number,sha,workspace):
    """Fetch a PR data ref with read-only gh credentials, then export exact blobs."""
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo) or type(number) is not int or number<=0 or not re.fullmatch(r'[0-9a-f]{40}',sha):
        raise TeamLibError('SCOPE_DENIED','Candidate provenance is invalid.')
    mirror=Path(workspace)/'candidate.git';_git(['init','--bare',str(mirror)])
    ref='refs/heads/team-library-candidate'
    _git(['--git-dir='+str(mirror),'-c','credential.helper=',
          '-c','credential.helper=!gh auth git-credential','fetch','--no-tags','--',
          'https://github.com/'+repo+'.git',f'refs/pull/{number}/head:'+ref])
    current=_git(['--git-dir='+str(mirror),'rev-parse','--verify',ref+'^{commit}']).stdout.decode().strip()
    if current!=sha:raise TeamLibError('STATUS_UNVERIFIED','Candidate head changed; rerun the check.')
    candidate=Path(workspace)/'candidate';export_tree(mirror,sha,candidate)
    return candidate


def prepare_push_context(base, event, config):
    """Build a post-push context without requiring a PR or member allowlist."""
    repo = event.get('repository', {}).get('full_name')
    if not isinstance(repo, str) or event.get('ref') != 'refs/heads/' + config.get('shared_branch', ''):
        raise TeamLibError('SCOPE_DENIED', 'Push is outside the configured shared branch.')
    before, after = event.get('before'), event.get('after')
    if not re.fullmatch(r'[0-9a-f]{40}', str(before)) or not re.fullmatch(r'[0-9a-f]{40}', str(after)):
        raise TeamLibError('STATUS_UNVERIFIED', 'Push provenance is incomplete.')
    actor = event.get('sender') or event.get('pusher') or {}
    login = actor.get('login')
    if actor.get('type', 'User') != 'User' or not isinstance(login, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', login):
        raise TeamLibError('SCOPE_DENIED', 'Push needs an individual GitHub account.')
    actor_key, role = login.lower(), 'contributor'
    try:
        members = read_json(Path(base) / 'governance/members.json')
        matches = [row for row in members.get('members', []) if isinstance(row, dict) and row.get('github_login', '').casefold() == login.casefold()]
        if len(matches) == 1:
            actor_key, role = matches[0]['actor_key'], matches[0]['role']
    except (OSError, TypeError, AttributeError):
        pass
    return {'actor_key': actor_key, 'role': role, 'proposal_author': actor_key,
            'public_write': True, 'base_commit': before, 'head_commit': after}


def _api(endpoint):
    # gh manages existing authentication and redirect handling; token is only an environment value.
    try:
        with tempfile.TemporaryFile() as response:
            result=subprocess.run(['gh','api',endpoint,'--hostname','github.com'],stdout=response,stderr=subprocess.DEVNULL,timeout=60)
            if result.returncode:raise TeamLibError('REMOTE_FAILED','Read-only platform access failed.')
            if response.tell()>64*1024*1024:
                raise TeamLibError('INVALID_PACKAGE','API response exceeds the size limit.')
            response.seek(0)
            return response.read()
    except (OSError,subprocess.SubprocessError):
        raise TeamLibError('REMOTE_FAILED','Read-only platform access did not complete.') from None


def main():
    try:
        event=read_json(Path(os.environ['GITHUB_EVENT_PATH']))
        repo=os.environ['GITHUB_REPOSITORY']
        if event.get('repository',{}).get('full_name')!=repo or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):
            raise TeamLibError('SCOPE_DENIED','Event repository differs from the trusted workflow context.')
        trusted=Path(__file__).resolve().parents[1]
        config=read_json(trusted/'library.json')
        push_event = event.get('ref') == 'refs/heads/' + config.get('shared_branch', '') and 'pull_request' not in event
        if push_event:
            context = prepare_push_context(trusted, event, config)
        else:
            number=event.get('number')
            if type(number) is not int or number<=0:raise TeamLibError('SCOPE_DENIED','Request identity is invalid.')
            request=json.loads(_api(f'repos/{repo}/pulls/{number}'))
            context=prepare_context(trusted,event,request)
        with tempfile.TemporaryDirectory(prefix='teamlib-ci-') as d:
            workspace=Path(d).resolve()
            base_git=_git(['-C',str(trusted),'rev-parse','--absolute-git-dir']).stdout.decode().strip()
            canonical_base=workspace/'base'
            export_tree(Path(base_git),context['base_commit'],canonical_base)
            if push_event:
                candidate=workspace/'candidate'; export_tree(Path(base_git),context['head_commit'],candidate)
            else:
                candidate=materialize_candidate(repo,number,context['head_commit'],workspace)
            context_path=workspace/'context.json';write_json(context_path,context)
            result=subprocess.run([sys.executable,'-I','-B',str(canonical_base/'tools/check_submission.py'),
                                   '--base',str(canonical_base),'--candidate',str(candidate),'--context',str(context_path)],
                                  capture_output=True,text=True,timeout=60)
            # Parse before forwarding to keep output structured and limited to the trusted checker.
            checked=json.loads(result.stdout);print(json.dumps(checked,ensure_ascii=False))
            return result.returncode
    except TeamLibError as exc:
        print(json.dumps({'allowed':False,'code':exc.code,'message':exc.message}));return 2
    except Exception:
        print(json.dumps({'allowed':False,'code':'INTERNAL_ERROR','message':'CI check did not complete.'}));return 1


if __name__=='__main__':raise SystemExit(main())
