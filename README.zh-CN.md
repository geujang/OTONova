<p align="center"><img src="assets/otonova-logo.png" width="128" alt="OTONova 标志"></p>

# OTONova V1.0

[한국어](README.md) · [English](README.en.md) · [日本語](README.ja.md) · **简体中文**

**面向 UTAU 音源的 Windows／macOS 自动原音设定工具。** 根据文件名、录音表和现有 oto.ini 别名生成音素序列，使用 WFL 模型进行强制对齐，再按照预设规则生成原音设定参数。

[下载 Windows 安装程序](https://github.com/geujang/OTONova/releases/tag/v1.0.0) · [支持格式与参考录音表](SUPPORTED_FORMATS.md) · [模型体积优化方法](MODEL_COMPRESSION.md) · [原作者与鸣谢](CREDITS.md) · [V1.0 发行说明](RELEASE_NOTES.md)

链接中的技术文档目前使用韩语编写。

## 正式支持 macOS

提供适用于 Apple Silicon 的 [macOS 版本](https://github.com/geujang/OTONova/releases/tag/v1.0.0)。已在 Mac 环境中通过原生应用构建、三种语言模型的音素对齐和 GUI 启动检查。正式支持 Windows x64 与 macOS Apple Silicon。Windows 与 Mac 版本在同一个 V1.0 发行页面提供。不支持 Intel Mac。使用方法与验证范围见 [MACOS.md](MACOS.md)。目前尚未进行 Apple Developer ID 分发签名及公证。

## 支持的音源语言与格式

| 音源语言 | 支持格式 |
|---|---|
| 日语 | CV（单独音）、CVVC、VCV（连续音） |
| 韩语 | CV（单独音）、CVVC、CVC、VCV |
| 英语 | ARPAsing、CVVC（DELTA / Salem）、VCCV（PaintedCz CORE） |

通过文件名、录音表和现有别名识别具体录音方式。若已有 oto.ini，则按照原有别名生成时间参数。

**中文音源支持计划在未来加入。韩语 COC、CBNN、CMPX、VCCV 也属于计划功能，V1.0 暂不支持。** 目前中文仅作为界面语言提供。Android / iOS 应用尚处于考虑阶段，当前发行目标为 Windows x64 与 macOS Apple Silicon。

## 主要功能

- 基于 WFL 模型估计音素边界，并按规则生成 oto.ini。
- 分两阶段编辑：第一阶段调整音素边界，第二阶段调整原音设定。修改边界后立即重新计算原音设定参数。
- 显示波形、RMS 能量和最高 15 kHz 的声谱图，提供六种配色。
- 右键点击两个标签之间可单独播放该区间。第一阶段使用音素标签，第二阶段使用原音设定标记。
- 拖动原音设定标记；按标记从左到右的顺序使用 1～5 键操作；Ctrl+Z 撤销。
- 韩语、日语、英语、中文界面，深色／浅色模式，以及按用户保存的设置。
- Windows 安装时可选择创建桌面快捷方式。

## 安装与使用

1. 从 [Releases](https://github.com/geujang/OTONova/releases/tag/v1.0.0) 下载 `OTONova-V1.0-Setup.exe`。
2. 安装到一个新的空文件夹。已包含 Python 和模型，无需单独安装。可在安装界面选择是否创建桌面快捷方式。
3. 运行 `OTONova.exe`，选择音源文件夹、语言与录音格式，再执行音素边界估计／原音设定生成。
4. 在**第一阶段**检查音素边界，在**第二阶段**调整原音设定参数。
5. 音素边界修改保存到边界缓存，第二阶段的修改写入 oto.ini。每次编辑会话首次保存时会备份原有 oto.ini。

英语 VCCV 可识别 CORE 子文件夹中的 WAV 和 oto.ini。仅在没有现有 oto 时自动生成别名并去重。建议试听并检查自动估计的边界。首次分析可能因模型加载和分析代码初始化而耗时较长。

## 如何缩小模型体积？

移除训练状态、共享相同的 Whisper 编码器，并对检查点进行无损压缩。**没有进行量化、FP16 转换或删除音素，保留了 FP32 推理权重。** 模型相关文件总量从约 1.35 GB 降至共享后的约 304 MB，再降至无损压缩后的约 254 MB。Windows 版安装后包含运行环境的文件总量约为 804 MB；实际磁盘占用随文件系统分配单元而变化。详细步骤与验证范围见 [MODEL_COMPRESSION.md](MODEL_COMPRESSION.md)。

## 从源码运行与构建

请参阅 [DEVELOPMENT.md](DEVELOPMENT.md)。本仓库包含代码、配置、音素表和录音表识别目录；模型权重与打包运行环境通过 Releases 安装程序提供。公开仓库不包含用户录音、训练数据、个人电脑路径或包含旧版大型模型的开发 Git 历史。

## 鸣谢

- WFL 原作者：[MLo7Ghinsan / Ghin_MLo7 — WFL-ASR](https://github.com/MLo7Ghinsan/WFL-ASR)，MIT。
- 英语模型：[Superbox2147](https://github.com/Superbox2147)。
- 日语、韩语模型：[Archivoice](https://github.com/Archivoice)。
- 共享编码器：[OpenAI Whisper base](https://huggingface.co/openai/whisper-base)。
- 训练数据集、录音表作者、音素对应表及原始使用条款：[CREDITS.md](CREDITS.md)、[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

制作：**KURO / geujang**。反馈问题时，请在 [Issues](https://github.com/geujang/OTONova/issues) 中提供使用的语言与格式、复现步骤和错误详情。
