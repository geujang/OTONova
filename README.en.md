<p align="center"><img src="assets/otonova-logo.png" width="128" alt="OTONova logo"></p>

# OTONova V2.0

**OTONova V2.0 is available for Windows x64 and macOS Apple Silicon.** Adds stage-three singer settings and ZIP export, Japanese romaji recognition, timing and editing improvements, and configurable spectrograms. See [V2.0 release notes](RELEASE_NOTES.md) (Korean).

[한국어](README.md) · **English** · [日本語](README.ja.md) · [简体中文](README.zh-CN.md)

**An automatic oto.ini configuration tool for UTAU voicebanks on Windows and macOS.** OTONova derives phoneme sequences from filenames, recording lists, and existing oto.ini aliases, uses WFL models for forced alignment, and generates timing values with predefined rules.

[Download Windows installer](https://github.com/geujang/OTONova/releases/tag/v2.0.0) · [Supported formats and reference lists](SUPPORTED_FORMATS.md) · [Model size reduction](MODEL_COMPRESSION.md) · [Original credits](CREDITS.md) · [V2.0 release notes](RELEASE_NOTES.md)

The linked technical documents are currently in Korean.

## Official macOS support

Download the [macOS V2.0 Apple Silicon DMG](https://github.com/geujang/OTONova/releases/tag/v2.0.0). It includes the same timing and singer-settings features as Windows. Intel Macs are unsupported. Apple Developer ID distribution signing and notarization have not been applied. See [MACOS.md](MACOS.md) for installation and validation limits.

## Supported voicebank languages and formats

| Language | Formats |
|---|---|
| Japanese | CV, CVVC, VCV, VCV & CVVC |
| Korean | CV, CVVC, CVC, VCV, COC, CBNN, CMPX |
| English | ARPAsing, CVVC (DELTA / Salem), VCCV (PaintedCz CORE) |

Recording conventions are detected from filenames, recording lists, and existing aliases. When an oto.ini exists, timing values are configured using its aliases.

**Chinese voicebank support is planned. Korean COC, CBNN and CMPX have been added to the development source using the CVVC timing rules; they are included in Windows and macOS V2.0. ~~Planned Korean VCCV~~ — reclist unverified (original list deleted).** Chinese is currently available only as a UI language. Android and iOS support is planned; current distributions target Windows x64 and macOS Apple Silicon.

## Features

- Stage 3 loads and edits existing `character.txt`, `character.yaml`, and optional `readme.txt`, including singer details and subbanks.
- Export a voicebank ZIP with current OTO and optional README. Alignment caches, projects, and temporary files are omitted; source files are preserved.
- Japanese romaji filenames and aliases are recognized.
- VC offset is 3/4 through the preceding vowel; overlap is 1/4 from offset to preutterance. Fixed timing before preutterance is moved to the midpoint between preutterance and cutoff.
- Moving preutterance moves all five oto markers together. Offset-to-fixed shading uses blue at 30% opacity.
- Configurable spectrogram ceiling (10,000 Hz default), fire palette default, and vertical waveform dragging to adjust displayed amplitude.
- Automatic Windows UI language selection and a step-by-step Setup wizard with administrator elevation and confirmed replacement of an existing installation.

- Save and open `.otonova` projects to restore boundaries and oto timings without running alignment again.
- Restore legacy label caches. Existing `oto.ini` aliases and timing values open in stage 2.
- Prepare waveform, energy and spectrogram data in the background and reuse cached data. Confirm reloads when WAV or OTO files change externally.
- Right-click a WAV in the file list → automatic oto generation to process only that file while preserving the others.
- Korean post-consonant glides no longer receive separate labels: `k y a → k a`, `s w a → s a`; alias spellings are retained.
- Bright pastel pink phoneme boundaries; Actions, Settings and Help menus at the top right.
- Help includes update checking, credits and feedback. Feedback is posted to a Discord forum; messages and optional contact details are visible to server members with channel access.

- WFL phoneme alignment and rule-based oto.ini generation.
- Three stages: phoneme boundaries, oto timings, then singer settings and ZIP export. Boundary edits immediately recalculate oto timings.
- Waveform, RMS energy, and spectrogram with a configurable frequency ceiling and six color palettes.
- Right-click between labels to play that interval: phoneme labels in stage 1, oto markers in stage 2.
- Drag oto markers, use keys 1–5 in left-to-right marker order, and undo with Ctrl+Z.
- Korean, Japanese, English, and Chinese UI; dark/light themes; per-user settings.
- Optional desktop shortcut during Windows installation.

## Installation and use

1. Download `OTONova-V2.0-Setup.exe` from the [V2.0 release](https://github.com/geujang/OTONova/releases/tag/v2.0.0). Follow the wizard to choose the location and shortcut option. Replacement of an existing installation requires confirmation. Python and models are bundled.
2. Launch `OTONova.exe` and select the voicebank folder. Visual data, existing OTO entries and valid label caches load automatically. Existing OTO entries open in stage 2.
3. For new alignment, select **Actions → automatic oto generation**, then choose **language → format** and confirm. Right-click a WAV in the file list to process just that file.
4. Edit phoneme boundaries in **stage 1** and oto timings in **stage 2**. Projects retain both. To apply the new Korean glide rule to an old cache, run automatic oto generation again for that WAV.
5. Open/save projects and save `oto.ini` from **Actions**; existing OTO files are backed up. Preferences are in **Settings**, and credits are in **Help**.

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

Created by **KURO**. Please report bugs in [Issues](https://github.com/geujang/OTONova/issues), including the language, recording format, reproduction steps, and error details.
