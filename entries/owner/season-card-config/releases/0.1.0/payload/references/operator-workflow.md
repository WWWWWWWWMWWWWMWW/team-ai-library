# 新赛季相册配置：照着做

适用国服，数值沿用上期。以下 S20 仅为示例，新一期换成本期编号；路径从 mergeclient 根目录开始。

## 开工清单：4 个 Excel、5 个页签、7 类资源

### 要配置哪些表

源表目录：`tool/data/data/docs/`。

| Excel 文件 | 要配置的页签 | 本期新增内容（以 S20 为例） | 用途 |
| --- | --- | --- | --- |
| `seasonCard/seasonCardSeries.xlsx` | `seasonCardSeries(s20)` | 复制上期为新页签，填 12 行 | 卡组名称、图片组编号、集齐奖励 |
| `seasonCard/seasonCardCard.xlsx` | `seasonCardCard(s20)` | 复制上期为新页签，填 108 行 | 卡名、图片编号、所属卡组、星级和权重 |
| `badgeList.xlsx` | `badgeList` | 追加 2 行 | 普通/高级徽章名称、资源名、活动关联 |
| `seasonCard/seasonCard.xlsx` | `seasonCardMail` | 追加 1 行 | 本期补发邮件 |
| 同上 | `seasonCardActivity` | 追加 1 行 | 主题、两轮奖励、邮件引用、规则版本 |

**本流程不改：**`seasonCardPack`、旧赛季数据和样式；抽卡规则、共享参数、礼包、商店、兑换表在数值沿用时也不改。

### 要准备哪些资源

下表数量、尺寸按 S20 模板；新一期有规格变化时先确认。

| 资源 | 数量 | 尺寸 | 目标文件名或路径 |
| --- | --- | --- | --- |
| 卡牌图 | 108 张 | 370×370 | 相册目录下 `Cards/组编号/卡编号.png` |
| 卡组入口图 | 12 张 | 200×200 | 相册目录下 `Series/Entrance/组编号.png` |
| 头图 | 1 张 | 636×291 | 相册目录下 `img_ui_bg.png` |
| 公告图 | 1 张 | 676×1089 | 相册目录下 `img_notice.png` |
| 结算图 | 1 张 | 676×722 | 相册目录下 `img_ending.png` |
| 普通/高级徽章图标 | 2 张 | 128×128 | 徽章图标目录下 `icon_Badge_<badgeRes>.png` |
| 普通/高级徽章动画 | 2 套，每套 atlas、png、skel | 按兼容引擎的美术导出规格 | 徽章动画目录下 `Badge<badgeRes>.atlas/.png/.skel` |

资源只放这三个位置：

- **相册目录：**`client/assets/remoteAsset/Texture/CardsSeason/s20/`
- **徽章图标目录：**`client/assets/remoteAsset/Texture/Badge/`
- **徽章动画目录：**`client/assets/spineAsset/Spine/Badge/`

**合计：127 张静态 PNG + 2 套动画（另含 2 张动画贴图）。**新增资源及文件夹的 `.meta` 由 Cocos 生成，检查后随资源提交，不需要美术提供。

**顺序：收资料 → 整理图片 → 导入 Cocos → 填卡组和卡牌 → 填徽章 → 填邮件和活动 → 导表测试。**

## 第 1 步：向带教同事拿齐资料

**准备什么**
- 最新文案表：主题、卡组名、每组卡名、两枚徽章名称。
- 本期赛季号、卡组起始 ID、卡牌起始 ID、两个徽章 ID、邮件 ID。
- 上一期配置，以及本期开发分支、测试服。

**记下编号：**S20 示例为赛季 `s20`、卡组 `1901～1912`、卡牌 `19001～19108`、普通/高级徽章 `22101/22102`、邮件 `19`。

**做完确认：**ID 未被占用，分支正确。本期编号由带教确认。

## 第 2 步：收图、编号、放目录

**准备什么：**下表美术，按文案表组序、卡序命名。

**放在哪里：**相册图片统一放到
`client/assets/remoteAsset/Texture/CardsSeason/s20/`

