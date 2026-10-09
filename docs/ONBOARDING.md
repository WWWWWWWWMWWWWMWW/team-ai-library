# 接入指南

工具已实现，接入实际私有 GitHub 仓库前要分别核对读取条件和发布条件。本文不把本地测试、账号 owner 权限或配置文件当成团队门禁生效的证据。

策划复制 [简化提示词](MEMBER_PROMPT.md) 后描述任务即可。以下环境、权限与取库细节由 AI 按 [自动操作手册](AI_OPERATIONS.md) 处理；本人登录和权限授予仍由相应人员完成。

## 当前接入卡

| 内容 | 当前配置/状态 |
|---|---|
| 仓库 | [WWWWWWWWMWWWWMWW/team-ai-library](https://github.com/WWWWWWWWMWWWWMWW/team-ai-library)，private |
| 共享分支 | `main` |
| 平台 | GitHub；复用既有个人账号登录，不保存密码/令牌 |
| 主维护者 | GitHub `WWWWWWWWMWWWWMWW` → actor_key `owner` |
| 备用维护者/普通成员 | 试用期间不配置、不邀请；多人协作暂不开放 |
| 工作区 | `library.json` 中 `.teamlib-workspace`，相对仓库根目录 |
| 当前安装 profile | `local_materials` → `.teamlib-installed`，tool=`library-directory` |
| 原生 AI 注册 | Codex Skill 注册和自动发现未实现/未验证 |
| 部署模式 | `protected` 为默认；已选择 `owner_trial` 仅 owner 试用，须部署到可信共享 main 后再验证 |
| 正式门禁 | 分支保护设置请求返回 403 并提示 GitHub Pro；服务器硬门禁尚未生效 |
| 试用投稿 | 共享部署及每次 owner 独占检查通过后可创建 PR；真实投稿与合并验收待完成 |
| 首次指令 | 阅读 README、AGENTS、AI_GUIDE，查看配置与 doctor，再按对应操作处理 |

本地已有六个 `owner/*` 示例，全部真实业务未验证。初次初始化必须将工具、`library.json`、治理文件及示例实际放入 `main`，再核实共享快照；尚未完成初始化时不要向成员宣称已发布或可以从远端取得这些条目。

## 已授权初始化与后续部署

用户已授权创建并 bootstrap 仓库；2026-10-08 已完成私有 main 初始化，提交 `8cfd19c84e6b0275c16f5d5d5e8b3aef055f31a3` 含源码、配置、指南和六个示例，远端 SHA 已核对。完成初始化不等于试用投稿已启用，也不证明正式团队门禁通过。

已选择 `owner_trial`：不购买 Pro、不公开仓库、不邀请成员。启用试用前，维护者将经过批准的工具、治理规则与 `deployment_mode=owner_trial` 配置部署到共享 `main`，再从该可信基线核验。不能只在本机配置添加模式就开通写入。共享与本机的 remote、shared_branch、platform、publish_mode=request 以及 owner_trial 自动入库策略必须一致；当前历史基线省略显式策略字段时，由 owner_trial 自动启用。

每次试用远程写入都重新核对私有库、当前个人账号为仓库 owner 且有 admin/push 权限、全部分页协作者唯一且为 owner、无待处理邀请、共享成员映射只有该 owner 维护者。任何新增协作者或邀请都会阻断写入；先切回 `protected`，补齐正式平台门禁并重测后才开放多人。

试用条件通过后，owner 可一句话让 AI 整理并分享材料到 PR。AI 负责包检查、可信 CI 核对与自动合并；结果须说明仅 owner 试用、服务器硬门禁未生效、检查未通过会暂停。完整包检查、不可变版本、可信基线检查器及当前内容/状态绑定继续保留。

正式多人协作仍需实际验证下列条件：

- 真实备用维护者与普通成员的权限和共享账号映射一致。
- 共享分支要求新鲜批准、禁止强推/删除、可信检查及 CI 隔离实际生效。
- 第二名成员完成读取、投稿、查询发布、复用与撤回治理演练；目标 AI 的实际业务效果有记录。

切换模式或新增成员都不是本次试用的自动动作，不用 `platform=local`、owner 直推或模拟测试代替正式门禁。

## 成员准备环境

需要 Python 3.11+、Git、GitHub CLI `gh`、可操作本地文件与终端的 AI。只用聊天的 AI 可以整理待审材料，不能声称已完成 Git 下载、安装或投稿。

先确认私有仓库访问和个人登录。以下只检查既有登录状态；需要登录时由成员按公司的个人账号方式完成 `gh auth login`，不把凭据放到命令参数、配置或 JSON 记录里。

```sh
python3 --version
git --version
gh --version
gh auth status
```

以下成员授权流程仅适用于未来通过验收的 `protected` 团队部署，试用期间不执行：维护者授予私有库权限，并把该个人 GitHub login 加入经过审批的共享 `governance/members.json`，分配稳定 actor_key/role。仅有访问权限而没有可信成员映射，也可能被工具阻断。当前文件只包含 `owner`，不能复制 owner 身份给其他成员。

共享 `main` 初始化并可读后，在新的独立目录取库：

```sh
git clone --branch main https://github.com/WWWWWWWWMWWWWMWW/team-ai-library.git team-ai-library
cd team-ai-library
python3 tools/library.py --help
python3 tools/library.py doctor
```

检查 `library.json` 的 remote/main、deployment_mode、publish_mode=`request`、owner_trial 自动入库策略、专用 workspace 和目标 profile。省略 deployment_mode 时按 `protected`；试用是否启用以可信共享配置和实时条件为准。路径按各成员本机实际目录配置，不从 AI 名称猜个人 Skill 目录；可复制为被忽略的 `library.local.json` 并显式使用：

```sh
python3 tools/library.py --config library.local.json search --query '策划案'
```

workspace 与源码、下载源和安装目标保持受支持的分离关系；目标只允许 library-directory 材料目录。配置与路径校验失败时按结果修正，不以改工作区或更换身份隐藏失败。

## 先验证读取

`doctor` 同时检查发布前提。`protected` 缺少分支保护、或 `owner_trial` 的共享部署/独占条件未满足时，投稿检查阻断不等于账号完全没有读取能力；读取成功时诊断保留 `data.readable=true`、`can_publish=false` 与 publishing_failure；`search`、`fetch`、`check-reuse` 会独立核对个人登录、private 仓库、pull 权限、可信成员映射和 fresh main。

```sh
python3 tools/library.py search --query '审策划案'
python3 tools/library.py fetch --id owner/design-review --version 0.1.0 --dest .teamlib-workspace/downloads/design-review-0.1.0
```

确认输出的 `state`、`code`、准确 ID/version/manifest 摘要与 source_commit。`fetch` 目标必须不存在；重复下载用新的明确目录或复用已完整保存的包，不覆盖未知内容。搜索无条目、main 不存在或映射缺失时报告该具体条件，不读取未提交本地示例来冒充远端结果。

随后按 [AI_GUIDE.md](AI_GUIDE.md) 准备实际任务摘要并运行 `check-reuse`。下载、材料安装及检查成功均不能证明原生 AI 发现或真实策划业务效果。

## 接入验收

已确认本地自动测试通过，最新全套证据见 tests/evidence，覆盖隔离 Git/文件系统和平台模拟。真实接入分别记录：谁的账号、哪种 AI/工具版本、环境、条目版本与摘要、操作结果、非敏感证据及未验证项。

当前真实 owner 自动投稿与合并验收、正式团队门禁、治理撤回闭环、真实 AI 业务结果和原生 Skill 发现均待验证。第二成员不属于当前试用范围。不得以本地模拟、doctor 配置或 owner 登录代替这些项目。

## 当前已完成的只读试用

2026-10-08，独立AI从远端新clone按指南完成真实owner读取、查找、完整依赖下载、check-reuse、合成策划审查与本地run记录；未安装或远端写入。此事实不替代第二成员、第二工具和正式投稿审批验收。该次 doctor 显示读取可用、发布保护缺项；这条历史证据不证明后续 owner_trial 已部署或真实 PR 已验收。
