# AI 操作指南

`tools/library.py` 已实现，Python 3.11+、标准库即可运行；GitHub 操作还需要 Git 和已登录个人账号的 `gh`。先读本仓库 `AGENTS.md`，再按用户当前意图选择流程。本文命令在仓库根目录运行，JSON 只保存脱敏任务摘要。

实际仓库为 private 的 [WWWWWWWWMWWWWMWW/team-ai-library](https://github.com/WWWWWWWWMWWWWMWW/team-ai-library)、共享 `main`。当前只有 owner 维护者，分支保护设置遇到 403/Pro 条件，服务器硬门禁未生效。当前选择仅 owner 的 `owner_trial` 试用方案，部署到可信共享基线并验证后才可创建试用 PR；真实试用投稿验收待完成。源码、配置、指南与六个示例已于 2026-10-08 初始化到 main，读取可用；试用方案不会开放第二成员。下面涉及远端条目的示例以当前账号/成员映射可读为前提。

## 按意图选择命令

| 用户意图 | 命令 | 可报告的完成阶段 |
|---|---|---|
| 检查接入 | `doctor` | 接入/发布条件检查；阻断按具体缺项报告 |
| 查找 | `search` | `prepared`；返回范围和候选，不安装 |
| 校验待分享条目 | `validate` | `prepared`；本地校验，不执行 payload |
| 下载固定版本 | `fetch` | `downloaded`；完整材料与依赖已保存 |
| 保存到明确材料目录 | `install` | `installed`；仅 library-directory，有真实收据 |
| 使用前核对 | `check-reuse` | `prepared`；不是业务验证或新增执行授权 |
| 记录实际结果 | `record-run` | `reused` 表示本地记录已写入，实际通过与否看 result |
| 本机明确更新 | `update` | 成功为 `installed`；冲突则保全并阻断 |
| 整理改编来源 | `derive` | `prepared`；保留来源与变化，不上传 |
| 明确分享/同步 | `propose` | 请求存在为 `submitted`，核实合并材料后才是 `published` |
| 查询投稿 | `status` | 按实际请求和共享材料报告，不猜成功 |
| 明确申请撤回 | `withdraw` | issue 成立为 `submitted`，不等于已撤回 |

“同步团队库”有歧义且会改变远端/本地材料时，先确定是拉取还是回传。不要把查找、下载、安装和分享混作同一个操作。

## 配置、登录与状态

```sh
python3 tools/library.py --help
python3 tools/library.py doctor
python3 tools/library.py search --query '审策划案'
```

默认使用仓库根目录 `library.json`，workspace 为 `.teamlib-workspace`。自定义 workspace 时，后续 JSON/下载/日志路径都要替换为实际 workspace，selection 也可使用实际绝对路径。自有本机配置可显式传入；`--config`、`--workspace` 可放在命令前或子命令后，目录仍受安全校验：

```sh
python3 tools/library.py --config library.local.json search --query '策划案'
```

`doctor` 分别核对读取条件和当前模式的投稿条件；投稿阻断时，读取通过仍保留 `data.readable=true`、`can_publish=false` 和 `publishing_failure`，按具体诊断处理。读取流程独立校验个人登录、private/pull 权限、可信共享成员映射及 main；不通过这些读取条件时仍须停止。

`deployment_mode` 是可选配置，省略为 `protected`，要求可核实的正式分支保护。`owner_trial` 仅允许 GitHub 私有库的唯一 owner 试用；它必须先写入经过批准的共享基线，不能仅改 `library.local.json` 或加本机标志启用。真实写入前重新检查 owner 身份、admin/push 权限、全部分页协作者只有 owner、无待处理邀请，以及可信成员映射只有 owner 维护者。共享配置也必须为 `owner_trial`，且 remote、shared_branch、platform、publish_mode=request、auto_merge=false 与本机一致。任何一项不符即停止写入；不要换身份、改为 local 平台或跳过检查。

试用结果应明确 `owner_trial=true`、`hard_gate_enforced=false`、`manual_review_required=true`。这些字段说明 owner 试用和人工审核责任，不能证明服务器禁止绕过。新增任何协作者或邀请后写入即阻断，须切回 `protected` 并重测门禁才能开放多人。主分支尚无初始化材料时，不把本地未提交内容当共享条目。

工具代码来自当前 clone；能力材料从独立工作区新鲜获取共享分支，因而 `clone HEAD` 可以与下载/复用的 `source_commit` 不同。以工具实际来源锁为准，不将仓库提交变化自动视为能力版本升级。更新工具指南时先保护本机改动，再由 AI 核对已批准共享分支。

每个命令 stdout 为一个 JSON 结果：protocol_version、operation_id、operation、state、code、message、data、checks、next_action。`code=OK` 的成功退出码为0；受控阻断为2，内部错误为1。每一步先看退出码及状态，再进行依赖它的下一步。

## 下载与临时复用示例

下面使用内置 `owner/design-review/0.1.0`：输入“策划案”、输出“审查报告”、范围标签 `planning-review`、要求 `filesystem.read`、effects=`read_only`。这项示例业务未验证。先阅读搜索结果或 manifest，只有实际任务符合时才采用这些值，不为通过检查伪填范围或权限。

```sh
python3 tools/library.py fetch --id owner/design-review --version 0.1.0 --dest .teamlib-workspace/downloads/design-review-0.1.0
```

下载目标须不存在；这个 workflow 精确依赖 `owner/review-checklist/0.1.0`，工具会同时下载并核对该 Skill 材料，selection 仍指向整个 workflow 下载根目录。完整包含 `download.json` 与 `releases/<id>/<version>`，依赖均固定在同一 source_commit。`downloaded` 不代表安装或执行。离线不能用旧缓存冒充最新撤回状态。

创建 `.teamlib-workspace/selection.json`：

```json
{
  "download_path": ".teamlib-workspace/downloads/design-review-0.1.0"
}
```

创建 `.teamlib-workspace/context.json`，按本次实际环境和用户授权填写；下面以 macOS 中只读审查为例：

```json
{
  "task_scope": {
    "inputs": ["策划案"],
    "outputs": ["审查报告"],
    "includes": ["planning-review"],
    "excludes": []
  },
  "environment": {
    "os": "macos",
    "tools": ["Codex desktop"],
    "capabilities": ["filesystem.read"],
    "runtimes": {}
  },
  "effects_authorized": ["read_only"]
}
```

AI 可以用正常文件工具写这两个 JSON；不要在里面放策划案原文、完整聊天或凭据。然后运行：

```sh
python3 tools/library.py check-reuse --selection .teamlib-workspace/selection.json --context .teamlib-workspace/context.json > .teamlib-workspace/preflight.json
```

确认 `code=OK`、`state=prepared`，逐项阅读 `data.checks` 和 `data.sources`。核验包括完整实际材料/传递依赖、固定来源、fresh 撤回/作废、范围、环境、已授权 effects。`business_verified=false`、`execution_authorized=false` 不会因检查成功变成 true。

通过后，读取下载包 `releases/owner/design-review/0.1.0/README.md`、manifest 的入口 `payload/instructions.md`，以及依赖 `releases/owner/review-checklist/0.1.0/payload/SKILL.md`，在当前任务授权内执行审查。不要自动运行包内脚本、安装 npm/pip 依赖、修改原稿或发送报告。此示例 `read_only` 描述对业务输入及项目的作用；在当前用户授权下生成本地审查报告、下载记录与工具证据属于本地输出，不能据此取得修改原稿或远端发送权限。实际任务需要写文件/改项目/远程发送时，须使用适用范围和 effects 都覆盖的能力，并获得对应用户授权，不能把这份只读示例扩大使用。

换条目或版本时重新填写实际 scope/environment/effects；不能沿用其他版本的业务证据。材料被本地改动会阻断原版复用，不能改 receipt/download.json 的摘要让它冒充原版。

## 材料目录安装与更新

仅当用户要求长期保存到配置目标时运行：

```sh
python3 tools/library.py install --id owner/design-review --version 0.1.0 --target local_materials
```

`local_materials` 已配置为 `.teamlib-installed`，tool=`library-directory`。目标必须为空或不存在；已存在未知内容不覆盖。同一材料目标不会默认容纳另一项独立安装。成功的 `data.receipt_path` 是实际收据位置，workspace 保存独立目标绑定和上游基线。

安装仍保存完整 `releases/<id>/<version>/...`，**不注册原生 Codex Skill**。`owner/review-checklist` 即使含 `payload/SKILL.md`，也只是可读取的 Skill 材料；不能报告 AI 已自动发现。

用安装收据复用时，selection JSON 只能选一个 receipt，填实际返回的绝对位置：

```json
{
  "receipt_path": "/实际仓库/.teamlib-workspace/installations/实际安装ID/receipt.json"
}
```

CLI 的 `--selection` 指向上述 JSON 文件，不是直接指向 download.json 或 receipt.json。安装ID和位置不能预填或从示例猜测。

用户明确更新且目标版本实际已发布时：

```sh
python3 tools/library.py update --receipt /实际返回的/receipt.json --version 0.2.0
```

`0.2.0` 只是待替换为实际已发布版本的示意，当前内置示例只有 `0.1.0`。工具按 base/local/upstream 比较：安全变化更新，未知本地文件保留；双方改同文件或上游删除已改文件则 `CONFLICT`，保留原件和候选，不自动合并脚本/工作簿。新 baseline 始终是新上游原版，receipt.files/local_changes 记录实际材料。恢复副本不会默认删除。

改编材料不继承原版验证。当前 check-reuse 仍会阻断其按原锁使用；derive 只记录来源，不是绕过检查的执行入口。

## 实际复用后记录

从成功 check-reuse 的 `data.sources` 提取真实锁定来源，保存为 `.teamlib-workspace/sources.json`，结构为 `{"sources":[...]}`。不得造 SHA；可执行以下本地提取，条件不满足则停止：

```sh
python3 - <<'PY'
import json
from pathlib import Path
workspace = Path('.teamlib-workspace')
check = json.loads((workspace / 'preflight.json').read_text(encoding='utf-8'))
if check.get('code') != 'OK' or check.get('state') != 'prepared':
    raise SystemExit('Reuse checks have not passed')
(workspace / 'sources.json').write_text(
    json.dumps({'sources': check['data']['sources']}, ensure_ascii=False, indent=2) + '\n',
    encoding='utf-8')
PY
```

实际使用后写 `.teamlib-workspace/run-summary.json`，根据结果填写；以下保守模板不声称业务通过：

```json
{
  "task_goal": "核对本次策划案的规则闭环",
  "environment": {"os": "macos", "tool": "Codex desktop"},
  "result": "unverified",
  "artifacts": [],
  "change_summary": "填写实际审查范围、修改或本地偏离摘要",
  "unverified": ["真实运行表现未验证"]
}
```

`result` 只允许 `passed`、`failed`、`unverified`；已实际核对业务验收条件才能写 passed。artifacts 填真实产物位置，多项能力保留全部来源；不记录完整聊天、原始业务输入或凭据。

```sh
python3 tools/library.py record-run --sources .teamlib-workspace/sources.json --summary .teamlib-workspace/run-summary.json
```

当前 run 的 started_at/finished_at 是记录时刻，不记录或证明实际任务耗时；需要业务执行时长时须另收集实际证据。

记录在本地 workspace/runs；`reused` 表示记录成功，不会替你执行任务或证明任务 passed。不自动上传经验。

改编时，source JSON 从已核对来源取 repository/id/version/manifest_sha256/source_commit；changes JSON 为：

```json
{
  "changed_files": ["payload/instructions.md"],
  "change_summary": "填写实际变化及适用范围变化"
}
```

```sh
python3 tools/library.py derive --source .teamlib-workspace/source.json --changes .teamlib-workspace/changes.json
```

得到 derived_from、changed_files、change_summary 和未验证声明。行为变化要产生新版本；只有用户明确要求共享才进入投稿流程。

## 上传时的中文说明格式

AI 整理材料后，先把能力名称、用途摘要、版本 README、提交说明和 PR 文案写成策划能理解的中文，再提交。条目 ID/版本/文件名可保留技术形式，但不能作为唯一说明。不要让策划自己填写这些字段。

提交标题示例：`新增工作流：活动配置表检查`。提交正文和 PR 正文应按以下内容组织；同能力升级必须具体写出本次变化：

1. **分享的内容**：它是什么、解决什么问题；不只写“新增了一个 Skill”。
2. **适用范围**：什么时候用，哪些情况不能用，需要什么输入，得到什么产物。
3. **怎么复用**：入口文件、准备条件、按顺序执行的步骤、结果核查；至少给一个脱敏示例。
4. **依赖与权限**：需要哪些团队能力或外部工具，会不会写文件或操作远端。
5. **本次变化**：新增哪些材料，改了哪些步骤，与原版有什么行为差异；未改动的旧版本不冒充升级。
6. **验证情况**：实际检查了什么、结果与证据；没有运行过的业务写“未验证”，不把上传成功写成能力有效。
7. **来源与限制**：原作者、改编来源、踩过的坑及已知限制。

工具会依据已校验的名称、摘要、各版本范围/入口/依赖/文件清单生成中文提交说明和 PR 概要。它不会替 AI 推断业务步骤、本次业务差异或效果；这些必须根据真实材料写入中文版本 README。标题与正文仍走完整出站检查和请求摘要绑定。

## 投稿、查询与撤回

用户可以说“把这份改进整理后分享到库里，检查通过后创建 PR，合并前让我核验”。这已授权 AI 准备包、检查出站材料并创建 PR；不代表授权合并。

`protected` 模式需要正式门禁通过；`owner_trial` 需要可信共享部署和每次 owner 独占检查通过。满足对应条件且用户明确要求分享/撤回后可运行以下命令；不要为演示自动创建远端请求。当前真实试用 PR 验收待完成，部署前不能报告投稿已启用。

本地可先准备完整 entry（meta/state/releases）并校验：

```sh
python3 tools/library.py validate --entry /实际待分享条目目录
```

首次 state 用模板且 owner/author 对应可信账号；既有条目按当前 state.owner_key 权限，新版本不可改写旧 release。普通投稿不修改既有治理状态。分享范围限定用户授权材料，出站清单、提交说明、标题、正文及新增历史均检查；不透明材料无法确定分享范围则保留本地。

```sh
python3 tools/library.py propose --entry /实际待分享条目目录
python3 tools/library.py status --request 实际PR编号或URL
```

propose 创建请求只是 submitted。owner 试用须在结果和请求正文明确“仅 owner 试用、服务器硬门禁未生效、需要人工审核”；由人核验具体 PR 的材料与检查结果，再明确授权合并，AI 不自动 merge。status 需要原投稿收据（通常工具在 workspace/proposals 找到），也可用 `--expected /实际投稿记录.json`。只有合并后共享材料和期望摘要匹配才 published，仍不等于业务验证。超时先查原请求，不盲目重复投稿，不直推 main、不自动合并。

```sh
python3 tools/library.py withdraw --id owner/design-review --version 0.1.0 --reason '填写本次非敏感撤回原因'
python3 tools/library.py status --kind governance --request 实际issue编号或URL
```

上述 ID/version 也必须换成用户明确申请的对象。withdraw 建立治理 issue，不修改本地/远端版本状态；issue closed 也不能证明撤回已经生效。维护者另按审核流程生成 state 提案，合并后核实。恢复使用明确安全版本、完整依赖和新的范围检查，不自动回滚业务项目，不强推或重写历史。

命令不成功时保留材料，报告 code、operation_id、阻断项及下一步。登录、成员映射、共享部署、当前模式条件分别处理，不能用缓存、假身份或跳过检查声称成功。完整包检查、不可变版本、可信基线检查器与当前内容/状态绑定在试用中继续执行。
