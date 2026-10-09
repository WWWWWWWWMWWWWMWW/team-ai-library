---
name: mergeclient-ui-concept
description: Create mobile live-event UI concept mockups in mergeclient's established visual language by retrieving a small set of curated project screenshots, drafting a truthful page structure, generating raster concepts, and reviewing style consistency. Use for activity landing pages, pass/reward tracks, competitions, minigames, collections, co-op events, and task pages. Do not use for production Prefabs, sliced assets, interaction-state completion, or config implementation.
---

# MergeClient 活动 UI 概念图

为 mergeclient 生成竖屏活动页面概念效果图。当前能力是设计知识蒸馏与少样本参考生成，不是专属模型权重训练。

## 边界

- 交付概念效果图、版式说明、使用的参考图与生成提示词。
- 不把概念图描述成已接入客户端，也不承诺可直接切图或制作 Prefab。
- 不臆造玩法、奖励、价格、概率、倒计时或业务文案。缺失内容用明确占位符，或只在不影响方向时做已声明的视觉假设。
- 原截图只作内部风格参考；不要覆盖、删除或改写来源工作簿。

## 必读参考

1. 每次创作先读 [references/style-profile.md](references/style-profile.md)。
2. 按页面目的选型时读 [references/page-archetypes.md](references/page-archetypes.md)。
3. 出图后按 [references/quality-rubric.md](references/quality-rubric.md) 复审。
4. 只有维护或重建参考库时才读 [references/research-and-maintenance.md](references/research-and-maintenance.md)。

## 工作流

1. 从用户需求提取：活动目的、核心行为、页面类型、主题包装、必须出现的信息、目标尺寸和禁用内容。仅当缺失信息会改变页面结构或验收标准时提一个问题；否则声明合理假设继续。
2. 从 `page-archetypes.md` 选择一个主原型；不要把入口图、规则弹窗、领奖弹窗或礼包页当成主页面模板。
3. 运行参考检索，默认取 4 张、最多 6 张：

   ```bash
   python3 scripts/select_references.py --brief "<用户需求>" --limit 4
   ```

   查看脚本返回的每张图片；为它们标注角色，例如“结构参考”“配色参考”“组件参考”。不得盲目混合互相冲突的页面原型。
4. 先写一份紧凑的页面结构：顶部主题区、核心状态区、主要交互区、奖励/进度区、主 CTA。明确哪些文本是逐字要求，哪些是占位符。
5. 使用可用的图像生成能力生成 `ui-mockup` 类型的竖屏高保真概念图。将参考图明确标为风格或结构参考，不把它们当作编辑目标。提示词应包含：
   - mergeclient 的暖色、圆润、手绘卡通视觉语言；
   - 当前活动的独立主题色和主题插画；
   - 清晰的纵向信息层级、奶油色内容面板、粗描边与柔和投影；
   - 绿色或橙黄色主 CTA、红色圆形关闭按钮、深棕正文；
   - 保持竖屏安全边距，不生成设备外壳、水印、无关角色或无法解释的按钮；
   - 所有业务数值与文案使用用户提供的原文或显式占位符。
6. 方向尚不明确时先出 2 个明显不同的版式方向；需求足够具体时先出 1 张，再做一次单点迭代。每轮只改变一个主要问题，最多连续自改 2 轮。
7. 按质量量表评分。总分低于 80，或命中任一硬性失败项，不得宣称完成；修正后重新检查。

## 交付说明

交付时列出：最终图片路径、页面原型、使用的参考图、关键假设、未验证项，以及它仍属于概念阶段。项目要使用的最终图片应复制到工作区内，不能只留在临时目录或默认生成目录。
