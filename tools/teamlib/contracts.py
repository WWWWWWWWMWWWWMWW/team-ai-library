"""Strict, non-executing JSON contracts shared by every library operation."""
import hashlib
from datetime import date
import json
import os
import re
import stat
import tempfile
from pathlib import Path


class TeamLibError(Exception):
    """Messages and data must contain categories/locations only, never source text."""
    def __init__(self, code, message, data=None):
        self.code = code
        self.message = message
        self.data = data if data is not None else {}
        super().__init__(message)


VERSION_PATTERN = r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'
ID_PATTERN = r'[a-z0-9][a-z0-9_-]*/[a-z0-9][a-z0-9_-]*'
KEY_PATTERN = r'[a-z0-9][a-z0-9_-]*'
HASH_PATTERN = r'[0-9a-f]{64}'


def validate_version(version):
    if not isinstance(version, str) or not re.fullmatch(VERSION_PATTERN, version):
        raise TeamLibError('INVALID_PACKAGE', 'Version must be canonical X.Y.Z.')


def validate_id(identifier):
    if not isinstance(identifier, str) or not re.fullmatch(ID_PATTERN, identifier):
        raise TeamLibError('INVALID_PACKAGE', 'Capability ID is invalid.')


def safe_relative(value):
    if not isinstance(value, str) or not value or '\\' in value or value.startswith('/'):
        raise TeamLibError('INVALID_PACKAGE', 'Path must be portable and relative.')
    parts = value.split('/')
    for part in parts:
        reserved = part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}
        if part in {'', '.', '..'} or ':' in part or part.endswith((' ', '.')) or reserved or any(ord(c) < 32 for c in part):
            raise TeamLibError('INVALID_PACKAGE', 'Path contains an unsafe component.')
    return value


def ensure_no_symlinks(path):
    path = Path(path).absolute()
    for part in [path, *path.parents]:
        if part.is_symlink() and not (str(part) in {'/var', '/tmp', '/etc'} and str(part.resolve()) == '/private' + str(part)):
            raise TeamLibError('INVALID_PACKAGE', 'Symbolic links are not allowed.')
    return path


def _open_regular(path):
    path = ensure_no_symlinks(path)
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            raise TeamLibError('INVALID_PACKAGE', 'Expected a regular file.')
        return os.fdopen(fd, 'rb')
    except OSError:
        raise TeamLibError('INVALID_PACKAGE', 'File is unavailable.') from None


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TeamLibError('INVALID_PACKAGE', 'Duplicate JSON keys are not allowed.')
        result[key] = value
    return result


def read_json(path):
    try:
        with _open_regular(path) as file:
            result = json.loads(file.read().decode('utf-8'), object_pairs_hook=_pairs,
                                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeError, ValueError, RecursionError):
        raise TeamLibError('INVALID_PACKAGE', 'JSON record is invalid.') from None
    if not isinstance(result, dict):
        raise TeamLibError('INVALID_PACKAGE', 'JSON record must be an object.')
    return result


def write_json(path, record):
    path = ensure_no_symlinks(path)
    if not isinstance(record, dict):
        raise TeamLibError('INVALID_PACKAGE', 'JSON record must be an object.')
    try:
        content = json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix='.teamlib-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as file:
                file.write(content); file.flush(); os.fsync(file.fileno())
            ensure_no_symlinks(path)
            os.replace(temp, path)
        finally:
            if os.path.exists(temp): os.unlink(temp)
    except (OSError, TypeError, ValueError):
        raise TeamLibError('INVALID_PACKAGE', 'Cannot write JSON record.') from None


def hash_file(path):
    digest = hashlib.sha256()
    with _open_regular(path) as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''): digest.update(chunk)
    return digest.hexdigest()


