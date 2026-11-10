from commitron.cli import _parser


def test_parser_supports_explain_and_provider_config():
    parser = _parser()
    args = parser.parse_args(["explain", "--unstaged"])
    assert args.command == "explain" and args.unstaged
    args = parser.parse_args(["config", "set", "provider", "openai"])
    assert args.command == "config"
    assert args.key == "provider" and args.value == "openai"


def test_config_show_does_not_require_git_repository(tmp_path, monkeypatch):
    from commitron import cli

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "config_path", lambda: tmp_path / "config.json")
    monkeypatch.setattr(cli, "load_config", lambda: {"provider": "gemini", "model": "", "base_url": ""})
    assert cli.main(["config", "show"]) == 0


def test_dry_run_does_not_commit_and_ai_markup_is_literal(tmp_path, monkeypatch, capsys):
    import subprocess
    from commitron import cli

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (tmp_path / "hello.txt").write_text("hello\n", encoding="utf-8")
    git("add", "hello.txt")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "generate_messages", lambda *args: ["fix: display [red] as text"])

    assert cli.main(["commit", "--dry-run", "--yes", "--count", "1"]) == 0
    output = capsys.readouterr().out
    assert "fix: display [red] as text" in output
    log = subprocess.run(["git", "log", "-1", "--oneline"], cwd=tmp_path, capture_output=True)
    assert log.returncode != 0


def test_parser_supports_new_v050_commands():
    parser = _parser()
    args = parser.parse_args(["branch", "suggest", "--description", "Add OAuth login"])
    assert args.command == "branch" and args.action == "suggest"
    args = parser.parse_args(["split", "--style", "plain"])
    assert args.command == "split" and args.style == "plain"
    args = parser.parse_args(["convention", "set", "Use ticket IDs"])
    assert args.command == "convention" and args.text == "Use ticket IDs"

def test_branch_suggest_does_not_create_branch(tmp_path, monkeypatch, capsys):
    import subprocess
    from commitron import cli

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "suggest_branch_name", lambda description, existing: "feat/add-oauth")
    monkeypatch.setattr(cli.Confirm, "ask", lambda *args, **kwargs: True)

    assert cli.main(["branch", "suggest", "--description", "Add OAuth login"]) == 0
    output = capsys.readouterr().out
    assert "feat/add-oauth" in output
    branches = subprocess.run(["git", "branch", "--list"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout
    assert "feat/add-oauth" not in branches

def test_split_command_only_suggests_and_does_not_change_index(tmp_path, monkeypatch, capsys):
    import subprocess
    from commitron import cli

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (tmp_path / "app.py").write_text("print('app')\n", encoding="utf-8")
    (tmp_path / "test_app.py").write_text("def test_app(): pass\n", encoding="utf-8")
    git("add", "app.py", "test_app.py")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "suggest_logical_commits", lambda *args: [
        {"message": "feat: add app", "reason": "Adds application code.", "files": ["app.py"]},
        {"message": "test: test app", "reason": "Adds tests.", "files": ["test_app.py"]},
    ])

    assert cli.main(["split"]) == 0
    output = capsys.readouterr().out
    assert "Suggestions only" in output
    cached = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=tmp_path, capture_output=True, text=True, check=True).stdout.splitlines()
    assert sorted(cached) == ["app.py", "test_app.py"]
    log = subprocess.run(["git", "log", "-1", "--oneline"], cwd=tmp_path, capture_output=True)
    assert log.returncode != 0


def test_repository_convention_command_writes_only_project_config(tmp_path, monkeypatch, capsys):
    import subprocess
    from commitron import cli

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["convention", "set", "Use ticket IDs in commit subjects"]) == 0
    config_path = tmp_path / ".commitron.json"
    assert config_path.exists()
    assert "Use ticket IDs" in config_path.read_text(encoding="utf-8")
    assert cli.main(["convention", "show"]) == 0
    assert "Use ticket IDs" in capsys.readouterr().out


