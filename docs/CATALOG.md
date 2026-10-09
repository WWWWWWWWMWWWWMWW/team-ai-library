<!-- teamlib-catalog: generated -->
# 团队能力总目录

按用途与类型浏览，点能力名称查看固定版本说明。此目录由 AI 从已批准共享内容生成，更新时无需上传者手填。

已入库能力 **22 项**，版本 **22 个**。条目入库不等于业务验证；使用前仍运行 search / check-reuse 核对当前状态与任务范围。

## 快速入口

- [接入能力库](MEMBER_PROMPT.md) · [盘点我的 Codex](CODEX_CAPTURE_PROMPT.md) · [整理项目素材](LOCAL_CAPTURE_PROMPT.md)
- [AI 操作手册](AI_OPERATIONS.md) · [具体命令](AI_GUIDE.md) · [目录维护规则](CATALOG_GUIDE.md)
- [技能](#技能) · [工作流](#工作流) · [提示词](#提示词) · [工具](#工具) · [案例](#案例) · [经验](#经验) · [研究资料](#研究资料) · [处理中请求](#处理中请求)
- [供 AI 读取的同源索引](catalog.json)

## 已入库内容

“推荐”只来自条目的明确状态，停用及依赖停用的版本不标推荐。验证记录仅绑定本版材料，不外推到其他环境或任务。

## 技能

| 能力及说明 | 解决什么问题 | 输入 → 产物 | 版本与状态 | 业务验证 | 依赖及使用入口 |
|---|---|---|---|---|---|
| [大乐透可靠查询与统计分析](../entries/owner/dlt-reliable-analysis/releases/0.1.0/README.md)<br>owner/dlt-reliable-analysis | 基于官方数据源和白名单镜像，完成开奖查询、历史统计、对奖核验和固定种子娱乐样本，不将统计包装成预测。 | 期号或历史数据、官方/白名单数据源、分析窗口 → 来源核验、统计结果、对奖报告或娱乐样本 | 0.1.0<br>已撤回 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/dlt-reliable-analysis/releases/0.1.0/payload/SKILL.md) |
| [游戏计费点批量生成](../entries/owner/game-billing-batch/releases/0.1.0/README.md)<br>owner/game-billing-batch | 根据商品 ID、中文名和 Cash 价格，按已有后台模板生成华为、国服 GM、港澳台 GM 的计费点批量文件，并执行重复 ID 与字段回读检查。 | 商品 ID、名称和 Cash 价格、后台导出模板 → 批量导入文件、ID/行数/字段核对结果 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/game-billing-batch/releases/0.1.0/payload/SKILL.md) |
| [玩法方案逐层拷问](../entries/owner/game-design-grill/releases/0.1.0/README.md)<br>owner/game-design-grill | 以玩家体验、规则闭环和证据为基础，逐个解决最影响方向的玩法歧义，形成可验收的设计方案。 | 策划方案、规则草稿、配置或代码证据 → 拷问记录、确认问题、修订建议 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/game-design-grill/releases/0.1.0/payload/SKILL.md) |
| [MergeClient 活动 UI 概念设计](../entries/owner/mergeclient-ui-concept/releases/0.1.0/README.md)<br>owner/mergeclient-ui-concept | 从少量风格参考建立页面结构，生成活动 UI 概念方案，并用质量量表复审；结果用于概念沟通，不代替 Prefab 或正式切图。 | 活动目标、行为和页面类型、风格参考、尺寸与禁用内容 → 页面结构、概念图说明、评分与迭代记录 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/mergeclient-ui-concept/releases/0.1.0/payload/SKILL.md) |
| [AI 工作成果检查清单](../entries/owner/review-checklist/releases/0.1.0/README.md)<br>owner/review-checklist | 内置示例：AI 工作成果检查清单。未验证真实策划业务，供试用与改编。 | 通用 → 通用 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/review-checklist/releases/0.1.0/payload/SKILL.md) |
| [赛季相册配置与运行验收](../entries/owner/season-card-config/releases/0.1.0/README.md)<br>owner/season-card-config | 串联赛季相册源表、卡牌/入口/徽章/Spine 资源、导出检查和运行时验收，降低配置遗漏与资源错配。 | 地区、赛季和编号范围、XLSX 页签、资源文件 → 字段映射、资源/UUID 检查结果、运行时验收清单 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/season-card-config/releases/0.1.0/payload/SKILL.md) |
| [任务交接与承接](../entries/owner/task-handoff/releases/0.1.0/README.md)<br>owner/task-handoff | 在任务暂停、换人或继续前，生成可审计的交接材料，记录目标、状态、证据、剩余工作和恢复入口。 | 任务目标、当前状态、文件和验证证据 → HANDOFF 文档、承接检查清单、恢复建议 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/task-handoff/releases/0.1.0/payload/SKILL.md) |
| [微信小程序本地包研究](../entries/owner/wechat-applet-unpack/releases/0.1.0/README.md)<br>owner/wechat-applet-unpack | 在 macOS 固定缓存路径内，对获得授权的小程序缓存进行收集、解包和 Lua 提取，保留版本范围与质量统计。 | 合法 wx ID、macOS 固定缓存路径、授权缓存 → 解包目录、Lua 提取结果、summary 统计 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/wechat-applet-unpack/releases/0.1.0/payload/SKILL.md) |
| [AI 与 Codex 一周简报](../entries/owner/weekly-ai-codex-brief/releases/0.1.0/README.md)<br>owner/weekly-ai-codex-brief | 按时间窗口检索并核验 AI/Codex 动态，优先官方来源，区分官方确认、社区经验和风险信息。 | 日期范围、上一期简报、公开来源 → 带原链的中文简报、官方/社区/风险分类 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/weekly-ai-codex-brief/releases/0.1.0/payload/SKILL.md) |
| [工作知识库检索与单向收录](../entries/owner/work-knowledge/releases/0.1.0/README.md)<br>owner/work-knowledge | 从明确项目和来源检索工作知识，保留来源和指纹，经 prepare/apply 流程单向收录到知识库。 | 项目或主题、知识库配置和来源文档 → 检索结果、来源指纹、候选收录记录 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/work-knowledge/releases/0.1.0/payload/SKILL.md) |

