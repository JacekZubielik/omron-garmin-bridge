#!/usr/bin/env python3
"""Check Garmin OAuth token status for all configured users."""

import sys
from pathlib import Path


def _find_project_root() -> Path:
    """Walk up from script to find pyproject.toml."""
    p = Path(__file__).resolve().parent
    for _ in range(10):
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    raise RuntimeError("Could not find project root (no pyproject.toml)")


project_root = _find_project_root()
sys.path.insert(0, str(project_root))

import yaml  # noqa: E402

from src.garmin_uploader import get_token_status, list_available_tokens  # noqa: E402


def main():
    config_path = project_root / "config" / "config.yaml"
    if not config_path.exists():
        print("ERROR: config/config.yaml not found")
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    tokens_path = Path(config.get("garmin", {}).get("tokens_path", "./data/tokens"))
    if not tokens_path.is_absolute():
        tokens_path = project_root / tokens_path

    print(f"Tokens directory: {tokens_path}")
    print()

    # Check configured users
    users = config.get("users", [])
    if not users:
        print("WARNING: No users configured in config.yaml")

    for user in users:
        name = user.get("name", "Unknown")
        email = user.get("garmin_email", "")
        slot = user.get("omron_slot", "?")
        enabled = user.get("garmin_enabled", False)

        print(f"User: {name} (slot {slot}, garmin={'ON' if enabled else 'OFF'})")

        if not email:
            print("  No garmin_email configured")
            print()
            continue

        status = get_token_status(tokens_path, email)
        if status["valid"]:
            print(f"  Email: {email}")
            print("  Status: VALID")
            print(f"  Display name: {status['display_name']}")
        elif status["exists"]:
            print(f"  Email: {email}")
            print(f"  Status: INVALID — {status['error']}")
            print(f"  Fix: pdm run python tools/import_tokens.py --email {email}")
        else:
            print(f"  Email: {email}")
            print(f"  Status: MISSING — {status['error']}")
            print(f"  Fix: pdm run python tools/import_tokens.py --email {email}")
        print()

    # List any extra token dirs not in config
    all_tokens = list_available_tokens(tokens_path)
    configured_emails = {u.get("garmin_email", "") for u in users}
    extra = [t for t in all_tokens if t.get("email") not in configured_emails]

    if extra:
        print("Extra token directories (not in config):")
        for t in extra:
            print(f"  {t['email']} — {'valid' if t['valid'] else t.get('error', 'unknown')}")


if __name__ == "__main__":
    main()
