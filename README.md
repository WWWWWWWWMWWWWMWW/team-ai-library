# 策划团队 AI 能力库

把经过整理的提示词、流程、Skill 材料和经验放进私有 Git 仓库，让自己的 AI 按具体任务查找、下载、核对并复用。成员描述业务目标，AI 处理材料、版本、依赖与来源记录。

实际仓库：[WWWWWWWWMWWWWMWW/team-ai-library](https://github.com/WWWWWWWWMWWWWMWW/team-ai-library)，共享分支 `main`。本地 `library.json` 已配置该地址、专用工作区和 `local_materials` 材料安装目标。

**浏览入口：[团队能力总目录](docs/CATALOG.md)**。按七类能力查看用途、输入产物、固定版本、验证状态、依赖与使用入口；待审核材料另列。目录由 AI 从已入库内容生成。

策划只需复制 [一段简化提示词](docs/MEMBER_PROMPT.md)，然后直接说本次业务需求。复杂流程写在 [AI 自动操作手册](docs/AI_OPERATIONS.md) 中，由 AI 自动读取；环境检查、资源整理、中文说明和 Git 操作均由 AI 处理。

想全面整理本地可沉淀内容，可直接复制 [全面整理提示词](docs/LOCAL_CAPTURE_PROMPT.md)，由 AI 产出完整盘点、详细中文能力草稿、缺项与建议上传清单。

盘点自己在 Codex 积累的能力，直接用 [Codex 自动盘点提示词](docs/CODEX_CAPTURE_PROMPT.md)。AI 自动定位本机素材，先建立清单再详细整理，不要求先提供业务项目路径；无 GitHub 登录也可完成本地整理。

日常可以直接说：

- 安装接入这套能力库，检查能不能用。
- 把我指定文件夹里的工作流和提示词整理后上传，写清中文用法，入库前让我审核。
- 找一个审查策划案的流程，先说明适用范围。
- 下载 `owner/design-review` 的 `0.1.0`，临时用于这次策划案审查。
- 把这次实际结果记在本地，不上传原始策划案或完整聊天。
- 将这份材料保存到已经配置的材料目录。
- 把这份改进整理后分享到库里；检查通过后创建 PR，合并前让我核验。
- 这个版本有问题，申请撤回，并核对可恢复的明确版本。

## 当前状态

**已确认：** 工具已实现，本地自动测试已通过（见 tests/evidence 最新全套证据）；包含完整依赖下载、实际材料与固定来源核对、当前撤回/作废检查、安装收据、更新冲突保全及本地复用记录。实现具备 `search`、`fetch`、`check-reuse` 等读取流程；真实使用仍需账号有私有库读取权限、可信成员映射和可取得的 `main`。

**已确认：** 当前账号为仓库 owner，只有一名维护者。私有库分支保护设置请求返回 403，提示需要 GitHub Pro；共享分支硬门禁尚未生效。当前采用仅仓库 owner 的 `owner_trial` 试用方案，不购买 Pro、不公开仓库、不邀请其他成员。

**已确认：** `owner_trial` 配置已部署到可信共享 `main`；当前 owner 的真实接入检查通过，读取与投稿可用。已有能力试用投稿请求，尚待审核入库。AI 不自动合并，具体请求由人核验并明确授权合并；成功创建请求不能称正式团队门禁已生效。

**已确认：** 2026-10-08 源码、配置、指南与六个示例已初始化到远端 `main`，初始化提交为 `8cfd19c84e6b0275c16f5d5d5e8b3aef055f31a3`。

**待验证：** 能力投稿合并后的发布验收、撤回治理闭环、真实业务复用、另一种 AI/目标工具。多人协作暂不开放；新增任何协作者或邀请都会阻断试用写入，切回 `protected` 并重测正式门禁后才能团队化。

**已确认：** 独立 AI 上下文从远端新 clone，仅按指南实际完成搜索、完整依赖下载、check-reuse、合成策划稿审查与本地 record-run。合成文档审查通过，真实游戏 runtime 未验证；此次同机器、同账号、同工具，不替代第二人或第二工具验收。

`install` 只把完整材料放到显式配置的 **library-directory** 目录。原生 Codex Skill 注册、自动发现与原生工具导入未实现/未验证；`payload/SKILL.md` 的存在也不代表已注册。

## 已有示例

内置示例的用途、准确 ID 与版本见 [能力总目录](docs/CATALOG.md)。这些示例**真实业务未验证**，不代表既有团队实绩；目录中仅列真实共享版本，待审核投稿不计入已入库能力。

## 开始使用

在本仓库根目录运行；需要 Python 3.11+、Git，以及已登录个人账号的 GitHub CLI `gh`。

```sh
python3 tools/library.py --help
python3 tools/library.py doctor
python3 tools/library.py search --query '审策划案'
python3 tools/library.py fetch --id owner/design-review --version 0.1.0 --dest .teamlib-workspace/downloads/design-review-0.1.0
```

`doctor` 分别报告读取和投稿条件。默认 `protected` 模式仍要求可核实的分支保护；`owner_trial` 只有共享部署和 owner 独占条件都通过才允许试用投稿。发布阻断时，若读取检查通过会保留 `data.readable=true`、`can_publish=false` 和发布失败原因。读取流程独立核对个人登录、私有库读取权限、成员映射与共享分支，不要求具有发布权限。若共享材料尚未初始化，则停止并由维护者完成部署，不把未提交本地文件当成已发布版本。

下载目录必须不存在。使用下载包前按 [AI 操作指南](docs/AI_GUIDE.md) 写当前任务的 `selection.json` 和 `context.json`，运行 `check-reuse`；检查通过只表示可在已授权范围内进一步使用，实际效果需在本地记录。

## 文档入口

| 文件 | 用途 |
|---|---|
| [团队能力总目录](docs/CATALOG.md) | 按分类浏览已入库能力、版本、范围、依赖和待审核材料 |
| [目录维护指南](docs/CATALOG_GUIDE.md) | AI 自动生成与维护目录的规则 |
| [本地网页设计规划](docs/LOCAL_WEB_PLAN.md) | 页面结构、交互、视觉与验收安排；建议方案，网页尚未实现 |
| [机器索引](docs/catalog.json) | 与人读目录同源的结构化导航，使用前仍核对实时状态 |
| [策划简化提示词](docs/MEMBER_PROMPT.md) | 一次复制，之后直接描述本次需求 |
| [AI 自动操作手册](docs/AI_OPERATIONS.md) | AI 自行读取的接入、整理、复用、上传与治理流程 |
| [本地全面整理提示词](docs/LOCAL_CAPTURE_PROMPT.md) | 让 AI 全面盘点并详细整理本地可沉淀内容 |
| [LOCAL_CAPTURE.md](docs/LOCAL_CAPTURE.md) | 完整检查清单、分类、来源、草稿、进度与交付要求 |
| [Codex 自动盘点提示词](docs/CODEX_CAPTURE_PROMPT.md) | 自动识别本机 Codex 素材，无需业务项目路径 |
| [CODEX_CAPTURE.md](docs/CODEX_CAPTURE.md) | Codex 来源发现、任务经验提炼与实际整理规则 |
| [AGENTS.md](AGENTS.md) | AI 操作边界与完成标准 |
| [ONBOARDING.md](docs/ONBOARDING.md) | 接入前提、实际配置、当前门禁缺项 |
| [AI_GUIDE.md](docs/AI_GUIDE.md) | 可直接运行的命令与 JSON 示例 |
| [GOVERNANCE.md](docs/GOVERNANCE.md) | 权限、审核与可信检查 |
| [DEPENDENCIES.md](docs/DEPENDENCIES.md) | 版本、范围与依赖规则 |
| [RECOVERY.md](docs/RECOVERY.md) | 冲突、撤回、恢复及泄漏响应 |
| [TRACEABILITY.md](docs/TRACEABILITY.md) | 来源、更新基线、复用与改编记录 |
| [条目说明模板](templates/entry-README.md) | 根据实际材料填写说明 |

上传与撤回需要用户明确意图及对应部署前提。owner 试用可创建待人工核验的请求；它不提供服务器强制审核门禁。查找不安装，临时复用不默认永久安装；本地记录不自动回传。
