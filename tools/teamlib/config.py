"""Configuration has no credentials or guessed remote/branch defaults."""
import re
from pathlib import Path
from urllib.parse import urlsplit, unquote
from .contracts import TeamLibError, read_json, ensure_no_symlinks, validate_record

CONFIG_KEYS = {'schema_version','remote','shared_branch','platform','workspace','publish_mode','auto_merge','target_profiles'}
OPTIONAL_CONFIG_KEYS = {'deployment_mode'}


def deployment_mode(config):
    mode = config.get('deployment_mode', 'protected')
    if mode not in ('protected', 'owner_trial') or (mode == 'owner_trial' and config.get('platform') != 'github'):
        raise TeamLibError('CONFIG_MISSING', 'Deployment mode is unsupported for this platform.')
    return mode


def normalize_directory(value, repository_root, *, allow_absolute=True):
    if not isinstance(value, str) or not value or '\x00' in value:
        raise TeamLibError('CONFIG_MISSING', 'Directory configuration is invalid.')
    p = Path(value).expanduser()
    if '..' in p.parts or (p.is_absolute() and not allow_absolute):
        raise TeamLibError('CONFIG_MISSING', 'Directory escapes its configured boundary.')
    p = ensure_no_symlinks(p if p.is_absolute() else repository_root / p)
    p = p.resolve()
    if p == Path(p.anchor) or p == Path.home() or repository_root.is_relative_to(p) or p.is_file():
        raise TeamLibError('CONFIG_MISSING', 'A dedicated directory is required.')
    return str(p)


def validate_local_remote(config):
    """Local test mode cannot reach network Git transports or remote helpers."""
    if config.get('platform') != 'local':
        raise TeamLibError('CONFIG_MISSING','Filesystem test remote requires local platform mode.')
    remote=config.get('remote')
    if not isinstance(remote,str) or not remote or remote.startswith('-') or any(ord(c)<32 for c in remote):
        raise TeamLibError('CONFIG_MISSING','Local filesystem remote is invalid.')
    if remote.startswith('file://'):
        parsed=urlsplit(remote)
        if parsed.scheme != 'file' or parsed.netloc or parsed.query or parsed.fragment or not parsed.path.startswith('/'):
            raise TeamLibError('CONFIG_MISSING','Local remote must be a host-free filesystem path.')
        value=unquote(parsed.path)
    else:
        if ':' in remote or '://' in remote or '@' in remote or remote.startswith('\\'):
            raise TeamLibError('CONFIG_MISSING','Local mode cannot use network transports or Git remote helpers.')
        value=remote
    if not value or any(ord(c)<32 for c in value):
        raise TeamLibError('CONFIG_MISSING','Local filesystem remote is invalid.')
    path=Path(value).expanduser()
    if not path.is_absolute():
        repository=config.get('repository_root')
        if not isinstance(repository,str) or not Path(repository).is_absolute() or '..' in path.parts:
            raise TeamLibError('CONFIG_MISSING','Relative filesystem remote requires an explicit repository root.')
        path=Path(repository)/path
    path=ensure_no_symlinks(path).resolve()
    if path == Path(path.anchor) or path.is_file():
        raise TeamLibError('CONFIG_MISSING','Local test remote must name a repository directory.')
    return str(path)


def validate_layout(config):
    """Cache and installation profiles must occupy disjoint dedicated directories."""
    repository=config.get('repository_root')
    if not isinstance(repository,str) or not Path(repository).is_absolute():
        raise TeamLibError('CONFIG_MISSING','Directory validation requires an explicit repository root.')
    root=ensure_no_symlinks(repository).resolve()
    workspace=Path(normalize_directory(config.get('workspace'),root))
    profiles=config.get('target_profiles')
    if not isinstance(profiles,dict):
        raise TeamLibError('CONFIG_MISSING','Target profiles must be an object.')
    locations=[workspace]
    for profile in profiles.values():
        if not isinstance(profile,dict) or 'path' not in profile:
            raise TeamLibError('CONFIG_MISSING','Target profile is invalid.')
        target=Path(normalize_directory(profile['path'],root))
        if any(target.is_relative_to(other) or other.is_relative_to(target) for other in locations):
            raise TeamLibError('CONFIG_MISSING','Workspace and target profiles must not overlap.')
        locations.append(target)


