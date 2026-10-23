# OTONova V1.0 — Windows & macOS

Windows와 macOS 배포본을 하나로 통합한 **OTONova V1.0**입니다.

[한국어](https://github.com/geujang/OTONova/blob/main/README.md) · [日本語](https://github.com/geujang/OTONova/blob/main/README.ja.md) · [English](https://github.com/geujang/OTONova/blob/main/README.en.md) · [简体中文](https://github.com/geujang/OTONova/blob/main/README.zh-CN.md)

## 다운로드 / Downloads

| 운영체제 / Platform | 파일 / File | 설치 / Installation |
|---|---|---|
| Windows x64 | `OTONova-V1.0-Setup.exe` | 실행 후 빈 폴더에 설치 / Run the installer |
| macOS Apple Silicon (arm64) | `OTONova-macOS-V1.0-arm64.dmg` | 앱을 Applications로 이동 / Drag the app into Applications |

Python과 영어·일본어·한국어 모델이 포함됩니다. / Python and the English, Japanese, and Korean models are bundled.

`SHA256SUMS.txt`는 두 설치 파일의 SHA-256을 포함합니다. / Contains SHA-256 checksums for both downloads.

## 지원 / Supported formats

- 일본어 / Japanese: CV, CVVC, VCV.
- 한국어 / Korean: CV, CVVC, CVC, VCV.
- 영어 / English: ARPAsing, CVVC (DELTA / Salem), VCCV (PaintedCz CORE).
- 한국어·일본어·영어·중국어 UI, 다크·라이트 모드 / Korean, Japanese, English and Chinese UI; dark/light themes.
- WFL 음소 정렬, 기존 oto.ini 에일리어스 보존, 규칙 기반 자동 원설 / WFL alignment, existing alias preservation and rule-based oto generation.
- 2단계 편집, 구간 재생, RMS 에너지, 15 kHz 스펙트로그램 / Two-stage editing, interval playback, RMS energy and spectrograms up to 15 kHz.

**중국어 음원 지원 예정 / Chinese voicebank support is planned.**

COC·CBNN·CMPX는 개발 소스에 추가되었습니다. 이 V1.0 설치 파일에는 아직 포함되지 않습니다. / COC, CBNN and CMPX have been added to the development source, but are not yet included in these V1.0 installers.

~~한국어 VCCV 추가 예정 / Planned Korean VCCV~~ — **리스트 미확인 / Reclist unverified** (원본 리스트 삭제 / original list deleted).

**Android·iOS 지원은 추가 예정입니다. 현재 모바일 버전은 제공하지 않습니다.** / **Android and iOS support is planned; mobile versions are not available yet.**

## Mac 검증과 제한 / Mac validation and limits

macOS 15 Apple Silicon에서 앱 빌드, 회귀 검사 67개(Windows 전용 2개 제외), 세 언어 모델 로딩·지정 음소열 정렬, GUI 시작·화면 캡처를 통과했습니다. DMG 마운트·전체 앱 파일 해시·심볼릭 링크·코드 서명 구조 검사도 통과했습니다.

The native Mac build passed 67 regression tests (2 Windows-only tests skipped), three-language model loading and constrained alignment, GUI startup and capture, plus DMG mounting, full app file hashes, symlinks and code-signature integrity checks.

Intel Mac은 미지원이며 Apple Developer ID 배포 서명·공증은 아직 적용하지 않았습니다. 실제 스피커 청음, 외장 드라이브 권한 변형, 긴 음원 작업은 별도 확인이 필요합니다. 이번 통합은 기존 검증된 바이너리를 재배포하며, Mac 앱 내부 빌드 버전은 1.0.1입니다.

Intel Macs are unsupported. Apple Developer ID distribution signing and notarization have not been applied. Physical speaker playback, external-drive permission variations and long recording sessions require separate validation. This unified release redistributes the previously validated binaries; the Mac app's internal build version remains 1.0.1.

[Mac app validation](https://github.com/geujang/OTONova/actions/runs/39790851377) · [DMG validation](https://github.com/geujang/OTONova/actions/runs/39794929691)

## 모델과 크레딧 / Models and credits

학습 상태 제거·동일 인코더 공유·무손실 압축으로 모델 관련 파일을 약 1.35 GB에서 약 254 MB로 줄였습니다. FP32 추론 가중치를 보존하며 양자화·FP16 변환·음소 삭제는 적용하지 않았습니다.

Model-related files were reduced from about 1.35 GB to 254 MB through training-state removal, identical encoder sharing and lossless compression. FP32 inference weights are preserved without quantization, FP16 conversion or phoneme removal.

WFL: [MLo7Ghinsan / Ghin_MLo7](https://github.com/MLo7Ghinsan/WFL-ASR), MIT. English model: [Superbox2147](https://github.com/Superbox2147). Japanese/Korean models: [Archivoice](https://github.com/Archivoice). Shared encoder: OpenAI Whisper base.

[지원 형식·리스트 / Formats and lists](https://github.com/geujang/OTONova/blob/main/SUPPORTED_FORMATS.md) · [용량 절감 / Compression](https://github.com/geujang/OTONova/blob/main/MODEL_COMPRESSION.md) · [전체 크레딧 / Full credits](https://github.com/geujang/OTONova/blob/main/CREDITS.md) · [소스 / Source](https://github.com/geujang/OTONova)
