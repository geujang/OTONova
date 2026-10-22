# 원본 기술과 제3자 자료

- WFL-ASR: Ghin_MLo7 / MLo7Ghinsan. [원본 저장소](https://github.com/MLo7Ghinsan/WFL-ASR), MIT. 전문: [assets/WFL-LICENSE.txt](assets/WFL-LICENSE.txt). WFL 추론 코드와 호환 구현을 수정해 사용합니다.
- 영어 WFL 모델: [Superbox2147](https://github.com/Superbox2147). 일본어·한국어: [Archivoice](https://github.com/Archivoice). 모델 제공자와 학습 데이터셋 크레딧은 [CREDITS.md](CREDITS.md)에 별도 표기합니다.
- Whisper base: [OpenAI](https://github.com/openai/whisper), [모델 페이지](https://huggingface.co/openai/whisper-base). 공통 인코더를 추론 체크포인트에서 공유합니다.
- 가나 변환표: 원본 GPLv3 전문 [assets/KANA-TABLE-LICENSE.txt](assets/KANA-TABLE-LICENSE.txt) 보존.
- PaintedCz CORE VCCV: [assets/vccv-core-terms.rtf](assets/vccv-core-terms.rtf)의 작성자 이용 조건 원문을 보존합니다. 카탈로그·에일리어스 대응을 사용하며 패키지의 음원과 BGM은 배포하지 않습니다.
- 기타 한국어·영어 녹음 리스트와 음소 대응표는 [CREDITS.md](CREDITS.md)의 제작자·배포처를 참고합니다.
- 번들 런타임은 Python, PySide6 / Qt, PyTorch / TorchAudio, Transformers, NumPy, SciPy, SoundFile / libsndfile, Numba / llvmlite 및 관련 의존성을 사용합니다. 배포본에 남아 있는 각 패키지의 원문 라이선스를 유지합니다. 라이브러리·모델·리스트의 권리를 OTONova의 자체 저작물과 동일하게 간주하지 않습니다.

V1.0에서 바뀐 부분은 원설 생성·수정 UI, 파일명 및 리스트 인식, WFL 강제 정렬 연결, 공통 인코더 및 체크포인트의 무손실 재포장입니다. 원본 WFL 기술과 기존 학습 모델의 제작을 OTONova가 수행했다고 주장하지 않습니다.
