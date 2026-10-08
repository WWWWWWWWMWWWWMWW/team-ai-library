"""Generate human and machine navigation from a fresh approved shared snapshot."""
import html
import json
from pathlib import Path
import re
import tempfile
import os
from urllib.parse import quote
from .contracts import TeamLibError, ensure_no_symlinks, read_json, validate_id
from .dependencies import load_catalog, resolve_dependencies
from .install import _revocation_check
from .package import validate_release, scan_text

KINDS = {'skill':'技能','workflow':'工作流','prompt':'提示词','tool':'工具',
         'case':'案例','lesson':'经验','research':'研究资料'}
MARKER = '<!-- teamlib-catalog: generated -->'
LABELS = {'any':'通用','planning-review':'策划案审查','meeting-summary':'会议记录整理',
          'experience-summary':'经验整理','recovery-review':'恢复复盘','reference-review':'资料核查',
          'production-change':'生产环境变更','external-send':'对外发送','unrequested-upload':'未明确要求的上传',
          'filesystem.read':'读取本地材料','read_only':'只读输入'}
AVAILABILITY = {'active':'可进一步检查使用','withdrawn':'已撤回','revoked':'已作废','blocked_dependency':'依赖已停用'}


def build_catalog(snapshot, *, pending=None, pending_status='not_checked'):
    if not re.fullmatch(r'[0-9a-f]{40}', snapshot.get('source_commit','')):
        raise TeamLibError('STATUS_UNVERIFIED','A concrete shared source commit is required.')
    if pending_status not in {'available','unavailable','not_checked'}:
        raise TeamLibError('INVALID_PACKAGE','Unknown pending-list state.')
    records = load_catalog(snapshot['root'])
    policy=read_json(Path(snapshot['root'])/'governance/policy.json')
    for row in records.values(): validate_release(Path(row['release_root']),policy=policy)
    releases = []
    for (identifier, version), row in sorted(records.items(), key=lambda pair:(pair[0][0],tuple(-int(v) for v in pair[0][1].split('.')))):
        state, meta = row['state'], row['meta']
        closure = resolve_dependencies(records,(identifier,version))
        def package(keys):
            return {'source_commit':snapshot['source_commit'], 'releases':[
                {'id':i,'version':v,'manifest_sha256':records[(i,v)]['manifest_sha256']} for i,v in keys]}
        availability = 'withdrawn' if version in state['withdrawn_versions'] else 'active'
        try: _revocation_check(snapshot,package([(identifier,version)]))
        except TeamLibError as exc:
            if exc.code!='WITHDRAWN': raise
            availability='revoked'
        if availability=='active':
            try: _revocation_check(snapshot,package(closure))
            except TeamLibError as exc:
                if exc.code!='WITHDRAWN': raise
                availability='blocked_dependency'
            if any(v in records[(i,v)]['state']['withdrawn_versions'] for i,v in closure if (i,v)!=(identifier,version)):
                availability='blocked_dependency'
        verification=[e for e in state['verification'] if e['id']==identifier and e['version']==version
                      and e['manifest_sha256']==row['manifest_sha256']]
        outcomes={e['result'] for e in verification}
        label = ('有通过与失败记录，须核对范围' if {'passed','failed'}<=outcomes else
                 '有失败记录' if 'failed' in outcomes else
                 '仅在记录范围通过' if 'passed' in outcomes else '未验证')
        prefix=f'entries/{identifier}/releases/{version}/'
        releases.append({**{key:meta[key] for key in ('id','title','summary','kind','tags','aliases','author_key','owner_key','source')},
                         'version':version,'manifest_sha256':row['manifest_sha256'],
                         'recommended':state['recommended_version']==version and availability=='active',
                         'availability':availability,'verification':verification,'verification_label':label,
                         **{key:row[key] for key in ('scope','compatibility','effects','dependencies')},
                         'readme':prefix+'README.md','entrypoints':[prefix+path for path in row['entrypoints']]})
    return {'schema_version':1,'generator':'teamlib-catalog',
            'source':{'repository':snapshot['repository'],'branch':snapshot['shared_branch'],'commit':snapshot['source_commit']},
            'capability_count':len({row['id'] for row in releases}),'version_count':len(releases),
            'releases':releases,'pending_status':pending_status,
            'pending_requests':sorted(pending or [],key=lambda row:row['number'])}


def _cell(value):
    text=html.escape(str(value),quote=False).replace('\\','\\\\')
    for char in ('[',']','*','`'): text=text.replace(char,'\\'+char)
    return text.replace('|','&#124;').replace('\r\n','\n').replace('\r','\n').replace('\n','<br>')


