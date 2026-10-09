---
name: season-card-config
description: 配置、检查 mergeclient 指定地区的赛季相册，覆盖源表、卡牌与入口资源、徽章图标和 Spine、Cocos 导入及运行排错；也用于编写新人可照做的赛季配置流程。
---

# Season Card Config

更新：2026-09-18。围绕“输入、源表、资源、导出、运行”维护同一份进度，按本次请求处理对应阶段。

## 使用范围与资料

- 配表、补资源、排错：先确认当前仓库和分支、地区、目标赛季、上一期，以及本次允许执行的阶段；直接继承本轮已明确的要求。
- “只检查”“写流程”只读业务文件；“先配表”“不用导表”“先传现有资源”按原范围完成，不强加导表或等待所有美术。
- 暂存、提交、推送、发送、发布、服务器部署/重启按用户明确范围执行；“配置相册”不自动授权这些附加操作。用户已授权的操作不重复询问。
- 读现有项目规则和相关源表。旧会话分支、角色、路径、时间只作线索，S20 示例不是新一期默认参数。
- 需要字段填法、命名和新人步骤时，读取 [新人操作流程](references/operator-workflow.md)。不用每次读取全部历史记录。
- 用户要新人流程：开头先列“涉及哪些表、哪些资源”；每步写“准备什么、在哪填/放什么、做完看什么确认”。使用一个真实编号例子贯穿，继承字段合并说明，避免堆成参考手册。

## 涉及范围

常规换期涉及 4 个源 XLSX、5 个页签。源目录为 `tool/data/data/docs/`：

| 文件 | 页签 | 动作 |
| --- | --- | --- |
| seasonCard/seasonCardSeries.xlsx | seasonCardSeries(sXX) | 复制上一期为新页签，填写卡组 |
| seasonCard/seasonCardCard.xlsx | seasonCardCard(sXX) | 复制上一期为新页签，填写卡牌 |
| badgeList.xlsx | badgeList | 追加普通、高级两行 |
| seasonCard/seasonCard.xlsx | seasonCardMail | 追加本期邮件 |
| 同上 | seasonCardActivity | 追加本期活动，关联邮件与徽章 |

默认保护旧赛季、旧样式及 seasonCardPack。兑换、礼包、商店、精选卡和抽卡规则只有在本期需求明确涉及它们时才改。

资源分三处：
- 相册：`client/assets/remoteAsset/Texture/CardsSeason/sXX/`
- 徽章图标：`client/assets/remoteAsset/Texture/Badge/`
- 徽章动画：`client/assets/spineAsset/Spine/Badge/`

S20 模板的 7 类资源为：108 卡图（370×370）、12 入口（200×200）、头图（636×291）、公告图（676×1089）、结算图（676×722）、2 徽章图标（128×128）、2 套 Spine（atlas/png/skel）。计 127 张静态 PNG 加 2 套动画；规格改变时按当前需求和 UI 验证。

## 执行顺序

### 1. 一次建立清单和基线

记录地区/分支/赛季、文案版本、ID 范围、卡组/卡牌/金卡数量、数值基线、徽章高低级映射、可用/缺失资源、保护项和请求阶段。

- 优先读取用户指定的最新原始材料。材料矛盾时只核实会影响当前写入的项，不重复索取已给信息。
- 保存开始时 Git 状态、HEAD、相关文件/旧数据及保护项哈希。保留已有工作区修改；不要把 HEAD 当作可覆盖用户修改的模板。
- 缺文案时只有用户接受才使用带明确标记的占位，缺美术列清单；已获准沿用的旧图可以复用，不能自行生成或复用掩盖缺失。

### 2. 预检、命名和增量导入资源

复制前核对本批全部输入、尺寸、内容映射和目标路径。预检失败不得先删除目标目录；用户只给部分资源时，安装已确认的批次并保留缺项。

- 卡牌：`Cards/<seriesRes>/<cardRes>.png`；入口：`Series/Entrance/<seriesRes>.png`。
- 头图/公告/结算：`img_ui_bg.png`、`img_notice.png`、`img_ending.png`。
- 图标：`icon_Badge_<badgeRes>.png`；动画：`Badge<badgeRes>.atlas/.png/.skel`。
- 用画面与卡牌内容确认组别，不能按上传顺序分配 3/9 等缺图；高低级不能只按 _1 后缀或文件尺寸猜。
- 新路径让 Cocos 生成独立 Meta；同路径替换保留原 UUID；UiSpine 复制到 Badge 时不复制源 Meta，atlas 引用 PNG 名必须一致。
- 使用当前项目版本打开 client 工程（S20 为 Cocos 2.4.9、Spine 3.8），集中导入当前批次后检查最终 Meta。
- 卡牌、入口、头图按既有模板保留完整帧，通常 trimType=none、偏移 0；同时核对 raw 和 frame 尺寸。公告/结算按验证过的模板，不统一强改 none。
- 检查图标/动画、SpriteFrame rawTextureUuid、skel 纹理引用、UUID 冲突和 library 映射，实际预览 idle。
- Cocos 自动产生的无关变更只报告并排除，不因看似“缓存噪声”就恢复、删除其他人的文件。

