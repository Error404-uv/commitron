#!/usr/bin/env python3
"""
Smart Git Commit Assistant
AI-powered commit message generator using Google Gemini.
"""

import os
import sys
import time
import argparse
import subprocess

import google.generativeai as genai
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

console = Console()

DEFAULT_MODEL = "gemini-1.5-flash"
MAX_DIFF_CHARS = 3000
NUM_OPTIONS = 3
MAX_RETRIES = 2


# --------------------------------------------------------------------------
# Git helpers
# --------------------------------------------------------------------------

def check_git_repo():
    """Check if current directory is a git repository"""
    try:
        subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        console.print(
            "[bold red]❌ Error:[/bold red] Ye folder ek Git repository nahi hai "
            "(ya git installed nahi hai). Pehle 'git init' chalayein."
        )
        sys.exit(1)


def _run_git_diff(staged: bool) -> str:
    cmd = ["git", "diff", "--staged"] if staged else ["git", "diff"]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stdout.strip()


def get_staged_diff() -> str:
    """Get git diff for staged files, offering to stage everything if needed."""
    diff = _run_git_diff(staged=True)

    if not diff:
        unstaged = _run_git_diff(staged=False)

        if unstaged:
            console.print(
                "[yellow]⚠️ Koi staged changes nahi mile. "
                "Kya aap saare changes stage (`git add .`) karna chahte hain?[/yellow]"
            )
            if Confirm.ask("Stage all changes?"):
                subprocess.run(["git", "add", "."])
                diff = _run_git_diff(staged=True)
            else:
                console.print("[red]Commit cancel kar diya gaya.[/red]")
                sys.exit(0)
        else:
            console.print("[bold yellow]ℹ️ Koi code changes detect nahi hue![/bold yellow]")
            sys.exit(0)

    return diff


def get_current_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return result.stdout.strip() or "unknown"


# --------------------------------------------------------------------------
# AI generation
# --------------------------------------------------------------------------

def build_prompt(diff_text: str, num_options: int, style: str) -> str:
    truncated = diff_text[:MAX_DIFF_CHARS]

    style_rules = {
        "conventional": (
            "Format: <type>(<scope>): <short summary>\n"
            "Types: feat, fix, docs, style, refactor, test, chore, perf"
        ),
        "gitmoji": (
            "Format: <emoji> <short summary>\n"
            "Use a relevant gitmoji (e.g. ✨ for feature, 🐛 for fix, 📝 for docs, "
            "♻️ for refactor, 🔥 for removing code, ✅ for tests)"
        ),
        "plain": "Format: <short, plain-English summary>. No prefixes or emojis.",
    }

    return f"""
You are an expert software engineer. Based on the following git diff, generate
{num_options} different single-line commit message options.

Rules:
- {style_rules.get(style, style_rules["conventional"])}
- Each option must be a complete, standalone commit message.
- Do NOT wrap messages in quotes, backticks, or numbers.
- Maximum 72 characters per message where possible.
- Output ONLY the {num_options} messages, one per line, nothing else.

Git Diff:
{truncated}
"""


