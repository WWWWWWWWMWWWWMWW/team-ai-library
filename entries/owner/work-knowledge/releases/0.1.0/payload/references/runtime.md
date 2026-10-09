# 本地知识库助手运行约定

运行：Python 3 + PyYAML（本轮已用 PyYAML 6.0.3 验证）。所有命令输出 JSON；失败返回码 1，`check` 有错误也返回 1。脚本无网络请求，无自动 Git 操作，无应用插件。

```sh
python knowledge.py --vault /absolute/vault index
python knowledge.py --vault /absolute/vault check
python knowledge.py --vault /absolute/vault search '阶段奖励' --project demo
python knowledge.py --vault /absolute/vault prepare --target 项目/demo/知识/奖励.md --candidate /absolute/candidate.md --authorization '用户明确要求更新奖励说明'
python knowledge.py --vault /absolute/vault apply --op UUID
python knowledge.py --vault /absolute/vault resume --op UUID
python knowledge.py --vault /absolute/vault backup --output /absolute/backups/dated-vault.zip
```

`prepare --manifest /absolute/manifest.json --authorization '…'` 支持多个目标，manifest 是非空 JSON 数组：`[{"target":"项目/demo/策划案/正文.md","candidate":"/absolute/candidate.md"}]`。目标必须是 Vault 内 Markdown；候选可在外部临时目录。更新须先 prepare 再 apply。`authorization` 是用户指令来源的审计描述，不是可验证身份签名，调用者必须已获得真实授权。

正式笔记 YAML frontmatter：`id/type/project/updated` 必填；updated 带时区。`id` 全库唯一，改名或移动不改变。无 frontmatter 的原始 Markdown 快照不计为正式笔记；有 frontmatter 但缺必填字段时报错。首页、索引、AGENTS，以及系统、.obsidian、.git、方法模板、模板、templates 不参与正式页索引。模板只是结构示例，不能作为项目事实。原始附件、原文件仍可进入 ZIP 备份。

派生引用采用：

```yaml
revision: v1
freshness: current
# 如是文档卡，用 working_revision 表示工作版本，document_state 表示草稿/定稿。
derived_from:
  - source_id: PLAN-demo-001
    source_revision: v1.2
    source_fingerprint: 64位SHA256
    locator: 第4节
  - source_path: /absolute/config.xlsx
    source_revision: cfg-demo-002
    source_fingerprint: 64位SHA256
    locator: 配置表!B2 / 字段名
```

库内引用以稳定 `source_id` 解析当前路径；可选 source_path 仅为位置提示，移动产生警告，不破坏 ID 引用。外部引用必须用绝对 `source_path`，只读。库内源版本比对 working_revision（优先）或 revision；外部 Markdown 有 frontmatter 时也比对其版本。Excel、Word、PDF 等二进制文件的版本是录入的来源标签，脚本只验证其字节指纹，不能自动证明该标签正确，不能解析表格、公式、批注、页码或段落。locator 记录范围，脚本验证非空，调用者回读具体位置。全文件原始字节 SHA-256，包括 Markdown frontmatter；指纹不写进被计算的源文件，避免自指。

飞书快照加 `source_kind: feishu_snapshot`、`captured_at`、`primary_source`；检索明确返回 `snapshot_not_live` 警告，不能证明远端当前状态。设计10、配置12须分别引用设计和配置；脚本不判断业务孰对，不声称线上结果或自动改值。

search 强制 project，最多返回3页真实相对路径，检查引用后排序。按类型还必须提供相应状态：plan_card/策划文档卡→document_state，decision/决策→decision_state，knowledge/知识及memory/记忆→freshness。缺少状态的页与其派生页默认排除，check 返回 missing_state 警告，其他完整页正常检索。状态采用允许清单：已提供 freshness 只认 current/当前，document_state 只认 approved/final/定稿，decision_state 只认 confirmed/decided/已确认/已决定。草稿、评审中、未知、待决定、候选、需复核、已替代、归档以及来源不匹配的页面均排除默认检索；库内及外部有元数据的 Markdown 来源状态同样核查；`--include-noncurrent` 可读历史但返回 `authoritative:false` 与原因。`authoritative` 仅指此检索页可作为其记录范围的当前入口，不证明业务内容或运行效果。警告、排除列表和核查报告仍随结果输出；重要答案需回读页面及原始资料。

`系统/内部/操作记录/UUID.json` 是操作事实来源；更新日志、待同步、索引可重建。prepare 保存所有候选、源先前字节备份、每文件 base/target SHA256、版本和授权，再持久化日志，之后才允许 apply。源直接派生及后续受字节变化影响的派生闭包均产生独立候选，并仅标 needs_review，保留其旧引用和正文；这不代表内容已同步。恢复对每个目标比较：等于 base 则写候选，等于 target 则补未完成步骤，均不同则冲突并保留候选。索引失败保留已写源和 pending 日志；修复实际阻塞后 resume。检查会报告未完成操作，不把它们当已核验。

临时文件在同目录写入、文件及目录 fsync 后 replace。fcntl 锁只协调本脚本写入者；落盘前复读仍无法对 Obsidian 人工编辑实现原子 compare-and-swap。页面自动写入时应避免同时人工编辑；无实时一致性或多文件原子事务承诺。读取也可能与人工编辑交错，重要结论需复读。

`check` 检查重复 ID、来源缺失、必需版本/指纹/定位、版本与指纹差异、派生循环、替代目标、未完成操作和库根路径形式的 wiki 链接文件存在性；优先匹配链接指向的实际文件，否则匹配附加 .md 的文件，支持文件名中的版本点号。需复核页的来源差异作为警告保留历史，不自动更新内容。标题锚点、Obsidian 简写链接解析、Word/Excel语义和应用UI尚未验证；移动后需修复指向旧路径的导航链接。源被删不级联删除知识。

备份 ZIP 包含 Vault 全部普通文件和附件，拒绝符号链接，输出须在 Vault 及原生 memories 外，拒绝覆盖已有备份。ZIP 验证 CRC；外部只读源原件不在备份范围，应另安排备份。对实时人工编辑的完整快照一致性没有保证。恢复建议解压到独立目录核查后有授权再替换；不要对不可信 ZIP 直接整体 extractall。

原生 `/Users/<user>/.codex/memories` 及其子目录禁止作为 Vault 或备份输出；每个解析后的写入目标都检查原生 memories 边界，即 Vault 在其父目录也不能绕过；任何笔记写入须通过库内规范路径检查，./ 等别名被拒绝，防止稳定 ID 校验绕过。脚本不写外部源，不改全局配置，不安装 Obsidian、不证明跨会话自动路由。

验证记录：`RED.txt` 为实现前19项测试的初始失败记录；`GREEN-first.txt` 为19项真实临时文件测试通过记录；`RED-edge.txt` 记录额外3项边界失败；`GREEN.txt` 为22项通过记录；`RED-review-all.txt` 记录评审5项回归失败，`GREEN-review.txt` 为27项通过记录；`RED-state-required.txt` 为2项必需状态回归失败，`GREEN-final.txt` 为29项通过记录；`RED-dotted-wikilink.txt` 复现中文带点标题误判，最新 `GREEN-dotted-wikilink.txt` 为30项通过记录。`index-preview.txt` 展示实际生成索引的可点击全路径双链，JSON 保持纯真实路径。源写入但日志未更新使用真实磁盘中断状态；索引故障使用目录占据索引路径；ZIP恢复实际替换一份测试笔记，非正式库。
