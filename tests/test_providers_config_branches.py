"""Targeted branch tests for credentials, providers, and config validation paths."""
import json
import sys
import types
import urllib.error

import pytest

from commitron import config, credentials
from commitron.providers import ProviderError, _extract_text, _request_json


# --- credentials edge branches --------------------------------------------------

def test_unsupported_provider_is_rejected_everywhere():
    for fn in (credentials.get_credential, credentials.credential_status):
        with pytest.raises(credentials.CredentialError, match="Unsupported"):
            fn("anthropic")
    with pytest.raises(credentials.CredentialError, match="Only Gemini and OpenAI"):
        credentials.set_credential("anthropic", "x")
    with pytest.raises(credentials.CredentialError, match="Only Gemini and OpenAI"):
        credentials.delete_credential("anthropic")


def test_empty_and_non_text_credentials_are_rejected():
    with pytest.raises(credentials.CredentialError, match="cannot be empty"):
        credentials._validated_value("   ")
    with pytest.raises(credentials.CredentialError, match="must be text"):
        credentials._validated_value(12345)


def test_keyring_inspection_failure_raises_credential_error(monkeypatch):
    class BrokenKeyring(types.ModuleType):
        def get_keyring(self):
            raise RuntimeError("no backend at all")

    monkeypatch.setitem(sys.modules, "keyring", BrokenKeyring("keyring"))
    with pytest.raises(credentials.CredentialError, match="Could not inspect"):
        credentials._keyring_module()


def test_zero_priority_backend_is_rejected(monkeypatch):
    class LowPriority:
        priority = 0

    fake = types.ModuleType("keyring")
    fake.get_keyring = lambda: LowPriority()
    monkeypatch.setitem(sys.modules, "keyring", fake)
    with pytest.raises(credentials.CredentialError, match="No supported secure OS credential"):
        credentials._keyring_module()


