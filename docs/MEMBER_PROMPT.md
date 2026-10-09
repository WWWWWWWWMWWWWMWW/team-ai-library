# 给团队成员的一段简化提示词

把下面整段复制给能操作本地文件的 AI。第一步只负责把网页打开；网页打开后，直接在网页里搜索和复制能力指令。

```text
请接入并打开团队 AI 能力库：

仓库：https://github.com/WWWWWWWWMWWWWMWW/team-ai-library.git
分支：main

请按以下顺序操作：

1. 在新的独立目录克隆公开仓库：
   git clone --branch main https://github.com/WWWWWWWWMWWWWMWW/team-ai-library.git team-ai-library

2. 进入仓库后，立即打开网页：
   - macOS：open docs/local-library.html
   - Windows：start docs\\local-library.html
   - Linux：xdg-open docs/local-library.html
   如果无法自动打开浏览器，直接返回该文件的绝对路径，让我双击打开。

3. 网页是主要入口。打开后让我浏览、搜索能力，点击“查看详情”和“复制使用指令给 AI”。

4. 我选定某项能力后，再按网页给出的 ID 和版本读取对应说明并使用。不要先要求安装 gh、登录 GitHub 或运行 doctor；公开仓库的网页浏览不需要这些工具。

5. 只有我明确要求“下载”“安装”“使用”或“上传”时，才执行对应操作，并先说明实际需要的工具、输入、产物和权限。不要自动上传、修改远程仓库、运行能力包脚本或安装外部依赖。

6. 完成后用中文简短报告网页路径、能力 ID/版本、实际做了什么和未验证项。
```

网页文件是 `docs/local-library.html`，无需启动服务、安装前端依赖或使用 `gh`。网页里的目录是生成时快照；真正使用某项能力时，再由 AI 按页面给出的固定版本和入口核对当前材料。
