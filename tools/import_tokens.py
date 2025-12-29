#!/usr/bin/env python3
"""Import/generate Garmin OAuth tokens.

This script helps you generate OAuth tokens for Garmin Connect.
The tokens are saved to data/tokens/<email>/ directory for multi-user support.

Usage:
    pdm run python tools/import_tokens.py
    pdm run python tools/import_tokens.py --email user@example.com
"""

import argparse
import getpass
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from garminconnect import Garmin, GarminConnectAuthenticationError


def email_to_folder(email: str) -> str:
    """Convert email to safe folder name.

    Args:
        email: Email address

    Returns:
        Safe folder name (@ replaced with _at_)
    """
    return email.replace("@", "_at_")


def generate_tokens(email: str, password: str, base_tokens_dir: Path) -> bool:
    """Generate and save OAuth tokens for a Garmin account.

    Args:
        email: Garmin Connect email
        password: Garmin Connect password
        base_tokens_dir: Base directory for token storage

    Returns:
        True if successful
    """
    # Create user-specific token directory
    user_tokens_dir = base_tokens_dir / email_to_folder(email)
    user_tokens_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nTokens will be saved to: {user_tokens_dir.absolute()}")
    print("\nAuthenticating with Garmin Connect...")

    try:
        # Create Garmin client and login
        garmin = Garmin(email, password)
        garmin.login()

        # Save tokens to user-specific directory
        garmin.garth.dump(str(user_tokens_dir))

        print("\n" + "=" * 60)
        print("SUCCESS! Tokens saved.")
        print("=" * 60)
        print(f"\nToken files created in: {user_tokens_dir.absolute()}")

        # Show user info
        try:
            display_name = garmin.display_name
            print(f"Logged in as: {display_name}")
        except Exception:  # nosec B110
            pass  # Display name is optional, ignore errors

        return True

    except GarminConnectAuthenticationError as e:
        print(f"\nAuthentication failed: {e}")
        print("\nPossible causes:")
        print("  - Wrong email or password")
        print("  - Account requires 2FA (not supported)")
        print("  - Account is locked")
        return False
    except Exception as e:
        print(f"\nError: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate Garmin Connect OAuth tokens",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  pdm run python tools/import_tokens.py
  pdm run python tools/import_tokens.py --email user@example.com
  pdm run python tools/import_tokens.py --email user1@example.com --email user2@example.com
        """,
    )
    parser.add_argument(
        "--email",
        action="append",
        help="Garmin Connect email (can be specified multiple times)",
    )
    parser.add_argument(
        "--tokens-dir",
        default="data/tokens",
        help="Base directory for token storage (default: data/tokens)",
    )

    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("Garmin Connect Token Generator")
    print("=" * 60 + "\n")

    base_tokens_dir = Path(args.tokens_dir)
    base_tokens_dir.mkdir(parents=True, exist_ok=True)

    emails = args.email or []

    # If no emails provided, prompt for one
    if not emails:
        email = input("Garmin Connect Email: ").strip()
        if not email:
            print("Email is required")
            sys.exit(1)
        emails = [email]

    success_count = 0
    for email in emails:
        print(f"\n--- Processing: {email} ---")

        password = getpass.getpass(f"Password for {email}: ")
        if not password:
            print("Password is required, skipping...")
            continue

        if generate_tokens(email, password, base_tokens_dir):
            success_count += 1

    print("\n" + "=" * 60)
    print(f"Completed: {success_count}/{len(emails)} accounts")
    print("=" * 60)

    if success_count > 0:
        print("\nYou can now run:")
        print("  pdm run python -m src.main sync")

    sys.exit(0 if success_count == len(emails) else 1)


if __name__ == "__main__":
    main()
