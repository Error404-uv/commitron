"""Windows-safe literal-pathspec tests.

The original tests used a file named ':(top)literal.txt'. Windows cannot
create such a name at all: NTFS reserves the leading-colon form (parsed as
an alternate data stream), and characters like '*' are illegal in Win32
filenames. The behavior under test -- that commitron stages paths literally
via --literal-pathspecs instead of letting git interpret magic/pathspec
syntax -- still needs coverage on every platform, so this module uses names
that ARE creatable on Windows but would still be misinterpreted without
literal mode:

  '[abc]x.txt' -> a glob character class; naive pathspec matching would
                  also stage ax.txt / bx.txt
  '@(at).txt'  -> resembles the start of a ':(...)attr' magic spec

The exact ':'-prefixed POSIX case stays covered by the skipif-guarded tests
in test_git_ops.py and test_stage_paths_stages_colon_magic_name below
(they run on Linux/macOS CI).
"""
import os
import subprocess

import pytest

from commitron.git_ops import GitError, files_changed, stage_paths, worktree_changes


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def test_worktree_changes_preserves_glob_like_and_spaced_names(tmp_path, monkeypatch):
    git(tmp_path, "init")
    (tmp_path / "notes with spaces.txt").write_text("draft", encoding="utf-8")
    (tmp_path / "[bracket].txt").write_text("literal", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    changes = worktree_changes()
    assert {item["path"] for item in changes} == {
        "notes with spaces.txt",
        "[bracket].txt",
    }
    assert all(item["status"] == "??" for item in changes)


def test_stage_paths_treats_bracket_name_literally(tmp_path, monkeypatch):
    git(tmp_path, "init")
    (tmp_path / "[abc]x.txt").write_text("selected", encoding="utf-8")
    (tmp_path / "ax.txt").write_text("not selected", encoding="utf-8")
    (tmp_path / "bx.txt").write_text("not selected", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    # Without --literal-pathspecs, '[abc]x.txt' is a glob character class
    # and would also match ax.txt/bx.txt.
    stage_paths(["[abc]x.txt"])
    assert files_changed(staged=True) == ["[abc]x.txt"]
    unstaged = git(tmp_path, "status", "--porcelain").stdout
    assert "ax.txt" in unstaged
    assert "bx.txt" in unstaged


def test_stage_paths_stages_only_selected_magic_like_path(tmp_path, monkeypatch):
    git(tmp_path, "init")
    (tmp_path / "@(at).txt").write_text("selected", encoding="utf-8")
    (tmp_path / "other.txt").write_text("not selected", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    stage_paths(["@(at).txt"])
    assert files_changed(staged=True) == ["@(at).txt"]
    unstaged = git(tmp_path, "status", "--porcelain").stdout
    assert "other.txt" in unstaged


def test_rejects_empty_path_list():
    with pytest.raises(GitError):
        stage_paths([])


@pytest.mark.skipif(
    os.name == "nt", reason="NTFS reserves ':'-prefixed names; uncreatable on Windows"
)
def test_stage_paths_stages_colon_magic_name(tmp_path, monkeypatch):
    # On POSIX a file literally named ':(top)literal.txt' is creatable and
    # must be staged as a literal path, not parsed as a magic pathspec.
    git(tmp_path, "init")
    (tmp_path / ":(top)literal.txt").write_text("selected", encoding="utf-8")
    (tmp_path / "other.txt").write_text("not selected", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    stage_paths([":(top)literal.txt"])
    assert files_changed(staged=True) == [":(top)literal.txt"]
    unstaged = git(tmp_path, "status", "--porcelain").stdout
    assert "other.txt" in unstaged