def test_commit_uses_repository_specific_convention(tmp_path, monkeypatch):
    import subprocess
    from commitron import cli

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")
    (tmp_path / "app.py").write_text("print('app')\n", encoding="utf-8")
    git("add", "app.py")
    (tmp_path / ".commitron.json").write_text(
        '{"commit_convention":"Use ticket ID then imperative summary."}', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    received = {}

    def fake_generate(diff, count, style, convention):
        received["convention"] = convention
        return ["ABC-10 add application output"]

    monkeypatch.setattr(cli, "generate_messages", fake_generate)
    assert cli.main(["commit", "--dry-run", "--yes", "--count", "1"]) == 0
    assert received["convention"] == "Use ticket ID then imperative summary."
    log = subprocess.run(["git", "log", "-1", "--oneline"], cwd=tmp_path, capture_output=True)
    assert log.returncode != 0

def test_commit_secret_warning_can_cancel_before_ai_request(tmp_path, monkeypatch):
    import subprocess
    from commitron import cli

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init")
    (tmp_path / "config.txt").write_text("password=very-secret-value-123\n", encoding="utf-8")
    git("add", "config.txt")
    monkeypatch.chdir(tmp_path)
    called = {"ai": False}

    def unexpected_ai(*args, **kwargs):
        called["ai"] = True
        raise AssertionError("AI must not receive the diff after cancellation")

    monkeypatch.setattr(cli, "generate_messages", unexpected_ai)
    monkeypatch.setattr(cli.Confirm, "ask", lambda *args, **kwargs: False)
    assert cli.main(["commit", "--dry-run", "--count", "1"]) == 1
    assert called["ai"] is False


def test_parser_supports_history_analysis_and_git_help():
    parser = _parser()
    args = parser.parse_args(["history", "--limit", "20", "--analyze"])
    assert args.command == "history" and args.analyze and args.limit == 20
    args = parser.parse_args(["git-help", "--error", "fatal: not a git repository"])
    assert args.command == "git-help"
    assert args.error == "fatal: not a git repository"


def test_history_analysis_requires_explicit_confirmation(tmp_path, monkeypatch, capsys):
    from commitron import cli
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "ensure_repo", lambda: None)
    monkeypatch.setattr(cli, "history_entries", lambda limit: [{
        "hash": "abc", "date": "2026-11-07", "subject": "test", "body": ""
    }])
    monkeypatch.setattr(cli.Confirm, "ask", lambda *a, **k: False)
    monkeypatch.setattr(cli, "summarize_history", lambda entries: (_ for _ in ()).throw(AssertionError("must not send")))
    assert cli.main(["history", "--analyze"]) == 0
    assert "No data was sent" in capsys.readouterr().out


def test_git_help_requires_explicit_confirmation(tmp_path, monkeypatch, capsys):
    from commitron import cli
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "ensure_repo", lambda: None)
    monkeypatch.setattr(cli.Confirm, "ask", lambda *a, **k: False)
    monkeypatch.setattr(cli, "explain_git_error", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not send")))
    assert cli.main(["git-help", "--error", "fatal: test error"]) == 0
    assert "No data was sent" in capsys.readouterr().out


def test_parser_supports_menu_and_config_profiles():
    parser = _parser()
    assert parser.parse_args(["menu"]).command == "menu"
    args = parser.parse_args(["config", "profile", "save", "work"])
    assert args.config_action == "profile" and args.profile_action == "save"
    assert args.name == "work"
    assert parser.parse_args(["config", "wizard"]).config_action == "wizard"


def test_config_profile_cli_saves_and_lists(tmp_path, monkeypatch, capsys):
    from commitron import cli
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "config_path", lambda: tmp_path / "config.json")
    monkeypatch.setattr("commitron.config.config_path", lambda: tmp_path / "config.json")
    assert cli.main(["config", "set", "provider", "ollama"]) == 0
    assert cli.main(["config", "profile", "save", "local"]) == 0
    assert cli.main(["config", "profile", "list"]) == 0
    assert "local" in capsys.readouterr().out


