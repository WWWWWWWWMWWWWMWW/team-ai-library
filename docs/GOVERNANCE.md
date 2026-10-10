# 权限与审核

## 当前部署事实

已确认：仓库 `WWWWWWWWMWWWWMWW/team-ai-library` 为公开 GitHub 仓库，共享分支为 `main`，当前配置为 `publish_mode=direct`、`deployment_mode=public_write`。公开仓库允许任何人读取；只有登录 GitHub 且被授予仓库 `Write` 权限的成员可以写入。

已确认：`main` 当前没有分支保护，因此成员可以直接推送。仓库不要求 Pull Request、审核或 GitHub Pro。匿名用户没有写入凭据或写入 API 路径。

待完成：当前实时协作者列表只有仓库所有者。维护者收到明确的 GitHub 用户名或组织 team slug 后，使用 GitHub 的 `push` 权限（界面名称为 `Write`）逐一授权；不把链接本身当作写权限。

## 公开直推规则

`public_write` 以 GitHub 当前身份和仓库权限为准：每次写入都核对个人账号、公开仓库、`pull=true`、`push=true`、共享分支和最新提交。`governance/members.json` 保留用于作者显示、维护者角色和治理记录，不再作为普通写入 allowlist；未列入名单的 GitHub Write 成员仍可以提交自己的新条目。

提交前 AI 会执行完整材料清单、元数据和 state 校验、敏感内容与出站检查、依赖与版本锁定、可信基线检查，以及只能改一个条目材料的范围检查。已发布版本目录不可改写；同一条目由当前 owner 继续发布新版本，其他成员创建自己的条目。维护与治理文件仍需要维护者角色。

直推只允许从最新 `main` 做一个 fast-forward 提交。禁止 force push、删除分支、覆盖竞争提交或绕过校验。main 在准备期间发生变化时重新获取；重复变化、身份变化、推送结果或读回材料无法核实时停止并保留本地回执。

## CI 与审核边界

Pull Request 不再是入库前提。`.github/workflows/check-submission.yml` 同时监听 PR 和 `main` 的 push；在 push 后使用可信基线以只读方式检查实际提交。CI 结果用于发现问题和回溯，不作为 GitHub 阻断规则，也不把 CI 通过说成业务验证通过。

身份来自 GitHub，提交材料当作数据读取；不执行投稿包脚本、hook 或安装代码。网页只展示能力目录，不授予 GitHub 权限。

## 离职、撤回与恢复

成员离开时，维护者在 GitHub 撤销其 collaborator 或 team 的 `Write` 权限，再按需要保留或移交条目所有权。删除 `members.json` 记录不会撤销 GitHub 权限。

撤回仍使用治理记录和固定版本状态；撤回请求不等于状态已生效。维护者核对共享状态后再报告撤回。历史提交保留，可在确认安全版本、依赖、范围和授权后恢复本地使用；不强推改写历史。
