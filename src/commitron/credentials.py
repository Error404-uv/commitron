"""Optional OS-backed credential storage; environment variables take precedence."""
from __future__ import annotations

import importlib
import os
import unicodedata
from typing import Optional


SERVICE_NAME = "commitron"
PROVIDER_ENV = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
}


class CredentialError(RuntimeError):
    """Raised when secure credential storage is unavailable or fails."""


def _keyring_module():
    try:
        module = importlib.import_module("keyring")
    except ImportError as exc:
        raise CredentialError(
            "Secure credential storage is optional. Install it with: "
            "python -m pip install 'commitron[secure-store]'"
        ) from exc
    try:
        backend = module.get_keyring()
        backend_name = (backend.__class__.__module__ + "." + backend.__class__.__name__).lower()
        priority = float(getattr(backend, "priority", 0))
    except Exception as exc:
        raise CredentialError("Could not inspect the operating-system credential backend.") from exc
    if priority <= 0 or any(token in backend_name for token in ("plaintext", "fail", "null", "chainer")):
        raise CredentialError(
            "No supported secure OS credential backend is active. Configure the system keychain "
            "or use the provider's environment variable instead."
        )
    return module


def _validated_value(value: object) -> str:
    """Validate opaque API-key text before it reaches an HTTP header or keychain."""
    if not isinstance(value, str):
        raise CredentialError("Credential must be text.")
    cleaned = value.strip()
    if not cleaned:
        raise CredentialError("Credential cannot be empty.")
    if len(cleaned) > 4096:
        raise CredentialError("Credential is unexpectedly long (maximum 4096 characters).")
    if any(unicodedata.category(char) == "Cc" for char in cleaned):
        raise CredentialError("Credential cannot contain control characters or line breaks.")
    return cleaned


def get_credential(provider: str) -> Optional[str]:
    """Return environment credential first, then an optional OS keychain value."""
    if provider == "ollama":
        return None
    env_name = PROVIDER_ENV.get(provider)
    if not env_name:
        raise CredentialError("Unsupported credential provider.")
    value = os.environ.get(env_name, "")
    if value.strip():
        return _validated_value(value)
    try:
        module = _keyring_module()
        saved = module.get_password(SERVICE_NAME, provider)
    except CredentialError:
        # A missing optional keyring must not break environment-only workflows.
        return None
    except Exception as exc:
        raise CredentialError("Could not read the saved credential from the OS keychain.") from exc
    return _validated_value(saved) if saved is not None else None


def set_credential(provider: str, value: str) -> None:
    if provider not in PROVIDER_ENV:
        raise CredentialError("Only Gemini and OpenAI API credentials can be stored.")
    cleaned = _validated_value(value)
    module = _keyring_module()
    try:
        module.set_password(SERVICE_NAME, provider, cleaned)
    except Exception as exc:
        raise CredentialError("Could not save the credential to the OS keychain.") from exc


def delete_credential(provider: str) -> bool:
    if provider not in PROVIDER_ENV:
        raise CredentialError("Only Gemini and OpenAI API credentials can be stored.")
    module = _keyring_module()
    try:
        module.delete_password(SERVICE_NAME, provider)
        return True
    except module.errors.PasswordDeleteError:
        return False
    except Exception as exc:
        raise CredentialError("Could not delete the credential from the OS keychain.") from exc


def credential_status(provider: str) -> str:
    env_name = PROVIDER_ENV.get(provider)
    if provider == "ollama":
        return "not required (local provider)"
    if not env_name:
        raise CredentialError("Unsupported credential provider.")
    if os.environ.get(env_name, "").strip():
        return "environment variable configured"
    try:
        module = _keyring_module()
        return "saved in OS keychain" if module.get_password(SERVICE_NAME, provider) else "not configured"
    except CredentialError:
        return "not configured (install secure-store extra for keychain support)"
    except Exception:
        return "keychain unavailable"
