<div align="center">

# ⚡ Commitron

### AI-powered Git commit messages — powered by Google Gemini

[![PyPI version](https://img.shields.io/pypi/v/commitron?color=blue)](https://pypi.org/project/commitron/)
[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/Error404-uv/commitron?style=social)](https://github.com/Error404-uv/commitron)

</div>

---

Never write "fixed stuff" or "final commit v2" again.
**Commitron** reads your `git diff` and writes a clean, professional commit
message for you — right from your terminal.

## 📸 Preview

```text
$ smart-commit

⚡ Smart Git Commit Assistant

Branch: main
╭─── Proposed Commit Messages ───────────────────────────╮
│ 1. feat(auth): add JWT refresh token support            │
│ 2. feat(auth): implement automatic token renewal logic  │
│ 3. fix(auth): handle expired token edge case             │
╰───────────────────────────────────────────────────────╯
Aapka choice [1/2/3/e/c] (1): 1
✅ Commit successfully ho gaya!
```

## ✨ Features

| | |
|---|---|
| 🤖 | AI-generated commit messages from your actual diff |
| 🎨 | Multiple styles — `conventional`, `gitmoji`, `plain` |
| 🔍 | `--dry-run` mode to preview without committing |
| ♻️ | Automatic retry on API hiccups |
| ✏️ | Edit or write your own message before confirming |
| ⚡ | Zero config beyond one API key |

## 📦 Installation

```bash
pip install commitron
```

<details>
<summary>Install from source instead</summary>

```bash
git clone https://github.com/Error404-uv/commitron.git
cd commitron
pip install -e .
```
</details>

## 🔑 Setup

Get a free Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey), then:

```bash
export GEMINI_API_KEY="your_key_here"     # macOS/Linux
set GEMINI_API_KEY=your_key_here          # Windows
```

## 🚀 Usage

```bash
smart-commit
```

| Flag | Description |
|---|---|
| `--dry-run` | Preview the message without committing |
| `--style` | `conventional` (default) · `gitmoji` · `plain` |
| `--count` | Number of message options to generate |
| `-y`, `--yes` | Skip the prompt, commit with the first suggestion |

```bash
smart-commit --style gitmoji --count 5
```

## 🛠️ Requirements

- Python 3.9+
- Git
- A free Gemini API key

## 🤝 Contributing

Issues and PRs are welcome. If something breaks, open an issue with your
Python version and the error output.

## 📄 License

[MIT](LICENSE) — free to use, modify, and share.

---

<div align="center">
Made with ⚡ by <a href="https://github.com/Error404-uv">Error404-uv</a>
</div>
