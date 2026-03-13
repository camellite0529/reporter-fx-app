# 기자용 시장 기사 자동 생성기

이 프로젝트는 다음 목적의 Vercel 배포용 샘플입니다.

- 환율 기준값: 한국은행 ECOS Open API
- 장중 지수/환율 현재값: yfinance
- 기사 복사: 브라우저 버튼 한 번

## 로컬 실행

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export BOK_API_KEY=YOUR_BOK_ECOS_KEY
flask --app api/article.py run --debug
```

정적 파일은 간단한 HTTP 서버로 열 수 있습니다.

```bash
python -m http.server 8000
```

브라우저에서 `http://127.0.0.1:8000` 를 열고, API는 `/api/article` 를 보도록 프록시를 붙이거나 Vercel에서 통합 배포하세요.

## Vercel 배포

1. GitHub 저장소 생성
2. 이 폴더 전체 업로드
3. Vercel에서 저장소 Import
4. Environment Variables에 `BOK_API_KEY` 추가
5. Deploy 클릭

## 주의

- yfinance는 Yahoo의 공개 API를 사용하는 오픈소스 도구이며, 공식 문서상 연구/교육 목적 및 개인적 사용 용도라는 고지가 있습니다.
- 상업적 뉴스 서비스 운영 전에는 데이터 이용 약관과 라이선스를 반드시 검토하세요.
- 외국인/개인/기관 수급은 현재 화면 입력값을 사용합니다. 완전 자동화가 필요하면 KRX 또는 pykrx를 추가로 붙이세요.