### 大乐透可靠查询与统计分析（0.1.0）

- 适用：公开数据分析、来源冲突检查、号码范围核验；不适用：预测中奖率、绕过官方来源、付费或自动下注。
- 环境：macos；工具：Codex、Python 3、网络访问；必要操作能力：读取本地材料、network.read、local_generate。
- 副作用约定：只读输入、local_generate；运行时条件：{}。
- 搜索词：数据分析、来源核验、彩票统计、大乐透分析、开奖统计。
- 来源：本机 Codex 自定义技能：/Users/hcm-b0263/.codex/skills/dlt-reliable-analysis；团队内部能力整理，本版本按原技能材料生成。；原作者：owner；当前负责人：owner。

### 游戏计费点批量生成（0.1.0）

- 适用：新增商品批量准备、同价模板复制、多后台格式转换；不适用：修改已有商品、缺少模板、直接操作后台。
- 环境：macos；工具：Codex、Python 3；必要操作能力：读取本地材料、filesystem.write、process.execute。
- 副作用约定：只读输入、local_generate；运行时条件：{}。
- 搜索词：计费点、批量生成、运营工具、计费批量生成、商品批量导入。
- 来源：本机 Codex 自定义技能：/Users/hcm-b0263/.codex/skills/game-billing-batch；团队内部能力整理，本版本按原技能材料生成。；原作者：owner；当前负责人：owner。

### 玩法方案逐层拷问（0.1.0）

- 适用：玩法方案评审、活动与赛事设计、奖励和对手规则；不适用：直接改生产代码、未经授权发布。
- 环境：macos；工具：Codex、读取本地材料；必要操作能力：读取本地材料、filesystem.write。
- 副作用约定：只读输入、local_generate；运行时条件：{}。
- 搜索词：游戏策划、玩法设计、方案评审、玩法拷问、拷问方案。
- 来源：本机 Codex 自定义技能：/Users/hcm-b0263/.codex/skills/game-design-grill；团队内部能力整理，本版本按原技能材料生成。；原作者：owner；当前负责人：owner。

### MergeClient 活动 UI 概念设计（0.1.0）

- 适用：活动页概念阶段、页面结构讨论、视觉风格复审；不适用：直接当作运行时 Prefab、未授权使用二进制素材。
- 环境：macos；工具：Codex、Python 3、图像生成工具；必要操作能力：读取本地材料、filesystem.write、network.read。
- 副作用约定：只读输入、local_generate；运行时条件：{}。
- 搜索词：UI设计、活动页面、概念图、活动UI概念、MergeClient UI方案。
- 来源：本机 Codex 自定义技能：/Users/hcm-b0263/.codex/skills/mergeclient-ui-concept；团队内部能力整理，本版本按原技能材料生成。；原作者：owner；当前负责人：owner。

