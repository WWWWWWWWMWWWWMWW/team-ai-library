#!/usr/bin/env python3
"""Small local knowledge-vault helper. JSON stdout; no service or remote writes."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import uuid
import zipfile
import yaml

REQUIRED = ('id', 'type', 'project', 'updated')
# Codex single-direction sync contains byte-preserved Markdown without formal
# frontmatter; keep it out of the formal knowledge-page index.
EXCLUDED = {'系统', '.obsidian', '.git', '方法模板', '模板', 'templates', 'Codex同步'}
GENERATED = {'索引.md', 'AGENTS.md', '首页.md'}
CURRENT_STATES = {
    'freshness': {'current', '当前'},
    'document_state': {'approved', 'final', '定稿'},
    'decision_state': {'confirmed', 'decided', '已确认', '已决定'},
}
TYPE_STATE = {
    'plan_card': 'document_state', '策划文档卡': 'document_state',
    'decision': 'decision_state', '决策': 'decision_state',
    'knowledge': 'freshness', '知识': 'freshness',
    'memory': 'freshness', '记忆': 'freshness',
}
REVIEW = {'needs_review', '需复核'}

class KnowledgeError(Exception):
    pass

def now():
    return datetime.now(timezone.utc).isoformat()

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def unpack(raw):
    text = raw.decode('utf-8-sig')
    match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)(.*)\Z', text, re.S)
    if not match:
        return None, text
    meta = yaml.safe_load(match.group(1))
    if not isinstance(meta, dict):
        raise KnowledgeError('frontmatter must be a mapping')
    return meta, match.group(2)

def pack(meta, body):
    return ('---\n' + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + '---\n' + body).encode('utf-8')

def revision(meta):
    return str(meta.get('working_revision', meta.get('revision', '')))

def noncurrent(meta):
    reasons=[f'{field}:{meta[field]}' for field,allowed in CURRENT_STATES.items() if field in meta and meta[field] not in allowed]
    required_state=TYPE_STATE.get(meta.get('type'))
    if required_state and not meta.get(required_state):
        reasons.append(f'missing_state:{required_state}')
    if meta.get('type') in {'candidate', '候选'}:
        reasons.append('candidate')
    if meta.get('superseded_by'):
        reasons.append('superseded')
    return reasons

def required(meta, path):
    missing = [key for key in REQUIRED if not meta.get(key)]
    if missing:
        raise KnowledgeError(f'missing_metadata {path}: {missing}')
    for key in REQUIRED:
        if not isinstance(meta[key], str):
            # PyYAML timestamp scalars are accepted only as a time, normalized below.
            if key == 'updated' and isinstance(meta[key], datetime):
                meta[key] = meta[key].isoformat()
            else:
                raise KnowledgeError(f'invalid_metadata {path}: {key} must be string')
    try:
        parsed = datetime.fromisoformat(meta['updated'].replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError()
    except ValueError:
        raise KnowledgeError(f'invalid_metadata {path}: updated requires timezone')
    refs = meta.get('derived_from', [])
    if not isinstance(refs, list) or any(not isinstance(ref, dict) for ref in refs):
        raise KnowledgeError(f'invalid_provenance {path}: derived_from must be list of mappings')

class Vault:
    def __init__(self, path):
        self.root = Path(path).expanduser().resolve()
        native = (Path.home()/'.codex/memories').resolve()
        if self.root == native or native in self.root.parents:
            raise KnowledgeError('native_memories_forbidden')
        if not self.root.is_dir():
            raise KnowledgeError('vault must already exist')
    def inside(self, relative):
        p = Path(relative)
        if p.is_absolute() or '..' in p.parts:
            raise KnowledgeError('path_outside_vault')
        path = self.root/p
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if parent != self.root and self.root in parent.parents):
            raise KnowledgeError('symlink_forbidden')
        resolved = path.resolve()
        native = (Path.home()/'.codex/memories').resolve()
        if resolved == native or native in resolved.parents:
            raise KnowledgeError('native_memories_forbidden')
        if resolved != self.root and self.root not in resolved.parents:
            raise KnowledgeError('path_outside_vault')
        return path
    def write_target(self, relative):
        if Path(relative).as_posix() != relative:
            raise KnowledgeError('noncanonical_target')
        path = self.inside(relative)
        if not relative or Path(relative).parts[0] in EXCLUDED or Path(relative).name in GENERATED or path.suffix.lower() != '.md':
            raise KnowledgeError('protected_target')
        return path
    def atomic(self, relative, raw):
        path = self.inside(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            # Check containment again after temporary file creation.
            self.inside(relative)
            os.replace(temp, path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    def json_write(self, relative, obj):
        self.atomic(relative, (json.dumps(obj, ensure_ascii=False, indent=2, default=str) + '\n').encode())
    @contextmanager
    def lock(self):
        path = self.inside('系统/.knowledge.lock')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a+b') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)
    def scan(self, replacements=None):
        replacements = replacements or {}
        pages = {}
        paths = set()
        for path in self.root.rglob('*.md'):
            relative = path.relative_to(self.root).as_posix()
            if set(Path(relative).parts[:-1]) & EXCLUDED or path.name in GENERATED:
                continue
            self.inside(relative)
            if path.is_file():
                paths.add(relative)
        paths.update(replacements)
        for relative in sorted(paths):
            raw = replacements.get(relative)
            if raw is None:
                raw = self.inside(relative).read_bytes()
            meta, body = unpack(raw)
            # Original markdown snapshots without frontmatter aren't formal pages.
            if meta is None:
                continue
            required(meta, relative)
            identifier = meta['id']
            if identifier in pages:
                raise KnowledgeError(f'duplicate_id {identifier}: {pages[identifier]["path"]}, {relative}')
            pages[identifier] = dict(meta=meta, path=relative, raw=raw, body=body, fingerprint=sha(raw))
        return pages
    def journals(self):
        directory = self.inside('系统/内部/操作记录')
        result=[]
        if directory.exists():
            for path in sorted(directory.glob('*.json')):
                self.inside(path.relative_to(self.root).as_posix())
                item=json.loads(path.read_text())
                if item.get('op_id') != path.stem:
                    raise KnowledgeError('invalid_operation_journal')
                result.append(item)
        return result
    def views(self):
        journals=self.journals()
        header='# 更新日志（由操作记录生成）\n\n'
        log=header + '\n'.join(f'- {j["op_id"]} | {j["state"]} | {j.get("updated", "")} | {j.get("authorization", "")}' for j in journals) + '\n'
        pending='# 待同步（由操作记录生成）\n\n' + '\n'.join(f'- {j["op_id"]} | {j["state"]} | {j.get("remaining_steps", [])}' for j in journals if j['state']!='verified') + '\n'
        self.atomic('系统/系统-更新日志.md',log.encode())
        self.atomic('系统/系统-待同步.md',pending.encode())
    def lint_names(self):
        """Check the human-facing vault tree for stable category prefixes."""
        ignored_dirs = {'内部', '原始', '原文件', '采集记录', '.obsidian', '.git'}
        allowed = {'首页.md', '索引.md', 'AGENTS.md'}
        prefixes = {
            '策划案': '策划-', '知识': '知识-', '项目': '项目-',
            '方法模板': '模板-', 'Codex记忆': '记忆-', '工作日志': '日志-',
            '系统': '系统-',
        }
        violations = []
        for path in sorted(self.root.rglob('*')):
            if not path.is_file() or path.suffix not in {'.md', '.base', '.canvas'}:
                continue
            rel = path.relative_to(self.root)
            parts = rel.parts
            if path.name in allowed or any(part in ignored_dirs for part in parts):
                continue
            if parts[0] == '收件箱':
                # Inbox is intentionally a quarantine; its contents are classified later.
                continue
            prefix = prefixes.get(parts[0])
            if parts[0] == '知识' and len(parts) > 1 and parts[1] == '活动规则':
                prefix = '规则-'
            if prefix and not path.name.startswith(prefix):
                violations.append({'path': rel.as_posix(), 'expected_prefix': prefix})
        return {'ok': not violations, 'violations': violations, 'checked': True}

    def index(self):
        pages=self.scan()  # Detect duplicates before any index write.
        data={key:dict(path=p['path'], type=p['meta']['type'], project=p['meta']['project'], revision=revision(p['meta']), freshness=p['meta'].get('freshness'), derived_from=p['meta'].get('derived_from',[]), fingerprint=p['fingerprint']) for key,p in pages.items()}
        rows=['# 索引（可重建，不作为业务依据）','', '| ID | 路径 | 类型 | 项目 | 版本 | 新鲜度 |','| --- | --- | --- | --- | --- | --- |']
        for key,p in data.items():
            escape=lambda value:str(value or '').replace('|','\\|').replace('\n',' ')
            rows.append('| ' + ' | '.join(escape(value) for value in [key,f'[[{p["path"]}]]',p['type'],p['project'],p['revision'],p['freshness']]) + ' |')
        self.atomic('索引.md', ('\n'.join(rows)+'\n').encode())
        self.json_write('系统/索引.json',data)
        self.views()
        return {'pages':data}
    def check(self, ignore_op=None):
        pages=self.scan()
        errors=[]; warnings=[]; graph={key:[] for key in pages}
        def issue(code, page, **details):
            report=dict(code=code, id=page['meta']['id'], path=page['path'], **details)
            native_memory = (
                page['meta'].get('type') == 'memory'
                and details.get('source_id') is None
                and code in {'missing_source','fingerprint_mismatch','revision_mismatch'}
            )
            if native_memory or (page['meta'].get('freshness') in REVIEW and code in {'missing_source','fingerprint_mismatch','revision_mismatch','missing_provenance'}):
                if native_memory:
                    report['reason'] = 'Codex原生记忆只读源可能随会话变化，需人工回读后刷新主题快照'
                warnings.append(report)
            else:
                errors.append(report)
        for identifier,page in pages.items():
            for reason in noncurrent(page['meta']):
                if reason.startswith('missing_state:'):
                    warnings.append(dict(code='missing_state',id=identifier,path=page['path'],field=reason.split(':',1)[1]))
            for ref in page['meta'].get('derived_from',[]):
                source=None; raw=None
                source_id=ref.get('source_id')
                if source_id:
                    graph[identifier].append(source_id)
                    source=pages.get(source_id)
                    if source is None:
                        issue('missing_source',page,source_id=source_id); continue
                    raw=source['raw']
                    # Optional source_path is a cached location; stable ID is authoritative.
                    if ref.get('source_path') and ref['source_path'] != source['path']:
                        warnings.append(dict(code='source_path_moved',id=identifier,path=page['path'],current_path=source['path']))
                elif ref.get('source_path'):
                    p=Path(ref['source_path']).expanduser()
                    if not p.is_absolute():
                        issue('invalid_external_path',page); continue
                    try:
                        raw=p.read_bytes()
                    except OSError:
                        issue('missing_source',page,source_path=str(p)); continue
                    if p.suffix.lower()=='.md':
                        meta,_=unpack(raw)
                        if meta:
                            source={'meta':meta}
                else:
                    issue('missing_source',page); continue
                if not all(ref.get(k) for k in ('source_revision','source_fingerprint','locator')):
                    issue('missing_provenance',page,source_id=source_id)
                if ref.get('source_fingerprint') != sha(raw):
                    issue('fingerprint_mismatch',page,source_id=source_id)
                if source and revision(source['meta']) != str(ref.get('source_revision','')):
                    issue('revision_mismatch',page,source_id=source_id,actual_revision=revision(source['meta']))
                if source and noncurrent(source['meta']):
                    warnings.append(dict(code='source_not_current',id=identifier,path=page['path'],source_id=source_id,source_path=ref.get('source_path'),reasons=noncurrent(source['meta'])))
            if page['meta'].get('source_kind')=='feishu_snapshot':
                warnings.append(dict(code='snapshot_not_live',id=identifier,path=page['path'],captured_at=page['meta'].get('captured_at','unknown')))
            for link in re.findall(r'!?\[\[([^\]]+)\]\]', page['body']):
                target=link.split('|')[0].split('#')[0]
                if not target:
                    continue
                try:
                    exists=self.inside(target).is_file() or self.inside(target+'.md').is_file()
                except KnowledgeError:
                    exists=False
                if not exists:
                    issue('broken_wikilink',page,target=target)
            replacement=page['meta'].get('superseded_by')
            if replacement and replacement not in pages:
                issue('missing_superseding_page',page,target=replacement)
        visiting=set(); visited=set()
        def visit(key, stack):
            if key in visiting:
                errors.append(dict(code='dependency_cycle',id=key,path=pages[key]['path'],chain=stack+[key])); return
            if key in visited or key not in graph:
                return
            visiting.add(key)
            for child in graph[key]:
                visit(child,stack+[key])
            visiting.remove(key); visited.add(key)
        for key in graph:
            visit(key,[])
        for op in self.journals():
            if op['state']!='verified' and op['op_id']!=ignore_op:
                errors.append(dict(code='unresolved_operation',op_id=op['op_id'],state=op['state']))
        return {'ok':not errors, 'errors':errors,'warnings':warnings,'page_count':len(pages)}
    def search(self, query, project, include_noncurrent=False):
        pages=self.scan(); report=self.check()
        own_issues={key:[] for key in pages}
        for item in report['errors']+report['warnings']:
            if item.get('id') in own_issues:
                own_issues[item['id']].append(item)
        pending_ids=set()
        for journal in self.journals():
            if journal['state']!='verified':
                pending_ids.update(journal.get('changed_ids',[]))
        def dependency_issues(key, seen):
            if key in seen:
                return []
            seen.add(key); results=list(own_issues[key])
            if noncurrent(pages[key]['meta']):
                results.append(dict(code='source_not_current',id=key))
            for ref in pages[key]['meta'].get('derived_from',[]):
                if ref.get('source_id') in pages:
                    results.extend(dependency_issues(ref['source_id'],seen))
            if key in pending_ids:
                results.append(dict(code='unresolved_operation',id=key))
            return results
        hits=[]; excluded=[]
        for key,p in pages.items():
            if p['meta']['project']!=project:
                continue
            score=sum((p['body']+' '+p['path']+' '+key).lower().count(term.lower()) for term in query.split())
            if score==0:
                continue
            warnings=dependency_issues(key,set())
            reasons=noncurrent(p['meta'])
            if '待确认' in Path(p['path']).parts or p['meta'].get('type')=='candidate':
                reasons.append('candidate')
            if any(w['code'] not in {'snapshot_not_live','source_path_moved'} for w in warnings):
                reasons.append('dependency_requires_review')
            for ref in p['meta'].get('derived_from',[]):
                src=pages.get(ref.get('source_id'))
                if src and noncurrent(src['meta']):
                    reasons.append('source_not_current')
            hit=dict(id=key,path=p['path'],project=project,revision=revision(p['meta']),freshness=p['meta'].get('freshness'),document_state=p['meta'].get('document_state'),warnings=warnings,reasons=sorted(set(reasons)),authoritative=not reasons,score=score,excerpt=p['body'][:500])
            if reasons and not include_noncurrent:
                excluded.append(hit)
            else:
                hits.append(hit)
        hits.sort(key=lambda h:(not h['authoritative'],-h['score'],h['path']))
        return {'hits':hits[:3],'excluded':excluded,'validation':report,'scope':'local files; fingerprints detect change, not business truth'}
    def prepare(self, entries, authorization):
        if not authorization.strip():
            raise KnowledgeError('authorization_required')
        pages=self.scan(); replacements={}; direct_targets={}
        for entry in entries:
            target=str(entry['target'])
            self.write_target(target)
            if target in replacements:
                raise KnowledgeError('duplicate_target')
            candidate=Path(entry['candidate']).expanduser().read_bytes()
            meta,_=unpack(candidate)
            if meta is None:
                raise KnowledgeError('candidate_requires_frontmatter')
            required(meta,target)
            previous=next((p for p in pages.values() if p['path']==target),None)
            if previous and meta['id']!=previous['meta']['id']:
                raise KnowledgeError('stable_id_change_forbidden')
            replacements[target]=candidate
            direct_targets[meta['id']]=target
        # Mark the dependency closure: metadata edits change whole-file fingerprints too.
        changed_ids=set(direct_targets)
        changed_paths={str(self.inside(target).resolve()) for target in replacements}
        marked=set()
        while True:
            added=False
            for page in pages.values():
                target=page['path']
                if target in marked:
                    continue
                refs=page['meta'].get('derived_from',[])
                affected=any(ref.get('source_id') in changed_ids or (ref.get('source_path') and str(Path(ref['source_path']).expanduser().resolve()) in changed_paths) for ref in refs)
                if affected:
                    raw=replacements.get(target,page['raw'])
                    meta,body=unpack(raw)
                    meta['freshness']='needs_review'; meta['updated']=now()
                    replacements[target]=pack(meta,body)
                    marked.add(target); changed_ids.add(meta['id'])
                    changed_paths.add(str(self.inside(target).resolve())); added=True
            if not added:
                break
        self.scan(replacements)  # Reject hypothetical duplicates before journal/candidate creation.
        op_id=str(uuid.uuid4()); records=[]
        for n,(target,raw) in enumerate(replacements.items()):
            path=self.write_target(target)
            previous=path.read_bytes() if path.is_file() else None
            old_meta,_=unpack(previous) if previous is not None else ({},'')
            new_meta,_=unpack(raw)
            candidate=f'系统/内部/更新候选/{op_id}/{n}.md'
            old=f'系统/内部/修订备份/{op_id}/{n}.md' if previous is not None else None
            self.atomic(candidate,raw)
            if old:
                self.atomic(old,previous)
            records.append(dict(target=target,id=new_meta['id'],base_revision=revision(old_meta or {}),final_revision=revision(new_meta),base_fingerprint=sha(previous) if previous is not None else None,target_fingerprint=sha(raw),candidate_path=candidate,previous_path=old,state='prepared'))
        journal=dict(op_id=op_id,authorization=authorization,changed_ids=[r['id'] for r in records],files=records,state='prepared',created=now(),updated=now(),completed_steps=['candidates_persisted'],remaining_steps=['apply_files','check','index'])
        self.save(journal)
        self.views()
        return journal
    def save(self,journal):
        journal['updated']=now()
        self.json_write(f'系统/内部/操作记录/{journal["op_id"]}.json',journal)
    def apply(self,op_id):
        try:
            uuid.UUID(op_id)
        except ValueError:
            raise KnowledgeError('invalid_op_id')
        path=self.inside(f'系统/内部/操作记录/{op_id}.json')
        journal=json.loads(path.read_text())
        if journal.get('op_id')!=op_id or not journal.get('authorization'):
            raise KnowledgeError('invalid_operation_journal')
        try:
            # Preflight all targets before any apply; existing completed writes still validated.
            validated=[]
            for record in journal['files']:
                target=self.write_target(record['target'])
                candidate=self.inside(record['candidate_path'])
                if not record['candidate_path'].startswith(f'系统/内部/更新候选/{op_id}/'):
                    raise KnowledgeError('invalid_candidate_path')
                raw=candidate.read_bytes()
                if sha(raw)!=record['target_fingerprint']:
                    raise KnowledgeError('candidate_fingerprint_mismatch')
                actual=sha(target.read_bytes()) if target.is_file() else None
                if actual not in (record['base_fingerprint'],record['target_fingerprint']):
                    journal['state']='conflict'; journal['remaining_steps']=['resolve_conflict']; self.save(journal); self.views()
                    raise KnowledgeError(f'conflict {record["target"]}')
                validated.append((record,target,raw))
            self.scan({record['target']:raw for record,_,raw in validated})
            for record,target,raw in validated:
                # Re-read immediately before replace; lock protects only cooperative scripts.
                actual=sha(target.read_bytes()) if target.is_file() else None
                if actual==record['target_fingerprint']:
                    record['state']='written'
                elif actual==record['base_fingerprint']:
                    self.atomic(record['target'],raw)
                    record['state']='written'
                else:
                    journal['state']='conflict'; self.save(journal); self.views()
                    raise KnowledgeError(f'conflict {record["target"]}')
                journal['state']='content_written'; self.save(journal)
            report=self.check(ignore_op=op_id)
            content_errors=[item for item in report['errors'] if item['code']!='unresolved_operation']
            if content_errors:
                raise KnowledgeError('post_write_check_failed: '+json.dumps(content_errors,ensure_ascii=False))
            self.index()
            journal['state']='verified'; journal['completed_steps']=['candidates_persisted','apply_files','check','index']; journal['remaining_steps']=[]
            journal['verification']=report; self.save(journal); self.views()
            return journal
        except Exception as exc:
            if journal['state']!='conflict':
                journal['state']='pending'; journal['remaining_steps']=['resume_check_and_index']; journal['error']=str(exc); self.save(journal)
                try:
                    self.views()
                except OSError:
                    pass
            raise
    def backup(self,output):
        destination=Path(output).expanduser().resolve()
        if destination==self.root or self.root in destination.parents:
            raise KnowledgeError('backup_must_be_outside_vault')
        native=(Path.home()/'.codex/memories').resolve()
        if destination==native or native in destination.parents:
            raise KnowledgeError('native_memories_forbidden')
        if destination.exists():
            raise KnowledgeError('backup_destination_exists')
        files=[]
        for path in self.root.rglob('*'):
            if path.is_symlink():
                raise KnowledgeError('backup_symlink_forbidden')
            if path.is_file():
                relative=path.relative_to(self.root).as_posix()
                self.inside(relative)
                files.append((path,relative))
        destination.parent.mkdir(parents=True,exist_ok=True)
        fd,temp=tempfile.mkstemp(prefix='.knowledge-backup-',dir=destination.parent); os.close(fd)
        try:
            with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as archive:
                for path,relative in files:
                    archive.write(path,relative)
            with zipfile.ZipFile(temp) as archive:
                if archive.testzip():
                    raise KnowledgeError('backup_verification_failed')
            with open(temp,'rb') as handle:
                os.fsync(handle.fileno())
            os.replace(temp,destination)
            directory=os.open(destination.parent,os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        return dict(path=str(destination),files=len(files),sha256=sha(destination.read_bytes()),scope='entire vault including attachments; external originals are not copied')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault',required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('index'); sub.add_parser('check'); sub.add_parser('lint-names')
    search=sub.add_parser('search'); search.add_argument('query'); search.add_argument('--project',required=True); search.add_argument('--include-noncurrent',action='store_true')
    prepare=sub.add_parser('prepare'); prepare.add_argument('--target'); prepare.add_argument('--candidate'); prepare.add_argument('--manifest'); prepare.add_argument('--authorization',required=True)
    for name in ('apply','resume'):
        p=sub.add_parser(name); p.add_argument('--op',required=True)
    backup=sub.add_parser('backup'); backup.add_argument('--output',required=True)
    args=parser.parse_args()
    try:
        vault=Vault(args.vault)
        if args.command=='lint-names':
            result=vault.lint_names(); code=0 if result['ok'] else 1
        elif args.command=='check':
            result=vault.check(); code=0 if result['ok'] else 1
        elif args.command=='search':
            result=vault.search(args.query,args.project,args.include_noncurrent); code=0
        else:
            with vault.lock():
                if args.command=='index':
                    result=vault.index()
                elif args.command=='prepare':
                    if args.manifest and (args.target or args.candidate):
                        raise KnowledgeError('choose_manifest_or_single_target')
                    if args.manifest:
                        entries=json.loads(Path(args.manifest).read_text())
                        if not isinstance(entries,list) or not entries:
                            raise KnowledgeError('manifest_requires_nonempty_list')
                    elif args.target and args.candidate:
                        entries=[dict(target=args.target,candidate=args.candidate)]
                    else:
                        raise KnowledgeError('target_and_candidate_required')
                    result=vault.prepare(entries,args.authorization)
                elif args.command in ('apply','resume'):
                    result=vault.apply(args.op)
                else:
                    result=vault.backup(args.output)
                code=0
        print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
        return code
    except (KnowledgeError,OSError,ValueError,KeyError,TypeError,yaml.YAMLError) as exc:
        print(json.dumps({'ok':False,'error':str(exc)},ensure_ascii=False))
        return 1

if __name__=='__main__':
    raise SystemExit(main())
