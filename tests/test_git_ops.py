import os
import subprocess

import pytest

from commitron.git_ops import GitError, commit, ensure_repo, staged_diff


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_staged_diff_and_commit(tmp_path):
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test")
    file = tmp_path / "hello.txt"
    file.write_text("hello", encoding="utf-8")
    git(tmp_path, "add", "hello.txt")
    old = os.getcwd()
    try:
        os.chdir(tmp_path)
        ensure_repo()
        assert "hello" in staged_diff()
        assert commit("test: add hello file").returncode == 0
    finally:
        os.chdir(old)


def test_rejects_non_repository(tmp_path):
    old = os.getcwd()
    try:
        os.chdir(tmp_path)
        with pytest.raises(GitError):
            ensure_repo()
    finally:
        os.chdir(old)


def test_commitron_does_not_stage_unstaged_files(tmp_path, monkeypatch):
    from commitron.cli import main

    git(tmp_path, "init")
    (tmp_path / "notes.txt").write_text("not staged", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main([]) == 1
    assert subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=tmp_path).returncode == 0


def test_git_native_branch_name_validation(tmp_path, monkeypatch):
    from commitron.git_ops import validate_branch_name

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.chdir(tmp_path)
    validate_branch_name("feat/add-login")
    with pytest.raises(GitError):
        validate_branch_name("feat/bad..name")


def test_history_entries_returns_structured_commit_metadata(tmp_path, monkeypatch):
    import subprocess
    from commitron import git_ops

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (tmp_path / "a.txt").write_text("one\n", encoding="utf-8")
    git("add", "a.txt")
    git("commit", "-m", "feat: add first file")
    monkeypatch.chdir(tmp_path)

    entries = git_ops.history_entries(5)
    assert len(entries) == 1
    assert entries[0]["subject"] == "feat: add first file"
    assert entries[0]["date"]
    assert len(entries[0]["hash"]) == 40


def test_history_entries_rejects_invalid_limit():
    import pytest
    from commitron.git_ops import GitError, history_entries

    with pytest.raises(GitError):
        history_entries(0)


@pytest.mark.skipif(
    os.name == "nt",
    reason="NTFS reserves ':'-prefixed names; uncreatable on Windows. "
    "Literal-pathspec behavior is covered cross-platform by "
    "test_git_ops_literal_paths_windows.py.",
)
def test_worktree_changes_includes_untracked_and_preserves_spaces(tmp_path, monkeypatch):
    import subprocess
    from commitron.git_ops import worktree_changes

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "notes with spaces.txt").write_text("draft", encoding="utf-8")
    (tmp_path / ":(top)literal.txt").write_text("literal", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    changes = worktree_changes()
    assert {item["path"] for item in changes} == {"notes with spaces.txt", ":(top)literal.txt"}
    assert all(item["status"] == "??" for item in changes)


@pytest.mark.skipif(
    os.name == "nt",
    reason="NTFS reserves ':'-prefixed names; uncreatable on Windows. "
    "Literal-pathspec behavior is covered cross-platform by "
    "test_git_ops_literal_paths_windows.py.",
)
def test_stage_paths_stages_only_literal_selected_path(tmp_path, monkeypatch):
    import subprocess
    from commitron.git_ops import stage_paths, files_changed

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / ":(top)literal.txt").write_text("selected", encoding="utf-8")
    (tmp_path / "other.txt").write_text("not selected", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    stage_paths([":(top)literal.txt"])
    assert files_changed(staged=True) == [":(top)literal.txt"]
    unstaged = subprocess.run(
        ["git", "status", "--porcelain"], cwd=tmp_path,
        check=True, capture_output=True, text=True,
    ).stdout
    assert "other.txt" in unstaged


def test_create_and_switch_branch_validate_names_before_git_mutation(tmp_path, monkeypatch):
    import subprocess
    from commitron.git_ops import GitError, create_branch, switch_branch

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)
    (tmp_path / "initial.txt").write_text("initial", encoding="utf-8")
    subprocess.run(["git", "add", "initial.txt"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.chdir(tmp_path)
    create_branch("feat/safe-branch")
    with pytest.raises(GitError, match="Invalid branch name"):
        create_branch("--orphan")
    with pytest.raises(GitError, match="Invalid branch name"):
        switch_branch("-c")
    branches = subprocess.run(
        ["git", "branch", "--list"], cwd=tmp_path,
        check=True, capture_output=True, text=True,
    ).stdout
    assert "feat/safe-branch" in branches
    assert "orphan" not in branches
