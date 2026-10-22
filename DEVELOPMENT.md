# 소스 실행과 빌드

## 가장 빠른 실행

Windows x64의 Python 3.11 또는 호환 환경을 사용합니다. Git 소스에는 모델 가중치와 런타임이 포함되지 않습니다. V1.0 설치 파일을 새 폴더에 풀고, 해당 폴더의 `runtime/python.exe -B -s vcv_gui.py`로 번들 소스를 실행할 수 있습니다.

Git 소스를 수정해서 실행하려면 설치 폴더를 복사한 작업 디렉터리에 이 저장소의 Python 파일·assets·tools·WFL 추론 소스를 덮어씌우고 번들 Python으로 실행하세요. 설치 폴더의 `English/last.ckpt`, `Japanese/last.ckpt`, `WFL/Archivoice/korean/last.ckpt`, `WFL/encoder/encoder.pt` 및 모델별 설정 파일을 함께 유지해야 합니다.

새 가상 환경에서는 `requirements.txt`의 의존성이 필요합니다. 기존 `requirements-lock.txt`는 초기 GUI 환경의 기록이며 WFL 백엔드 전체를 설치하는 최신 잠금 파일로 사용하지 않습니다. 학습 모델 원본을 별도로 받을 때는 `config.yaml`, `phonemes.txt`, 언어 매핑과 체크포인트를 짝지어야 합니다.

## 빌드 도구

- `build_distribution.py --version 1.0`: `release/OTONova-Windows-V1.0`을 검사하고 `OTONova-V1.0-Setup.exe`를 만듭니다. .NET Framework C# 컴파일러와 원본 번들 런타임이 필요합니다.
- `build_otonova.py`: 검증된 기존 v36 런타임을 복사하고 최신 소스를 덮어 V1.0을 구성하는 개발용 이관 도구입니다. 깨끗한 Git clone에는 과거 런타임이 없으므로 바로 실행할 수 없습니다. 새 릴리스에서는 설치 배포본을 기준 런타임으로 준비하세요.
- `slim_models.py`, `build_compact_runtime.py`, `build_extra_compact.py`: 모델·런타임 축약 과정을 보존한 이력 도구입니다. 과거 원본과 백업 태그를 전제로 하므로 현재 파일에 재실행하지 않습니다.

## 테스트

```powershell
python -B -m unittest test_audio_review test_audio_playback test_ui_settings test_stages test_detection test_english_vccv test_english_cvvc test_arpasing test_formats test_korean test_installer_shortcut
```

`test_stages`와 `test_audio_review`는 QtTest가 있는 개발용 PySide6를 사용합니다. 일부 통합 검증은 원본 음원 및 모델을 필요로 하며 이 저장소에는 해당 음원을 포함하지 않습니다. 무손실 축약 당시 기록은 `validation/`에서 확인할 수 있습니다.

## 저장소 범위

개발 PC의 Git 기록 대신 소스만 추려 새 이력으로 공개합니다. 모델 가중치·음원·학습용 JSON·로그·인증 정보·개인 PC 경로는 업로드하지 않습니다. 모델 및 런타임은 Git의 대형 파일로 올리지 않고 Releases에 포함합니다.
