# 지원 형식과 참고한 리스트

## 음원 형식

| 언어 | 사용자 선택 형식 | 인식 자료 |
|---|---|---|
| 일본어 | CV / CVVC / VCV | 히라가나·가타카나 파일명, 기존 oto.ini |
| 한국어 | COC / CBNN / CMPX | COC 기본·특수음소 제외, CBNN 전체 기본 oto, CMPX main 및 선택 확장 |
| 한국어 | CV | 단독음 파일명, 기존 oto.ini |
| 한국어 | CVVC | 말차·마따따비 신/구 리스트 |
| 한국어 | CVC | 제티·빈빈·규탱 Light / Plus 리스트 |
| 한국어 | VCV | 서딕호 기본/확장, 말차 7/15모라 리스트 |
| 영어 | ARPAsing | ARPAsing 표기 리스트 카탈로그, 사용자가 제공한 index |
| 영어 | CVVC | DELTA English, Salem S-CVVC LITE / FULL |
| 영어 | VCCV | PaintedCz CORE American English VCCV 10개 섹션 |

한국어 세부 방식의 제작자 이름은 인식 근거이며 UI에서는 한국어 CVVC / CVC / VCV / CV로 묶어 제공합니다. 사설 확장이나 변형 표기가 모두 인식되는 것은 아닙니다. 기존 oto.ini의 에일리어스와 접두·접미사를 우선하며, 정확히 대응하지 못하는 행은 검토 경고를 표시합니다.

## 영어 음소 대응

- [ARPAsing 공식 음소표](https://arpasing.tubs.wtf/en/resources/phoneme-chart).
- [Salem 발음 및 기호 대응표](https://utau.felinewasteland.com/en/phones#conv).
- [Salem 개요](https://utau.felinewasteland.com/en/overview), [LITE](https://utau.felinewasteland.com/en/lite), [FULL GA](https://utau.felinewasteland.com/en/full_ga).
- [DELTA 공식 설명](https://delta-kimigatame.hatenablog.jp/entry/ar761052), [KLAD 번역·리스트 안내](https://tl.tubs.wtf/2020/11/09/delta-eng).
- [ARPAsing 녹음 리스트 디렉터리](https://arpasing.tubs.wtf/en/directories/reclists): ARPAsing 표기만 사용하며 배포 중지·다른 음소 체계의 변환 자료는 내장 카탈로그에서 제외했습니다.
- [YinP: CZ’s VCCV English Tutorial](https://www.deviantart.com/yinp/journal/CZ-s-VCCV-English-Tutorial-699787422).

DELTA / Salem 입력을 영어 모델의 ARPAsing 계열 음소로 대응시킵니다. `ju → y uh`, `ts → t+s`, `dz → d+z`, `{+ → {`, `e → E` 규칙을 적용하고 원래 에일리어스는 유지합니다. 모델이 표현하지 못하는 모음의 세부 구분은 근사값이며 필요 시 검토해야 합니다. MEL / SEL / Cdra / Sango 리스트를 영어 CVVC 지원 목록으로 등록하지 않았습니다. Vocaloid SAMPA 전체 리스트 호환을 보장하지 않습니다.

## 원본 자료의 위치

한국어 각 리스트의 원본 배포 링크, ARPAsing 카탈로그 출처, 모델 학습 데이터셋은 [CREDITS.md](CREDITS.md)에 정리했습니다. 원본 학습 음원·BGM·사용자 음원을 포함하지 않습니다. 원문 이용 조건이 있는 CORE 자료는 `assets/vccv-core-terms.rtf`를 보존했습니다.

## 예정

**중국어 음원 자동 원설 지원을 추가할 예정입니다.** V1.0의 중국어 메뉴는 UI 번역이며 중국어 음원 정렬 모델 지원을 의미하지 않습니다. 구체적인 형식과 시점은 확정하지 않았습니다.

~~한국어 VCCV 추가 예정~~ — **리스트 미확인**: 원본 녹음 리스트가 삭제되어 추가를 보류합니다. 영어 VCCV 지원과는 별개입니다.

**Android·iOS 지원은 추가 예정입니다.** 현재 배포 대상은 Windows x64와 macOS Apple Silicon이며, 모바일 버전의 출시 일정은 아직 정하지 않았습니다.

COC·CBNN·CMPX는 Windows와 macOS V2.0에 포함됩니다. 기존 CVVC 규칙을 재사용하며 CBNN 숫자 접미사, CMPX 분류 접두사 및 COC 대문자 받침을 따로 해석합니다.
