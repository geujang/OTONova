<p align="center"><img src="assets/otonova-logo.png" width="128" alt="OTONova 标志"></p>

# OTONova V2.0

**OTONova V2.0 现面向 Windows x64 和 macOS Apple Silicon 发布。** 新增第三阶段音源设置、ZIP 导出、日语罗马字识别、原音设定规则与编辑改进、频谱图设置。[V2.0 更新记录](RELEASE_NOTES.md)（韩语）。

[한국어](README.md) · [English](README.en.md) · [日本語](README.ja.md) · **简体中文**

**面向 UTAU 音源的 Windows／macOS 自动原音设定工具。** 根据文件名、录音表和现有 oto.ini 别名生成音素序列，使用 WFL 模型进行强制对齐，再按照预设规则生成原音设定参数。

[下载 Windows 安装程序](https://github.com/geujang/OTONova/releases/tag/v2.0.0) · [支持格式与参考录音表](SUPPORTED_FORMATS.md) · [模型体积优化方法](MODEL_COMPRESSION.md) · [原作者与鸣谢](CREDITS.md) · [V2.0 发行说明](RELEASE_NOTES.md)

链接中的技术文档目前使用韩语编写。

## 正式支持 macOS

提供 [macOS V2.0 Apple Silicon DMG](https://github.com/geujang/OTONova/releases/tag/v2.0.0)，包含与 Windows 相同的原音设定和音源设置功能。不支持 Intel Mac，尚未进行 Apple Developer ID 分发签名及公证。安装方法与验证范围见 [MACOS.md](MACOS.md)。

## 支持的音源语言与格式

| 音源语言 | 支持格式 |
|---|---|
| 日语 | CV（单独音）、CVVC、VCV（连续音） |
| 韩语 | CV（单独音）、CVVC、CVC、VCV、COC、CBNN、CMPX |
| 英语 | ARPAsing、CVVC（DELTA / Salem）、VCCV（PaintedCz CORE） |

通过文件名、录音表和现有别名识别具体录音方式。若已有 oto.ini，则按照原有别名生成时间参数。

**中文音源支持计划在未来加入。韩语 COC、CBNN、CMPX 已使用 CVVC 时间规则加入开发源码，已包含在 Windows 和 macOS V2.0 中。~~计划支持韩语 VCCV~~ — 录音表未确认（原表已删除）。** 目前中文仅作为界面语言提供。计划在未来支持 Android / iOS，当前发行目标为 Windows x64 与 macOS Apple Silicon。

## 主要功能

- 第三阶段读取并编辑现有 `character.txt`、`character.yaml` 和可选 `readme.txt`，设置音源信息及子音库。
- 导出包含最新 OTO 和可选 README 的音源 ZIP；排除对齐缓存、项目和临时文件，保留原始数据。
- 识别日语罗马字文件名与别名。
- VC 偏移位于前元音的 3/4，重叠位于偏移至先行发声的 1/4。固定位置早于先行发声时，调整到先行发声与截止的中点。
- 移动先行发声时，五个原音设定标记一起移动。偏移至固定区域使用 30% 不透明度蓝色覆盖。
- 频谱图上限频率可设置（默认 10,000Hz），默认火焰配色；上下拖动波形可缩放振幅显示。
- 自动识别 Windows 界面语言，新增分步 Setup 向导，保留管理员权限与已有安装替换确认。

- 保存和打开 `.otonova` 项目，直接恢复音素边界与原音设定参数，无需重新对齐。
- 恢复旧版标签缓存；在第二阶段显示现有 oto.ini 的别名与时间参数。
- 后台准备波形、能量及声谱图并复用缓存；WAV 或 OTO 在外部变更时询问是否重新加载。
- 在 WAV 列表中右键选择自动原音设定，只处理该文件，保留其他文件的边界与参数。
- 韩语子音后的半母音不再独立标注：`k y a → k a`、`s w a → s a`，保留原别名。
- 音素边界改为明亮的柔粉色，操作、设置和帮助菜单位于右上角。
- 帮助中提供更新检查、鸣谢及反馈。反馈发布至 Discord 论坛，内容与可选联系方式对拥有频道访问权限的服务器成员可见。

- 基于 WFL 模型估计音素边界，并按规则生成 oto.ini。
- 分两阶段编辑：第一阶段调整音素边界，第二阶段调整原音设定。修改边界后立即重新计算原音设定参数。
- 显示波形、RMS 能量及可设置上限频率的声谱图，提供六种配色。
- 右键点击两个标签之间可单独播放该区间。第一阶段使用音素标签，第二阶段使用原音设定标记。
- 拖动原音设定标记；按标记从左到右的顺序使用 1～5 键操作；Ctrl+Z 撤销。
- 韩语、日语、英语、中文界面，深色／浅色模式，以及按用户保存的设置。
- Windows 安装时可选择创建桌面快捷方式。

## 安装与使用

1. 从 [V2.0 发行页面](https://github.com/geujang/OTONova/releases/tag/v2.0.0) 下载并运行 `OTONova-V2.0-Setup.exe`，按向导选择位置和快捷方式。替换现有安装前需要确认。已包含 Python 和模型。
2. 启动 `OTONova.exe` 并选择音源文件夹，自动加载可视化数据、现有 OTO 及有效的旧标签缓存。现有 OTO 在第二阶段显示。
3. 需要重新估计时，点击右上角**操作 → 自动原音设定**，依次选择**语言 → 格式**并确认。在 WAV 列表右键可仅处理单个文件。
4. 在**第一阶段**编辑音素边界，在**第二阶段**编辑原音设定参数，项目保存两者。若要对旧缓存应用新的韩语半母音规则，请重新处理该 WAV。
5. 在**操作**菜单打开／保存项目和保存 oto.ini；原有 OTO 会备份。偏好设置位于**设置**，鸣谢位于**帮助**。

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

制作：**KURO**。反馈问题时，请在 [Issues](https://github.com/geujang/OTONova/issues) 中提供使用的语言与格式、复现步骤和错误详情。
