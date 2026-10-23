<p align="center"><img src="assets/otonova-logo.png" width="128" alt="OTONova logo"></p>

# OTONova V1.5

**Windows V1.5를 배포합니다.** 프로젝트 저장·캐시 복원·기존 OTO 표시·파일별 자동원설·한국어 COC/CBNN/CMPX·Discord 포럼 피드백이 추가되었습니다. [V1.5 변경 내역](RELEASE_NOTES.md). macOS DMG는 기존 V1.0입니다.

**한국어** · [English](README.en.md) · [日本語](README.ja.md) · [简体中文](README.zh-CN.md)

**UTAU 음원을 위한 Windows·macOS 자동 원설기.** 파일명·녹음 리스트·기존 oto.ini에서 음소열을 만들고, WFL 모델로 경계를 강제 정렬한 뒤 지정 규칙으로 원설을 생성합니다.

[설치 파일 다운로드](https://github.com/geujang/OTONova/releases/tag/v1.5.0) · [지원 형식·참고 리스트](SUPPORTED_FORMATS.md) · [모델 용량 절감 방식](MODEL_COMPRESSION.md) · [원본 크레딧](CREDITS.md) · [V1.5 릴리스 노트](RELEASE_NOTES.md)

## macOS 정식 지원

Apple Silicon용 [macOS 다운로드](https://github.com/geujang/OTONova/releases/tag/v1.0.0)를 제공합니다. Mac 환경에서 앱 빌드·세 언어 모델 정렬·GUI 시작 검사를 통과했습니다. Windows x64와 macOS Apple Silicon을 정식 지원합니다. Windows와 Mac 배포본은 하나의 V1.0 릴리스에서 제공합니다. Intel Mac은 지원하지 않습니다. 실행법과 검증 범위는 [MACOS.md](MACOS.md)를 참고하세요.

## 지원 언어와 형식

| 음원 언어 | 지원 형식 |
|---|---|
| 일본어 | CV(단독음), CVVC, VCV |
| 한국어 | CV(단독음), CVVC, CVC, VCV |
| 영어 | ARPAsing, CVVC(DELTA / Salem), VCCV(PaintedCz CORE) |

세부 녹음 방식은 파일명·녹음 리스트·기존 에일리어스에서 인식합니다. 기존 oto.ini가 있으면 해당 에일리어스를 기준으로 시간 값을 설정합니다. **중국어 음원 지원은 향후 추가할 예정입니다. COC·CBNN·CMPX는 개발 소스에 추가되었으며 기존 CVVC 규칙으로 처리합니다. Windows V1.5 설치 파일에 포함됩니다. ~~한국어 VCCV 추가 예정~~ — 리스트 미확인(원본 리스트 삭제).** 현재 중국어는 UI 표시 언어로만 제공됩니다. Android / iOS 지원은 추가 예정이며 현재 배포 대상은 Windows x64와 macOS Apple Silicon입니다.

## 주요 기능

- WFL 모델 기반 음소 경계 추정과 규칙 기반 oto.ini 생성.
- 1단계 음소 경계 편집 / 2단계 원설 조정. 음소 경계 수정 시 원설 즉시 재계산.
- 파형·RMS 에너지·최대 15kHz 스펙트로그램. 색상표 6종.
- 라벨 사이 우클릭으로 해당 구간만 재생. 1단계는 음소 라벨, 2단계는 원설 라벨 기준.
- 원설 라벨 드래그, 왼쪽부터 1~5 키 조정, Ctrl+Z 되돌리기.
- 한국어·일본어·영어·중국어 UI, 다크 / 라이트 모드, 사용자별 설정 저장.
- 설치 시 바탕화면 바로가기 생성 옵션.

## 설치 및 사용

1. [Releases](https://github.com/geujang/OTONova/releases/tag/v1.0.0)에서 `OTONova-V1.0-Setup.exe`를 내려받습니다.
2. 비어 있는 새 폴더에 설치합니다. Python과 모델이 포함되어 별도 설치 없이 실행할 수 있습니다. 설치 화면에서 바탕화면 바로가기 생성 여부를 선택할 수 있습니다.
3. `OTONova.exe` 실행 → 음원 폴더 → 언어와 녹음 형식 → **음소 경계 추정 / 원설 생성**을 선택합니다.
4. **1단계**에서 음소 경계를 검토하고, **2단계**에서 원설 값을 조정합니다.
5. 음소 수정은 경계 캐시에 저장되며, 2단계 원설 수정은 oto.ini에 반영됩니다. 편집 세션 첫 저장 시 기존 oto.ini를 백업합니다.

영어 VCCV는 CORE 하위 폴더의 WAV·oto.ini를 인식합니다. 기존 oto가 없을 때만 에일리어스를 자동 생성하고 중복을 제거합니다. 자동 추정 결과는 청음과 경계 검토를 권장합니다. 첫 분석은 모델 로딩과 분석 코드 준비로 시간이 걸릴 수 있습니다.

## 모델 용량은 어떻게 줄였나요?

학습 상태 제거, 동일한 Whisper 인코더 공유, 체크포인트 무손실 압축을 적용했습니다. **양자화·FP16 변환·음소 삭제를 적용하지 않았으며 FP32 추론 가중치를 보존합니다.** 모델 관련 파일 합계는 기존 약 1.35GB에서 공유화 후 약 304MB, 추가 무손실 압축 후 약 254MB로 줄었습니다. 런타임까지 포함한 설치 후 파일 합계는 약 804MB이며 디스크 할당 단위에 따라 실제 차지하는 공간은 달라집니다. 자세한 단계와 검증 범위는 [MODEL_COMPRESSION.md](MODEL_COMPRESSION.md)에 정리했습니다.

## 소스 실행과 빌드

[DEVELOPMENT.md](DEVELOPMENT.md)를 참고하세요. 이 Git 저장소에는 코드·설정·음소표·리스트 식별 카탈로그를 올리고, 모델 가중치와 번들 런타임은 Releases 설치 파일로 제공합니다. 사용자 음원, 학습 데이터, 개인 PC 경로, 과거 대형 모델을 포함한 개발 Git 기록은 공개 저장소에 포함하지 않습니다.

## 크레딧

- WFL 원본: [MLo7Ghinsan / Ghin_MLo7 — WFL-ASR](https://github.com/MLo7Ghinsan/WFL-ASR), MIT.
- 영어 모델: [Superbox2147](https://github.com/Superbox2147).
- 일본어·한국어 모델: [Archivoice](https://github.com/Archivoice).
- 공통 인코더: [OpenAI Whisper base](https://huggingface.co/openai/whisper-base).
- 학습 데이터셋, 녹음 리스트 제작자, 음소 대응표와 원문 이용 조건: [CREDITS.md](CREDITS.md), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

제작: **KURO / geujang**. 오류 제보 시 사용한 언어·형식, 재현 방법과 오류 내용을 [Issues](https://github.com/geujang/OTONova/issues)에 남겨주세요.