### AI 工作成果检查清单（0.1.0）

- 适用：通用；不适用：生产环境变更、对外发送、未明确要求的上传。
- 环境：通用；工具：未指定；必要操作能力：读取本地材料。
- 副作用约定：只读输入；运行时条件：{}。
- 搜索词：内置示例、skill、查漏项。
- 来源：本次平台实现生成的内置示例；非既有团队实绩或真实业务资料。；原作者：owner；当前负责人：owner。

### 赛季相册配置与运行验收（0.1.0）

- 适用：赛季相册配置、卡牌和徽章资源检查、入口与奖励验收；不适用：没有源表或资源证据、未经授权导表。
- 环境：macos；工具：Codex、Node.js、XLSX/OOXML 工具；必要操作能力：读取本地材料、filesystem.write、process.execute。
- 副作用约定：只读输入、local_generate、project_write；运行时条件：{}。
- 搜索词：游戏配置、赛季相册、资源验收、赛季卡配置、相册配置验收。
- 来源：本机 Codex 自定义技能：/Users/hcm-b0263/.codex/skills/season-card-config；团队内部能力整理，本版本按原技能材料生成。；原作者：owner；当前负责人：owner。

### 任务交接与承接（0.1.0）

- 适用：任务交接、跨会话承接、阶段性冻结；不适用：自行创建新任务、自行提交或发布。
- 环境：macos；工具：Codex、读取本地材料、filesystem.write；必要操作能力：读取本地材料、filesystem.write。
- 副作用约定：只读输入、local_generate；运行时条件：{}。
- 搜索词：任务交接、承接、可审计、写交接、恢复任务。
- 来源：本机 Codex 自定义技能：/Users/hcm-b0263/.codex/skills/task-handoff；团队内部能力整理，本版本按原技能材料生成。；原作者：owner；当前负责人：owner。

### 微信小程序本地包研究（0.1.0）

- 适用：本地授权研究、Unity+xLua 资源分析、版本对比；不适用：越界搜索、覆盖既有结果、无授权采集。
- 环境：macos；工具：Codex、macOS shell、Python 3、Node.js；必要操作能力：读取本地材料、filesystem.write、process.execute。
- 副作用约定：只读输入、local_generate；运行时条件：{}。
- 搜索词：小程序、解包、Lua研究、小程序解包、wxapkg分析。
- 来源：本机 Codex 自定义技能：/Users/hcm-b0263/.codex/skills/wechat-applet-unpack；团队内部能力整理，本版本按原技能材料生成。；原作者：owner；当前负责人：owner。

### AI 与 Codex 一周简报（0.1.0）

- 适用：周期性研究、产品动态跟踪、工具选择参考；不适用：无法核验来源、把传闻写成事实。
- 环境：macos；工具：Codex、网络浏览器；必要操作能力：读取本地材料、network.read、local_generate。
- 副作用约定：只读输入、local_generate；运行时条件：{}。
- 搜索词：研究、AI资讯、Codex、AI周报、Codex周报。
- 来源：本机 Codex 自定义技能：/Users/hcm-b0263/.codex/skills/weekly-ai-codex-brief；团队内部能力整理，本版本按原技能材料生成。；原作者：owner；当前负责人：owner。

### 工作知识库检索与单向收录（0.1.0）

- 适用：工作知识检索、知识条目更新、来源追溯；不适用：直接修改数据库、未授权改写原始知识。
- 环境：macos；工具：Codex、Python 3、Obsidian 文件库；必要操作能力：读取本地材料、filesystem.write、process.execute。
- 副作用约定：只读输入、local_generate、project_write；运行时条件：{}。
- 搜索词：知识库、Obsidian、来源追溯、工作知识库、知识收录。
- 来源：本机 Codex 自定义技能：/Users/hcm-b0263/.codex/skills/work-knowledge；团队内部能力整理，本版本按原技能材料生成。；原作者：owner；当前负责人：owner。

## 工作流