def test_get_credential_wraps_keychain_read_failure(monkeypatch):
    class FailingKeyring(types.ModuleType):
        def get_keyring(self):
            class Backend:
                priority = 1
            return Backend()

        def get_password(self, service, username):
            raise OSError("keychain locked")

    monkeypatch.setitem(sys.modules, "keyring", FailingKeyring("keyring"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(credentials.CredentialError, match="Could not read the saved credential"):
        credentials.get_credential("gemini")


def test_set_and_delete_wrap_keychain_write_failures(monkeypatch):
    class FailingKeyring(types.ModuleType):
        def get_keyring(self):
            class Backend:
                priority = 1
            return Backend()

        def set_password(self, *args):
            raise OSError("locked")

        def delete_password(self, *args):
            raise RuntimeError("boom")

    failing = FailingKeyring("keyring")
    failing.errors = types.SimpleNamespace(PasswordDeleteError=type("PDE", (Exception,), {}))
    monkeypatch.setitem(sys.modules, "keyring", failing)
    with pytest.raises(credentials.CredentialError, match="Could not save"):
        credentials.set_credential("gemini", "secret-value")
    with pytest.raises(credentials.CredentialError, match="Could not delete"):
        credentials.delete_credential("gemini")


def test_credential_status_reports_env_and_unconfigured(monkeypatch):
    missing = types.ModuleType("keyring")
    def no_backend():
        raise ImportError("not installed")
    missing.get_keyring = no_backend
    monkeypatch.setitem(sys.modules, "keyring", missing)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert credentials.credential_status("openai").startswith("not configured")
    monkeypatch.setenv("OPENAI_API_KEY", "abc")
    assert credentials.credential_status("openai") == "environment variable configured"


# --- provider response handling --------------------------------------------------

def test_request_json_surfaces_http_error_body(monkeypatch):
    from commitron import providers

    body = b'{"error": {"message": "rate limited"}}'
    http_error = urllib.error.HTTPError(
        "https://api.test", 429, "Too Many Requests", {},
        __import__("io").BytesIO(body))

    class Resp:
        def open(self, *args, **kwargs):
            raise http_error

    monkeypatch.setattr(providers.urllib.request, "build_opener", lambda *a: Resp())
    with pytest.raises(ProviderError, match="HTTP 429"):
        _request_json("https://api.test/v1", {"p": 1}, {})


def test_request_json_wraps_network_and_decode_failures(monkeypatch):
    from commitron import providers

    class Resp:
        def __init__(self, payload=b"not-json{{"):
            self.payload = payload
        def open(self, request, timeout=None):
            raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(providers.urllib.request, "build_opener", lambda *a: Resp())
    with pytest.raises(ProviderError, match="AI request failed"):
        _request_json("https://api.test/v1", {}, {})

    class BadJson:
        def open(self, request, timeout=None):
            class R:
                def read(self, n):
                    return b"<html>not json</html>"
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
            return R()

    monkeypatch.setattr(providers.urllib.request, "build_opener", lambda *a: BadJson())
    with pytest.raises(ProviderError, match="invalid JSON"):
        _request_json("https://api.test/v1", {}, {})


def test_request_json_rejects_non_dict_and_error_payloads(monkeypatch):
    from commitron import providers

    class ListResp:
        def open(self, request, timeout=None):
            class R:
                def read(self, n):
                    return b"[1, 2, 3]"
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
            return R()

    monkeypatch.setattr(providers.urllib.request, "build_opener", lambda *a: ListResp())
    with pytest.raises(ProviderError, match="unexpected response"):
        _request_json("https://api.test/v1", {}, {})

    class ErrResp:
        def open(self, request, timeout=None):
            class R:
                def read(self, n):
                    return json.dumps({"error": "quota exceeded"}).encode()
                def __enter__(self):
                    return self
                def __exit__(self, *a):
                    return False
            return R()

    monkeypatch.setattr(providers.urllib.request, "build_opener", lambda *a: ErrResp())
    with pytest.raises(ProviderError, match="quota exceeded"):
        _request_json("https://api.test/v1", {}, {})


def test_extract_text_handles_malformed_shapes():
    with pytest.raises(ProviderError, match="no usable text"):
        _extract_text({}, "ollama")
    with pytest.raises(ProviderError, match="no usable text"):
        _extract_text({"choices": []}, "openai")
    # openai content list with mixed blocks keeps only text parts
    data = {"choices": [{"message": {"content": [
        {"type": "text", "text": "kept"}, {"type": "image_url"}, {"text": 7}
    ]}}]}
    assert _extract_text(data, "openai") == "kept"


# --- config validation branches ---------------------------------------------------

def test_base_url_rejects_credentials_in_authority():
    with pytest.raises(ValueError, match="Do not put credentials"):
        config._validate_base_url("https://user:***@api.example.com/v1")


def test_base_url_rejects_plain_http_for_non_local_hosts():
    with pytest.raises(ValueError, match="HTTPS"):
        config._validate_base_url("http://api.example.com/v1")
    config._validate_base_url("http://localhost:11434")  # local http allowed


def test_profiles_roundtrip_and_unknown_profile_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "config_path", lambda: tmp_path / "config.json")
    monkeypatch.setattr(config, "profiles_path", lambda: tmp_path / "profiles.json")
    monkeypatch.setattr(config, "load_config", lambda: {"provider": "openai", "model": "m", "base_url": ""})
    config.save_profile("work")
    assert "work" in config.list_profiles()
    with pytest.raises(ValueError, match="No profile named"):
        config.use_profile("ghost")
    with pytest.raises(ValueError, match="No profile named"):
        config.delete_profile("ghost")


def test_profiles_reject_malformed_store(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "profiles_path", lambda: tmp_path / "profiles.json")
    path = tmp_path / "profiles.json"
    path.write_text("[1,2]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        config.list_profiles()
    path.write_text(json.dumps({"bad name!!": {"provider": "openai"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid profile name"):
        config.list_profiles()
    path.write_text(json.dumps({"ok": {"provider": "mistral"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported provider"):
        config.list_profiles()
    path.write_text(json.dumps({"ok": {"provider": "openai", "extra": "x"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported settings"):
        config.list_profiles()
