# 接入指南

工具已实现，接入公开 GitHub 仓库前仍要分别核对读取条件、GitHub 登录和 Write 权限。网页浏览不需要 `gh`；投稿和实时诊断需要 Git、Python 3.11+、GitHub CLI `gh` 以及个人账号登录。

策划复制 [简化提示词](MEMBER_PROMPT.md) 后描述任务即可。环境、权限与取库细节由 AI 按 [自动操作手册](AI_OPERATIONS.md) 处理；本人登录和权限授予仍由相应人员完成。

## 当前接入卡

| 内容 | 当前配置/状态 |
|---|---|
| 仓库 | [WWWWWWWWMWWWWMWW/team-ai-library](https://github.com/WWWWWWWWMWWWWMWW/team-ai-library)，公开 |
| 共享分支 | `main` |
| 平台 | GitHub；复用既有个人账号登录，不保存密码/令牌 |
| 主维护者 | GitHub `WWWWWWWWMWWWWMWW` → actor_key `owner` |
| 团队成员 | 需要维护者按 GitHub 用户名或 team slug 授予 `Write`；当前实时列表只有 owner |
| 工作区 | `library.json` 中 `.teamlib-workspace`，相对仓库根目录 |
| 当前安装 profile | `local_materials` → `.teamlib-installed`，tool=`library-directory` |
| 原生 AI 注册 | Codex Skill 注册和自动发现未实现/未验证 |
| 部署模式 | `public_write`；公开可读，登录成员直推 `main` |
| Pull Request / 审核 | 不要求；main 当前没有分支保护 |
| 首次指令 | 阅读 README、AGENTS、AI_GUIDE，查看配置与 doctor，再按对应操作处理 |

本地已有示例的真实业务效果仍未验证。网页目录是快照，使用具体能力时由 AI 核对最新版本、依赖、撤回状态和授权范围。

## 成员授权

维护者在 GitHub 仓库 Settings → Collaborators and teams 中添加成员或 team，并选择 `Write`。公开链接只提供读取能力，不产生写权限。成员完成登录后，在独立目录克隆 `main` 并运行 `doctor`；不要共享密码、令牌或部署密钥。

当前授权检查可以直接使用：

```sh
python3 --version
git --version
gh --version
gh auth status
```

## 取得仓库与诊断

```sh
git clone --branch main https://github.com/WWWWWWWWMWWWWMWW/team-ai-library.git team-ai-library
cd team-ai-library
python3 tools/library.py --help
python3 tools/library.py doctor
```

`doctor` 会核对公开仓库、个人登录、`pull=true`、`push=true`、共享 `main` 和 direct 配置。成员名单仅用于作者显示与维护者角色，不是普通成员的写入 allowlist。若缺少 GitHub Write、仓库不可读、main 发生竞争或工具缺失，AI 只保留本地材料并报告具体阻断。

## 日常使用

```sh
python3 tools/library.py search --query '审策划案'
python3 tools/library.py fetch --id owner/design-review --version 0.1.0 --dest .teamlib-workspace/downloads/design-review-0.1.0
```

下载、安装、check-reuse 和 record-run 仍按 [AI_GUIDE.md](AI_GUIDE.md) 执行；网页浏览、查找、下载和上传是不同操作。下载目标必须是新目录，不能覆盖本地未知文件。

## 直推流程

用户明确要求分享后，AI 锁定材料并先执行完整包、敏感内容、依赖、版本和范围检查。通过后从最新 `main` 生成一个只含条目材料的提交，以 fast-forward 方式推送 `main`，再读回共享材料核对。main 在准备期间变化、身份变化、推送结果或读回内容无法核实时停止；不会 force push、删除分支或要求成员创建 Pull Request。

CI 在 push 后运行只读检查，用于发现和追溯问题，不提供 GitHub 阻断门槛。CI 通过也不代表真实业务效果已验证。

## 接入验收

完成接入需能确认：独立目录存在、远端和分支为批准值、`doctor` 报告 `readable=true` 与 `can_publish=true`（当前账号具备 Write 时），网页可打开。报告当前 main 提交、账号、工具版本和未验证项；不要用本地模拟代替真实账号验收。
