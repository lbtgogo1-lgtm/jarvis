"""Prepare local SearXNG configuration without overwriting a user's existing file."""

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    target = ROOT / "data" / "searxng" / "settings.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        print(
            "Keeping existing data/searxng/settings.yml. Ensure search.formats includes json."
        )
        return
    template = (ROOT / "config/searxng/settings.yml").read_text(encoding="utf-8")
    with target.open("x", encoding="utf-8") as file:
        file.write(template.replace("GENERATE_LOCAL_SECRET", secrets.token_hex(32)))
    # The container runs as an unprivileged user; only this generated config is readable.
    target.chmod(0o644)
    print("Prepared data/searxng/settings.yml with a new local instance secret.")


if __name__ == "__main__":
    main()
