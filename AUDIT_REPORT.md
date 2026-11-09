# Commitron repository audit and release-candidate reconciliation

Audit date: 2026-11-07

## Scope and evidence

This report separates the public `main` branch observed on GitHub from the locally built release-candidate source tree. The public repository was not modified.

Public repository: https://github.com/Error404-uv/commitron

Observed public `main` at audit time:

| Public file | Finding |
|---|---|
| `.gitignore` | Ignores virtual environments, bytecode, `.env`, egg-info, build, and dist. It does not yet ignore common test/coverage/linter caches. |
| `LICENSE` | MIT License is present with 2026 Error404-uv copyright. |
| `README.md` | Still presents the project as a Gemini-only commit-message generator, documents the old `smart-commit` command, and states Python 3.9+. |
| `requirements.txt` | Contains `google-generativeai` and `rich` without version constraints. |
| `setup.py` | Declares version `0.2.0`, Python `>=3.9`, those two dependencies, and only the `smart-commit` console entry point. |
| `smart_commit.py` | Uses `git add .` after a broad confirmation, truncates diffs to 3,000 characters, and does not check the return code of its diff subprocess helper. Its Gemini request loop catches broad exceptions and retries without an explicit request timeout. |

The public repository page showed one commit and no visible test, CI, or release files at audit time.

Sources:

- Repository listing and README: https://github.com/Error404-uv/commitron
- Original implementation: https://github.com/Error404-uv/commitron/blob/main/smart_commit.py
- Original packaging: https://github.com/Error404-uv/commitron/blob/main/setup.py
- Original dependencies: https://github.com/Error404-uv/commitron/blob/main/requirements.txt

## Reconciliation in this release candidate

The six-file public baseline has now been reviewed file by file. The v1.0.0rc3 working copy contains a modern `src/commitron` package, `pyproject.toml`, a `commitron` console command, test and optional secure-store extras, CI configuration, a test suite, documentation, and the MIT license. The old root `smart_commit.py` has been replaced with a compatibility shim that delegates to the maintained CLI. This prevents the legacy entry point from retaining its separate bulk-staging behavior.

## Additional fixes in rc2

- Branch creation and switching now validate names with Git before executing the command. This rejects option-like names before they can be interpreted as Git flags.
- Custom API base URLs reject whitespace, control characters, query strings, fragments, and invalid ports.
- Provider HTTP redirects are disabled so credentials are not forwarded through an unexpected redirect chain.
- Provider response bodies are limited to 2 MB.
- Mixed OpenAI text/non-text content blocks are parsed without type errors.
- Existing project configuration must be a JSON object before an update is attempted.

## Additional fixes in rc3

- API credentials from environment variables and the optional OS keychain are validated before provider use. Control characters and line breaks are rejected, and credential values are limited to 4,096 characters.
- Keychain values that are not text are rejected rather than passed into HTTP authorization headers.
- README's current Python CI matrix now matches the workflow configuration.

## Verification completed in this environment

- Automated tests: 98 tests pass locally.
- Coverage: 86% line coverage; exceeds the configured 80% threshold.
- Python compilation: passed.
- Wheel build: passed.
- Local sdist build: see release output.
- Ruff could not be run because it is not installed and this environment has no package-index network access.

## Still requiring external verification

- Hosted GitHub Actions matrix on Windows, Linux, and macOS.
- Ruff run in a network-enabled environment.
- `pip-audit` results in CI against current package advisories.
- Live Gemini/OpenAI requests and an Ollama server integration test.
- Native Windows Credential Manager, macOS Keychain, and Linux Secret Service tests.
- Final dependency license compatibility review before publishing.
- Explicit owner approval before any push to GitHub or PyPI publication.

A release candidate is not a stable release until those checks have passed. This archive does not modify the user's GitHub repository or local machine.
