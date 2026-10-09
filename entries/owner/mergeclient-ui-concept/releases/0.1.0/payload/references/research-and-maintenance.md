# 研究结论与参考库维护

## 首版采用的方案

首版使用“质量审计 + 去重 + 语义标签检索 + 少量参考图 + 图像生成 + 量表复审”。这是知识与工作流蒸馏，不训练专属模型权重。

选择原因：当前 43 类活动已经覆盖多个页面原型，但素材混有入口图、弹窗和礼包页。直接 LoRA 会把页面角色混在一起；先建立干净、可追溯的参考库更容易验证，也便于后续定位是检索、提示词还是模型控制的问题。

## 经过核实的方法来源

- OpenAI Skills：Skill 适合封装指令、参考资料和可选脚本，并采用渐进加载。<https://learn.chatgpt.com/docs/build-skills>
- OpenAI 图像生成：支持图片输入、生成、编辑和多轮迭代，但文字精确性、品牌一致性与复杂构图仍需复审。<https://developers.openai.com/api/docs/guides/image-generation>
- CleanVision：可审计模糊、亮度、尺寸、宽高比、低信息和重复等图像问题。<https://cleanvision.readthedocs.io/en/stable/tutorials/tutorial.html>
- FiftyOne 去重：成熟流程是文件哈希查完全重复，再用图像相似度聚类并保留代表图。<https://docs.voxel51.com/plugins/plugins_ecosystem/image_deduplication.html>
- OpenAI CLIP：图文共同表征可用于相关性检索。当前首版为避免新增大模型依赖，使用活动名、原型与标签检索；素材继续增长时可升级为 CLIP 向量索引。<https://github.com/openai/CLIP>
- IP-Adapter：轻量图片提示适配器，可与文字提示和可控生成工具组合。<https://github.com/tencent-ailab/IP-Adapter>
- ControlNet：通过边缘、深度、姿态等额外条件控制扩散模型结构。<https://github.com/lllyasviel/ControlNet>
- ComfyUI ControlNet：官方工作流支持草图/条件图、强度与生效区间控制，并可串联多个 ControlNet。<https://docs.comfy.org/tutorials/controlnet/controlnet>
- Hugging Face Diffusers LoRA：LoRA 只训练少量新增权重，较省显存和存储，但仍需要整理数据集、训练和推理维护。<https://huggingface.co/docs/diffusers/training/lora>

## 升级条件

1. **先升级检索**：参考库超过约 1000 张，或活动名/标签频繁找不到正确视觉邻居时，增加 CLIP 向量索引。
2. **再升级结构控制**：连续多个需求出现明显布局漂移，且提示词与参考图迭代仍无法稳定时，引入 ComfyUI + IP-Adapter + ControlNet。
3. **最后考虑 LoRA**：只有经过一组固定测试需求后，前两层仍无法达到风格一致性，且有足够干净、同一页面角色、授权明确的数据时才训练。

## 重建参考库

使用工作区依赖提供的 Python 与 Pillow：

```bash
python3 scripts/build_reference_library.py \
  --workbook /absolute/path/to/活动截图.xlsx \
  --skill-dir /absolute/path/to/mergeclient-ui-concept
```

脚本只读工作簿，按 SHA-256 查完全重复、按感知哈希标记近似重复，并对完整竖屏候选计算清晰度、亮度、信息量和遮罩风险。每类活动默认保留一张代表图，输出可审计清单。重建后必须查看 `assets/reference-contact-sheet.jpg`，人工确认没有把入口图、弹窗或明显压暗画面选为代表图。
