# OTONova V1.5

Windows x64 설치 파일과 업데이트된 소스코드를 배포합니다. macOS 배포본은 기존 [V1.0 릴리스](https://github.com/geujang/OTONova/releases/tag/v1.0.0)의 Apple Silicon DMG를 이용해주세요. 이 릴리스에는 새 macOS 빌드가 포함되지 않습니다.

## V1.0 이후 변경 사항

- 프로젝트 파일(`.otonova`) 생성·저장·복원: 추정한 경계를 보존하며 프로젝트를 다시 열 때 재추정하지 않습니다.
- WAV 시각자료(파형·15 kHz 스펙트로그램·RMS 에너지)를 백그라운드에서 준비하고 디스크·메모리 캐시로 재사용합니다.
- 프로젝트 파일이 없는 구버전의 `auto-*/labels` 라벨 캐시도 읽어 바로 경계를 표시합니다. WAV 해시가 맞지 않는 캐시는 제외합니다.
- 기존 `oto.ini`의 에일리어스와 시간값을 읽고 2단계 원설 화면에 표시합니다. 현재 OTO를 과거 자동원설 보고서보다 우선합니다.
- WAV 또는 OTO의 외부 변경을 감지해 다시 로드할지 확인합니다. 취소하면 현재 표시를 유지합니다.
- WAV 목록 우클릭 → 자동원설: 해당 WAV만 처리하고 다른 파일의 경계·원설값을 유지합니다. 실패하면 해당 파일의 기존 원설값도 유지합니다.
- 자동원설을 누르면 언어권(한국어·일본어·영어)을 먼저 고르고 해당 언어의 형식을 선택합니다. 언어권을 고르기 전에는 형식을 선택할 수 없습니다.
- 상단 버튼을 오른쪽 상단의 작업·설정·도움말 메뉴로 정리했습니다. 크레딧은 도움말에서 볼 수 있습니다.
- 도움말에 업데이트 확인·GitHub 링크·버전 정보·피드백을 추가했습니다.
- 피드백은 Cloudflare Worker를 통해 Discord 피드백 포럼에 게시됩니다. 분류별 제목과 대응 태그를 적용합니다. 작성 내용·선택 연락처·분류·버전을 채널 접근 권한이 있는 서버 멤버가 볼 수 있으며 음원·OTO·로그는 전송하지 않습니다. 실패한 내용은 PC에 보관됩니다.
- 한국어 COC·CBNN·CMPX 형식을 추가했습니다.
- 한국어 자음 뒤 반모음의 독립 라벨을 제거했습니다: `캬: k y a → k a`, `솨: s w a → s a`. 원래 에일리어스 표기는 유지합니다. 기존 캐시에 적용하려면 해당 WAV의 자동원설을 다시 실행해주세요.
- 음소 경계 점선을 밝은 파스텔 분홍색으로 변경했습니다. 2단계에서는 흐리게 표시하고 OTO 선보다 뒤에 그립니다.
- Windows 작업 표시줄과 실행 파일의 OTONova 아이콘 표시를 보완했습니다.

## 지원 형식

- 일본어: CV, CVVC, VCV.
- 한국어: CV, CVVC, CVC, VCV, COC, CBNN, CMPX.
- 영어: ARPAsing, CVVC(DELTA·Salem), VCCV(PaintedCz CORE).
- UI: 한국어·일본어·영어·중국어, 다크·라이트 모드.

중국어 음원 및 Android·iOS 지원은 예정입니다. ~~한국어 VCCV~~ — 리스트 미확인(원본 리스트 삭제).

## 다운로드

`OTONova-V1.5-Setup.exe`를 실행해 새 폴더에 설치하세요. 실행 중인 이전 버전은 먼저 종료해주세요. `OTONova-V1.5-SHA256SUMS.txt`로 설치 파일의 SHA-256을 확인할 수 있습니다.

모델·데이터셋 원본 크레딧: [CREDITS.md](https://github.com/geujang/OTONova/blob/v1.5.0/CREDITS.md). 모델 용량 절감 방식: [MODEL_COMPRESSION.md](https://github.com/geujang/OTONova/blob/v1.5.0/MODEL_COMPRESSION.md). 지원 리스트와 참고자료: [SUPPORTED_FORMATS.md](https://github.com/geujang/OTONova/blob/v1.5.0/SUPPORTED_FORMATS.md).
