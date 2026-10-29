# 本地AI版技术验收记录

日期：2026年10月29日。状态：开发者技术检查已进行，用户体验和真实商户效果待验收。

## 已实际执行

- `run_benchmark.py`：47项通过，包含原30项和新增商品绑定、多帧冲突、弃权、异常分数、路径、字幕边界；合成输入，不能称47条真实视频。
- `verify_local_pipeline.py`：实际加载量化Chinese-CLIP，分析4个模拟镜头，候选均待确认；3个镜头弃权。随后测试代码显式恢复模拟真值，生成到店与引流样片，绝不是模型自动标对4段。
- 到店片：9.533042秒，720×1280，音轨存在，本次命令行渲染4.594秒。
- 引流片：8.7585秒，720×1280，音轨存在，渲染3.624秒。
- 字幕短句均在实测语音和段落范围内；不使用tpad长停帧，语速在1—1.18范围。
- 实测旁白4.8秒/素材1秒时拒绝；模拟促销旁白7.8秒/素材6秒时拒绝。促销拒绝记录在promo-duration-check.json。
- 两张CC0静态照片推理冒烟：coffee得到商品候选；chelsea猫图弃权。每张重复3次只验证推理能运行，不能当成真实三时刻视频识别评估。来源和作者保存在public-test-images/sources.json。
- 通过网页点击本地AI分析；全部标签变为未确认；直接编排时显示补拍/确认，生成按钮禁用。人工复核标签和商品后生成到店片。
- 网页任务b90523a8fd90464e87f9e9700f69245f：9.533042秒，渲染约3.5秒，播放器readyState=4，currentTime从0.109207前进至9.533042且ended=true；不是只看播放器出现。
- 真实文件选择器上传模拟source.mp4成功；退出模拟事实卡，店名等清空；新镜头未确认，本地分析后保持待判断。这个上传仍是技术素材，不是真实商户样本。
- 49个原项目文件的SHA256、大小、mtime核对无变化：source-integrity-local-ai.json。

## 环境与复现

本机Windows，i9-14900HX、32GB内存；本轮使用CPU推理，未测试GPU加速。

ONNX Runtime 1.23.2，tokenizers 0.22.1；完整版本在requirements-local-lock.txt。模型来源Xenova/chinese-clip-vit-base-patch16，提交f26904860903e70e050b8f48255e5f48401816e9，权重190842404字节，SHA256 a2c2849329eafb24100acec5a9421a39f8cb445296444c5c98855b69e5e7a751。下载脚本分块复用，校验完整SHA后才使用，无远程代码执行。

模型卡声明转换自[原Chinese-CLIP](https://huggingface.co/OFA-Sys/chinese-clip-vit-base-patch16)，[转换模型卡](https://huggingface.co/Xenova/chinese-clip-vit-base-patch16)给出图文分类用法；原代码许可[MIT-LICENSE.txt](https://github.com/OFA-Sys/Chinese-CLIP/blob/master/MIT-LICENSE.txt)。转换仓库未单列许可，模型不入Git；对外分发权重前须单独核对，不由原代码许可推定所有训练数据与权重许可。

## 未通过、未做或不能外推

- 模拟绘图3/4弃权，表示当前用途模型对这些素材没有稳定判断；未调整阈值强行通过。
- 图文相似度不是自由视觉推理，更不能证明确切商品、店名、地址、价格或优惠。阈值1.5未经真实店铺校准；三帧不能覆盖整段所有瞬间。
- 当前只能单个商品事实绑定，无法自动发现用户作出的错误确认。研究要独立标注评估假阳性和人工负担。
- 旁白过长会失败；并未实现自动把长优惠文案分配到多个商品镜头。不得声称三种目标所有输入均能成片。
- 用户真人听看、自然度、手机/跨电脑、浏览器下载以及真实商户发布意愿均未完成验收。文件输出与HTTP检查不能替代这些验收。
- 本轮生成无付费模型API；未计量电力、设备、人工成本。没有成功云端视觉推理。

## 证据

constraint-results.json、local-model-lock.json、local-vision-smoke.json、local-pipeline-results.json、promo-duration-check.json、public-test-images/model-results.json、ui-local-ai-preview.png、browser-local-acceptance.json。媒体文件在data/和交付/本地AI技术验证/，未入Git。
