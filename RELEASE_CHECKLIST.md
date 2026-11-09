# Commitron 1.0.0 Release Checklist

This checklist separates automated checks from checks that require hosted CI or real external services.

## Automated in the local release-candidate build

- [x] Public `main` baseline reviewed and reconciled in `AUDIT_REPORT.md`.
- [x] Legacy root `smart_commit.py` replaced with a maintained-CLI compatibility shim.
- [x] Git branch create/switch names validated before command execution.
- [x] Custom API URLs reject query strings, fragments, invalid ports, whitespace, and control characters.
- [x] Provider redirects disabled and response body size bounded.
- [x] API credentials reject control characters and values longer than 4,096 characters before storage/use.
- [x] Existing project configuration object validated before update.

- [x] Test suite passes from the repository root.
- [x] Total measured line coverage is at least 80%.
- [x] Python source compiles.
- [x] Source distribution and wheel build successfully.
- [x] Wheel installs into an isolated target directory.
- [x] Installed CLI exposes the expected version and help output.
- [x] ZIP archive integrity is verified.

## Required before stable 1.0.0

- [x] Ruff lint check passes in a network-enabled environment (verified locally on Windows, Python 3.12: `ruff check src tests` clean).
- [ ] Hosted GitHub Actions matrix passes on Windows, Linux, and macOS.
- [ ] Test supported Python versions against the actual runners; remove versions unavailable or unsupported by dependencies.
- [ ] Verify Gemini and OpenAI requests against real test credentials; verify Ollama against a local server.
- [ ] Verify native keychain integration on Windows Credential Manager, macOS Keychain, and supported Linux Secret Service backends. (Windows half now verified: `keyring.backends.Windows.WinVaultKeyring` priority 5 accepted by the backend gate; real set/read/delete round-trip through Credential Manager passed, including correct `False` for deleting a missing entry.)
- [ ] `pip-audit` completes in hosted CI and dependency license compatibility is reviewed.
- [x] Review all six files in the current public GitHub baseline and document differences in `AUDIT_REPORT.md`.
- [x] Correct README Python CI matrix and add v1.0.0rc3 notes.
- [ ] Review README, changelog, examples, and release metadata before stable release.
- [ ] Obtain explicit approval before publishing to PyPI or pushing any repository changes.

A passing local test suite does not prove cross-platform compatibility, provider availability, or native keychain behavior.
