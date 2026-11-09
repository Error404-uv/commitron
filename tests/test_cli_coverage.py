"""CLI edge-path tests: error limits, secret warnings, cancellation, and failure handling."""
import subprocess

from commitron import cli

SECRET_BODY = "GEMINI_API_KEY=AIzaSyD0123456789abcdefghijklmnopqrstuv\n"


def git(cwd, *args, check=True):
    return subprocess.run(["git", *args], cwd=str(cwd), check=check,
                          capture_output=True, text=True)


def make_repo(tmp_path, monkeypatch, files=None, stage_all=True):
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "test@example.com")
    git(tmp_path, "config", "user.name", "Test")
    for name, body in (files or {"hello.txt": "hello\n"}).items():
        (tmp_path / name).write_text(body, encoding="utf-8")
    if stage_all:
        git(tmp_path, "add", "--", *sorted(files or {"hello.txt": ""}))
    monkeypatch.chdir(tmp_path)


# --- commit command guards ---------------------------------------------------

def test_commit_rejects_out_of_range_count(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch)
    assert cli.main(["commit", "--count", "9"]) == 2
    assert "between 1 and 5" in capsys.readouterr().out


def test_commit_stops_on_empty_diff_without_calling_ai(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch, stage_all=False)
    called = []
    monkeypatch.setattr(cli, "generate_messages", lambda *a: called.append(1))
    assert cli.main(["commit"]) == 1
    output = capsys.readouterr().out
    assert "No staged changes" in output and not called


def test_commit_blocks_oversized_diff_before_sending_anything(tmp_path, monkeypatch, capsys):
    # Build a staged diff that exceeds MAX_DIFF_CHUNKS with unique hunks.
    make_repo(tmp_path, monkeypatch, {"big.txt": "seed\n"})
    git(tmp_path, "commit", "-m", "seed")
    (tmp_path / "big.txt").write_text(
        "".join(f"line {i}\n{'x' * 300}\n" for i in range(4000)), encoding="utf-8")
    git(tmp_path, "add", "big.txt")
    called = []
    monkeypatch.setattr(cli, "generate_messages", lambda *a: called.append(1))
    assert cli.main(["commit"]) == 1
    assert "safe processing limit" in capsys.readouterr().out and not called


def test_commit_secret_warning_cancel_sends_nothing(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch, {"leak.txt": SECRET_BODY})
    monkeypatch.setattr(cli.Confirm, "ask", lambda *a, **k: False)
    called = []
    monkeypatch.setattr(cli, "generate_messages", lambda *a: called.append(1))
    assert cli.main(["commit"]) == 1
    output = capsys.readouterr().out
    assert "Possible sensitive content detected" in output and not called


def test_commit_allow_secrets_flag_skips_prompt_and_edits_choice(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch, {"leak.txt": SECRET_BODY})
    monkeypatch.setattr(cli, "generate_messages", lambda *a: ["feat: one", "fix: two"])
    answers = iter(["2"])
    monkeypatch.setattr(cli.Prompt, "ask", lambda *a, **k: next(answers))
    monkeypatch.setattr(cli.Confirm, "ask", lambda *a, **k: True)
    assert cli.main(["commit", "--allow-secrets", "--count", "2"]) == 0
    log = git(tmp_path, "log", "-1", "--pretty=%s")
    assert log.stdout.strip() == "fix: two"


def test_commit_ai_error_is_reported_cleanly(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch)
    def boom(*a):
        raise cli.AIError("provider exploded")
    monkeypatch.setattr(cli, "generate_messages", boom)
    assert cli.main(["commit", "--yes", "--count", "1"]) == 1
    assert "AI error: provider exploded" in capsys.readouterr().out


def test_commit_cancel_after_options_leaves_no_commit(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "generate_messages", lambda *a: ["feat: only"])
    monkeypatch.setattr(cli.Prompt, "ask", lambda *a, **k: "c")
    assert cli.main(["commit", "--count", "1"]) == 0
    assert "Cancelled." in capsys.readouterr().out
    log = git(tmp_path, "log", "--pretty=%s", check=False)
    assert "feat: only" not in log.stdout


# --- explain ------------------------------------------------------------------

def test_explain_requires_changes(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch, stage_all=False)
    assert cli.main(["explain"]) == 1
    assert "No matching changes" in capsys.readouterr().out


def test_explain_secret_warning_cancel_sends_nothing(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch, {"s.txt": SECRET_BODY})
    monkeypatch.setattr(cli.Confirm, "ask", lambda *a, **k: False)
    called = []
    monkeypatch.setattr(cli, "explain_changes", lambda *a: called.append(1))
    assert cli.main(["explain"]) == 1
    assert "Possible sensitive content detected" in capsys.readouterr().out and not called


