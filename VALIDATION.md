# 검증 기록 — 2026-10-23

대상: Linux 클라우드, Python 3.12.14, Node 24.19.0, 시스템 Chromium(소프트웨어 WebGL). Windows/RTX 3080 성능 결과가 아닙니다.

| 검사 | 결과 | 범위/제약 |
| --- | --- | --- |
| Python 의존성 설치 / pip check | 통과 | 가상환경에서 실제 설치 |
| npm ci / npm run build | 통과 | lockfile 고정 설치 및 로컬 자산 번들 |
| pytest | 18 passed | 실제 SQLite·API 및 런처, AI/STT 성공 경로는 대역 사용 |
| 런처 시작·HTTP 준비·종료 | 통과 | Linux에서 실제 Uvicorn 자식 프로세스 사용, 브라우저 실행은 대역 사용 |
| 런처 실패 진단 | 통과 | 시작 실패 로그·잠금 해제, 브라우저 실패 안내, 포트 충돌 보호 |
| 실제 HTTP 서버 | 통과 | `/` 200, `/api/health` server=true |
| WebGL HUD | 통과 | Chromium에서 실제 Canvas 및 셰이더 렌더링 |
| 브라우저 JS 예외 | 0 | 브라우저 smoke 시나리오 |
| Ollama 부재 UI | 통과 | 실제 503 응답 및 해결 안내 표시; 예상된 실패 |
| 프런트엔드 스트리밍 | 통과 | 명시적인 테스트 응답 대역 사용 |
| 마이크 녹음→전사→전송 흐름 | 통과 | Chromium 가상 마이크 및 STT 응답 대역, 실제 한국어 인식 아님 |
| 설정창 | 통과 | 열기/품질 선택/닫기 |
| 반응형 | 통과 | 1920×1080, 390×844; 모바일 가로 넘침 없음 |
| 실제 Ollama 추론/한국어 품질/문맥 | 미검증 | Ollama 및 모델 미설치 |
| 실제 한국어 STT/CPU·CUDA fallback | 미검증 | Whisper 캐시 및 실제 음성 장치 없음 |
| 실제 오프라인 한국어 TTS/마이크 잠금 | 미검증 | Windows 로컬 한국어 음성 필요 |
| Windows bat / RTX 3080 / 완전 오프라인 통합 | 미검증 | 해당 PC의 인수 검증 필요 |

`tests/test_api.py`에는 영속 기록/삭제, 누락 모델, 스트림 및 이전 문맥, 설정 유효성/저장, Origin/Host 차단, 요약 메모 및 문맥 제한, 빈 음성/중복 요청, 전사 경로 임시 파일 삭제, Ollama 부재, 미완료 응답 저장 방지, Ollama/GPU와 독립적인 준비 확인을 검증하는 11개 테스트가 있습니다. `tests/test_launcher.py`의 7개 검사는 실제 서버 시작·종료, 자식 프로세스 실패 로그, 브라우저 연결 실패 시 주소 표시, 다른 서비스 구분 및 포트 충돌·빌드 누락 진단을 확인합니다. 음성 인식 및 모델 품질을 검증하는 테스트로 해석하지 마세요.

브라우저 smoke는 통합 서버가 실행된 상태에서 다음처럼 재현할 수 있습니다. 별도 선택 개발 도구이며 Windows 기본 실행에는 필요하지 않습니다.

```sh
.venv/bin/python -m pip install playwright
.venv/bin/python tests/browser_smoke.py
```

이 스크립트는 `/usr/bin/chromium`이 있는 Linux 클라우드 전용입니다. `data/hud-desktop.png`, `data/hud-mobile.png`를 생성하고, 테스트 대역은 메모리상의 브라우저 라우트에만 적용합니다. 캡처를 실제 모델 답변 증거로 사용하지 마세요. 소프트웨어 GPU FPS는 RTX 3080 성능 지표가 아닙니다.

초기 Playwright 브라우저 다운로드는 cdn.playwright.dev에 대한 네트워크 정책(403)으로 실패했습니다. 검증을 끄지 않고 기존 시스템 Chromium으로 대체하여 브라우저 검사를 마쳤습니다. 추가 네트워크 허용이나 비밀 키는 요청하지 않았습니다.

Starlette TestClient가 AnyIO의 이전 별칭을 사용하는 DeprecationWarning 1개가 있습니다. 테스트 실패는 아닙니다. Vite는 `dist`가 frontend 바깥 경로라는 안내를 출력하며 빌드가 성공합니다.

클라우드 구성 초안의 `install_script`와 `start_skill`을 저장했습니다. 저장은 스크립트 실행/게시를 의미하지 않습니다. 현재 인스턴스에서 설치·빌드·테스트·서버 검사를 별도로 실행했으며 새 작업에서의 스냅샷 복원은 미검증입니다. 환경 설정에서 검토·저장 후 게시해야 후속 작업에 적용됩니다.