def validate_config_fields(config):
    """Validate configuration data without accessing its configured directories."""
    try: validate_record('library', config)
    except TeamLibError: raise TeamLibError('CONFIG_MISSING', 'Library configuration fields are missing or unsupported.') from None
    if not CONFIG_KEYS <= config.keys() or set(config) - CONFIG_KEYS - OPTIONAL_CONFIG_KEYS or type(config.get('schema_version')) is not int or config['schema_version'] != 1:
        raise TeamLibError('CONFIG_MISSING', 'Library configuration fields are missing or unsupported.')
    deployment_mode(config)
    if config['publish_mode'] != 'request' or config['auto_merge'] is not False:
        raise TeamLibError('CONFIG_MISSING', 'Publication requires reviewed requests with automatic merging disabled.')
    if config['platform'] not in {'github','local','unconfigured'}:
        raise TeamLibError('CONFIG_MISSING', 'Platform configuration is unsupported.')
    if not isinstance(config['remote'], str) or not isinstance(config['shared_branch'], str):
        raise TeamLibError('CONFIG_MISSING', 'Remote and shared branch must be explicitly configured strings.')
    remote = config['remote']; branch = config['shared_branch']
    if any(ord(c) < 32 or (c.isspace() and config['platform'] != 'local') for c in remote) or remote.startswith('-'):
        raise TeamLibError('CONFIG_MISSING', 'Remote configuration is invalid.')
    if '://' in remote:
        parsed = urlsplit(remote)
        if parsed.password is not None or (parsed.username is not None and parsed.scheme in {'https','http'}) or parsed.query or parsed.fragment:
            raise TeamLibError('CONFIG_MISSING', 'Remote URLs must not contain credentials or query data.')
    if branch and (branch.startswith(('-', '/', '.')) or branch.endswith(('/', '.', '.lock')) or '..' in branch or '@{' in branch or re.search(r'[\s~^:?*\[\\\x00-\x1f]',branch) or '//' in branch):
        raise TeamLibError('CONFIG_MISSING', 'Shared branch configuration is invalid.')
    if config['platform'] == 'unconfigured' and (remote or branch):
        raise TeamLibError('CONFIG_MISSING', 'Unconfigured platform must not contain connected settings.')
    if config['platform'] != 'unconfigured' and (not remote or not branch):
        raise TeamLibError('CONFIG_MISSING', 'Connected platform requires an explicit remote and shared branch.')
    if not isinstance(config['target_profiles'], dict):
        raise TeamLibError('CONFIG_MISSING', 'Target profiles must be an object.')
    for name, profile in config['target_profiles'].items():
        if not isinstance(name,str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*',name) or not isinstance(profile,dict) or set(profile) - {'path','tool'} or 'path' not in profile:
            raise TeamLibError('CONFIG_MISSING', 'Target profile is invalid.')
        if 'tool' in profile and (not isinstance(profile['tool'],str) or not profile['tool']):
            raise TeamLibError('CONFIG_MISSING', 'Target tool configuration is invalid.')


def load_config(path):
    path = ensure_no_symlinks(path)
    try: config = read_json(path)
    except TeamLibError:
        raise TeamLibError('CONFIG_MISSING', 'Library configuration is unavailable or invalid.') from None
    validate_config_fields(config)
    config['deployment_mode'] = deployment_mode(config)
    root = path.parent.resolve()
    config['workspace'] = normalize_directory(config['workspace'], root)
    profiles = {}
    for name, profile in config['target_profiles'].items():
        profiles[name] = dict(profile, path=normalize_directory(profile['path'], root))
    config['target_profiles'] = profiles
    config['repository_root'] = str(root)
    if config['platform'] == 'local': config['remote']=validate_local_remote(config)
    validate_layout(config)
    config['config_path'] = str(path)
    return config
