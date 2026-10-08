#!/usr/bin/env python3
"""Discover local Codex source metadata; never read or execute source content."""
import argparse
import json
import os
from pathlib import Path
import stat


SKIP_DIRS = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'logs', 'cache', 'tmp'}
SECRET_NAMES = {'.env', 'auth.json', 'credentials.json', 'token.json', 'tokens.json',
                'config.toml', 'id_rsa', 'id_ed25519'}


def safe_path(path):
    path = Path(path).absolute()
    for part in [path, *path.parents]:
        system_alias = str(part) in {'/var', '/tmp', '/etc'} and str(part.resolve()) == '/private' + str(part)
        if part.is_symlink() and not system_alias:
            raise ValueError('symlink')
    return path


def discover(user_home, codex_home):
    user_home, codex_home = Path(user_home).absolute(), Path(codex_home).absolute()
    specs = [('personal_skills', codex_home/'skills', None, 'unknown'),
             ('agent_skills', user_home/'.agents/skills', None, 'unknown'),
             ('prompts', codex_home/'prompts', {'.md', '.txt', '.json', '.yaml', '.yml'}, 'unknown'),
             ('rules', codex_home/'AGENTS.md', None, 'unknown'),
             ('automations', codex_home/'automations', {'automation.toml'}, 'unknown'),
             ('sessions', codex_home/'sessions', {'.jsonl'}, 'unknown'),
             ('archived_sessions', codex_home/'archived_sessions', {'.jsonl'}, 'unknown'),
             ('history', codex_home/'history.jsonl', None, 'unknown'),
             ('plugin_material', codex_home/'plugins/cache', None, 'unknown_or_third_party')]
    sources = []
    for category, root, allowed, authorship in specs:
        record = {'category': category, 'path': str(root), 'authorship': authorship,
                  'status': 'discovered', 'files': [], 'issues': []}
        sources.append(record)
        def issue(path, reason):
            record['issues'].append({'path': str(path), 'reason': reason})
        def accept(path):
            lower = path.name.lower()
            if lower in SECRET_NAMES or lower.startswith('.env') or lower.endswith(('.sqlite', '.sqlite3', '.db', '.pyc')):
                return False
            if category == 'plugin_material' and 'skills' not in path.relative_to(root).parts:
                return False
            return allowed is None or path.suffix.lower() in allowed or path.name in allowed
        def add(path):
            try:
                safe_path(path)
                info = path.stat(follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):
                    issue(path, 'not_regular'); return
                if accept(path):
                    record['files'].append({'path': str(path), 'relative_path': path.relative_to(root).as_posix() if path != root else path.name,
                                            'bytes': info.st_size, 'mtime_ns': info.st_mtime_ns, 'state': 'pending'})
            except (OSError, ValueError):
                issue(path, 'unavailable_or_linked')
        try:
            safe_path(root)
            if not root.exists():
                record['status'] = 'missing'; continue
            if root.is_file():
                add(root); continue
            if not root.is_dir():
                record['status'] = 'blocked'; issue(root, 'not_directory'); continue
            def walk_error(error):
                issue(error.filename or root, 'unreadable_directory')
            for directory, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
                directory = Path(directory)
                kept = []
                for name in sorted(dirs):
                    path = directory/name
                    if path.is_symlink(): issue(path, 'symlink')
                    elif name not in SKIP_DIRS: kept.append(name)
                dirs[:] = kept
                for name in sorted(names): add(directory/name)
        except (OSError, ValueError):
            record['status'] = 'blocked'; issue(root, 'unavailable_or_linked')
    return {'schema_version': 1, 'operation': 'discover_codex_sources', 'state': 'discovered',
            'content_read': False, 'codex_home': str(codex_home), 'sources': sources,
            'summary': {'source_roots': sum(row['status']=='discovered' for row in sources),
                        'files': sum(len(row['files']) for row in sources),
                        'blocked_paths': sum(len(row['issues']) for row in sources)},
            'exclusions': ['credentials', 'personal_settings', 'databases', 'raw_logs', 'cache',
                           'memories_unless_explicitly_selected', 'unselected_business_projects'],
            'next_action': 'Read allowed source content in batches and prepare local Chinese capability drafts; do not upload.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user-home', type=Path, default=Path.home())
    parser.add_argument('--codex-home', type=Path)
    parser.add_argument('--output', type=Path, help='New local JSON file outside all source directories.')
    args = parser.parse_args()
    codex_home = args.codex_home or Path(os.environ.get('CODEX_HOME') or args.user_home/'.codex')
    try:
        result = discover(args.user_home.expanduser(), codex_home.expanduser())
        if args.output is not None:
            output = safe_path(args.output.expanduser())
            protected = [Path(result['codex_home']), *[Path(row['path']) for row in result['sources']]]
            if any(output == root or output.is_relative_to(root) for root in protected):
                raise ValueError('source_output')
            if output.exists(): raise ValueError('existing_output')
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('x', encoding='utf-8') as stream:
                json.dump(result, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
            result = {key: result[key] for key in ('schema_version', 'operation', 'state', 'content_read', 'summary')}
            result['output_path'] = str(output)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (OSError, ValueError):
        print(json.dumps({'state': 'blocked', 'code': 'LOCAL_DISCOVERY_BLOCKED',
                          'message': 'Local output must be new, outside sources, and free of links.'}))
        return 2


if __name__ == '__main__': raise SystemExit(main())