def _words(values): return '、'.join(_cell(LABELS.get(value,value)) for value in values) or '未指定'
def _link(label,path): return '['+_cell(label)+']('+quote('../'+path,safe='/._-')+')'


def render_markdown(record):
    lines=[MARKER,'# 团队能力总目录','',
           '按用途与类型浏览，点能力名称查看固定版本说明。此目录由 AI 从已批准共享内容生成，更新时无需上传者手填。','',
           f"已入库能力 **{record['capability_count']} 项**，版本 **{record['version_count']} 个**。条目入库不等于业务验证；使用前仍运行 search / check-reuse 核对当前状态与任务范围。",'',
           '## 快速入口','',
           '- [接入能力库](MEMBER_PROMPT.md) · [盘点我的 Codex](CODEX_CAPTURE_PROMPT.md) · [整理项目素材](LOCAL_CAPTURE_PROMPT.md)',
           '- [AI 操作手册](AI_OPERATIONS.md) · [具体命令](AI_GUIDE.md) · [目录维护规则](CATALOG_GUIDE.md)',
           '- '+' · '.join(f'[{label}](#{label})' for label in KINDS.values())+' · [待审核材料](#待审核材料)',
           '- [供 AI 读取的同源索引](catalog.json)','',
           '## 已入库内容','',
           '“推荐”只来自条目的明确状态，停用及依赖停用的版本不标推荐。验证记录仅绑定本版材料，不外推到其他环境或任务。']
    for kind,label in KINDS.items():
        rows=[row for row in record['releases'] if row['kind']==kind]
        lines+=['',f'## {label}','']
        if not rows:
            lines+=['尚无已入库条目。']; continue
        lines+=['| 能力及说明 | 解决什么问题 | 输入 → 产物 | 版本与状态 | 业务验证 | 依赖及使用入口 |',
                '|---|---|---|---|---|---|']
        for row in rows:
            name=_link(row['title'],row['readme'])+'<br>'+_cell(row['id'])
            inputs=_words(row['scope']['inputs'])+' → '+_words(row['scope']['outputs'])
            version=_cell(row['version'])+('（推荐）' if row['recommended'] else '')+'<br>'+AVAILABILITY[row['availability']]
            dependencies='<br>'.join(_link(dep['id']+'@'+dep['version'],f"entries/{dep['id']}/releases/{dep['version']}/README.md") for dep in row['dependencies']) or '无团队能力依赖'
            starts='<br>'.join(_link('使用入口'+str(n),path) for n,path in enumerate(row['entrypoints'],1))
            lines.append('| '+' | '.join([name,_cell(row['summary']),inputs,version,_cell(row['verification_label']),dependencies+'<br>'+starts])+' |')
        for row in rows:
            lines+=['',f"### {_cell(row['title'])}（{row['version']}）",'',
                    '- 适用：'+_words(row['scope']['includes'])+'；不适用：'+_words(row['scope']['excludes'])+'。',
                    '- 环境：'+_words(row['compatibility']['os'])+'；工具：'+_words(row['compatibility']['tools'])+'；必要操作能力：'+_words(row['compatibility']['capabilities'])+'。',
                    '- 副作用约定：'+_words(row['effects'])+'；运行时条件：'+_cell(json.dumps(row['compatibility']['runtimes'],ensure_ascii=False))+'。',
                    '- 搜索词：'+_words(row['tags']+row['aliases'])+'。',
                    '- 来源：'+_cell(row['source']['reference'])+'；原作者：'+_cell(row['author_key'])+'；当前负责人：'+_cell(row['owner_key'])+'。']
            for evidence in row['verification']:
                lines.append('- 验证记录：'+_cell(evidence['date'])+'，'+_cell(evidence['business_scope'])+'，'+_cell(evidence['tool'])+'，结果 '+_cell(evidence['result'])+'；证据：'+_words(evidence['evidence'])+'。')
    lines+=['','## 待审核材料','',
            '以下仅是生成目录时的请求快照，尚未入库，不能当已共享能力下载。具体内容、最新版本与审核状态以平台请求为准。','']
    if record['pending_status']=='available':
        if not record['pending_requests']: lines+=['生成时未发现待审核请求。']
        else:
            lines+=['| 请求 | 材料类别 | 涉及能力 | 阶段 |','|---|---|---|---|']
            kinds={'publication':'能力投稿','maintenance':'工具与规则维护','governance':'状态与权限治理','mixed':'混合变更，须核验'}
            for row in record['pending_requests']:
                lines.append(f"| [审核请求 #{row['number']}]({row['url']}) | {kinds[row['kind']]} | {_words(row['ids']) if row['ids'] else '仓库维护材料'} | 待审核 |")
    elif record['pending_status']=='unavailable': lines+=['未能刷新待审核列表，请查看仓库平台；不能将缺失列表理解为没有待审核材料。']
    else: lines+=['本次未查询待审核列表，请查看仓库平台。']
    lines+=['','## 目录来源与时效','',
            f"- 来源：{_cell(record['source']['repository'])}，共享分支 {_cell(record['source']['branch'])}。",
            f"- 固定来源提交：`{record['source']['commit']}`。",
            '- 目录和机器索引由同一快照生成；可能落后于后续发布、撤回与新投稿，使用前以实时查找、状态查询和使用前检查为准。','']
    return '\n'.join(lines)


