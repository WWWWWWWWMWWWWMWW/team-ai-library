# 策划团队 AI 能力库

把经过整理的提示词、流程、Skill 材料和经验放进私有 Git 仓库，让自己的 AI 按具体任务查找、下载、核对并复用。成员描述业务目标，AI 处理材料、版本、依赖与来源记录。

实际仓库：[WWWWWWWWMWWWWMWW/team-ai-library](https://github.com/WWWWWWWWMWWWWMWW/team-ai-library)，共享分支 `main`。本地 `library.json` 已配置该地址、专用工作区和 `local_materials` 材料安装目标。

对具备文件和终端操作能力的 AI 说：

> 阅读本仓库 README.md、AGENTS.md、docs/ONBOARDING.md 和 docs/AI_GUIDE.md，检查当前配置和账号。先按我的任务查找并核对适用范围；需要使用时下载固定版本并运行 check-reuse。不要把下载、检查或材料安装说成业务已验证。

日常可以直接说：

- 找一个审查策划案的流程，先说明适用范围。
- 下载 `owner/design-review` 的 `0.1.0`，临时用于这次策划案审查。
- 把这次实际结果记在本地，不上传原始策划案或完整聊天。
- 将这份材料保存到已经配置的材料目录。
- 把这份改进整理后分享到库里；检查通过后创建 PR，合并前让我核验。
- 这个版本有问题，申请撤回，并核对可恢复的明确版本。

## 当前状态

**已确认：** 工具已实现，本地自动测试已通过（见 tests/evidence 最新全套证据）；包含完整依赖下载、实际材料与固定来源核对、当前撤回/作废检查、安装收据、更新冲突保全及本地复用记录。实现具备 `search`、`fetch`、`check-reuse` 等读取流程；真实使用仍需账号有私有库读取权限、可信成员映射和可取得的 `main`。

**已确认：** 当前账号为仓库 owner，只有一名维护者。私有库分支保护设置请求返回 403，提示需要 GitHub Pro；共享分支硬门禁尚未生效。当前采用仅仓库 owner 的 `owner_trial` 试用方案，不购买 Pro、不公开仓库、不邀请其他成员。

**待验证：** 试用配置须先由维护者部署到可信共享 `main`，再核对真实私有库、owner 身份及唯一协作者、无待处理邀请等条件。部署并验证后，owner 可让 AI 整理材料并创建 PR；AI 不自动合并，具体 PR 由人核验并明确授权合并。当前真实试用投稿与合并验收仍待完成，不能称正式团队门禁已生效。

**已确认：** 2026-10-08 源码、配置、指南与六个示例已初始化到远端 `main`，初始化提交为 `8cfd19c84e6b0275c16f5d5d5e8b3aef055f31a3`。

**待验证：** 真实试用投稿与发布、撤回治理闭环、真实业务复用、另一种 AI/目标工具。多人协作暂不开放；新增任何协作者或邀请都会阻断试用写入，切回 `protected` 并重测正式门禁后才能团队化。

**已确认：** 独立 AI 上下文从远端新 clone，仅按指南实际完成搜索、完整依赖下载、check-reuse、合成策划稿审查与本地 record-run。合成文档审查通过，真实游戏 runtime 未验证；此次同机器、同账号、同工具，不替代第二人或第二工具验收。

`install` 只把完整材料放到显式配置的 **library-directory** 目录。原生 Codex Skill 注册、自动发现与原生工具导入未实现/未验证；`payload/SKILL.md` 的存在也不代表已注册。

## 已有示例

以下六项已共享内置示例均为 `0.1.0`，**真实业务未验证**；不代表既有团队实绩。可按准确 ID 查找和下载。

| ID | 用途 |
|---|---|
| `owner/design-review` | 策划案审查流程 |
| `owner/meeting-summary` | 会议记录整理提示词 |
| `owner/review-checklist` | 工作成果检查清单 Skill 材料 |
| `owner/experience-case` | 可复用经验沉淀模板 |
| `owner/reference-evaluation` | AI 工具资料核查框架 |
| `owner/recovery-retrospective` | 误上传恢复复盘模板 |

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
| [AGENTS.md](AGENTS.md) | AI 操作边界与完成标准 |
| [ONBOARDING.md](docs/ONBOARDING.md) | 接入前提、实际配置、当前门禁缺项 |
| [AI_GUIDE.md](docs/AI_GUIDE.md) | 可直接运行的命令与 JSON 示例 |
| [GOVERNANCE.md](docs/GOVERNANCE.md) | 权限、审核与可信检查 |
| [DEPENDENCIES.md](docs/DEPENDENCIES.md) | 版本、范围与依赖规则 |
| [RECOVERY.md](docs/RECOVERY.md) | 冲突、撤回、恢复及泄漏响应 |
| [TRACEABILITY.md](docs/TRACEABILITY.md) | 来源、更新基线、复用与改编记录 |
| [条目说明模板](templates/entry-README.md) | 根据实际材料填写说明 |

上传与撤回需要用户明确意图及对应部署前提。owner 试用可创建待人工核验的请求；它不提供服务器强制审核门禁。查找不安装，临时复用不默认永久安装；本地记录不自动回传。
