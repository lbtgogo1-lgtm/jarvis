import threading
from .config import DATA

_lock = threading.Lock()
_model = None
_name = None
status = {"loaded": False, "device": None, "error": None}


def transcribe(path, name):
    global _model, _name
    from faster_whisper import WhisperModel

    with _lock:
        try:
            if _model is None or name != _name:
                try:
                    _model = WhisperModel(
                        name,
                        device="cuda",
                        compute_type="float16",
                        download_root=str(DATA / "models"),
                        local_files_only=True,
                    )
                    status["device"] = "cuda"
                    # CUDA libraries may initialize only on first inference.
                    list(_model.transcribe(path, language="ko", vad_filter=True)[0])
                except Exception:
                    _model = WhisperModel(
                        name,
                        device="cpu",
                        compute_type="int8",
                        download_root=str(DATA / "models"),
                        local_files_only=True,
                    )
                    status["device"] = "cpu/int8"
                _name = name
            segments, _ = _model.transcribe(path, language="ko", vad_filter=True)
            text = "".join(s.text for s in segments).strip()
            status.update(loaded=True, error=None)
            return text
        except Exception:
            _model = None
            status.update(
                loaded=False,
                error="STT 모델 또는 CUDA 초기화 실패. README의 모델 준비 절차를 확인하세요.",
            )
            raise