| 能力及说明 | 解决什么问题 | 输入 → 产物 | 版本与状态 | 业务验证 | 依赖及使用入口 |
|---|---|---|---|---|---|
| [策划案 AI 审查流程](../entries/owner/design-review/releases/0.1.0/README.md)<br>owner/design-review | 内置示例：策划案 AI 审查流程。未验证真实策划业务，供试用与改编。 | 策划案 → 审查报告 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | [owner/review-checklist@0.1.0](../entries/owner/review-checklist/releases/0.1.0/README.md)<br>[使用入口1](../entries/owner/design-review/releases/0.1.0/payload/instructions.md) |
| [证据驱动调试与验证门禁](../entries/owner/evidence-debugging/releases/0.1.0/README.md)<br>owner/evidence-debugging | 把失败现象拆成证据链，区分确认、观察、推断和待验证项，完成最小修复并逐层验证。 | 证据、相关源码或配置、当前失败现象 → 定位结论、最小改动、回归结果、未验证项 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/evidence-debugging/releases/0.1.0/payload/instructions.md) |
| [MergeClient 源码到运行时追踪](../entries/owner/mergeclient-runtime-trace/releases/0.1.0/README.md)<br>owner/mergeclient-runtime-trace | 将截图或录屏沿请求、客户端调用、服务端分支、配置和资源链追到实际运行时行为。 | 截图/录屏、请求信息、源码路径、配置和资源 → 证据链、影响字段、运行时验证计划 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/mergeclient-runtime-trace/releases/0.1.0/payload/instructions.md) |
| [提示助手修复与本地交付](../entries/owner/prompt-assistant-delivery/releases/0.1.0/README.md)<br>owner/prompt-assistant-delivery | 围绕本机提示助手完成问题定位、聚焦回归、构建、签名、安装和健康检查，并记录 UI 或宿主缺口。 | 失败证据、源码、测试入口 → 修复补丁、测试/构建/签名/安装记录 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/prompt-assistant-delivery/releases/0.1.0/payload/instructions.md) |
| [团队能力库本地捕获](../entries/owner/teamlib-local-capture/releases/0.1.0/README.md)<br>owner/teamlib-local-capture | 按共享指南完成独立取库、环境和权限检查、元数据盘点、内容提炼和本地草稿，保留上传边界。 | 共享仓库、Codex 素材位置、允许读取的材料 → 来源清单、能力草稿、进度和阻塞报告 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/teamlib-local-capture/releases/0.1.0/payload/instructions.md) |

### 策划案 AI 审查流程（0.1.0）

- 适用：策划案审查；不适用：生产环境变更、对外发送、未明确要求的上传。
- 环境：通用；工具：未指定；必要操作能力：读取本地材料。
- 副作用约定：只读输入；运行时条件：{}。
- 搜索词：内置示例、workflow、审策划案。
- 来源：本次平台实现生成的内置示例；非既有团队实绩或真实业务资料。；原作者：owner；当前负责人：owner。

### 证据驱动调试与验证门禁（0.1.0）

- 适用：跨模块 bug 定位、运行时问题追踪、发布前检查；不适用：无运行证据直接下结论、未经授权扩大修改范围。
- 环境：macos；工具：Codex、读取本地材料、filesystem.write；必要操作能力：读取本地材料、filesystem.write、process.execute。
- 副作用约定：只读输入、local_generate、project_write；运行时条件：{}。
- 搜索词：debugging、verification、evidence、debugging、verification。
- 来源：本机 Codex 历史任务中的团队内部工作方法；已整理为可复用流程，未复制原始聊天。；原作者：owner；当前负责人：owner。

### MergeClient 源码到运行时追踪（0.1.0）

- 适用：活动配置、Prefab/资源排查、客户端服务端联动；不适用：只看截图下结论、把单项目规则外推。
- 环境：macos；工具：Codex、读取本地材料、项目工具；必要操作能力：读取本地材料、local_generate。
- 副作用约定：只读输入、local_generate；运行时条件：{}。
- 搜索词：mergeclient、运行时追踪、配置排查、mergeclient、运行时追踪。
- 来源：本机 Codex 历史任务中的团队内部工作方法；已整理为可复用流程，未复制原始聊天。；原作者：owner；当前负责人：owner。

### 提示助手修复与本地交付（0.1.0）

- 适用：本机应用修复、可逆本地交付；不适用：发布、推送、生产部署、无证据重构。
- 环境：macos；工具：Codex、macOS、Xcode/本机构建工具；必要操作能力：读取本地材料、filesystem.write、process.execute。
- 副作用约定：只读输入、project_write、local_generate；运行时条件：{}。
- 搜索词：提示助手、回归、安装验证、提示助手、回归。
- 来源：本机 Codex 历史任务中的团队内部工作方法；已整理为可复用流程，未复制原始聊天。；原作者：owner；当前负责人：owner。

### 团队能力库本地捕获（0.1.0）