def test_interactive_menu_exits_cleanly(monkeypatch, capsys):
    from commitron import cli
    monkeypatch.setattr(cli.Prompt, "ask", lambda *args, **kwargs: "Exit")
    assert cli.main(["menu"]) == 0
    assert "Goodbye" in capsys.readouterr().out


def test_config_wizard_saves_provider_settings(tmp_path, monkeypatch, capsys):
    from commitron import cli
    from commitron import config
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "config_path", lambda: path)
    monkeypatch.setattr(cli, "config_path", lambda: path)
    answers = iter(["ollama", "qwen2.5-coder:7b", "http://localhost:11434"])
    monkeypatch.setattr(cli.Prompt, "ask", lambda *args, **kwargs: next(answers))
    assert cli.main(["config", "wizard"]) == 0
    assert config.load_config()["provider"] == "ollama"
    assert "API keys are not stored in config" in " ".join(capsys.readouterr().out.split())


def test_interactive_profile_menu_saves_applies_and_deletes(tmp_path, monkeypatch, capsys):
    from commitron import cli, config

    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "config_path", lambda: path)
    monkeypatch.setattr(cli, "config_path", lambda: path)
    config.save_config({"provider": "openai", "model": "gpt-test"})
    answers = iter([
        "Save current settings", "work",
        "Apply profile", "work",
        "Delete profile", "work",
        "Back",
    ])
    monkeypatch.setattr(cli.Prompt, "ask", lambda *args, **kwargs: next(answers))
    monkeypatch.setattr(cli.Confirm, "ask", lambda *args, **kwargs: True)

    assert cli._manage_profiles_menu() == 0
    assert config.list_profiles() == {}
    assert config.load_config()["provider"] == "openai"
    output = capsys.readouterr().out
    assert "Saved profile 'work'" in output
    assert "Applied profile 'work'" in output
    assert "Deleted profile 'work'" in output


def test_interactive_profile_menu_handles_empty_apply_and_delete(tmp_path, monkeypatch, capsys):
    from commitron import cli, config

    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.json")
    answers = iter(["Apply profile", "Delete profile", "Back"])
    monkeypatch.setattr(cli.Prompt, "ask", lambda *args, **kwargs: next(answers))
    assert cli._manage_profiles_menu() == 0
    output = capsys.readouterr().out
    assert "No profiles to apply" in output
    assert "No profiles to delete" in output


def test_main_menu_routes_to_profile_manager(tmp_path, monkeypatch, capsys):
    from commitron import cli, config

    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.json")
    answers = iter(["Manage AI profiles", "List", "Back", "Exit"])
    monkeypatch.setattr(cli.Prompt, "ask", lambda *args, **kwargs: next(answers))
    monkeypatch.setattr(cli.Confirm, "ask", lambda *args, **kwargs: True)
    assert cli.main(["menu"]) == 0
    output = capsys.readouterr().out
    assert "Manage provider profiles" in output
    assert "No saved profiles" in output
    assert "Goodbye" in output


def test_profile_menu_overwrite_requires_confirmation(tmp_path, monkeypatch, capsys):
    from commitron import cli, config

    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "config_path", lambda: path)
    monkeypatch.setattr(cli, "config_path", lambda: path)
    config.save_config({"provider": "openai", "model": "original"})
    config.save_profile("work")
    config.save_config({"provider": "ollama", "model": "replacement"})
    answers = iter(["Save current settings", "work", "Back"])
    monkeypatch.setattr(cli.Prompt, "ask", lambda *args, **kwargs: next(answers))
    monkeypatch.setattr(cli.Confirm, "ask", lambda *args, **kwargs: False)

    assert cli._manage_profiles_menu() == 0
    assert config.list_profiles()["work"]["provider"] == "openai"
    assert "Cancelled" in capsys.readouterr().out


