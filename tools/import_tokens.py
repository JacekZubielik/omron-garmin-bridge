#!/usr/bin/env python3
"""Import/generate Garmin OAuth tokens.

This script helps you generate OAuth tokens for Garmin Connect.
The tokens are saved to data/tokens/ directory.

Usage:
    pdm run python tools/import_tokens.py
"""

import getpass
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from garminconnect import Garmin, GarminConnectAuthenticationError


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("Garmin Connect Token Generator")
    print("=" * 60 + "\n")

    # Get credentials
    email = input("Garmin Connect Email: ").strip()
    if not email:
        print("Email is required")
        sys.exit(1)

    password = getpass.getpass("Garmin Connect Password: ")
    if not password:
        print("Password is required")
        sys.exit(1)

    # Token directory
    tokens_dir = Path("data/tokens")
    tokens_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nTokens will be saved to: {tokens_dir.absolute()}")
    print("\nAuthenticating with Garmin Connect...")

    try:
        # Create Garmin client and login
        garmin = Garmin(email, password)
        garmin.login()

        # Save tokens
        garmin.garth.dump(str(tokens_dir))

        print("\n" + "=" * 60)
        print("SUCCESS! Tokens saved.")
        print("=" * 60)
        print(f"\nToken files created in: {tokens_dir.absolute()}")
        print("\nYou can now run:")
        print("  pdm run python -m src.main sync")

        # Show user info
        try:
            display_name = garmin.display_name
            print(f"\nLogged in as: {display_name}")
        except Exception:  # nosec B110
            pass  # Display name is optional, ignore errors

    except GarminConnectAuthenticationError as e:
        print(f"\nAuthentication failed: {e}")
        print("\nPossible causes:")
        print("  - Wrong email or password")
        print("  - Account requires 2FA (not supported)")
        print("  - Account is locked")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
