# 步骤与衔接

1. 新AI上下文拉取私有main，只读README、AGENTS、接入与操作指南。
2. doctor区分readable=true与发布缺保护；依指南继续允许的只读查找。
3. 用“审策划案”别名定位owner/design-review@0.1.0，fetch取得workflow及review-checklist@0.1.0完整依赖。
4. 按真实文档审查任务填写scope/environment/effects，不伪造范围；check-reuse核对包、依赖、当前状态和来源。
5. 读取两项实际入口，对合成稿识别时间、资格、计数、兑换、奖励、清算、幂等与同步缺口。未修改原稿，未永久安装。
6. 将真实来源与脱敏结果交给record-run，只记本地，不回传原稿或完整聊天。

# 踩过的坑

判断：doctor被阻断是否意味着完全不可读？依据：JSON明确readable=true/can_publish=false，指南拆分读写条件。调整：保持发布阻断，独立完成只读流程。经验：失败必须按操作范围解释，不能越权放行。

判断：clone HEAD能否当下载来源？依据：试用期间指南更新，fresh source_commit与clone不同而能力版本未变。调整：保留下载/检查的真实锁定SHA。经验：仓库提交和能力独立版本分别追溯。

# 证据边界

来源JSON固定原实际试用材料及摘要，不预填本案例未来发布SHA。passed仅为合成文档7项审查条件实际自检；生产游戏运行、第二成员、第二工具、原生Skill发现及正式平台保护均未验证。来源版本须使用前重查当前撤回/作废状态。本例收录不继承原流程的业务验证。
