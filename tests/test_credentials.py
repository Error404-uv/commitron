import sys
import types

import pytest

from commitron import credentials


class FakeBackend:
    priority = 1


class FakeKeyring(types.ModuleType):
    def __init__(self):
        super().__init__("keyring")
        self.values = {}
        self.errors = types.SimpleNamespace(PasswordDeleteError=type("PasswordDeleteError", (Exception,), {}))

    def get_keyring(self):
        return FakeBackend()

    def get_password(self, service, username):
        return self.values.get((service, username))

    def set_password(self, service, username, value):
        self.values[(service, username)] = value

    def delete_password(self, service, username):
        key = (service, username)
        if key not in self.values:
            raise self.errors.PasswordDeleteError()
        del self.values[key]


def test_environment_credential_takes_precedence(monkeypatch):
    fake = FakeKeyring()
    fake.values[(credentials.SERVICE_NAME, "gemini")] = "keychain-value"
    monkeypatch.setitem(sys.modules, "keyring", fake)
    monkeypatch.setenv("GEMINI_API_KEY", "environment-value")

    assert credentials.get_credential("gemini") == "environment-value"


def test_keyring_credential_can_be_saved_read_and_deleted(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setitem(sys.modules, "keyring", fake)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    credentials.set_credential("openai", "secret-value")
    assert credentials.get_credential("openai") == "secret-value"
    assert credentials.credential_status("openai") == "saved in OS keychain"
    assert credentials.delete_credential("openai") is True
    assert credentials.get_credential("openai") is None


def test_insecure_plaintext_keyring_backend_is_rejected(monkeypatch):
    fake = FakeKeyring()

    class PlaintextBackend:
        priority = 1

    fake.get_keyring = lambda: PlaintextBackend()
    monkeypatch.setitem(sys.modules, "keyring", fake)
    with pytest.raises(credentials.CredentialError, match="No supported secure OS credential"):
        credentials.set_credential("gemini", "secret-value")


def test_keyring_chainer_backend_is_rejected(monkeypatch):
    fake = FakeKeyring()

    class ChainerBackend:
        priority = 1

    fake.get_keyring = lambda: ChainerBackend()
    monkeypatch.setitem(sys.modules, "keyring", fake)
    with pytest.raises(credentials.CredentialError, match="No supported secure OS credential"):
        credentials.set_credential("openai", "secret-value")


def test_environment_only_works_when_keyring_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "keyring", None)
    monkeypatch.setenv("GEMINI_API_KEY", "environment-only")
    assert credentials.get_credential("gemini") == "environment-only"


def test_ollama_has_no_api_credential(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "cloud-key")
    assert credentials.get_credential("ollama") is None
    assert credentials.credential_status("ollama") == "not required (local provider)"


def test_rejects_credentials_with_control_characters(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setitem(sys.modules, "keyring", fake)
    with pytest.raises(credentials.CredentialError, match="control characters"):
        credentials.set_credential("gemini", "valid-prefix\nInjected: value")
    assert fake.values == {}


def test_rejects_oversized_credentials(monkeypatch):
    fake = FakeKeyring()
    monkeypatch.setitem(sys.modules, "keyring", fake)
    with pytest.raises(credentials.CredentialError, match="4096"):
        credentials.set_credential("openai", "x" * 4097)
    assert fake.values == {}


def test_rejects_control_characters_from_environment(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "valid-prefix\r\nInjected: value")
    with pytest.raises(credentials.CredentialError, match="control characters"):
        credentials.get_credential("gemini")


def test_rejects_non_text_keyring_value(monkeypatch):
    fake = FakeKeyring()
    fake.values[(credentials.SERVICE_NAME, "openai")] = b"not-text"
    monkeypatch.setitem(sys.modules, "keyring", fake)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(credentials.CredentialError, match="must be text"):
        credentials.get_credential("openai")
