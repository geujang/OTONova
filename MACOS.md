# macOS 정식 지원

**macOS Apple Silicon(arm64)을 정식 지원합니다.** Windows 설치 파일을 Mac에서 실행하는 방식이 아니라, 동일한 모델과 소스를 Mac용 Python / PyTorch / Qt로 묶습니다. Intel Mac은 지원하지 않습니다.

## 다운로드와 검증 상태

[OTONova V2.0 — Windows & macOS](https://github.com/geujang/OTONova/releases/tag/v2.0.0)에서 DMG를 내려받아 열고 `OTONova.app`을 옆의 Applications 폴더로 끌어 옮겨 사용합니다. Mac 다운로드 파일은 `OTONova-macOS-V2.0-arm64.dmg`입니다. Python과 모델이 앱에 포함됩니다.

macOS 15 Apple Silicon CI에서 회귀 검사, 소스 및 frozen 앱의 영어·일본어·한국어 정렬, GUI 시작·화면 캡처와 DMG 검증을 수행합니다. 현재 릴리스의 검증 실행은 [GitHub Actions](https://github.com/geujang/OTONova/actions/workflows/macos.yml)에서 확인할 수 있습니다.

Apple Developer ID 배포 서명·공증은 적용하지 않았습니다. 실제 Mac의 스피커 청음, 다양한 외장 드라이브 권한, 긴 음원 작업은 별도 사용자 검증이 필요합니다. Intel Mac은 미지원입니다.

## 소스 실행

Python 3.11이 설치된 Mac에서 저장소를 내려받고 다음을 실행합니다.

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-macos.txt
python prepare_macos_models.py
python -B mac_entry.py
```

`prepare_macos_models.py`는 공개 Windows V1.0 설치 파일의 고정 SHA-256과 내부 페이로드 해시를 확인하고, 운영체제에 독립적인 네 개의 모델 파일만 추출합니다. Windows 프로그램이나 런타임을 실행하지 않습니다. 기존 모델이 다른 경우 덮어쓰지 않고 중단합니다. 이미 받은 설치 파일은 `--installer /path/to/OTONova-V1.0-Setup.exe`로 지정할 수 있습니다.

## .app 빌드

```sh
source .venv/bin/activate
python build_macos.py
```

`dist/OTONova.app`과 CPU 종류가 표시된 ZIP 및 DMG를 만듭니다. DMG는 읽기 전용으로 마운트하여 앱의 모든 파일 해시·심볼릭 링크와 코드 서명을 검증합니다. Mac용 빌드는 Mac에서 수행해야 합니다. 서명 인증서가 준비되어 있다면 `OTONOVA_CODESIGN_IDENTITY` 환경 변수로 PyInstaller에 전달할 수 있습니다. 현재 배포본에는 Apple Developer ID 배포 서명·공증을 적용하지 않았습니다.

## 검증

```sh
QT_QPA_PLATFORM=offscreen python -B -m unittest test_platform_support test_audio_review test_audio_playback test_ui_settings test_stages test_detection test_english_vccv test_english_cvvc test_arpasing test_formats test_korean test_installer_shortcut
python smoke_macos.py
python smoke_macos.py --app dist/OTONova.app
QT_QPA_PLATFORM=offscreen dist/OTONova.app/Contents/MacOS/OTONova --ui-check
```

모델 smoke test는 합성 신호에서 영어·일본어·한국어 모델 로드 및 지정 음소열 정렬의 실행 여부를 검사합니다. 실제 음원의 정확도 평가가 아닙니다. CI 성공과 별도로 실제 Mac의 스피커 출력, 파일 선택·권한, Retina 화면, 긴 음원 처리 및 Finder 실행을 확인해야 합니다.

## 플랫폼 처리

- Mac 기본 오디오 백엔드를 사용하며 Windows Media Foundation을 강제하지 않습니다.
- 한국어·일본어·중국어 UI에는 Mac 시스템 글꼴을 사용합니다.
- 로그: `~/Library/Logs/OTONova/`. 모델과 앱 번들을 수정하지 않습니다.
- frozen `.app`은 같은 실행 파일을 `--wfl-backend` 모드로 실행해 Python 설치 없이 추론합니다.
- 모델 가중치와 원설 규칙은 Windows와 공유합니다. CPU 추론부터 검증하며 MPS 가속은 적용하지 않습니다.

## 배포 식별자

Windows와 macOS를 `v2.0.0`의 OTONova V2.0 릴리스로 함께 제공합니다. Mac 앱 내부 버전은 2.0.0입니다. 과거 V1.0 모델 추출 경로는 검증된 동일 가중치를 가져오기 위한 빌드 입력이며 V2.0 앱의 버전과는 별개입니다.
