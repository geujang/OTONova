<p align="center"><img src="assets/otonova-logo.png" width="128" alt="OTONova logo"></p>

# OTONova V1.0

[한국어](README.md) · **English** · [日本語](README.ja.md) · [简体中文](README.zh-CN.md)

**An automatic oto.ini configuration tool for UTAU voicebanks on Windows and macOS.** OTONova derives phoneme sequences from filenames, recording lists, and existing oto.ini aliases, uses WFL models for forced alignment, and generates timing values with predefined rules.

[Download Windows installer](https://github.com/geujang/OTONova/releases/tag/v1.0.0) · [Supported formats and reference lists](SUPPORTED_FORMATS.md) · [Model size reduction](MODEL_COMPRESSION.md) · [Original credits](CREDITS.md) · [V1.0 release notes](RELEASE_NOTES.md)

The linked technical documents are currently in Korean.

## Official macOS support

A [macOS build for Apple Silicon](https://github.com/geujang/OTONova/releases/tag/v1.0.1-macos-preview) is available. Native app builds, alignment with the three language models, and GUI startup checks passed on Mac. Windows x64 and macOS Apple Silicon are officially supported. The Mac release is V1.0.1. Intel Macs are unsupported. See [MACOS.md](MACOS.md) for instructions and validation limits. Apple Developer ID distribution signing and notarization have not been applied.

## Supported voicebank languages and formats

| Language | Formats |
|---|---|
| Japanese | CV, CVVC, VCV |
| Korean | CV, CVVC, CVC, VCV |
| English | ARPAsing, CVVC (DELTA / Salem), VCCV (PaintedCz CORE) |

Recording conventions are detected from filenames, recording lists, and existing aliases. When an oto.ini exists, timing values are configured using its aliases.

**Chinese voicebank support is planned. Korean COC, CBNN, CMPX, and VCCV are also planned and are not supported in V1.0.** Chinese is currently available only as a UI language. Android and iOS apps are under consideration; current distributions target Windows x64 and macOS Apple Silicon.

## Features

- WFL phoneme alignment and rule-based oto.ini generation.
- Two editing stages: phoneme boundaries first, oto timings second. Boundary edits immediately recalculate oto timings.
- Waveform, RMS energy, and spectrogram up to 15 kHz, with six color palettes.
- Right-click between labels to play that interval: phoneme labels in stage 1, oto markers in stage 2.
- Drag oto markers, use keys 1–5 in left-to-right marker order, and undo with Ctrl+Z.
- Korean, Japanese, English, and Chinese UI; dark/light themes; per-user settings.
- Optional desktop shortcut during Windows installation.

## Installation and use

1. Download `OTONova-V1.0-Setup.exe` from [Releases](https://github.com/geujang/OTONova/releases/tag/v1.0.0).
2. Install into a new, empty folder. Python and models are bundled; no separate installation is required. Choose whether to create a desktop shortcut.
3. Launch `OTONova.exe`, select the voicebank folder, language, and recording format, then select phoneme alignment / oto generation.
4. Review phoneme boundaries in **stage 1**, then adjust oto timings in **stage 2**.
5. Boundary edits are stored in the boundary cache; stage 2 timing edits are written to oto.ini. The existing oto.ini is backed up on the first save of an editing session.

English VCCV recognizes WAV files and oto.ini in CORE subfolders. Aliases are generated and deduplicated only when no existing oto is available. Listen to the recordings and review automatic boundaries. The first analysis can take longer while models and analysis code initialize.

## How were the models made smaller?

Training state was removed, identical Whisper encoders were shared, and checkpoints were compressed losslessly. **No quantization, FP16 conversion, or phoneme removal was applied; FP32 inference weights are preserved.** Model-related files went from about 1.35 GB to 304 MB after encoder sharing, then to 254 MB after lossless compression. The installed Windows files, including the runtime, total about 804 MB; allocated disk space varies with filesystem allocation units. See [MODEL_COMPRESSION.md](MODEL_COMPRESSION.md) for the process and validation scope.

## Running and building from source

See [DEVELOPMENT.md](DEVELOPMENT.md). This repository contains code, configuration, phoneme inventories, and recording-list identification catalogs. Model weights and bundled runtimes are provided through release installers. User recordings, training datasets, private PC paths, and development Git history containing older large models are excluded from the public repository.

## Credits

- Original WFL: [MLo7Ghinsan / Ghin_MLo7 — WFL-ASR](https://github.com/MLo7Ghinsan/WFL-ASR), MIT.
- English model: [Superbox2147](https://github.com/Superbox2147).
- Japanese and Korean models: [Archivoice](https://github.com/Archivoice).
- Shared encoder: [OpenAI Whisper base](https://huggingface.co/openai/whisper-base).
- Training datasets, recording-list authors, phoneme conversion references, and original terms: [CREDITS.md](CREDITS.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Created by **KURO / geujang**. Please report bugs in [Issues](https://github.com/geujang/OTONova/issues), including the language, recording format, reproduction steps, and error details.