def _schema_check(schema, value):
    for sub in schema.get('allOf', []): _schema_check(sub, value)
    if 'if' in schema:
        try: _schema_check(schema['if'], value); condition=True
        except TeamLibError: condition=False
        branch=schema.get('then' if condition else 'else')
        if branch is not None: _schema_check(branch, value)
    if 'anyOf' in schema:
        for option in schema['anyOf']:
            try: _schema_check(option, value); return
            except TeamLibError: pass
        raise TeamLibError('INVALID_PACKAGE', 'Record field type or value is invalid.')
    kind = schema.get('type')
    valid = {'object': isinstance(value, dict), 'array': isinstance(value, list), 'string': isinstance(value, str), 'integer': type(value) is int, 'boolean': type(value) is bool, 'null': value is None}
    if kind and not valid.get(kind, False):
        raise TeamLibError('INVALID_PACKAGE', 'Record field type is invalid.')
    if 'const' in schema and (value != schema['const'] or type(value) is not type(schema['const'])):
        raise TeamLibError('INVALID_PACKAGE', 'Record field constant is invalid.')
    if 'enum' in schema and value not in schema['enum']:
        raise TeamLibError('INVALID_PACKAGE', 'Record field value is invalid.')
    if isinstance(value, str):
        if schema.get('format') == 'date':
            try: valid_date=date.fromisoformat(value).isoformat() == value
            except ValueError: valid_date=False
            if not valid_date: raise TeamLibError('INVALID_PACKAGE','Record calendar date is invalid.')
        if len(value) < schema.get('minLength', 0) or (schema.get('pattern') and not re.fullmatch(schema['pattern'], value)):
            raise TeamLibError('INVALID_PACKAGE', 'Record string constraint failed.')
    if type(value) is int and value < schema.get('minimum', value):
        raise TeamLibError('INVALID_PACKAGE', 'Record number constraint failed.')
    if isinstance(value, dict):
        if len(value) < schema.get('minProperties',0):
            raise TeamLibError('INVALID_PACKAGE','Record object must contain concrete fields.')
        if not set(schema.get('required', [])) <= value.keys():
            raise TeamLibError('INVALID_PACKAGE', 'Required record fields are missing.')
        properties = schema.get('properties', {})
        if schema.get('additionalProperties') is False and not value.keys() <= properties.keys():
            raise TeamLibError('INVALID_PACKAGE', 'Unknown record fields are not allowed.')
        for key, item in value.items():
            sub = properties.get(key, schema.get('additionalProperties'))
            if isinstance(sub, dict): _schema_check(sub, item)
    if isinstance(value, list):
        if len(value) < schema.get('minItems', 0):
            raise TeamLibError('INVALID_PACKAGE', 'Record list is empty.')
        if schema.get('uniqueItems') and len({json.dumps(x, sort_keys=True) for x in value}) != len(value):
            raise TeamLibError('INVALID_PACKAGE', 'Duplicate record list items are not allowed.')
        for item in value:
            if 'items' in schema: _schema_check(schema['items'], item)


def validate_record(kind, record):
    if kind not in {'meta','manifest','state','receipt','run','library'}:
        raise TeamLibError('INVALID_PACKAGE', 'Unknown record kind.')
    schema = read_json(Path(__file__).resolve().parents[2] / 'schemas' / (kind + '.schema.json'))
    _schema_check(schema, record)
    if kind == 'meta' and record['id'].split('/')[0] != record['author_key']:
        raise TeamLibError('INVALID_PACKAGE', 'Original author must match the ID namespace.')
    if kind == 'manifest':
        for p in record['entrypoints']:
            safe_relative(p)
            if not p.startswith('payload/'):
                raise TeamLibError('INVALID_PACKAGE', 'Entrypoint must be inside payload.')
        paths = []
        for row in record['files']:
            safe_relative(row['path']); paths.append(row['path'])
            if row['path'] != 'README.md' and not row['path'].startswith('payload/'):
                raise TeamLibError('INVALID_PACKAGE', 'Inventory path must be README or payload.')
        if paths != sorted(paths) or len({p.casefold() for p in paths}) != len(paths):
            raise TeamLibError('INVALID_PACKAGE', 'Inventory paths must be sorted and unique.')
        deps = [(x['id'], x['version']) for x in record['dependencies']]
        if len(deps) != len(set(deps)):
            raise TeamLibError('INVALID_PACKAGE', 'Duplicate dependency locks are not allowed.')
    if kind == 'state':
        if record['recommended_version'] in record['withdrawn_versions']:
            raise TeamLibError('INVALID_PACKAGE', 'Recommended version cannot be withdrawn.')
    if kind == 'receipt':
        for key in ('files','baseline_files'):
            paths=[safe_relative(row['path']) for row in record[key]]
            if paths != sorted(paths) or len({p.casefold() for p in paths}) != len(paths):
                raise TeamLibError('INVALID_PACKAGE', 'Receipt inventories must be sorted and unique.')
        locks={}
        for row in record['releases']:
            safe_relative(row['path'])
            key=(row['id'],row['version'])
            if key in locks or row['path'] != 'releases/'+row['id']+'/'+row['version']:
                raise TeamLibError('INVALID_PACKAGE', 'Receipt release locations must be exact and unique.')
            locks[key]=row['manifest_sha256']
        root=(record['id'],record['version'])
        if locks.get(root) != record['manifest_sha256']:
            raise TeamLibError('INVALID_PACKAGE', 'Receipt root binding does not match installed releases.')
        expected={key:sha for key,sha in locks.items() if key!=root}
        actual={(row['id'],row['version']):row['manifest_sha256'] for row in record['dependency_lock']}
        if actual != expected or len(actual) != len(record['dependency_lock']):
            raise TeamLibError('INVALID_PACKAGE', 'Receipt dependency locks must match all installed dependencies.')
        if any(not Path(record[key]).is_absolute() for key in ('target','baseline','receipt_path')) or ('recovery_backup' in record and not Path(record['recovery_backup']).is_absolute()):
            raise TeamLibError('INVALID_PACKAGE', 'Receipt local provenance paths must be absolute.')
