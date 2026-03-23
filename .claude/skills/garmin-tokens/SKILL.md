---
name: garmin-tokens
description: >-
  This skill should be used when the user asks to "check tokens", "regenerate tokens",
  "token status", "garmin login", "fix garmin auth", "import tokens", "list tokens",
  "garmin authentication", "token expired", or mentions Garmin OAuth token management.
---

# Garmin Token Management

Manage Garmin Connect OAuth tokens for multi-user blood pressure sync.

## Token Architecture

Garmin Connect uses OAuth1 + OAuth2 tokens stored per-user:

```
data/tokens/
├── user1_at_example.com/
│   ├── oauth1_token.json
│   └── oauth2_token.json
└── user2_at_example.com/
    ├── oauth1_token.json
    └── oauth2_token.json
```

Email-to-folder mapping: `@` → `_at_` (e.g., `user@example.com` → `user_at_example.com`)

## Check Token Status

Use the status script to verify all configured tokens:

```bash
pdm run python scripts/check_tokens.py
```

This checks:
- Token directory exists for each configured user
- OAuth1 and OAuth2 files present
- Token validates against Garmin API (login attempt)
- Display name returned on success

## Generate New Tokens

### Via CLI tool

```bash
pdm run python tools/import_tokens.py --email user@example.com
```

Interactive process — opens Garmin SSO login. Tokens saved to `data/tokens/<email>/`.

### Via Streamlit UI

Navigate to **Settings** page → **Garmin Tokens** section → **Generate Tokens** button.

## Token Lifecycle

- Tokens are valid for approximately **1 year**
- `garminconnect` library handles automatic refresh transparently
- If refresh fails → `GarminConnectAuthenticationError` → regenerate tokens

## Configuration Mapping

`config/config.yaml` maps OMRON user slots to Garmin accounts:

```yaml
users:
  - name: "User1"
    omron_slot: 1
    garmin_email: "user1@example.com"
    garmin_enabled: true
```

The `garmin_email` field determines which token directory to load.

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `FileNotFoundError: Token directory not found` | Missing tokens | Run `import_tokens.py` |
| `GarminConnectAuthenticationError` | Expired/invalid tokens | Regenerate tokens |
| `Authentication failed` after token present | Corrupt token files | Delete dir, regenerate |
| Wrong user data in Garmin | `omron_slot` mismatch | Verify slot mapping in config |

## Scripts

- **`scripts/check_tokens.py`** — Verify token status for all configured users
