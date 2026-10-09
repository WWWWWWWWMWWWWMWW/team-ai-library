---
name: work-knowledge
description: "检索、收录和维护用户的 Obsidian 工作知识库，连接策划原稿、来源知识和 Codex 外置记忆。用户问知识库、过去的项目决策、已保存流程/偏好，或要求依据策划资料继续工作时使用；简单无背景任务跳过。"
---

# 工作知识库

读取本技能目录 `config.local.json` 获取 Vault 和本机项目映射；路径不从历史摘要猜测。读取 Vault `AGENTS.md`、`系统/系统-维护规则.md`。具体字段和脚本契约见 `references/runtime.md`。

## 读取

1. 确定问题类型和项目。config 的最长目录前缀映射优先；未映射则按用户指定的资料集合/项目与标题查询，不能把资料集合推断为代码项目。
2. 用 `scripts/knowledge --vault "<vault>" search "关键词" --project ID` 找前1–3页。项目明确时按该ID检索；跨项目主题逐个查实际集合，通用偏好用global。中文使用具体主题关键词，未命中可缩短关键词或用 `rg`；不是语义检索。
3. 回读命中全文和来源章节，比较指纹/版本。需要草稿和历史时用 `--include-noncurrent` 并显式标注。运行 `check` 读取实际问题，不把索引当权威。
4. 设计看策划，确认看决策，实现看配置/代码/运行证据。引用源ID、版本或采集时间、章节/工作表字段，以及适用环境。飞书快照只代表采集时的本地资料；问远端最新须重新访问原链接。

## 收录和更新

用户明确要求保存/收录/修改即授权相关本地范围；无保存授权时只提出建议。自发记忆候选不自动写正式区。

- 原稿保持唯一编辑主位置；导入不升级定稿或已上线。保存字节不变的采集快照和文档卡，摘要另页附来源指纹与定位。图表、公式、批注未核查要标缺口。
- 新页面最低 id/type/project/updated；派生关系和状态按 runtime.md。不要给原始导出文件加 frontmatter；它作为 source_path 来源且置于原文件/或版本/。
- 已有正式笔记先写 work 中候选，再 `prepare`（持久化候选、基线/目标指纹、授权）→ `apply`。收到 conflict 保留候选并停止覆盖。主稿变化后直接派生页需复核；语义同步需要回读后另操作。
- 完成 index、check 和日志核查。有未完成操作先查 journal 再 resume；保留已成功内容，按 base/target/其他三态恢复，不能盲目重放。
- 原生 `/Users/hcm-b0263/.codex/memories` 只读查线索；不手改生成文件、SQLite、会话日志，不做双向同步。正式纠正存在冲突时回读新记录和证据。
- 首版只本机、明确操作，不能承诺自动跨设备、自动写飞书、实时监听或聊天结束必然保存。

## 备份

按 config 的 backup_dir 显式调用 backup；附件包含在本地 Vault 快照中。外部编辑主稿/远端资料只有已采集副本被备份；原生记忆和 Codex设置分别维护。不添加定时任务、不自动提交或上传。

## Codex → Obsidian 单向同步

需要把 Codex 生成或更新的 Markdown 文档/记忆送入 Obsidian 时，源文件放入 `/Users/hcm-b0263/Documents/Codex/同步到Obsidian`；原生记忆由同步配置只读扫描。同步服务将字节保留的原始 Markdown 写入 Vault 的 `收件箱/Codex同步/原始/`，并生成 `收件箱/Codex同步/索引/Codex同步索引.md` 和 `系统/Codex单向同步状态.json`。方向固定为 Codex → Obsidian：不读取 Obsidian 的修改作为 Codex 输入，不写回 `/Users/<user>/.codex/memories`。

手动立即同步：

```sh
/Users/hcm-b0263/.codex/skills/work-knowledge/.venv/bin/python \
  /Users/hcm-b0263/.codex/skills/work-knowledge/scripts/codex_to_obsidian_sync.py \
  --vault "/Users/hcm-b0263/Documents/Obsidian/工作知识库" sync
```

本机 LaunchAgent `com.hcm.codex-to-obsidian-sync` 每30秒检查一次源目录；源删除默认只在索引中标记，Obsidian 历史副本不自动删除。同步源、目标和间隔以 Vault 内 `系统/Codex单向同步.json` 为准。

维护命名时先运行 `knowledge --vault "<vault>" lint-names`；工作层文件使用“类别-主题”前缀，活动规则使用 `规则-活动名`。技术层（内部操作归档、原稿目录、同步原始副本）保留稳定路径，不参与日常侧栏整理。
