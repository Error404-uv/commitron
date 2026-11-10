import json

import pytest

from commitron import config


def test_config_defaults_and_environment_override(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.json")
    monkeypatch.setenv("COMMITRON_PROVIDER", "openai")
    settings = config.load_config()
    assert settings["provider"] == "openai"
    assert settings["model"] == ""


def test_save_config_does_not_store_api_keys(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config, "config_path", lambda: path)
    config.save_config({"provider": "ollama", "model": "qwen2.5-coder:7b"})
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["provider"] == "ollama"
    assert "api_key" not in saved
    assert "GEMINI_API_KEY" not in saved


def test_rejects_insecure_remote_http_base_url(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.json")
    with pytest.raises(ValueError, match="HTTPS"):
        config.save_config({"base_url": "http://example.com/v1"})


def test_accepts_local_ollama_http_url(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.json")
    config.save_config({"provider": "ollama", "base_url": "http://localhost:11434"})
    assert config.load_config()["base_url"] == "http://localhost:11434"


def test_repository_convention_is_saved_and_loaded(tmp_path):
    convention = config.save_project_convention(tmp_path, "Use feat(scope): summary and lowercase scopes.")
    assert convention == tmp_path / ".commitron.json"
    assert config.load_project_convention(tmp_path) == "Use feat(scope): summary and lowercase scopes."
    config.save_project_convention(tmp_path, "")
    assert config.load_project_convention(tmp_path) == ""

def test_repository_convention_rejects_oversized_value(tmp_path):
    with pytest.raises(ValueError, match="cannot exceed"):
        config.save_project_convention(tmp_path, "x" * (config.MAX_CONVENTION_CHARS + 1))

def test_repository_convention_refuses_symlink(tmp_path):
    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / ".commitron.json"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable in this environment")
    with pytest.raises(ValueError, match="symlinked"):
        config.save_project_convention(tmp_path, "Use Conventional Commits")


def test_profiles_save_list_use_and_delete(tmp_path, monkeypatch):
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(config, "config_path", lambda: config_file)
    config.save_config({"provider": "openai", "model": "gpt-test", "base_url": ""})
    config.save_profile("work")
    profiles = config.list_profiles()
    assert profiles["work"]["provider"] == "openai"
    assert profiles["work"]["model"] == "gpt-test"
    config.save_config({"provider": "ollama", "model": "local-test"})
    config.use_profile("work")
    assert config.load_config()["provider"] == "openai"
    assert config.load_config()["model"] == "gpt-test"
    config.delete_profile("work")
    assert config.list_profiles() == {}


def test_profile_rejects_invalid_names_and_unknown_profiles(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.json")
    with pytest.raises(ValueError, match="Profile name"):
        config.save_profile("../unsafe")
    with pytest.raises(ValueError, match="No profile"):
        config.use_profile("missing")


def test_profile_store_never_contains_api_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.json")
    monkeypatch.setenv("OPENAI_API_KEY", "do-not-store-this")
    config.save_config({"provider": "openai", "model": "gpt-test"})
    profile_path = config.save_profile("work")
    stored = profile_path.read_text(encoding="utf-8")
    assert "do-not-store-this" not in stored
    assert "OPENAI_API_KEY" not in stored


def test_save_config_refuses_to_silently_reset_malformed_existing_setting(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text('{"provider": 123, "model": "existing-model"}', encoding="utf-8")
    monkeypatch.setattr(config, "config_path", lambda: path)
    with pytest.raises(ValueError, match="provider.*must be a string"):
        config.save_config({"model": "new-model"})
    assert json.loads(path.read_text(encoding="utf-8"))["model"] == "existing-model"


def test_load_file_ignores_unknown_keys_but_validates_known_types(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"provider": "openai", "legacy_option": true}', encoding="utf-8")
    assert config.load_file(path) == {"provider": "openai"}
    path.write_text('{"provider": ["openai"]}', encoding="utf-8")
    with pytest.raises(ValueError, match="provider.*must be a string"):
        config.load_file(path)


def test_config_path_uses_windows_appdata(monkeypatch, tmp_path):
    from commitron import config

    monkeypatch.delenv("APPDATA", raising=False)
    # The nt branch always wraps Path() results with str(...), so build the
    # expected string directly (never instantiate a WindowsPath on a POSIX
    # runner where pathlib refuses cross-flavour joins).
    home = str(tmp_path).replace("/", "\\")
    assert str(config.config_path()).replace("\\", "/") == f"{home}/AppData/Roaming/commitron/config.json"


def test_config_path_prefers_appdata_env_on_windows(monkeypatch, tmp_path):
    from commitron import config

    monkeypatch.setattr(config.os, "name", "nt")
    appdata = str(tmp_path / "Roaming").replace("/", "\\")
    monkeypatch.setenv("APPDATA", appdata)
    # APPDATA is read as a string and wrapped in Path(), so on POSIX runners
    # the comparison stays a pure string match with forward slashes.
    assert str(config.config_path()).replace("\\", "/") == f"{appdata}/commitron/config.json"


def test_config_path_uses_macos_application_support(monkeypatch, tmp_path):
    from commitron import config

    monkeypatch.setattr(config.os, "name", "posix")
    monkeypatch.setattr(config, "sys_platform", lambda: "darwin")
    monkeypatch.setattr(config.Path, "home", lambda: tmp_path)
    assert config.config_path() == tmp_path / "Library" / "Application Support" / "commitron" / "config.json"


def test_base_url_rejects_query_fragment_invalid_port_and_whitespace(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.json")
    for url in (
        "https://api.example.com/v1?token=unexpected",
        "https://api.example.com/v1#fragment",
        "https://api.example.com:99999/v1",
        "https://api.example.com/ bad",
    ):
        with pytest.raises(ValueError):
            config.save_config({"base_url": url})


def test_project_convention_rejects_existing_non_object_json(tmp_path):
    path = tmp_path / ".commitron.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        config.save_project_convention(tmp_path, "Use ticket IDs")
    assert path.read_text(encoding="utf-8") == "[]"
