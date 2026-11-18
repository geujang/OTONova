# OTONova V2.2

Windows x64 설치 파일과 macOS Apple Silicon DMG를 함께 제공합니다. 제작자는 KURO입니다.

## V2.0 이후 변경 사항

- 일반 VC의 오버랩을 오프셋과 선행 사이의 **3/4 지점**으로 변경했습니다. 일본어·한국어·영어에 적용하며 VC 오프셋은 앞 모음 구간의 3/4 지점입니다.
- 음소 경계를 편집해 재계산할 때도 새 VC 오버랩 규칙을 적용합니다.
- vLabeler의 인코딩 선택 목록 10종을 지원합니다. UTF-8, Shift-JIS, GBK, ISO-8859-1, Windows-1251, Windows-1252, GB2312, ISO-8859-9, EUC-JP, EUC-KR입니다.
- 기존 CP949와 UTF-8 BOM, UTF-16 BOM, UTF-32 BOM을 포함해 텍스트 인코딩 14개를 선택할 수 있습니다.
- **작업 → 원본 OTO 다시 읽기 (인코딩 선택)**을 추가했습니다. 원본 OTO의 인코딩을 직접 선택해 화면에 다시 불러오며 폴더별 선택을 기억합니다.
- BOM, `#Charset:` 선언과 `character.yaml`의 `text_file_encoding`을 읽습니다. 선언 없는 레거시 인코딩은 직접 지정할 수 있습니다.
- 가수 설정 파일·OTO·ZIP 내보내기에 선택한 인코딩을 적용합니다. 기존 OTO의 문자 인코딩 선언도 저장 시 유지합니다.
- 중첩 OTO를 읽고 저장할 때 음원 루트의 인코딩 설정을 적용합니다.
- 가수 설정에서 인코딩을 바꿔 저장하면 화면의 OTO 저장 인코딩도 갱신합니다.

## 다운로드

- Windows x64 — `OTONova-V2.2-Setup.exe`
- macOS Apple Silicon — `OTONova-macOS-V2.2-arm64.dmg`
- 소스 — `v2.2.0` 태그 및 `OTONova-V2.2-source.zip`

각 배포 파일의 SHA-256을 제공합니다. macOS 앱 버전은 2.2.0입니다. Apple Developer ID 서명과 공증은 적용하지 않았으며 Intel Mac은 지원하지 않습니다.

## 지원 형식과 예정

일본어 CV·CVVC·VCV·VCV & CVVC, 한국어 CV·CVVC·CVC·VCV·COC·CBNN·CMPX, 영어 ARPAsing·CVVC(DELTA / Salem)·VCCV(PaintedCz CORE)를 지원합니다.

중국어 음원 지원은 향후 예정입니다. 중국어는 현재 UI 언어로 제공합니다. ~~한국어 VCCV~~ — 리스트 미확인(원본 리스트 삭제).

인코딩 목록 참고 자료는 [vLabeler Encoding.kt](https://github.com/sdercolin/vlabeler/blob/f839362e4fd4c0471e439d7da36f751d940f92ca/src/jvmMain/kotlin/com/sdercolin/vlabeler/util/Encoding.kt)입니다.

원본 크레딧은 [CREDITS.md](CREDITS.md), 용량 절감 방식은 [MODEL_COMPRESSION.md](MODEL_COMPRESSION.md), 지원 리스트는 [SUPPORTED_FORMATS.md](SUPPORTED_FORMATS.md), 이전 변경 사항은 [V2.0](RELEASE_NOTES_V2.0.md)을 참고하세요.
