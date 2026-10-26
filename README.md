# J.A.R.V.I.S. v1.0 — 로컬 AI 음성 비서

Three.js/GLSL 에너지 구체, FastAPI, Ollama 스트리밍, faster-whisper 한국어 STT, 오프라인 한국어 브라우저 TTS, SQLite 기록을 사용하는 Windows용 소스 프로젝트입니다. 유료 API 키는 필요하지 않습니다. AI가 시스템 명령을 실행하는 기능은 없습니다.

## 선택 기능: 인터넷 검색·날씨

SearXNG 무료 검색, 선택 Tavily, Open-Meteo 날씨, 출처 저장 및 SEARCHING 애니메이션을 추가했습니다. 기본은 인터넷 OFF입니다. **설치·사용·제한 사항은 [WEB_SEARCH.md](WEB_SEARCH.md)**를 참고하세요. 기존 `setup.bat` → `start.bat` 실행 방식은 유지하며, 인터넷 검색은 Docker Desktop 설치 후 `setup_web.bat`으로 별도 준비합니다.

## Windows 11 설치

1. Python **3.11 또는 3.12**, Node.js **22 LTS 이상**, Google Chrome, [Ollama](https://ollama.com)를 직접 설치하세요. Python은 PATH에 추가하세요. 관리자 권한 설치를 자동으로 실행하지 않습니다.
2. ZIP 파일의 압축을 먼저 푼 뒤, `setup.bat`을 실행하세요. 가상환경 생성, Python 패키지 설치, `npm ci`, 프런트엔드 빌드를 수행합니다. **`Setup complete` 문구가 나와야 설치가 완료된 것입니다.** 최초 설치에는 인터넷이 필요합니다. Python Launcher의 3.12/3.11을 우선 탐색하며, 지원되는 기존 가상환경은 재사용합니다.
3. Ollama 앱을 실행하세요. 서버가 없으면 별도 터미널에서 `ollama serve`를 실행합니다.
4. 다운로드 용량과 사용 모델을 확인한 뒤 직접 실행하세요. 프로그램은 모델을 자동 다운로드하지 않습니다.

```bat
ollama pull qwen3:8b
```

VRAM이 부족하면 `ollama pull qwen3:4b`를 선택하세요. `qwen3:14b`는 3080 10/12GB에서 STT 및 화면 렌더링과 경쟁하거나 CPU로 일부 오프로딩될 수 있습니다. GPU 이름·전체/여유 VRAM(MiB)은 HUD에 `nvidia-smi`의 실제 결과로 표시됩니다. 조회할 수 없으면 추측하지 않습니다.

5. 한국어 STT 모델도 최초 한 번 명시적으로 다운로드하세요. 모델 변경 시 해당 모델도 미리 준비해야 합니다.

```bat
.venv\Scripts\python prepare_stt.py --model small
```

모델 다운로드는 Hugging Face에서 이루어지며, 이후 STT 실행은 로컬 캐시만 사용합니다. 사용자 녹음은 로컬 FastAPI 서버로만 전송됩니다. 서버 임시 파일은 성공·실패 후 삭제합니다.

6. Windows 설정 → 시간 및 언어 → 음성에서 한국어 로컬 음성을 설치하세요. Chrome SpeechSynthesis가 `ko` 및 `localService=true`로 보고하는 음성만 사용합니다. 없으면 텍스트 답변을 제공하고 음성 없음 상태를 표시합니다. 외부 온라인 음성을 자동 선택하지 않습니다.

## 실행 / 종료

```bat
start.bat
stop.bat
```

`start.bat`은 전용 런처에서 가상환경의 서버를 `127.0.0.1:8000`에 실행하고 준비 응답 후 기본 브라우저를 엽니다. 기본 브라우저를 Chrome으로 지정하세요. 실행 창은 열어두세요. `stop.bat` 또는 실행 창에서 Ctrl+C로 이 런처가 생성한 서버만 종료합니다. 외부 Ollama는 종료하지 않습니다. 8000 포트가 이미 사용 중이면 다른 프로세스를 종료하지 않고 실패합니다. 비정상 종료 후에는 서버가 없는지 확인한 뒤 `data/server.lock`을 삭제할 수 있습니다.

설치·시작 실패 시 검은 창을 유지하여 오류를 읽을 수 있습니다. 서버 출력은 `data/startup.log`에도 남깁니다. 브라우저가 자동으로 열리지 않아도 서버가 실행 중이면 Chrome 주소창에 `http://127.0.0.1:8000`을 입력하세요. HUD 준비 확인은 `/api/ready`에서 수행하며 Ollama 연결이나 GPU 조회를 기다리지 않습니다.

`.env.example`은 셸 설정 예시이며 자동으로 읽지 않습니다. 기본 데이터 위치는 `data/`입니다. 다른 위치는 실행 전 `set JARVIS_DATA=C:\원하는\폴더`로 지정하세요. API 키·클라우드 연결은 필요 없습니다.

## 사용

- 텍스트 입력 또는 마이크 버튼 → 말하기 → 다시 눌러 종료. 녹음은 최대 60초/업로드 12MB로 제한됩니다. 권한 거부 시 Chrome 주소 표시줄의 사이트 설정에서 마이크 권한을 허용하세요. 텍스트 대화는 계속 가능합니다.
- 실제 마이크 RMS·주파수 데이터가 입자 및 셰이더 정점 변위에 반영됩니다. `IDLE / LISTENING / TRANSCRIBING / THINKING / SPEAKING`을 부드럽게 전환합니다.
- 음성 출력 중에는 마이크 버튼이 비활성화됩니다. 브라우저 TTS는 출력 파형 접근이 불가능하므로 SPEAKING 상태 기반의 근사 리듬을 사용합니다. 중지 버튼은 응답 요청 및 음성을 취소합니다. 취소한 불완전 응답은 AI 문맥에 저장하지 않습니다.
- 설정: 설치된 모델, temperature, STT 크기, 그래픽 LOW/MEDIUM/HIGH(입자 밀도), 입자 크기, 한국어 로컬 음성, 속도, 시스템 프롬프트를 변경합니다. 시스템 설정은 `data/settings.json`, 기록은 `data/jarvis.sqlite`에 보존합니다. 기본 프롬프트는 `config/jarvis_personality.txt`입니다. 음성 선택·속도·ON/OFF·볼륨은 브라우저에 보존됩니다.
- 최근 24개 메시지 중 최대 24,000자를 문맥으로 전달합니다. 오래된 핵심 내용은 **대화 요약 메모 편집**으로 보존하세요. 요약 메모를 시스템 문맥에 추가하며 자동 요약을 실행했다고 주장하지 않습니다.
- 기록 삭제에는 확인이 필요합니다. 새 대화/목록에서 이전 대화를 이어갈 수 있습니다.
- 기본 MEDIUM, 제한된 픽셀 비율과 BufferGeometry를 사용하며 저 FPS에서는 LOW로 낮춥니다. 모바일 화면은 구체·채팅을 세로로 분리합니다.

## STT GPU 및 오프라인

GPU 초기화와 첫 추론이 실패하면 CPU INT8로 재시도합니다. Windows CUDA/cuDNN 호환 설치가 없어도 CPU로 사용할 수 있습니다. 실행 장치는 첫 STT 처리 후 HUD의 STT 항목에 표시됩니다. GPU를 사용하려면 설치한 CTranslate2 버전에 맞는 NVIDIA CUDA/cuDNN을 준비하세요. 앱은 관리자 권한 드라이버 설치를 하지 않습니다.

패키지, Ollama 모델, Whisper 모델, Windows 로컬 음성을 준비한 후 네트워크를 끄고 실행하세요. 앱은 CDN 스크립트·웹 폰트·클라우드 AI API를 사용하지 않습니다. Ollama는 고정된 `127.0.0.1:11434`로만 연결합니다. 외부 사이트 Origin/Host 요청을 거부하고 CORS를 열지 않습니다. 로컬 다른 프로그램에 대한 인증 수단은 아니므로 신뢰할 수 있는 PC 사용자 환경에서 사용하세요.

## 문제 해결

| 현상 | 조치 |
| --- | --- |
| 시작 창이 바로 닫힘(이전 버전) | 프로젝트 폴더의 탐색기 주소창에 `cmd` 입력 → Enter → `start.bat` 실행. 창에 남는 오류를 확인하고 최신 ZIP으로 업데이트 |
| `Python environment is missing` | 같은 폴더의 `setup.bat` 실행. Python 3.11/3.12와 Node.js 22 이상 설치 후 `Setup complete`까지 확인 |
| `The interface has not been built` | `setup.bat`의 npm 설치·빌드 단계 오류 해결 후 재실행 |
| `Port 8000 is already in use` | JARVIS가 이미 실행 중이면 Chrome에서 `http://127.0.0.1:8000` 열기. 다른 앱이면 해당 앱을 직접 종료하거나 포트 사용 설정 확인 |
| `Server exited during startup` | 검은 창의 오류 또는 `data/startup.log` 확인. Python 패키지 누락이면 `setup.bat` 재실행 |
| Ollama 연결 실패 | Ollama 실행, `ollama list` 확인, 포트 11434 확인 후 연결 재확인 |
| 모델 미설치 | 원하는 모델의 `ollama pull`을 직접 실행하고 설정에서 선택 |
| STT 모델 로딩 실패 | 동일한 데이터 경로에서 `prepare_stt.py --model small` 실행, CPU 라이브러리 설치 결과 확인 |
| 음성 출력 없음 | Windows 로컬 한국어 음성 팩 설치, Chrome 재시작; 사용자 클릭 후 음성 재생 확인 |
| 구체 표시 안 됨 | Chrome 하드웨어 가속/WebGL 활성화. 실패해도 채팅 사용 가능 |
| GPU 메모리 부족/느림 | Qwen3 4B 선택, 그래픽 LOW, 다른 GPU 프로그램 종료 |

## 개발 및 테스트

Linux 클라우드 개발 환경:

```sh
cd /workspace/jarvis
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci --cache /tmp/jarvis-npm-cache
npm run build
.venv/bin/python -m pytest -q
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

빌드된 정적 파일은 FastAPI가 제공하므로 별도 Node 서버가 필요 없습니다. 소스 수정 후 `npm run build`하고 페이지를 새로고침하세요. 별도 Vite dev 서버는 API 프록시가 구성되어 있지 않으므로 통합 실행 방식으로 개발하세요. Cloud 작업은 이미 격리되어 있으므로 기존 체크아웃을 사용하며 별도 Git worktree를 만들 필요가 없습니다.

### 현재 검증 범위

- Linux Python 3.12에서 의존성 설치 및 `pip check`, Vite 프로덕션 빌드 통과.
- 기존 API·런처 18개, 검색 확장 35개, 한국어 날씨 32개, 구글·네이버 지정 검색/열기 22개, 총 **107개 테스트**가 통과했습니다. 기존 API 검사에 독립적인 준비 상태 확인, 실제 서버 프로세스의 시작·HTTP·종료, 시작 실패 로그 및 잠금 해제, 브라우저 실패 시 수동 접속 안내, 포트 충돌 처리를 추가했습니다. Windows의 `.bat` 및 기본 브라우저 연결은 실기 미검증입니다. **AI/STT 성공 경로 테스트는 테스트 대역을 사용하며 실제 추론 증거가 아닙니다.**
- 2026-10-26 Open-Meteo 실제 API에서 한국어 질문 두 개로 서울 현재값·7일 예보 수신을 확인했습니다. 한국어 지명 검색이 비어 있을 때 영문 도시명으로 재조회합니다. 자세한 업데이트 방법과 검증 범위는 `WEB_SEARCH.md`, `VALIDATION.md`를 참고하세요.
- 실제 서버의 HUD 및 상태 API HTTP 200 확인. 상세 브라우저 결과는 `VALIDATION.md` 참고.
- 이 클라우드에는 Ollama/NVIDIA GPU/실제 마이크/Windows 음성이 없어 실제 AI 답변 품질, 실제 한국어 STT/TTS, 완전 오프라인 통합 및 `.bat` 실행은 미검증입니다. 완료로 간주하지 마세요.

### Windows 인수 검증 체크리스트

1. 위 설치 후 `start.bat` → 브라우저 HUD, Ollama ONLINE 및 모델 설치 YES 확인.
2. 한국어 질문 후 스트리밍 확인 → “첫 번째 제안을 발전시켜 주세요”로 문맥 확인.
3. 마이크 허용 후 한국어 녹음 → 실제 볼륨 구체 반응, 전사, 답변 확인. 권한 거부도 시험.
4. 로컬 한국어 음성 선택 → 실제 발화와 SPEAKING 상태, 재생 중 마이크 잠금 확인. 첫 자동 안내가 브라우저 정책으로 차단되면 사용자 클릭 후 다시 시험.
5. stop/start 후 이전 대화 이어가기, 삭제, 설정 저장, 생성 중지 시험.
6. 인터넷 연결을 해제하고 텍스트 대화·STT·로컬 TTS 재시험.
7. 모델을 설치하지 않은 이름으로 설정했을 때 오류와 해결 안내 확인. Ollama 종료 후 재시작하여 연결 재확인 시험.
8. 3080의 10/12GB 실제 상태와 STT CPU/GPU 장치, 1080p에서 구체와 스트리밍 동시 동작 확인.

## 소스 구성

`app.py` API·정적 제공 / `backend/ai_engine.py` Ollama / `database.py` SQLite / `speech_to_text.py` 로컬 STT / `text_to_speech.py` 향후 로컬 엔진 인터페이스 / `health.py` GPU 조회 / `config.py` 설정 / `frontend/src/sphere.js`, `shaders.js` WebGL / `audio.js` 마이크·TTS / `main.js` UI·채팅 통합 / `windows_launcher.py` 서버 수명 제어 / `tests/test_api.py` API 테스트.
