# 验证脚本的范围与排错

按问题阅读本文件，不为每次局部补图重跑全部检查。两个现有脚本均只读；它们不会导表、导入 Cocos 或运行游戏。

## verify_season_config.mjs

必填参数：repo、region、season、previous、series-start、card-start、series-count、cards-per-series、gold-count。

读取已生成的区域 JSON，核对活动、卡组、卡牌、邮件、徽章关联、连续编号、数量、名称占位、金卡总数、上一期继承值和 TS/Go 映射。与当前 HEAD 比较旧 JSON 和 seasonCardPack。

实际限制：

- 不读取源 XLSX，不验证旧样式、公式或源表与导出的时效一致性；需单独校验本次源表。
- 旧 JSON 基线来自当前 HEAD；读取不到基线时部分旧对象比较会跳过。已提交到 HEAD 的历史污染无法由此发现，必须保留修改前基线。
- 它假定 cardRes/seriesRes 是从 1 开始的连续编号，且本期同位置星级、金卡、权重、组奖励继承上一期。合法改数值或结构时，不能为了脚本通过撤销需求，应单独比对批准的变化。
- 输出的 seasonCardPack SHA-256 是当前文件哈希；脚本对 HEAD 的保护是对象比较，逐字节保护另用事前保存的哈希核对。
- --assets 要求卡图、入口和徽章配套已存在；分批缺卡/入口时会直接失败，不是完整的缺项盘点工具。
- --require-all-art 必须与 --assets 一起用；missingArt 仅收集头图、公告图、结算图缺项。missingArt=[] 不等于所有显示都已验证。
- 图片尺寸检查覆盖卡牌 370×370、入口 200×200、徽章图标 128×128；三张大图只检查存在，尺寸需另外核对。
- UUID 去重覆盖目标卡图/入口的顶层纹理 UUID，不能证明全项目无冲突；不会全面检查 subMeta、trimType、SpriteFrame 尺寸或图片内容。
- 不证明 Config.bin/语言资源被运行客户端加载，更不证明服务端初始化、发奖或画面正确。

## verify_badge_assets.mjs

调用：node scripts/verify_badge_assets.mjs <仓库路径> <badgeRes...>。

检查图标及 Meta、atlas/PNG/skel 及 Meta，rawTextureUuid、skel 贴图 UUID、atlas 引用的 PNG 名。若 library/uuid-to-mtime.json 存在，还会比对路径与 UUID。

限制：library 文件不存在时跳过该检查；路径缺失只输出 warning，仍可能 OK。它不会实际解析/播放 Spine 动画，也不证明 idle 存在或版本兼容。动画需另在 Cocos 与游戏中预览。

## 对应关系与短排错路径

| 现象 | 检查顺序 |
| --- | --- |
| 入口/卡图错组 | 需求表图案 → 卡牌 seriesId → 卡组 seriesRes → cardRes → 实际 PNG；不用上传次序推断 |
| PNG 尺寸正确但显示偏移 | Meta 的 raw 尺寸 → SpriteFrame width/height/trim/offset → UI 实际显示 |
| 徽章高级/普通反了 | firstReward/secondReward → Badge<ID> → badgeID → badgeRes → 图标与 Spine 全套 |
| 徽章只有光效 | Spine/Badge 是否存在 → atlas/PNG/skel → texture UUID → Spine 版本和 idle → 游戏主体节点 |
| 公告 MISSING | 当前活动 content → 赛季目录 img_notice → Meta 导入 → 实际加载资源版本 |
| 结算图未换 | 当前代码 HasNextRound 分支、角色轮次；S20 无下一轮时使用 Texture/CardSeason/img_ending 共享图 |
| 名称没生效 | 源 XLSX → 区域导出及语言资源 → 当前客户端实际加载版本 |
| 10015 配置错误 | 服务端校验日志 → 实际加载分支/区域/JSON → 排期 content → 关联表，不先改图 |
| WPS 拒绝打开 | XLSX XML/RELS 严格解析、r:id 命名空间、关系唯一性，再验证 ExcelJS/桌面打开 |
| 旧徽章出现 140、边框变虚线 | 共享字符串误读/整本格式重存，按保存基线只修本次意外变化 |

最后报告实际证据：执行了什么、输出结果、哪些跳过/未验证。不要把脚本静态通过写成服务器或游戏已通过。