def generate_commit_messages(diff_text: str, num_options: int = NUM_OPTIONS, style: str = "conventional"):
    """Generate one or more commit message candidates using Gemini API."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        console.print("[bold red]❌ Error:[/bold red] GEMINI_API_KEY environment variable set nahi hai!")
        console.print(
            "Set karein: [green]export GEMINI_API_KEY='your_key'[/green] "
            "ya Windows me [green]set GEMINI_API_KEY=your_key[/green]"
        )
        sys.exit(1)

    genai.configure(api_key=api_key)

    if len(diff_text) > MAX_DIFF_CHARS:
        console.print(
            f"[yellow]⚠️ Diff bahut bada hai ({len(diff_text)} chars). "
            f"Sirf pehle {MAX_DIFF_CHARS} characters AI ko bheje ja rahe hain.[/yellow]"
        )

    prompt = build_prompt(diff_text, num_options, style)
    model = genai.GenerativeModel(DEFAULT_MODEL)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 2):  # initial try + retries
        try:
            with console.status("[bold green]🤖 AI commit message generate kar raha hai...[/bold green]"):
                response = model.generate_content(prompt)
                raw = response.text.strip()

            lines = [
                line.strip().strip("`").strip('"').lstrip("-•").strip()
                for line in raw.splitlines()
                if line.strip()
            ]
            lines = [l for l in lines if l][:num_options]

            if not lines:
                raise ValueError("Empty response from model")

            return lines

        except Exception as e:  # noqa: BLE001
            last_error = e
            if attempt <= MAX_RETRIES:
                console.print(f"[yellow]⚠️ Attempt {attempt} fail ho gaya, retry kar rahe hain...[/yellow]")
                time.sleep(1.5 * attempt)
            else:
                console.print(f"[bold red]❌ AI Error:[/bold red] {last_error}")
                sys.exit(1)


# --------------------------------------------------------------------------
# Commit
# --------------------------------------------------------------------------

def do_commit(message: str) -> bool:
    result = subprocess.run(
        ["git", "commit", "-m", message],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if result.returncode == 0:
        console.print("[bold green]✅ Commit successfully ho gaya![/bold green]\n")
        return True
    else:
        console.print(f"[bold red]❌ Commit fail ho gaya:[/bold red]\n{result.stderr.strip()}\n")
        return False


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        prog="smart-commit",
        description="AI-powered Git commit message generator (Gemini).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Sirf commit message dikhao, actually commit mat karo.",
    )
    parser.add_argument(
        "--style", choices=["conventional", "gitmoji", "plain"], default="conventional",
        help="Commit message style (default: conventional).",
    )
    parser.add_argument(
        "--count", type=int, default=NUM_OPTIONS,
        help=f"Kitne commit message options generate karne hain (default: {NUM_OPTIONS}).",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true",
        help="Pehla suggestion bina poochhe commit kar do.",
    )
    return parser.parse_args()


def choose_message(options: list[str]) -> str | None:
    """Show options and let user pick one, edit one, or cancel."""
    panel_lines = "\n".join(f"[bold cyan]{i+1}.[/bold cyan] {msg}" for i, msg in enumerate(options))
    console.print(Panel(panel_lines, title="Proposed Commit Messages", border_style="cyan"))

    choices = [str(i + 1) for i in range(len(options))] + ["e", "c"]
    console.print("[dim]Number chuno, 'e' custom message likhne ke liye, ya 'c' cancel karne ke liye[/dim]")
    pick = Prompt.ask("Aapka choice", choices=choices, default="1")

    if pick == "c":
        return None
    if pick == "e":
        return Prompt.ask("Apna commit message likhein")
    return options[int(pick) - 1]


def main():
    args = parse_args()

    console.print("\n[bold cyan]⚡ Smart Git Commit Assistant[/bold cyan]\n")

    check_git_repo()
    diff = get_staged_diff()
    branch = get_current_branch()
    console.print(f"[dim]Branch: {branch}[/dim]")

    options = generate_commit_messages(diff, num_options=max(1, args.count), style=args.style)

    if args.yes:
        commit_msg = options[0]
        console.print(Panel(f"[bold green]{commit_msg}[/bold green]", title="Commit Message", border_style="cyan"))
    else:
        commit_msg = choose_message(options)
        if commit_msg is None:
            console.print("[yellow]❌ Commit cancel kar diya gaya.[/yellow]\n")
            sys.exit(0)

    if args.dry_run:
        console.print("[bold blue]🔎 Dry run mode:[/bold blue] koi commit nahi banaya gaya.")
        console.print(Panel(commit_msg, title="Final Message (preview)", border_style="blue"))
        return

    if args.yes or Confirm.ask("\nIs message ke sath commit karein?"):
        do_commit(commit_msg)
    else:
        console.print("[yellow]❌ Commit cancel kar diya gaya.[/yellow]\n")


if __name__ == "__main__":
    main()