def collect_pending(config):
    from .platform import repository_name, _paginated, _api
    repo=repository_name(config); branch=quote(config['shared_branch'],safe='')
    requests=_paginated(repo,f'/pulls?state=open&base={branch}&per_page=100')
    rows=[]
    for request in requests:
        number=request.get('number'); head=request.get('head',{}).get('sha','')
        if type(number) is not int or number<=0 or not re.fullmatch(r'[0-9a-f]{40}',head):
            raise TeamLibError('STATUS_UNVERIFIED','Pending request identity is invalid.')
        if request.get('base',{}).get('ref')!=config['shared_branch']:
            raise TeamLibError('STATUS_UNVERIFIED','Pending request base is inconsistent.')
        files=_paginated(repo,f'/pulls/{number}/files?per_page=100')
        ids=set(); maintenance=False; governance=False; has_entries=False
        for file in files:
            name=file.get('filename','')
            if not isinstance(name,str): raise TeamLibError('STATUS_UNVERIFIED','Pending paths are invalid.')
            if name.startswith('entries/'):
                parts=name.split('/')
                if len(parts)<4: raise TeamLibError('STATUS_UNVERIFIED','Pending entry identity is invalid.')
                identifier='/'.join(parts[1:3]); validate_id(identifier); ids.add(identifier); has_entries=True
                if name.endswith('/state.json') and file.get('status')!='added': governance=True
            elif name.startswith('governance/'): governance=True
            else: maintenance=True
        latest=_api(repo,f'/pulls/{number}')
        if latest.get('state')!='open': continue
        if latest.get('head',{}).get('sha')!=head or latest.get('base',{}).get('ref')!=config['shared_branch']:
            raise TeamLibError('STATUS_UNVERIFIED','Pending request changed during collection.')
        kind='mixed' if maintenance and has_entries else 'maintenance' if maintenance else 'governance' if governance else 'publication'
        rows.append({'number':number,'kind':kind,'ids':sorted(ids),'head_commit':head,'url':f'https://github.com/{repo}/pull/{number}'})
    return rows


def write_catalog(record, directory, *, web_html=None):
    directory=ensure_no_symlinks(Path(directory).absolute())
    markdown=render_markdown(record)
    encoded=json.dumps(record,ensure_ascii=False,indent=2)+'\n'
    scan_text(markdown,'catalog_markdown'); scan_text(encoded,'catalog_json')
    targets=[(directory/'CATALOG.md',markdown),(directory/'catalog.json',encoded)]
    if web_html is not None:
        from .local_web import MARKER as WEB_MARKER
        if not web_html.startswith(WEB_MARKER):
            raise TeamLibError('INVALID_PACKAGE','Local web output lacks its generated marker.')
        targets.append((directory/'local-library.html',web_html))
    for target,_ in targets:
        ensure_no_symlinks(target)
        if target.exists():
            valid=(target.read_text(encoding='utf-8').startswith(WEB_MARKER) if target.suffix=='.html' else
                   target.read_text(encoding='utf-8').startswith(MARKER) if target.suffix=='.md' else
                   read_json(target).get('generator')=='teamlib-catalog')
            if not valid: raise TeamLibError('CONFLICT','Existing manual directory must be preserved.')
    directory.mkdir(parents=True,exist_ok=True)
    for target,content in targets:
        fd, staging=tempfile.mkstemp(prefix='.teamlib-catalog-',dir=directory)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                stream.write(content); stream.flush(); os.fsync(stream.fileno())
            ensure_no_symlinks(target); os.replace(staging,target)
        finally:
            if os.path.exists(staging): os.unlink(staging)
    paths={'markdown':str(targets[0][0]),'json':str(targets[1][0])}
    if web_html is not None: paths['html']=str(targets[2][0])
    return paths
