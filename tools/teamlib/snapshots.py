"""Fresh, isolated Git snapshots. No user checkout or payload is executed."""
import hashlib
import os
import re
import subprocess
import uuid
from pathlib import Path
from .contracts import TeamLibError,ensure_no_symlinks,safe_relative


def _git(args, *, check=True, input=None):
    env = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_TERMINAL_PROMPT='0',GIT_CONFIG_NOSYSTEM='1')
    try:
        result=subprocess.run(['git','-c','core.hooksPath=/dev/null',*args],
                              env=env,capture_output=True,timeout=90,input=input)
    except (OSError,subprocess.TimeoutExpired):
        raise TeamLibError('REMOTE_FAILED','Git access did not complete.') from None
    if check and result.returncode:
        raise TeamLibError('REMOTE_FAILED','Git access failed; check configured remote and login.')
    return result


def export_tree(mirror,source,root):
    """Read raw tracked blobs, ignoring export-ignore/export-subst and filters."""
    ensure_no_symlinks(root)
    listing=_git(['--git-dir='+str(mirror),'ls-tree','-r','-l','-z',source]).stdout
    files=[];paths=set();total=0
    try:
        for item in listing.split(b'\0'):
            if not item:continue
            descriptor,name_bytes=item.split(b'\t',1)
            mode,kind,oid,size_text=descriptor.split()
            name=name_bytes.decode('utf-8');safe_relative(name)
            if any(part.casefold()=='.git' for part in name.split('/')):
                raise TeamLibError('INVALID_PACKAGE','Tracked Git metadata paths are forbidden.')
            if kind!=b'blob' or mode not in (b'100644',b'100755'):
                raise TeamLibError('INVALID_PACKAGE','Snapshot links and submodules are forbidden.')
            if not re.fullmatch(rb'(?:[0-9a-f]{40}|[0-9a-f]{64})',oid):
                raise TeamLibError('INVALID_PACKAGE','Git blob identity is invalid.')
            size=int(size_text);total+=size;folded=name.casefold()
            if folded in paths:raise TeamLibError('INVALID_PACKAGE','Snapshot paths collide.')
            paths.add(folded);files.append((name,oid,size,mode))
            if len(files)>25000 or total>512*1024*1024:
                raise TeamLibError('INVALID_PACKAGE','Snapshot exceeds material limits.')
        data=_git(['--git-dir='+str(mirror),'cat-file','--batch'],input=b''.join(oid+b'\n' for _,oid,_,_ in files)).stdout
        cursor=0;verified=[]
        for name,oid,size,mode in files:
            end=data.find(b'\n',cursor)
            header=data[cursor:end].split()
            if end<0 or header!=[oid,b'blob',str(size).encode()]:
                raise TeamLibError('INVALID_PACKAGE','Git object response differs from the tracked tree.')
            start=end+1;payload=data[start:start+size]
            if len(payload)!=size or data[start+size:start+size+1]!=b'\n':
                raise TeamLibError('INVALID_PACKAGE','Tracked Git content is incomplete.')
            verified.append((name,payload,mode));cursor=start+size+1
        if cursor!=len(data):raise TeamLibError('INVALID_PACKAGE','Git object response has unexpected material.')
        root.mkdir(parents=True)
        for name,payload,mode in verified:
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as output:output.write(payload)
            target.chmod(0o755 if mode==b'100755' else 0o644)
    except (OSError,UnicodeError,ValueError):
        raise TeamLibError('INVALID_PACKAGE','Tracked Git tree cannot be materialized safely.') from None


def open_snapshot(config,workspace,commit=None):
    platform=config.get('platform')
    if platform=='github':
        from .platform import doctor_read
        doctor_read(config)
    elif platform=='local':
        from .config import validate_local_remote
        validate_local_remote(config)
    else:
        raise TeamLibError('CONFIG_MISSING','A supported connected platform must be configured.')
    remote=config.get('remote');branch=config.get('shared_branch')
    if not isinstance(remote,str) or not remote or not isinstance(branch,str) or not branch:
        raise TeamLibError('CONFIG_MISSING','A real remote and shared branch must be configured.')
    if remote.startswith('-') or '\n' in remote or branch.startswith('-'):
        raise TeamLibError('CONFIG_MISSING','Remote or branch is invalid.')
    branch_check=_git(['check-ref-format','refs/heads/'+branch],check=False)
    if branch_check.returncode:raise TeamLibError('CONFIG_MISSING','Shared branch is invalid.')
    workspace=ensure_no_symlinks(Path(workspace).absolute())
    workspace.mkdir(parents=True,exist_ok=True)
    key=hashlib.sha256((remote+'\0'+branch).encode()).hexdigest()
    mirror=workspace/'mirrors'/key
    ensure_no_symlinks(mirror)
    mirror.parent.mkdir(exist_ok=True)
    if not mirror.exists():_git(['init','--bare',str(mirror)])
    ref='refs/heads/team-library-shared'
    # Refresh is mandatory even for an explicitly pinned source. No cached success.
    _git(['--git-dir='+str(mirror),'fetch','--no-tags','--force','--',remote,
          'refs/heads/'+branch+':'+ref])
    head=_git(['--git-dir='+str(mirror),'rev-parse','--verify',ref+'^{commit}']).stdout.decode().strip()
    source=head
    if commit is not None:
        if not isinstance(commit,str) or not re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})',commit):
            raise TeamLibError('INVALID_PACKAGE','Source commit must be a full Git object ID.')
        result=_git(['--git-dir='+str(mirror),'merge-base','--is-ancestor',commit,head],check=False)
        if result.returncode:raise TeamLibError('STATUS_UNVERIFIED','Pinned source is not reachable from the shared branch.')
        source=commit
    # A unique materialization avoids trusting mutable cache contents as current state.
    dest=workspace/'snapshots'/source/('tree-'+uuid.uuid4().hex)
    ensure_no_symlinks(dest)
    export_tree(mirror,source,dest)
    return {'root':str(dest),'source_commit':source,'repository':remote,'shared_branch':branch,
            'workspace':str(workspace),'config':config}