| 要准备的图 | 数量、尺寸 | 在上述目录内怎样放 |
| --- | --- | --- |
| 卡牌 | 12 组×9 张，370×370 | 第 1 组放 `Cards/1/1.png～9.png`，第 2 组放 `Cards/2/1.png～9.png`，依次到第 12 组 |
| 卡组入口 | 12 张，200×200 | `Series/Entrance/1.png～12.png` |
| 头图 | 1 张，636×291 | `img_ui_bg.png` |
| 公告图 | 1 张，676×1089 | `img_notice.png` |
| 结算图 | 1 张，676×722 | `img_ending.png` |

普通、高级徽章各准备一张 **128×128 图标**和一套 **atlas、png、skel 动画**，分开放：

| 目录 | 普通徽章文件名（S20） | 高级徽章文件名（S20） |
| --- | --- | --- |
| `client/assets/remoteAsset/Texture/Badge/` | `icon_Badge_Card2610_1.png` | `icon_Badge_Card2610.png` |
| `client/assets/spineAsset/Spine/Badge/` | `BadgeCard2610_1.atlas`、同名 .png 和 .skel | `BadgeCard2610.atlas`、同名 .png 和 .skel |

**做完确认：**图片尺寸正确；每组 9 张与卡名对应，入口属于本组；普通/高级映射经美术确认，不凭上传顺序猜。缺图登记补交。

## 第 3 步：让 Cocos 导入资源

**准备什么：**第二步整理好的资源，Cocos Creator **2.4.9**。

**在哪里操作：**打开 `client/` 工程，在 Assets 面板找到新资源，等待导入。

1. 新文件让 Cocos 自动生成 `.meta`，不要带入旧赛季的 Meta；替换同路径修正版图片时保留已有 Meta。
2. 选中卡牌、入口、头图的 **SpriteFrame 子资源**，裁切设为 **None** 并应用。
3. 预览两套徽章动画，确认贴图正常、`idle` 能播放。运行文件要在 `Spine/Badge/`，不能只在 UiSpine 目录。

**做完确认：**完整帧分别为 370×370、200×200、636×291，无偏移；公告/结算按上期设置。资源有 Meta、无导入报错，动画与图标一致。

## 第 4 步：先填卡组，再填卡牌

**准备什么：**卡组/卡名表、第二步的图片编号、本期 ID。以下 Excel 都在 `tool/data/data/docs/`。

**打开** `seasonCard/seasonCardSeries.xlsx`，复制上期页签为 `seasonCardSeries(s20)`，保留前四行，填数据：

| 字段 | 填什么 |
| --- | --- |
| `id` | 本期卡组 ID，如 1903 |
| `seriesName` | 本组名称，如「寻花之旅」 |
| `seriesRes` | 图片组编号，如 3；对应 Cards/3 和入口 3.png |
| `reward` | 本组集齐奖励，沿用上一期对应组 |

**再打开** `seasonCard/seasonCardCard.xlsx`，复制上一期页签，改名为 `seasonCardCard(s20)`：

| 字段 | 填什么 |
| --- | --- |
| `id` | 本期卡牌 ID，如 19024 |
| `cardName` | 对应图片的卡名，如「夹竹桃」 |
| `seriesId` | 所属卡组 ID，如 1903 |
| `cardRes` | 组内图片编号，如 6；不填 .png |
| `star`、`isGolden` | 星级、是否金卡，沿用上期对应位置；金卡为 1 |
| `weight`、`newweight` | 抽卡权重、下一张 new 卡权重，沿用上期 |

**做完确认：**12 组×9 张，金卡分布与上期一致（S20 共 20 张）。逐组按下面方法对图：

```text
卡牌「夹竹桃」：seriesId = 1903，cardRes = 6
→ 找卡组 id = 1903：seriesRes = 3
→ 打开 s20/Cards/3/6.png，应当是夹竹桃
→ 打开 s20/Series/Entrance/3.png，应当是这一组的入口
```

**seriesId 是卡组 ID，seriesRes 才是图片目录编号。**

## 第 5 步：填两枚徽章

**准备什么：**已确认的普通/高级图标、动画、名称和 ID。

**在哪里填：**`badgeList.xlsx` 的 `badgeList` 页签。复制上期普通、高级两行到末尾：

| 字段 | 普通徽章（S20） | 高级徽章（S20） |
| --- | --- | --- |
| `badgeID`：徽章 ID | 22101 | 22102 |
| `badgeRes`：资源后缀 | Card2610_1 | Card2610 |
| `badgeName`：名称 | 馨香满怀 | 花开有期 |
| `actType`：关联赛季 | cardSeason_s20 | cardSeason_s20 |

