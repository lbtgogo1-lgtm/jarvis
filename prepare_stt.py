"""Explicit online model preparation. Never called automatically at application startup."""

import argparse
from backend.config import DATA

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download a local Whisper model (Internet required)."
    )
    parser.add_argument(
        "--model",
        choices=["tiny", "base", "small", "medium", "large-v3"],
        default="small",
    )
    args = parser.parse_args()
    print("Downloading explicitly requested STT model:", args.model)
    from faster_whisper.utils import download_model

    download_model(args.model, cache_dir=str(DATA / "models"))
    print("Model cached. Runtime STT uses local_files_only=True.")
