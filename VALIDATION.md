# 검증 기록 — 2026-10-23

대상: Linux 클라우드, Python 3.12.14, Node 24.19.0, 시스템 Chromium(소프트웨어 WebGL). Windows/RTX 3080 성능 결과가 아닙니다.

| 검사 | 결과 | 범위/제약 |
| --- | --- | --- |
| Python 의존성 설치 / pip check | 통과 | 가상환경에서 실제 설치 |
| npm ci / npm run build | 통과 | lockfile 고정 설치 및 로컬 자산 번들 |
| pytest | 10 passed | 실제 SQLite·API, AI/STT 성공 경로는 대역 사용 |
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

`tests/test_api.py`에는 영속 기록/삭제, 누락 모델, 스트림 및 이전 문맥, 설정 유효성/저장, Origin/Host 차단, 요약 메모 및 문맥 제한, 빈 음성/중복 요청, 전사 경로 임시 파일 삭제, Ollama 부재, 미완료 응답 저장 방지를 검증하는 10개 테스트가 있습니다. 음성 인식 및 모델 품질을 검증하는 테스트로 해석하지 마세요.

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
