# OTONova V1.0

개발 배포본 v36을 **OTONova V1.0**으로 정리한 첫 공개 릴리스입니다.

- 일본어 CV / CVVC / VCV.
- 한국어 CV / CVVC / CVC / VCV, 리스트 세부 방식 자동 인식.
- 영어 ARPAsing / DELTA·Salem CVVC / PaintedCz CORE VCCV.
- WFL 모델 기반 경계 추정, 기존 oto.ini 에일리어스 유지, 규칙 기반 원설 생성.
- 음소 경계 / 원설 2단계 편집, 즉시 재계산, 실행 취소.
- 라벨 구간 우클릭 재생, RMS 에너지, 15kHz 스펙트로그램과 색상표 6종.
- 한국어·일본어·영어·중국어 UI, 다크 / 라이트 모드.
- 설치 화면의 바탕화면 바로가기 생성 옵션.
- FP32 가중치를 유지한 공통 인코더 공유 및 무손실 압축.

## 다운로드

`OTONova-V1.0-Setup.exe`를 실행해 비어 있는 새 폴더에 설치합니다. Windows x64용이며 Python과 모델이 포함됩니다. SHA-256은 같은 릴리스의 `SHA256SUMS.txt`로 확인할 수 있습니다.

**중국어 음원 지원은 앞으로 추가할 예정입니다.** 현재 중국어는 UI 표시 언어입니다.

[지원·리스트](SUPPORTED_FORMATS.md) · [모델 축약 설명](MODEL_COMPRESSION.md) · [원본 크레딧](CREDITS.md) · [제3자 자료](THIRD_PARTY_NOTICES.md)