其余字段继承上期：`badgeTopThreeDesc` 获得说明、`badgePrevDesc` 未获得说明、`badgeTime` 日期模板，保留 {0} 等占位符。`showCondition` 显示条件及排行榜字段 `badgeHundredDesc/badgeIntro/badgeRankBg/worldRank`，S20 为空。

**做完确认：**两行都存在。用 badgeRes 对文件名：

```text
badgeRes = Card2610_1
→ 图标 icon_Badge_Card2610_1.png
→ 动画 BadgeCard2610_1.skel，以及同名 atlas、png
```

高级同样检查；badgeRes 只填后缀。

## 第 6 步：填邮件，再填赛季活动

**准备什么：**邮件 ID、赛季号、主题、两枚徽章 ID。

**在哪里填：**打开 `seasonCard/seasonCard.xlsx`。

先在 **seasonCardMail** 页签复制上期一行到末尾：
- `id` 改成本期邮件 ID（S20：19），`belong` 改成本期赛季号（s20）。
- `mailTitle/mailContent` 是标题/正文，`mailIcon/mailBg` 是邮件图标/配图，`mailSignature` 是署名，`mailValidity` 是有效天数；均沿用上期，检查文案没有旧主题残留。

再在 **seasonCardActivity** 页签复制上期一行到末尾：

| 字段 | 填什么 |
| --- | --- |
| `id` | 本期赛季号 s20，必须与两个新页签后缀、资源目录一致 |
| `themeName` | 本期总主题「缱绻花语」 |
| `firstReward` | 首轮奖励：数值沿用，徽章换成普通 Badge22101 |
| `secondReward` | 二轮奖励：数值沿用，徽章换成高级 Badge22102 |
| `passRewardMailID` | 刚新增的邮件 ID：19 |
| `ruleGroupCondition` | 抽卡规则选择条件，沿用上期；S20 为 return 1 |
| `DrawRule2Prefix/NewRule2Prefix` | 抽卡/新卡规则版本，沿用上期；S20 为 v1/v2 |

S20 奖励填写示例（英文冒号和竖线）：

```text
firstReward：Energy:1000|Badge22101:1|Diamond:1000
secondReward：Energy:1200|Badge22102:1|Diamond:1500
```

**做完确认：**首轮引用普通徽章，二轮引用高级徽章；邮件 ID 对应 belong=s20。旧配置、样式及 seasonCardPack 不改。

## 第 7 步：导表，进入测试服检查

**准备什么：**保存好的四张 Excel、导入完成的资源、约定的测试服和角色。

**在哪里操作：**在 `tool/data/` 逐条运行，前一步成功再执行下一步：

```bash
npm run ts_zh
npm run go_zh
bash fixGoConfig.sh
npm run compress_zh
```

确认日志无错误、国服导出有本期数据、Go 入口为 `func _GetConfig()`；修复脚本执行一次。明确不导表时跳过，记录运行未验证。

请负责人设置测试排期 **type=cardSeason、content=s20**、起止时间，并加载服务端新配置。content 决定哪期相册，配表不会自动开活动。

**做完确认：**请带教准备首轮、二轮和结束状态的测试角色，按下表验收。

| 打开哪里 | 对着什么检查 |
| --- | --- |
| 相册主页 | 主题等于 themeName；头图正常；12 组入口与 seriesName、seriesRes 对应 |
| 每个卡组和卡牌详情 | 每组 9 张，图与 cardName 一致；星级、金卡框、组奖励正确，无裁切或错位 |
| 首轮/二轮奖励 | 分别是普通/高级徽章，名称、图标、奖励数量正确且实际到账 |
| 徽章室 | 两枚图标与名称正确；大图主体、动画都显示，不是只有光效 |
| 公告、结算、邮件 | 背景和文案完整；结算无下一轮时使用共享背景；邮件内容及奖励正确 |
| 重进游戏 | 仍进入本期，显示和角色数据正常 |

出现 MISSING，先查实际加载路径、文件和 Cocos 导入；初始化返回 10015，查服务端日志、配置版本和活动引用。

最后在 UGit 只选择本期表格、资源/Meta 和必要国服产物。保存验收截图、注明未测项，按团队流程审查提交。
