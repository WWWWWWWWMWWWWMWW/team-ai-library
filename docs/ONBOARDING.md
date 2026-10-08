# 接入指南

工具已实现，接入实际私有 GitHub 仓库前要分别核对读取条件和发布条件。本文不把本地测试、账号 owner 权限或配置文件当成团队门禁生效的证据。

## 当前接入卡

| 内容 | 当前配置/状态 |
|---|---|
| 仓库 | [WWWWWWWWMWWWWMWW/team-ai-library](https://github.com/WWWWWWWWMWWWWMWW/team-ai-library)，private |
| 共享分支 | `main` |
| 平台 | GitHub；复用既有个人账号登录，不保存密码/令牌 |
| 主维护者 | GitHub `WWWWWWWWMWWWWMWW` → actor_key `owner` |
| 备用维护者/普通成员 | 尚未配置；不能声称双成员验收完成 |
| 工作区 | `library.json` 中 `.teamlib-workspace`，相对仓库根目录 |
| 当前安装 profile | `local_materials` → `.teamlib-installed`，tool=`library-directory` |
| 原生 AI 注册 | Codex Skill 注册和自动发现未实现/未验证 |
| 发布条件 | 分支保护设置请求返回 403并提示 GitHub Pro；发布工具保持阻断，部署选择待确认 |
| 首次指令 | 阅读 README、AGENTS、AI_GUIDE，查看配置与 doctor，再按对应操作处理 |

本地已有六个 `owner/*` 示例，全部真实业务未验证。初次初始化必须将工具、`library.json`、治理文件及示例实际放入 `main`，再核实共享快照；尚未完成初始化时不要向成员宣称已发布或可以从远端取得这些条目。

## 已授权初始化与后续部署

用户已授权创建并 bootstrap 仓库；2026-10-08 已完成私有 main 初始化，提交 `8cfd19c84e6b0275c16f5d5d5e8b3aef055f31a3` 含源码、配置、指南和六个示例，远端 SHA 已核对。完成初始化不等于下列团队条件已通过：

- 增加真实备用维护者和普通成员，平台权限与共享治理中的账号映射一致。
- 核实共享分支要求新鲜批准、禁止强推/删除、可信检查及 CI 隔离；升级/迁移等部署选择尚未确定时，不用改 `platform=local` 绕过真实 GitHub 门禁。
- 用第二名成员完成读取、投稿、查询发布、复用与撤回治理演练；用实际目标 AI 记录任务效果。

当前没有保护时，`doctor`/`propose` 的发布检查会阻断；不要改源码或配置跳过检查，不用 owner 直推替代日常评审。只有在平台条件和明确分享意图都满足后才进入正式投稿流程。

## 成员准备环境

需要 Python 3.11+、Git、GitHub CLI `gh`、可操作本地文件与终端的 AI。只用聊天的 AI 可以整理待审材料，不能声称已完成 Git 下载、安装或投稿。

先确认私有仓库访问和个人登录。以下只检查既有登录状态；需要登录时由成员按公司的个人账号方式完成 `gh auth login`，不把凭据放到命令参数、配置或 JSON 记录里。

```sh
python3 --version
git --version
gh --version
gh auth status
```

维护者先授予私有库权限，并把该个人 GitHub login 加入经过审批的共享 `governance/members.json`，分配稳定 actor_key/role。仅有访问权限而没有可信成员映射，也可能被工具阻断。当前文件只包含 `owner`，不能复制 owner 身份给其他成员。

共享 `main` 初始化并可读后，在新的独立目录取库：

```sh
git clone --branch main https://github.com/WWWWWWWWMWWWWMWW/team-ai-library.git team-ai-library
cd team-ai-library
python3 tools/library.py --help
python3 tools/library.py doctor
```

检查 `library.json` 的 remote/main、publish_mode=`request`、auto_merge=`false`、专用 workspace 和目标 profile。路径按各成员本机实际目录配置，不从 AI 名称猜个人 Skill 目录；可复制为被忽略的 `library.local.json` 并显式使用：

```sh
python3 tools/library.py --config library.local.json search --query '策划案'
```

workspace 与源码、下载源和安装目标保持受支持的分离关系；目标只允许 library-directory 材料目录。配置与路径校验失败时按结果修正，不以改工作区或更换身份隐藏失败。

## 先验证读取

`doctor` 同时检查发布前提。当前缺少分支保护时，整体 `blocked/SCOPE_DENIED` 不等于账号完全没有读取能力；读取成功时诊断保留 `data.readable=true`、`can_publish=false` 与 publishing_failure；`search`、`fetch`、`check-reuse` 会独立核对个人登录、private 仓库、pull 权限、可信成员映射和 fresh main。

```sh
python3 tools/library.py search --query '审策划案'
python3 tools/library.py fetch --id owner/design-review --version 0.1.0 --dest .teamlib-workspace/downloads/design-review-0.1.0
```

确认输出的 `state`、`code`、准确 ID/version/manifest 摘要与 source_commit。`fetch` 目标必须不存在；重复下载用新的明确目录或复用已完整保存的包，不覆盖未知内容。搜索无条目、main 不存在或映射缺失时报告该具体条件，不读取未提交本地示例来冒充远端结果。

随后按 [AI_GUIDE.md](AI_GUIDE.md) 准备实际任务摘要并运行 `check-reuse`。下载、材料安装及检查成功均不能证明原生 AI 发现或真实策划业务效果。

## 接入验收

已确认本地自动测试通过，最新全套证据见 tests/evidence，覆盖隔离 Git/文件系统和平台模拟。真实接入分别记录：谁的账号、哪种 AI/工具版本、环境、条目版本与摘要、操作结果、非敏感证据及未验证项。

当前真实第二成员、正式投稿/审核生效、治理撤回闭环、真实 AI 业务结果和原生 Skill 发现均待验证。不得以本地模拟、doctor 配置或 owner 登录代替这些项目。

## 当前已完成的只读试用

2026-10-08，独立AI从远端新clone按指南完成真实owner读取、查找、完整依赖下载、check-reuse、合成策划审查与本地run记录；未安装或远端写入。此事实不替代第二成员、第二工具和正式投稿审批验收。doctor仍明确显示读取可用、发布保护缺项。
