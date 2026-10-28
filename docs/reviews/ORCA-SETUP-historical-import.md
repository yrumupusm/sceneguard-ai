# 기존 실험 기록 가져오기 — 총괄 검토 초안

원문/원시 출력은 보존했고 JSON에서 선택된 실측만 읽었다. 기존 실험의 실행 완료와 모델 채택은 별개다. 사람의 영상 의미 검수와 독립 테스트가 추가로 필요하다. 이 기록은 AI 검토이며 사용자 확정 정답이 아니다.

EXP-0001~0002는 프레임 루프 처리량, EXP-0003은 동일 출력 검증 프레임 수, EXP-0004~0006은 진단 집계, EXP-0007은 생성 시간과 프로세스 GPU 할당 메모리를 표시한다. 지표·표본·측정 범위가 달라 실험 간 성능 순위로 합치지 않는다. EXP-0006·0007의 기본 적용 보류를 유지한다. 과거 실행의 agent 모델은 미확인이므로 null이다.

| 원문 | 원문 SHA256 | metrics SHA256 |
| --- | --- | --- |
| EXP-0001 | `1398be451890f1a79be2c53da7346753f7368f70a558f73ce5792221b0a64cb6` | `178557439bf31015199fdb5eacfcef62d539935c41e746f226ffa56eb751ee03` |
| EXP-0002 | `8c80edb8a720204b57a8097c54c42f4695eca1f534c7e086d8edf40b8db98bce` | `abd9bf26fae2586f841a39cc8b43d9ce9abefea2ff053b909409538d02717636` |
| EXP-0003 | `89b532fcc70025b82fc921b38ce665e5b938f840085517f95a2fda077f0fe715` | `062d343f73c9556b9f2c15c4f4411556b485bf2d1dacf463b71d81e1286d3b82` |
| EXP-0004 | `3f4212fd685f20ce1b7894e50dc51ffb7cc6a36b1f0bd29736fb01414b81552f` | `f891ab5e82aba37cde7b7c0b5816bdc558b5ef0bc37fc4cfdc3b3a7e5d0303b5` |
| EXP-0005 | `bfbf00f6af39b8682c05d73d0456fc78c22f7f1b59f4a455cc80f9f9acf5944b` | `94f3cd4f5efe39eab5cb9655c1640112650808df1bc27829284cd9a0fffd4399` |
| EXP-0006 | `6aea3068b517b90cc8512a0e207c2487767b9d04d2f7b30808f5ba73f3231ea5` | `df8cfd45383b23ffbe561c5ac5a39aacf45ed2f8e61b91d1baf3e82efb4be742` |
| EXP-0007 | `6e0547b4c298de232cac9532e1abebd315c9e6c1f6d9b1c3dee37c235317eda7` | `270fd6fcba459880a8e31e30f5058fb048858298aad8d8be124ca5fc59f4fc6d` |