def test_interactive_stage_stages_only_selected_file(tmp_path, monkeypatch, capsys):
    import subprocess
    from commitron import cli

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "one file.txt").write_text("one", encoding="utf-8")
    (tmp_path / "two.txt").write_text("two", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.Prompt, "ask", lambda *args, **kwargs: "1")
    monkeypatch.setattr(cli.Confirm, "ask", lambda *args, **kwargs: True)

    assert cli.main(["stage"]) == 0
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=tmp_path,
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    assert len(staged) == 1
    assert staged[0] == "one file.txt"


def test_interactive_stage_cancel_does_not_change_index(tmp_path, monkeypatch):
    import subprocess
    from commitron import cli

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "one.txt").write_text("one", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.Prompt, "ask", lambda *args, **kwargs: "c")

    assert cli.main(["stage"]) == 0
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only"], cwd=tmp_path,
        check=True, capture_output=True, text=True,
    ).stdout
    assert staged == ""


def test_auth_status_is_available_outside_git_repository(tmp_path, monkeypatch, capsys):
    from commitron import cli

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "credential_status", lambda provider: "not configured")
    assert cli.main(["auth", "status"]) == 0
    output = capsys.readouterr().out
    assert "gemini" in output and "openai" in output and "ollama" in output


def test_auth_parser_accepts_supported_providers():
    parser = _parser()
    args = parser.parse_args(["auth", "set", "gemini"])
    assert args.command == "auth" and args.auth_action == "set" and args.provider == "gemini"


def test_stage_command_stages_only_confirmed_selected_path(tmp_path, monkeypatch):
    import subprocess
    from commitron import cli
    from commitron.git_ops import files_changed

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init")
    (tmp_path / "selected file.txt").write_text("selected\n", encoding="utf-8")
    (tmp_path / "leave unstaged.txt").write_text("not selected\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.Prompt, "ask", lambda *args, **kwargs: "2")
    monkeypatch.setattr(cli.Confirm, "ask", lambda *args, **kwargs: True)

    assert cli.main(["stage"]) == 0
    assert files_changed(staged=True) == ["selected file.txt"]
    assert "leave unstaged.txt" not in files_changed(staged=True)


def test_stage_command_cancel_leaves_index_unchanged(tmp_path, monkeypatch):
    import subprocess
    from commitron import cli

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "draft.txt").write_text("draft\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.Prompt, "ask", lambda *args, **kwargs: "1")
    monkeypatch.setattr(cli.Confirm, "ask", lambda *args, **kwargs: False)

    assert cli.main(["stage"]) == 0
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"], cwd=tmp_path, check=False
    )
    assert result.returncode == 0


def test_interactive_command_handles_closed_stdin(tmp_path, monkeypatch, capsys):
    from commitron import cli

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli, "ensure_repo", lambda: None)
    monkeypatch.setattr(cli, "worktree_changes", lambda: [{"status": "??", "path": "draft.txt"}])
    monkeypatch.setattr(
        cli.Prompt, "ask", lambda *args, **kwargs: (_ for _ in ()).throw(EOFError())
    )

    assert cli.main(["stage"]) == 130
    assert "Input closed" in capsys.readouterr().out


def test_legacy_smart_commit_entrypoint_delegates_to_current_cli(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(project_root / "smart_commit.py"), "--help"],
        cwd=tmp_path, capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0
    assert "A safer AI-powered Git assistant" in result.stdout
    commit_help = subprocess.run(
        [sys.executable, str(project_root / "smart_commit.py"), "commit", "--help"],
        cwd=tmp_path, capture_output=True, text=True, timeout=15,
    )
    assert commit_help.returncode == 0
    assert "--dry-run" in commit_help.stdout


def test_legacy_entrypoint_no_longer_contains_unsafe_bulk_staging():
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1]
    source = (project_root / "smart_commit.py").read_text(encoding="utf-8")
    assert "git add ." not in source
    assert "commitron.cli" in source
