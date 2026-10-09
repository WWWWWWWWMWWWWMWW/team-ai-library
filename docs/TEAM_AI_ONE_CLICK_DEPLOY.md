# 团队库 AI 一键部署手册

这份手册给团队成员和能够操作本地文件、终端与浏览器的 AI 使用。目标只有一件事：把公开的团队能力库放到一个独立目录，并直接打开能力库网页。

仓库：<https://github.com/WWWWWWWWMWWWWMWW/team-ai-library.git>  
分支：`main`  
网页启动文件：`00-打开团队能力库网页.html`

## 直接复制给 AI

```text
请作为团队能力库部署助手，完成公开团队库的本地接入并打开网页。

仓库：https://github.com/WWWWWWWWMWWWWMWW/team-ai-library.git
分支：main

请按以下步骤执行：

1. 不要修改我的业务项目，不要覆盖已有目录，不要 reset、clean 或删除已有修改。
2. 在独立目录取得仓库：
   - 如果目标目录不存在：克隆 main 分支。
   - 如果目标目录已经存在且工作区干净：核对远端后执行 git pull --ff-only origin main。
   - 如果目标目录有本地修改：保留原目录，另建一个新的独立目录获取 main。
3. 取得仓库后，确认根目录存在 `00-打开团队能力库网页.html`。
4. 立即打开这个文件：
   - macOS：open "00-打开团队能力库网页.html"
   - Windows：start "00-打开团队能力库网页.html"
   - Linux：xdg-open "00-打开团队能力库网页.html"
5. 如果系统不能自动打开浏览器，返回这个文件的绝对路径，让我双击打开。
6. 打开网页后停止部署动作，让我在网页中搜索能力、查看详情和复制使用指令。

不要先安装 gh、登录 GitHub、运行 doctor、执行 fetch/install，也不要上传材料、修改远程仓库、运行能力包脚本或安装外部依赖。只有我另外明确要求时，才执行这些操作。

最后用中文简短报告：部署状态、仓库绝对路径、当前 main 提交、网页绝对路径，以及是否已经看到网页。
```

## 手动部署命令

### macOS

```sh
git clone --branch main https://github.com/WWWWWWWWMWWWWMWW/team-ai-library.git team-ai-library
cd team-ai-library
open "00-打开团队能力库网页.html"
```

### Windows PowerShell

```powershell
git clone --branch main https://github.com/WWWWWWWWMWWWWMWW/team-ai-library.git team-ai-library
Set-Location team-ai-library
Start-Process ".\00-打开团队能力库网页.html"
```

### Linux

```sh
git clone --branch main https://github.com/WWWWWWWWMWWWWMWW/team-ai-library.git team-ai-library
cd team-ai-library
xdg-open "00-打开团队能力库网页.html"
```

## 已有副本如何更新

先在网页关闭状态下更新本地副本：

```sh
cd /实际路径/team-ai-library
git status --short
git pull --ff-only origin main
open "00-打开团队能力库网页.html"    # macOS
```

如果 `git status --short` 有输出，不要覆盖本地修改；让 AI 另取一个新目录，或先由本人处理本地修改。

## 网页使用方式

打开后按这三个动作使用：

1. 在“能力总览”搜索要解决的问题。
2. 打开能力详情，查看适用范围、输入、产物、依赖和版本。
3. 点击“复制使用指令给 AI”，把指令粘贴到自己的 AI 对话中。

网页是离线快照，不执行能力包脚本，也不会自动读取本机文件、聊天、账号或令牌。网页能看到能力不代表真实业务已经验证；使用具体能力时，仍由 AI 根据当前任务核对版本、依赖和授权范围。

## 常见问题

| 现象 | 处理方式 |
|---|---|
| 根目录看不到网页文件 | 在仓库目录执行 `git pull --ff-only origin main`，刷新 Finder 或文件管理器。 |
| 双击没有自动打开 | 直接双击 `00-打开团队能力库网页.html`；它会跳转到 `docs/local-library.html`。 |
| AI 提示缺少 `gh` | 网页部署不需要 `gh`；先打开网页即可。 |
| 页面内容较旧 | 更新仓库后重新打开根目录启动文件；不要只刷新旧的浏览器标签页。 |
| 想使用某项能力 | 在网页中复制该项固定版本的使用指令，再交给 AI 按当前任务处理。 |

## 完成标准

部署完成必须能确认四件事：

- 仓库位于独立目录，业务项目没有被修改。
- 当前分支是 `main`，并能报告实际提交号。
- 根目录存在 `00-打开团队能力库网页.html`。
- 浏览器已经打开能力库网页，或已返回可双击的绝对路径。

这份一键部署只负责本地接入和网页展示。能力下载、安装、执行、上传和治理属于后续独立操作，必须由用户明确提出。