### 3. 按依赖填写源表

先卡组，再卡牌，再徽章和邮件，最后活动引用。资源未到齐不阻止已授权的配表。

- 保留前四行表头；页签使用英文括号的 seasonCardCard(sXX)、seasonCardSeries(sXX)。
- 卡牌 seriesId 指向卡组 id；seriesRes 是组图片目录；cardRes 是组内图片编号。卡牌 ID 不是文件名。
- firstReward/secondReward 分别引用确认过的普通/高级 Badge<ID>，再经 badgeRes 找到图标与动画。
- passRewardMailID 指向新增邮件 id，邮件 belong、徽章 actType=cardSeason_sXX 与目标赛季一致。
- 数值继承按同位置逐项比对 star、isGolden、weight、newweight、组奖励；权重不能解释成固定概率。
- ruleGroupCondition、DrawRule2Prefix、NewRule2Prefix 按批准规则继承，规则前缀不是赛季号。

程序写表需保留旧 OOXML、共享字符串和样式，避免整本转换重存。追加多行预分配位置，防止两枚徽章互相覆盖；关系 ID 当作不透明字符串，保证唯一有效，不生成 rId-Infinity；新增 r:id 使用正确命名空间。

保存后检查包内 XML/RELS、关系引用、项目 ExcelJS 读取和桌面表格软件可打开；检查旧值/样式零意外差异、新文案无零宽字符、名称可读。数量、引用、金卡分布和批准占位状态通过后才进入导表。

### 4. 在请求范围内导出和验证

不用导表时，停在源表/资源证据，不能拿旧 JSON 验证冒充本次源表已生效。

国服在 tool/data 逐条执行，前一步失败即停：

```bash
npm run ts_zh
npm run go_zh
bash fixGoConfig.sh
npm run compress_zh
```

fixGoConfig 仅紧跟本次 go_zh 执行一次，检查 func _GetConfig() 存在、func GetConfig() 不存在。不要只信聚合脚本退出码；不处理意外生成的其他地区产物。

按真实清单替换参数，脚本相对于本 Skill：

```bash
SEASON_SKILL_DIR="/实际路径/season-card-config"
SEASON_REPO_DIR="/实际路径/mergeclient"
node "$SEASON_SKILL_DIR/scripts/verify_season_config.mjs" \
  --repo "$SEASON_REPO_DIR" --region zh --season s20 --previous s19 \
  --series-start 1901 --card-start 19001 \
  --series-count 12 --cards-per-series 9 --gold-count 20 \
  --assets --require-all-art
node "$SEASON_SKILL_DIR/scripts/verify_badge_assets.mjs" "$SEASON_REPO_DIR" Card2610 Card2610_1
```

这些是 S20 示例，不是下一期的默认编号。具体检查限制见 [验证与排错](references/verification.md)，不得扩大 passed/OK 的含义。

### 5. 运行核查与交付

活动排期 type=cardSeason、content=sXX；content 指向 seasonCardActivity.id。Excel 不自动设置排期。核对测试服实际加载的分支/地区/版本；未授权服务器操作时提供具体待验证项，不伪造结果。

验收初始化、全部组与卡名/图案、星级和金卡、两轮奖励到账、两枚徽章静态图和 idle、公告/结算、邮件及重进。无下一轮时可能读取共享结算背景，先核对当前代码和角色轮次。

- MISSING：追实际路径、文件、Meta、加载版本。
- 10015：追服务端校验日志、配置部署和活动引用；错误码不能证明某个具体字段坏了。
- 只有光效：追 Spine/Badge 主体动画，不重复替换图标。

仅在用户要求时按白名单暂存，并检查 diff --cached --check；不自动提交/推送。UGit 锁或 HEAD 变化先检查，不删除活跃 index.lock，也不将并发提交当成自己执行的操作。

## 交付状态

分别报告源表、资源、导出、运行、Git 状态和缺项，避免一个“完成”掩盖未做事项。
- 源表已配、资源不齐：配置待资源；导出可为未执行。
- 源表/资源齐，但未导出：配置和资源就绪，未导表。
- 适用的静态检查通过，但游戏未验收：资源待运行验证。
- 整期完成：所需导出、服务端加载、初始化、显示和奖励均有证据。是否提交单独报告。
- “只检查/补图/写指南”的范围内工作可完成，不能由此声称整期已验收。

按需更新当前任务交接；不要强制每个局部任务更新记忆或复盘。复用清单、基线和验证脚本；限制搜索到相关模块和目标目录，只输出本次变化、失败与待办。