- 适用：能力库接入、本地能力盘点、上传前准备；不适用：未经授权上传、读取凭据或完整聊天。
- 环境：macos；工具：Codex、Git、Python 3；必要操作能力：读取本地材料、filesystem.write、process.execute。
- 副作用约定：只读输入、local_generate；运行时条件：{}。
- 搜索词：team-library、capture、audit、team-library、capture。
- 来源：本机 Codex 历史任务中的团队内部工作方法；已整理为可复用流程，未复制原始聊天。；原作者：owner；当前负责人：owner。

## 提示词

| 能力及说明 | 解决什么问题 | 输入 → 产物 | 版本与状态 | 业务验证 | 依赖及使用入口 |
|---|---|---|---|---|---|
| [会议记录整理提示词](../entries/owner/meeting-summary/releases/0.1.0/README.md)<br>owner/meeting-summary | 内置示例：会议记录整理提示词。未验证真实策划业务，供试用与改编。 | 会议记录 → 决策清单 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/meeting-summary/releases/0.1.0/payload/instructions.md) |

### 会议记录整理提示词（0.1.0）

- 适用：会议记录整理；不适用：生产环境变更、对外发送、未明确要求的上传。
- 环境：通用；工具：未指定；必要操作能力：读取本地材料。
- 副作用约定：只读输入；运行时条件：{}。
- 搜索词：内置示例、prompt、整理会议。
- 来源：本次平台实现生成的内置示例；非既有团队实绩或真实业务资料。；原作者：owner；当前负责人：owner。

## 工具

尚无已入库条目。

## 案例

| 能力及说明 | 解决什么问题 | 输入 → 产物 | 版本与状态 | 业务验证 | 依赖及使用入口 |
|---|---|---|---|---|---|
| [可复用经验沉淀模板](../entries/owner/experience-case/releases/0.1.0/README.md)<br>owner/experience-case | 内置示例：可复用经验沉淀模板。未验证真实策划业务，供试用与改编。 | 脱敏经验 → 经验说明 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/experience-case/releases/0.1.0/payload/instructions.md) |
| [Food Street 订单规则与 Prefab 迁移案例](../entries/owner/foodstreet-order-prefab/releases/0.1.0/README.md)<br>owner/foodstreet-order-prefab | 从订单源码区分随机、配置和 fallback 选择逻辑，并独立完成 Prefab 迁移的静态引用检查，明确运行时接入缺口。 | 订单源码、Prefab 文件、UUID 和引用清单 → 规则说明、迁移清单、静态检查和运行时缺口 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/foodstreet-order-prefab/releases/0.1.0/payload/instructions.md) |
| [MergeServer 赛事与邮件规则反查案例](../entries/owner/mergeserver-rules-trace/releases/0.1.0/README.md)<br>owner/mergeserver-rules-trace | 围绕 tournament、oneVsOne、robotRank 和 email 模块，记录服务端规则、关键字段和客户端联动验证项。 | 服务端源码/配置、客户端调用和测试证据 → 模块规则说明、待确认项、验证建议 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/mergeserver-rules-trace/releases/0.1.0/payload/instructions.md) |

### 可复用经验沉淀模板（0.1.0）

- 适用：经验整理；不适用：生产环境变更、对外发送、未明确要求的上传。
- 环境：通用；工具：未指定；必要操作能力：读取本地材料。
- 副作用约定：只读输入；运行时条件：{}。
- 搜索词：内置示例、case、整理经验。
- 来源：本次平台实现生成的内置示例；非既有团队实绩或真实业务资料。；原作者：owner；当前负责人：owner。

### Food Street 订单规则与 Prefab 迁移案例（0.1.0）

- 适用：规则反查、资源迁移案例；不适用：把静态导入当作运行时完成、覆盖不明时宣称通过。
- 环境：macos；工具：Codex、读取本地材料、项目资源工具；必要操作能力：读取本地材料、local_generate。
- 副作用约定：只读输入、local_generate；运行时条件：{}。
- 搜索词：FoodStreet、订单规则、Prefab迁移、FoodStreet、订单规则。
- 来源：本机 Codex 历史任务中的团队内部工作方法；已整理为可复用流程，未复制原始聊天。；原作者：owner；当前负责人：owner。

### MergeServer 赛事与邮件规则反查案例（0.1.0）

