# OTONova V2.0 · 원본 기술·모델·자료 크레딧

## WFL 원본 기술

- 원저자: **Ghin_MLo7 / MLo7Ghinsan (Ghinsan)**.
- 원본 프로젝트: [WFL-ASR — Whisper/WavLM for Phoneme Labeling](https://github.com/MLo7Ghinsan/WFL-ASR).
- 원본 저작권: **Copyright (c) 2025 Ghin_MLo7**. MIT 라이선스 전문은 [WFL-LICENSE.txt](assets/WFL-LICENSE.txt)에 보존합니다.
- OTONova는 WFL의 음소 정렬 기능을 원설 생성·수정 UI에 연결하고, 배포 체크포인트를 무손실 공유 인코더 형식으로 재구성했습니다. 새 음향 모델을 학습한 것은 아닙니다.
- 공통 음향 인코더: [OpenAI Whisper base](https://huggingface.co/openai/whisper-base), [원본 Whisper 프로젝트](https://github.com/openai/whisper).
- 아래 학습 데이터셋 목록은 모델 제공 정보에 따른 크레딧입니다. 원본 학습 데이터와 음원은 배포하지 않습니다.

## 영어 모델

모델 제공: [Superbox2147](https://github.com/Superbox2147)

학습 데이터셋:

- NeuroSynth EN
- EvilSynth EN
- Arden's dad
- voder
- MURIN
- fae
- VERON1KA
- Alex (NeoDIVA)
- AlexFlorea (legacy)
- DAYTON
- NGYY
- AIDOL
- ACV-001
- Deshi
- LIEE corpus

## 일본어 모델

모델 제공: [Archivoice](https://github.com/Archivoice)

학습 데이터셋:

- ACV-001

## 한국어 모델

모델 제공: [Archivoice](https://github.com/Archivoice)

학습 데이터셋:

- CSD relabeled
- ACV-001

## 녹음 형식 참고 자료

모델 학습 데이터와 별도로, 다음 제작자의 공개 녹음 리스트와 에일리어스 규칙을 참고했습니다. 원본 샘플 음원과 원본 원설 템플릿은 배포본에 포함하지 않습니다.

- 말차: [한국어 CVVC 9모라](https://drive.google.com/file/d/1g5yrCGkksEKapvBP91uA86stgWkilmli/view), [VCV 7모라](https://drive.google.com/file/d/1Zm-C0Om2KdjOxdXY6gugg0AK93qUICOV/view), [VCV 15모라](https://drive.google.com/file/d/1zeR82znQiSlhpjacFMkkoqMwLfeH05NW/view)
- 마따따비: [CVVC 신버전](https://drive.google.com/drive/folders/1-zWX63I8VXeKVLWlx6oNX90FqUYedx-s), [구버전](https://drive.google.com/drive/folders/1WCNkM6Q2NyrJHR--fJ-gQzyRkH1pNBF3)
- 제티: [한국어 CVC](https://blog.naver.com/zetty123/221728323094)
- 빈빈: [한국어 CVC 8·11모라 및 모음 확장](https://drive.google.com/file/d/1BtvdBHF9doNlnPNl0Ha6-orUiejoxUGE/view)
- 규탱: [한국어 CVC Light·Plus](https://drive.google.com/drive/folders/1P2_eiSbRkSTi_SUXpyCoYhC0DWVf4QZd)
- 서딕호: [VCV 기본](https://drive.google.com/file/d/1kXEeMBzzXNi8EWG7M2nevicbpkyPek6d/view), [특수음소 포함](https://drive.google.com/file/d/1TzeaANXdB-rXuq4D15N6X9w_vD9glxLd/view)


## ARPAsing 녹음 리스트 / 인덱스 자료

ARPAsing 디렉터리(https://arpasing.tubs.wtf/en/directories/reclists)의 공개 자료에서 파일명→ARPAbet 대응표를 구성했습니다. 원저자 표기를 유지하며, 음원 오디오는 배포하지 않습니다. Liverpool·ix·VCCV 변환 자료와 배포 중지 링크는 내장 카탈로그에서 제외했습니다.

- Adlez27: https://klad.tubs.wtf/download?f=arpasing-kladlist
- Biggity_Boy: https://www.mediafire.com/file/vac16q69yoxisgk/Biggity_Boy%2527s_%255BArpasing_Reclist%255D.zip/file
- cadlaxa: https://mega.nz/file/MuBQRCwI#6hnUuOS9ZSVWUgv1psMpuxX2EfaQFUxtEiLyT15Kc4k
- cadlaxa: https://mega.nz/folder/cyhWxJCQ#P1M1SXci89Q6kfg1MZqSTA
- Carnegie Mellon University (script)  Jeremy Burke (index): https://klad.tubs.wtf/download?f=cmu-arctic-arpasing
- deadbyte: https://drive.google.com/drive/folders/1Y5tOWTYuVHxMcNxZAVmGSazwnZkNLbBh?usp=drive_link
- Kanru Hua: https://klad.tubs.wtf/download?f=arpasing-0.1.0-index
- Kanru Hua: https://klad.tubs.wtf/download?f=arpasing-0.1.0-noindex
- Kanru Hua: https://klad.tubs.wtf/download?f=arpasing-0.2.0-index
- Kanru Hua: https://klad.tubs.wtf/download?f=arpasing-0.2.0-noindex
- Kanru Hua, edited by Adlez27: https://klad.tubs.wtf/download?f=arpasing-0.2.0-6syl-index
- Kanru Hua, edited by Adlez27: https://klad.tubs.wtf/download?f=arpasing-0.2.0-6syl-noindex
- MouseDarkArts: https://www.mediafire.com/file/rbhjc9ct8612jr9/Avocado_Arpasing_Reclist.zip/file
- SaKe: https://mega.nz/file/stAwFY7D#dp8jESMCi0p1fi0-EsYmm_TofFxmln6Xjp2nn2eUppU
- WinterdrivE: https://www.dropbox.com/s/mwu8ufuqj0fjbkc/WinterdrivE%27s%20ARPAsing%20dx%20reclist.zip?dl=0
- Yukito Yuki: https://klad.tubs.wtf/download?f=yuki-6mora-arpasing
- Yukito Yuki: https://klad.tubs.wtf/download?f=yuki-arpasing-ver1
- Yukito Yuki, edited by Adlez27: https://klad.tubs.wtf/download?f=yukilist-verklad
- Zestea: https://mega.nz/file/bKRwiJQZ#qIBSfl_VFNzu7K4uhTgvWm5EL8wu3AjwuB4jylTvf1s
- Zestea: https://mega.nz/file/GS4QBQKa#MV0eCbIIR9WNWDjiXCz6BtMNr6okKifQOrX9USiIXCw
- 水音 (みなと): https://bowlroll.net/file/300269


## OTONova 로고 및 영어 CVVC 리스트 인식

로고: 사용자가 제공한 원본 이미지.

Salem S-CVVC: Feline Wasteland (Salem). 공식 LITE/FULL 리스트의 4/8박 및 교체·추가 목록을 식별합니다. 배포에는 원본 리스트 대신 SHA-256 지문을 포함합니다. 기존 영어 WFL 모델로 경계를 추정합니다.

DELTA English: デルタ (delta_kuro). [공식 배포·설명](https://delta-kimigatame.hatenablog.jp/entry/ar761052), [KLAD 번역·g00–g07 배포 안내](https://tl.tubs.wtf/2020/11/09/delta-eng). 파일명 표기와 oto 표기를 구분하며 원본 리스트는 배포하지 않고 지문만 포함합니다.

음소 대응 참고: [ARPAsing 음소표](https://arpasing.tubs.wtf/en/resources/phoneme-chart), [Salem 작성자 발음·대응표](https://utau.felinewasteland.com/en/phones#conv). 모델에 없는 조음 차이는 근사 경고로 표시합니다. MEL/SEL/Cdra/Sango 입력 형식은 등록하지 않았습니다.

## PaintedCz CORE American English VCCV

- 녹음 리스트 및 기본 oto: **PaintedCz (Casey Chapman)**. 사용자가 제공한 CORE American English VCCV 패키지를 기준으로 합니다.
- 설명: **YinP**, [CZ's VCCV English Tutorial](https://www.deviantart.com/yinp/journal/CZ-s-VCCV-English-Tutorial-699787422).
- 발음 대응 참고: [ARPAsing 공식 음소표의 PaintedCZ 열](https://arpasing.tubs.wtf/en/resources/phoneme-chart).
- 작성자의 원문 이용 조건(2023년 갱신 포함)은 `assets/vccv-core-terms.rtf`에 보존합니다. 패키지의 BGM·음원은 포함하지 않습니다.
- 빈/누락된 기본 에일리어스를 보완한 행에는 검토 경고를 붙입니다. 원설 계산 코드는 OTONova의 독립 구현이며 음향 추정은 기존 영어 WFL 모델을 사용합니다.

https://utau.felinewasteland.com/en/overview
https://utau.felinewasteland.com/en/lite
https://utau.felinewasteland.com/en/full_ga

## 가나 변환표

`kana2phonemes.table`은 [ENUNU](https://github.com/oatsu-gh/ENUNU)의 가나 변환표를 바탕으로 사용합니다. [pyshiro](https://github.com/wavtechyukky/pyshiro)의 ENUNU 기반 표를 참고했으며, 현재 음향 추정에는 SHIRO 모델을 사용하지 않습니다. 원본 GPLv3 전문은 `KANA-TABLE-LICENSE.txt`에 보존합니다. 이 자료의 권리를 OTONova 자체 코드나 모델의 권리와 동일하게 취급하지 않습니다.

## 한국어 COC · CBNN · CMPX

- COC: 사용자가 제공한 `COC Reclist.zip`의 기본·특수음소 제외 리스트와 기본 oto의 파일명·에일리어스 관계를 참고했습니다. 압축파일에 제작자 표기가 없어 임의로 추정하지 않았습니다.
- CBNN: [EX3exp / UTAU-Korean-CBNN](https://github.com/EX3exp/UTAU-Korean-CBNN). 원본 BSD-3-Clause 전문을 `assets/CBNN-LICENSE.txt`에 보존합니다. 전체 기본 oto의 숫자 접미사를 유지합니다.
- CMPX: [2xxbin / UTAU-Korean-CMPX](https://github.com/2xxbin/UTAU-Korean-CMPX). main, option_consonant, option_sepcial, option_vowel의 파일명·에일리어스 관계를 참고했습니다.
- CMPX 원본은 리스트 재배포를 금지하므로 원본 녹음 리스트와 원문 파일명은 배포하지 않습니다. 목록 인식용 SHA-256 지문과 원설 대응용 음소 별칭 관계만 압축 카탈로그로 포함하며, 원본 시간값·가이드 BGM·음원·포네마이저 코드는 포함하지 않습니다. 원설 계산은 기존 CVVC 규칙을 사용한 독립 구현입니다.
- 모델이 구분하지 못하는 특수 발음은 기존 치환 또는 근사 음소를 사용하고 경고를 표시합니다. 실제 녹음에 대한 발음 정확도는 청음 검토가 필요합니다.


## 가수 설정 형식 참고

`character.txt` / `character.yaml` 필드와 가수 음원 ZIP 구조는 OpenUtau의 공개 사양·로더를 참고했습니다. OpenUtau 실행 파일이나 코드를 배포본에 포함하지 않습니다.

- [VoicebankConfig.cs](https://github.com/openutau/OpenUtau/blob/master/OpenUtau.Core/Classic/VoicebankConfig.cs)
- [VoicebankLoader.cs](https://github.com/openutau/OpenUtau/blob/master/OpenUtau.Core/Classic/VoicebankLoader.cs)
- [character.yaml 기술 문서](https://openutau.com/tech-note-%E2%80%90-character.yaml/)