def test_explain_prints_provider_explanation(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(cli, "explain_changes", lambda diff: "Adds the greeting file.")
    assert cli.main(["explain"]) == 0
    assert "Adds the greeting file." in capsys.readouterr().out


# --- history ------------------------------------------------------------------

def test_history_plain_lists_commits(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch)
    git(tmp_path, "commit", "-m", "seed: hello")
    assert cli.main(["history"]) == 0
    assert "seed: hello" in capsys.readouterr().out


def test_history_analyze_cancel_sends_no_data(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch)
    git(tmp_path, "commit", "-m", "seed: hello")
    monkeypatch.setattr(cli.Confirm, "ask", lambda *a, **k: False)
    called = []
    monkeypatch.setattr(cli, "summarize_history", lambda *a: called.append(1))
    assert cli.main(["history", "--analyze"]) == 0
    assert "Cancelled. No data was sent." in capsys.readouterr().out and not called


def test_history_analyze_fails_cleanly_without_commits(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch)  # no commits yet -> git log exits non-zero
    assert cli.main(["history", "--analyze"]) == 1
    assert "Git error" in capsys.readouterr().out


# --- git-help -----------------------------------------------------------------

def test_git_help_cancel_and_confirm_paths(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch)
    monkeypatch.setattr(cli.Confirm, "ask", lambda *a, **k: False)
    assert cli.main(["git-help", "--error", "fatal: bad object"]) == 0
    assert "Cancelled. No data was sent." in capsys.readouterr().out
    monkeypatch.setattr(cli.Confirm, "ask", lambda *a, **k: True)
    monkeypatch.setattr(cli, "explain_git_error", lambda e, c: "Run git fsck to inspect objects.")
    assert cli.main(["git-help", "--error", "fatal: bad object"]) == 0
    assert "git fsck" in capsys.readouterr().out


# --- branch -------------------------------------------------------------------

def test_branch_list_create_switch_via_cli(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch)
    git(tmp_path, "commit", "-m", "seed")
    assert cli.main(["branch"]) == 0
    monkeypatch.setattr(cli, "create_branch", lambda name: None)
    monkeypatch.setattr(cli, "switch_branch", lambda name: None)
    assert cli.main(["branch", "create", "feat/x"]) == 0
    assert "Created and switched to feat/x" in capsys.readouterr().out
    assert cli.main(["branch", "switch", "main"]) == 0
    assert "Switched to main" in capsys.readouterr().out


def test_branch_suggest_secret_context_cancel(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch)
    answers = iter([True])  # first Confirm: send description+branches; then secrets -> cancel
    monkeypatch.setattr(cli.Confirm, "ask", lambda *a, **k: next(answers, False))
    called = []
    monkeypatch.setattr(cli, "suggest_branch_name", lambda d, e: called.append(1))
    assert cli.main(["branch", "suggest", "--description",
                     "client_secret=AIzaSyD0123456789abcdefghijklmnopqrstuv fix auth"]) == 1
    assert "Possible sensitive content detected" in capsys.readouterr().out and not called


# --- split --------------------------------------------------------------------

def test_split_needs_two_files(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch)
    assert cli.main(["split"]) == 1
    assert "at least two tracked files" in capsys.readouterr().out


def test_split_ai_error_reported(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch, {"a.py": "a\n", "b.py": "b\n"})
    monkeypatch.setattr(cli.Confirm, "ask", lambda *a, **k: True)
    def boom(*a):
        raise cli.AIError("grouping failed")
    monkeypatch.setattr(cli, "suggest_logical_commits", boom)
    assert cli.main(["split"]) == 1
    assert "AI error: grouping failed" in capsys.readouterr().out


# --- status / diff / files ------------------------------------------------------

def test_status_diff_files_commands(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch)
    assert cli.main(["status"]) == 0
    assert cli.main(["diff"]) == 0
    assert cli.main(["diff", "--stat"]) == 0
    assert cli.main(["files"]) == 0
    assert "hello.txt" in capsys.readouterr().out


# --- config profile delete + convention clear ----------------------------------

def test_config_profile_delete_cancel(tmp_path, monkeypatch, capsys):
    from commitron import config
    monkeypatch.setattr(config, "profiles_path", lambda: tmp_path / "profiles.json")
    monkeypatch.setattr(cli.Confirm, "ask", lambda *a, **k: False)
    assert cli.main(["config", "profile", "delete", "work"]) == 0
    assert "Cancelled." in capsys.readouterr().out


def test_convention_clear_removes_value(tmp_path, monkeypatch, capsys):
    make_repo(tmp_path, monkeypatch)
    assert cli.main(["convention", "set", "Use ticket IDs"]) == 0
    assert cli.main(["convention", "show"]) == 0
    assert "Use ticket IDs" in capsys.readouterr().out
    assert cli.main(["convention", "clear"]) == 0
    assert "Removed repository-specific commit convention" in capsys.readouterr().out


# --- top-level exception handlers ----------------------------------------------

def test_main_handles_keyboard_interrupt(monkeypatch, capsys):
    monkeypatch.setattr(cli, "ensure_repo", lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert cli.main(["status"]) == 130


def test_main_handles_closed_stdin(monkeypatch, capsys):
    monkeypatch.setattr(cli, "ensure_repo", lambda: (_ for _ in ()).throw(EOFError()))
    assert cli.main(["status"]) == 130


def test_module_entrypoint_runs():
    import sys
    result = subprocess.run(
        [sys.executable, "-m", "commitron", "--version"],
        capture_output=True, text=True, check=True)
    assert result.stdout.strip()
