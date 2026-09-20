# Security Policy

## ⚠️ Disclaimer

This software automates Twitter (X) interactions using web scraping via `twikit`.
**Use at your own risk.** Automated interactions may violate Twitter's Terms of
Service. The maintainers are not responsible for account suspensions or any
damages from misuse.

**Always use a burner/secondary account, NEVER your primary account.**

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| v4.x    | ✅ Active          |
| v3.x    | ⚠️ Critical fixes only |
| < v3    | ❌ End of life     |

## Reporting a Vulnerability

If you discover a security issue in this project:

1. **DO NOT** open a public issue
2. Open a [GitHub Security Advisory](../../security/advisories/new) (preferred)
3. Or email the maintainers privately (see repo description)

We aim to respond within 7 days.

## Reporting Twitter Account Issues

This bot may cause Twitter to:
- Issue a CAPTCHA challenge
- Suspend your account temporarily (read-only mode)
- Permanently ban your account

If your account is suspended, this is **NOT** a vulnerability in this software -
it's Twitter enforcing its TOS.**

## Best Practices

- ✅ Use a burner account
- ✅ Start with `DRY_RUN = True` for 1-2 days
- ✅ Keep rate limits low (3-5/h for comments)
- ✅ Enable typo injection (less "perfect" output)
- ✅ Use behavior diversity (65% comment, 25% like, 10% follow)
- ✅ Don't run multiple accounts from the same IP simultaneously
- ✅ Don't operate the bot and web client simultaneously
- ❌ Never commit `.env`, `accounts.yaml`, `cookies_*.json`, or `*.db` files