"""Browser-local TTS is the default. Future engines can implement synthesize()."""

from typing import Protocol


class LocalTTSEngine(Protocol):
    def synthesize(self, text: str) -> bytes: ...