Windows 설치·실제 장치 검증 단계는 README.md를 따르세요. 현재 결과는 소스 구현 및 개발 환경 검사이며, 모든 최종 사용 시나리오를 완료 검증했다는 뜻이 아닙니다.

## 인터넷 검색 확장 검사 — 2026-10-26

- 최종 Python 검사: **53 passed** (기존 API·런처 18개 + 검색 확장 35개). 기존 SQLite 스키마에서 데이터 손실 없이 출처 열을 추가하는 검사도 포함합니다.
- Vite 빌드 및 `pip check` 통과. 기존 마이크·TTS 모듈은 변경하지 않았습니다.
- SearXNG 공식 이미지 `2026.10.25-54ca1d9cf`를 실제 Docker로 실행했습니다. Compose 설정 검사, 컨테이너 healthy, 올바른 인스턴스 이름 및 선택한 5개 엔진, `/config`와 `/search?format=json`의 실제 HTTP 200·JSON 응답을 확인했습니다.
- 외부 정책을 우회하지 않도록 검증 컨테이너는 **인터넷이 없는 내부 Docker 네트워크**로 실행했습니다. 컨테이너 내부에서 JSON API를 확인했으며 이 검증용 네트워크에서는 호스트의 8080 포트로 연결할 수 없었습니다. 배포용 Compose는 이 임시 오버라이드를 포함하지 않고 `127.0.0.1:8080` 게시를 지정합니다. Windows 호스트 포트 접근은 실기 미검증입니다.
- 실제 검색 엔진 결과 수신은 미검증입니다. 위 JSON 응답의 결과는 0개이고 상위 엔진 연결 실패가 명시되어 있었습니다. 이를 검색 성공으로 계산하지 않았습니다.
- 클라우드에서 Open-Meteo 지오코딩 도메인 요청은 egress proxy HTTP 403으로 차단됐습니다. 새 네트워크 초안 저장 후 재확인해도 실행 중인 정책은 그대로였습니다. 실제 날씨 API 성공·실제 데이터 정확성은 미검증입니다.
- 검색·날씨의 정상 파싱은 HTTP/JSON 테스트 대역으로 검사했습니다. Tavily는 선택 키 존재 확인, 인증 헤더 구성, 결과 정규화, 상태 폴링의 유료 API 호출 방지를 검사했으며 실제 키를 이용한 인증·과금 호출은 하지 않았습니다.
- 공개 페이지 읽기: 사설/루프백/메타데이터 주소 및 비표준 포트 차단, DNS 응답에 내부 IP가 섞인 경우 차단, 검증한 IP 연결, 내부 주소로의 리디렉션 거부, 본문 크기 제한, 스크립트 제거를 검사했습니다. 허용된 GitHub 공개 README 원문 읽기를 시도했지만 직접 DNS 해석이 실패했습니다. 실제 공개 사이트 본문 통신은 미검증이며 검증/TLS 확인을 우회하지 않았습니다.
- `tests/browser_web_smoke.py`: 실제 FastAPI·SQLite·Chromium/WebGL에 **Ollama/SearXNG 테스트 서버**를 연결하여 SEARCHING 전환, 도구 프로토콜, 명령 대체, 출처 링크·날짜·재로드 복원, 검색 취소, 검색 실패 후 로컬 대화, 인터넷 OFF 차단, 날씨 카드 단위·기준 시각·예보 표시를 확인했습니다. JavaScript 예외 0개. 실제 Qwen3 추론이나 실제 최신 뉴스·날씨를 확인한 결과는 아닙니다.
- Windows Docker Desktop, Windows 배치 실행, 실제 한국어 음성 장치와 Qwen3 모델에서의 검색 결과 요약 품질은 추가 인수 검증이 필요합니다.

재현 명령(빌드 후):

```sh
.venv/bin/python -m pytest -q
.venv/bin/python tests/browser_web_smoke.py
```

브라우저 검사에는 Playwright와 시스템 Chromium이 필요합니다. 8000·8080·11434 포트가 비어 있을 때만 실행하며 사용자 서비스는 종료하지 않습니다. 실제 PC에서는 `setup_web.bat`, `check_web.py --weather Seoul`과 `WEB_SEARCH.md`의 검색 예제로 확인하세요.

클라우드 초안에는 검색 서비스 시작 지침과 Open-Meteo·SearXNG 문서·선택 Tavily·설정된 검색 엔진 도메인을 추가했습니다. 검토·저장·게시 및 새 인스턴스의 실제 외부 접속 확인은 별도입니다.

기존 `tests/browser_smoke.py`도 인터넷 OFF 및 Ollama 미설치 상태에서 재실행했습니다. HUD·설정창·모바일 배치·미연결 오류·가상 마이크 녹음/전사 전달이 통과했고 JavaScript 예외는 0개였습니다.
