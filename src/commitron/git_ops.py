"""Git operations. All subprocess calls use argument arrays (never a shell)."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import List


class GitError(RuntimeError):
    """Raised when a Git command fails."""


@dataclass
class GitResult:
    stdout: str
    stderr: str
    returncode: int


def run_git(*args: str, check: bool = True) -> GitResult:
    try:
        proc = subprocess.run(
            ["git", *args], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=30, check=False,
        )
    except FileNotFoundError as exc:
        raise GitError("Git executable was not found. Install Git and ensure it is on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("Git command timed out after 30 seconds.") from exc
    result = GitResult(proc.stdout, proc.stderr, proc.returncode)
    if check and proc.returncode:
        detail = proc.stderr.strip() or proc.stdout.strip() or "Unknown Git error"
        raise GitError(detail)
    return result


def ensure_repo() -> None:
    run_git("rev-parse", "--is-inside-work-tree")


def staged_diff() -> str:
    return run_git("diff", "--cached", "--no-ext-diff", "--no-color").stdout


def unstaged_diff() -> str:
    return run_git("diff", "--no-ext-diff", "--no-color").stdout


def diff_stat(staged: bool = True) -> str:
    args = ["diff"]
    if staged:
        args.append("--cached")
    args.extend(["--stat", "--no-ext-diff"])
    return run_git(*args).stdout


def files_changed(staged: bool = True) -> List[str]:
    args = ["diff"]
    if staged:
        args.append("--cached")
    args.extend(["--name-only", "-z"])
    output = run_git(*args).stdout
    return [name for name in output.split("\0") if name]


def status_porcelain() -> str:
    return run_git("status", "--short", "--branch").stdout


def current_branch() -> str:
    result = run_git("branch", "--show-current", check=False)
    if result.returncode:
        raise GitError(result.stderr.strip() or "Could not determine current branch")
    return result.stdout.strip() or "(detached HEAD)"


def history(limit: int = 10) -> str:
    return run_git("log", f"-{limit}", "--date=short", "--pretty=format:%h %ad %s").stdout


def branches() -> str:
    return run_git("branch", "--list", "--no-color").stdout


def create_branch(name: str) -> None:
    validate_branch_name(name)
    run_git("switch", "-c", name)


def switch_branch(name: str) -> None:
    validate_branch_name(name)
    run_git("switch", name)


def commit(message: str) -> GitResult:
    if not message.strip():
        raise GitError("Commit message cannot be empty")
    return run_git("commit", "-m", message, check=False)


def changed_files() -> List[str]:
    output = run_git("diff", "--cached", "--name-only", "-z").stdout
    return [name for name in output.split("\0") if name]


def repository_root() -> str:
    """Return the absolute root directory of the current Git repository."""
    result = run_git("rev-parse", "--show-toplevel")
    root = result.stdout.strip()
    if not root:
        raise GitError("Could not determine the Git repository root.")
    return root

def validate_branch_name(name: str) -> None:
    """Raise GitError when a proposed branch name is not valid for Git."""
    if not name or name.startswith("-") or any(ord(char) < 32 or ord(char) == 127 for char in name):
        raise GitError("Invalid branch name returned by the AI provider.")
    result = run_git("check-ref-format", "--branch", name, check=False)
    if result.returncode:
        raise GitError("AI suggested an invalid Git branch name: {}".format(name))


def history_entries(limit: int = 20) -> List[dict]:
    """Return structured recent commit metadata without invoking a shell."""
    if not 1 <= limit <= 100:
        raise GitError("History limit must be between 1 and 100.")
    fmt = "%H%x00%ad%x00%s%x00%b%x1e"
    output = run_git(
        "log", "-{}".format(limit), "--date=short", "--no-show-signature",
        "--pretty=format:" + fmt,
    ).stdout
    entries = []
    for record in output.split("\x1e"):
        record = record.strip("\r\n")
        if not record:
            continue
        fields = record.split("\x00", 3)
        if len(fields) != 4:
            raise GitError("Git returned an unexpected history record format.")
        commit_hash, date, subject, body = fields
        entries.append({
            "hash": commit_hash.strip(),
            "date": date.strip(),
            "subject": subject.strip(),
            "body": body.strip(),
        })
    return entries


def worktree_changes() -> List[dict]:
    """Return staged, unstaged, and untracked paths using NUL-delimited status.

    Rename detection is disabled so each status record has one unambiguous path.
    """
    output = run_git(
        "status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames"
    ).stdout
    changes = []
    for record in output.split("\0"):
        if not record:
            continue
        if len(record) < 4 or record[2] != " ":
            raise GitError("Git returned an unexpected status record.")
        changes.append({"status": record[:2], "path": record[3:]})
    return changes


def stage_paths(paths: List[str]) -> GitResult:
    """Stage only explicitly supplied paths, treating them as literal pathspecs."""
    if not paths:
        raise GitError("Select at least one path to stage.")
    if any(not isinstance(path, str) or not path or "\0" in path for path in paths):
        raise GitError("A selected path is invalid.")
    unique_paths = list(dict.fromkeys(paths))
    return run_git("--literal-pathspecs", "add", "--", *unique_paths)
