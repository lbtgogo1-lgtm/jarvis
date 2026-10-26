"""Prepare SearXNG; add Naver engines while preserving user settings and secrets."""

import secrets
import shutil
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent


def enable_naver(target):
    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Existing SearXNG settings must be a YAML mapping.")
    defaults = data.get("use_default_settings")
    changed = False
    if isinstance(defaults, dict):
        keep = defaults.get("engines", {}).get("keep_only")
        if isinstance(keep, list):
            for name in ("naver", "naver news"):
                if name not in keep:
                    keep.append(name)
                    changed = True
    engines = data.setdefault("engines", [])
    if not isinstance(engines, list):
        raise ValueError("Existing engines setting must be a list.")
    for name, category in (("naver", "general"), ("naver news", "news")):
        entry = next(
            (
                engine
                for engine in engines
                if isinstance(engine, dict) and engine.get("name") == name
            ),
            None,
        )
        if entry is None:
            engines.append(
                {
                    "name": name,
                    "engine": "naver",
                    "naver_category": category,
                    "categories": [category],
                    "disabled": False,
                }
            )
            changed = True
        elif entry.get("disabled", True):
            entry["disabled"] = False
            changed = True
    if changed:
        backup = target.with_name("settings.before-naver.yml")
        if not backup.exists():
            shutil.copy2(target, backup)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        temporary.chmod(0o644)
        temporary.replace(target)
        print(
            "Enabled Naver engines; other settings and secret retained. Backup: data/searxng/settings.before-naver.yml"
        )
    else:
        print("Keeping existing SearXNG settings; Naver engines already enabled.")


def main():
    target = ROOT / "data" / "searxng" / "settings.yml"
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        enable_naver(target)
        return
    template = (ROOT / "config/searxng/settings.yml").read_text(encoding="utf-8")
    with target.open("x", encoding="utf-8") as file:
        file.write(template.replace("GENERATE_LOCAL_SECRET", secrets.token_hex(32)))
    # The container runs as an unprivileged user; only this generated config is readable.
    target.chmod(0o644)
    print("Prepared data/searxng/settings.yml with a new local instance secret.")


if __name__ == "__main__":
    main()