- 适用：服务端规则反查、跨模块联动排查；不适用：未核对当前部署版本、把历史会话推断当线上事实。
- 环境：macos；工具：Codex、读取本地材料、服务端开发工具；必要操作能力：读取本地材料、local_generate。
- 副作用约定：只读输入、local_generate；运行时条件：{}。
- 搜索词：mergeServer、服务端规则、运行时证据、mergeServer、服务端规则。
- 来源：本机 Codex 历史任务中的团队内部工作方法；已整理为可复用流程，未复制原始聊天。；原作者：owner；当前负责人：owner。

## 经验

| 能力及说明 | 解决什么问题 | 输入 → 产物 | 版本与状态 | 业务验证 | 依赖及使用入口 |
|---|---|---|---|---|---|
| [能力误上传恢复经验模板](../entries/owner/recovery-retrospective/releases/0.1.0/README.md)<br>owner/recovery-retrospective | 内置示例：能力误上传恢复经验模板。未验证真实策划业务，供试用与改编。 | 恢复记录 → 复盘摘要 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/recovery-retrospective/releases/0.1.0/payload/instructions.md) |
| [安全清理与可再生缓存边界](../entries/owner/safe-cache-cleanup/releases/0.1.0/README.md)<br>owner/safe-cache-cleanup | 在保留 Git/LFS 和用户材料的前提下，确认进程与缓存状态，只清理可再生目录并做前后复核。 | HEAD/status、进程、目录大小、远端校验结果 → 清理前后证据、保留项、风险和复核结果 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/safe-cache-cleanup/releases/0.1.0/payload/instructions.md) |

### 能力误上传恢复经验模板（0.1.0）

- 适用：恢复复盘；不适用：生产环境变更、对外发送、未明确要求的上传。
- 环境：通用；工具：未指定；必要操作能力：读取本地材料。
- 副作用约定：只读输入；运行时条件：{}。
- 搜索词：内置示例、lesson、误上传复盘。
- 来源：本次平台实现生成的内置示例；非既有团队实绩或真实业务资料。；原作者：owner；当前负责人：owner。

### 安全清理与可再生缓存边界（0.1.0）

- 适用：本机磁盘维护、可再生缓存清理；不适用：直接删除 .git/lfs、删除模型或源码、未验证远端就清理。
- 环境：macos；工具：Codex、Git、git-lfs、macOS shell；必要操作能力：读取本地材料、filesystem.write、process.execute。
- 副作用约定：只读输入、project_write、local_generate；运行时条件：{}。
- 搜索词：缓存清理、LFS、磁盘维护、缓存清理、LFS。
- 来源：本机 Codex 历史任务中的团队内部工作方法；已整理为可复用流程，未复制原始聊天。；原作者：owner；当前负责人：owner。

## 研究资料

| 能力及说明 | 解决什么问题 | 输入 → 产物 | 版本与状态 | 业务验证 | 依赖及使用入口 |
|---|---|---|---|---|---|
| [AI 工具资料核查框架](../entries/owner/reference-evaluation/releases/0.1.0/README.md)<br>owner/reference-evaluation | 内置示例：AI 工具资料核查框架。未验证真实策划业务，供试用与改编。 | 来源材料 → 核查报告 | 0.1.0（推荐）<br>可进一步检查使用 | 未验证 | 无团队能力依赖<br>[使用入口1](../entries/owner/reference-evaluation/releases/0.1.0/payload/instructions.md) |

### AI 工具资料核查框架（0.1.0）

- 适用：资料核查；不适用：生产环境变更、对外发送、未明确要求的上传。
- 环境：通用；工具：未指定；必要操作能力：读取本地材料。
- 副作用约定：只读输入；运行时条件：{}。
- 搜索词：内置示例、research、核对参考资料。
- 来源：本次平台实现生成的内置示例；非既有团队实绩或真实业务资料。；原作者：owner；当前负责人：owner。

## 处理中请求

以下仅是生成目录时的请求快照，尚未核实为已入库，不能当已共享能力下载。具体内容、最新版本与处理状态以平台请求为准。

| 请求 | 材料类别 | 涉及能力 | 阶段 |
|---|---|---|---|
| [处理请求 #1](https://github.com/WWWWWWWWMWWWWMWW/team-ai-library/pull/1) | 能力投稿 | owner/cold-start-reuse-case | 处理中 |

## 目录来源与时效

- 来源：https://github.com/WWWWWWWWMWWWWMWW/team-ai-library.git，共享分支 main。
- 固定来源提交：`ee35de264a2071cbe74e23bad7c28d19e2d6374a`。
- 目录和机器索引由同一快照生成；可能落后于后续发布、撤回与新投稿，使用前以实时查找、状态查询和使用前检查为准。
