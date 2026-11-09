"""User configuration with environment-variable overrides and no stored API keys."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from typing import Any, Dict


DEFAULTS: Dict[str, str] = {
    "provider": "gemini",
    "model": "",
    "base_url": "",
}


def config_path() -> Path:
    """Return the platform-appropriate per-user config path."""
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
    elif sys_platform() == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    return root / "commitron" / "config.json"


def sys_platform() -> str:
    # Kept as a function to make path selection straightforward to test.
    import sys
    return sys.platform


def load_config() -> Dict[str, str]:
    path = config_path()
    data: Dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Cannot read Commitron config at {}: {}".format(path, exc)) from exc
        if not isinstance(loaded, dict):
            raise ValueError("Commitron config must contain a JSON object.")
        data = loaded
    config = dict(DEFAULTS)
    for key in DEFAULTS:
        value = data.get(key)
        if value is not None:
            if not isinstance(value, str):
                raise ValueError("Config value '{}' must be a string.".format(key))
            config[key] = value.strip()
    env_map = {
        "provider": "COMMITRON_PROVIDER",
        "model": "COMMITRON_MODEL",
        "base_url": "COMMITRON_BASE_URL",
    }
    for key, env_name in env_map.items():
        if os.environ.get(env_name, "").strip():
            config[key] = os.environ[env_name].strip()
    provider = config["provider"].lower()
    if provider not in {"gemini", "openai", "ollama"}:
        raise ValueError("Unsupported provider '{}'. Choose gemini, openai, or ollama.".format(provider))
    config["provider"] = provider
    _validate_base_url(config["base_url"])
    return config


def save_config(updates: Dict[str, str]) -> Path:
    unknown = set(updates) - set(DEFAULTS)
    if unknown:
        raise ValueError("Unsupported config key(s): {}".format(", ".join(sorted(unknown))))
    current = dict(DEFAULTS)
    path = config_path()
    if path.exists():
        current.update(load_file(path))
    for key, value in updates.items():
        if not isinstance(value, str):
            raise ValueError("Config values must be strings.")
        current[key] = value.strip()
    provider = current["provider"].lower()
    if provider not in {"gemini", "openai", "ollama"}:
        raise ValueError("Unsupported provider '{}'. Choose gemini, openai, or ollama.".format(provider))
    current["provider"] = provider
    _validate_base_url(current["base_url"])
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="config-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(current, handle, indent=2)
            handle.write("\n")
        if os.name != "nt":
            try:
                os.chmod(temp_name, 0o600)
            except OSError:
                pass
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return path


def load_file(path: Path) -> Dict[str, str]:
    """Read known settings without silently discarding malformed values."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Cannot read Commitron config at {}: {}".format(path, exc)) from exc
    if not isinstance(data, dict):
        raise ValueError("Commitron config must contain a JSON object.")
    settings: Dict[str, str] = {}
    for key in DEFAULTS:
        if key not in data or data[key] is None:
            continue
        if not isinstance(data[key], str):
            raise ValueError("Config value '{}' must be a string.".format(key))
        settings[key] = data[key]
    return settings


def _validate_base_url(value: str) -> None:
    if not value:
        return
    parsed = urlsplit(value)
    if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("base_url cannot contain whitespace or control characters.")
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("base_url must be an absolute http:// or https:// URL.")
    if parsed.query or parsed.fragment:
        raise ValueError("base_url cannot contain a query string or fragment.")
    try:
        parsed.port  # Force validation of malformed or out-of-range ports.
    except ValueError as exc:
        raise ValueError("base_url contains an invalid port.") from exc
    if parsed.username or parsed.password:
        raise ValueError("Do not put credentials in base_url; use the provider's environment variable.")
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme == "http" and parsed.hostname not in local_hosts:
        raise ValueError("Non-local base_url must use HTTPS to protect API credentials.")


PROJECT_CONFIG_NAME = ".commitron.json"
MAX_CONVENTION_CHARS = 1000

def load_project_convention(repo_root: Path) -> str:
    """Load repository-local commit guidance, if configured."""
    path = Path(repo_root) / PROJECT_CONFIG_NAME
    if path.is_symlink():
        raise ValueError("Refusing to read a symlinked project config file.")
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Cannot read project Commitron config at {}: {}".format(path, exc)) from exc
    if not isinstance(data, dict):
        raise ValueError("Project Commitron config must contain a JSON object.")
    convention = data.get("commit_convention", "")
    if not isinstance(convention, str):
        raise ValueError("Project commit_convention must be a string.")
    convention = convention.strip()
    if len(convention) > MAX_CONVENTION_CHARS:
        raise ValueError("Project commit convention cannot exceed {} characters.".format(MAX_CONVENTION_CHARS))
    return convention

def save_project_convention(repo_root: Path, convention: str) -> Path:
    """Atomically save repository-local commit guidance in .commitron.json."""
    if not isinstance(convention, str):
        raise ValueError("Project commit convention must be a string.")
    convention = convention.strip()
    if len(convention) > MAX_CONVENTION_CHARS:
        raise ValueError("Project commit convention cannot exceed {} characters.".format(MAX_CONVENTION_CHARS))
    path = Path(repo_root) / PROJECT_CONFIG_NAME
    if path.is_symlink():
        raise ValueError("Refusing to overwrite a symlinked project config file.")
    existing = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Cannot update project Commitron config at {}: {}".format(path, exc)) from exc
        if not isinstance(existing, dict):
            raise ValueError("Project Commitron config must contain a JSON object.")
    if convention:
        existing["commit_convention"] = convention
    else:
        existing.pop("commit_convention", None)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="commitron-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(existing, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        if os.name != "nt":
            try:
                os.chmod(temp_name, 0o600)
            except OSError:
                pass
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return path


PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")

def profiles_path() -> Path:
    """Return the per-user profile store next to the main config file."""
    return config_path().with_name("profiles.json")

def _read_profiles() -> Dict[str, Dict[str, str]]:
    path = profiles_path()
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Cannot read Commitron profiles at {}: {}".format(path, exc)) from exc
    if not isinstance(raw, dict):
        raise ValueError("Commitron profiles must contain a JSON object.")
    profiles: Dict[str, Dict[str, str]] = {}
    for name, values in raw.items():
        if not isinstance(name, str) or not PROFILE_NAME_RE.fullmatch(name):
            raise ValueError("Invalid profile name in {}.".format(path))
        if not isinstance(values, dict) or set(values) - set(DEFAULTS):
            raise ValueError("Profile '{}' contains unsupported settings.".format(name))
        if any(not isinstance(v, str) for v in values.values()):
            raise ValueError("Profile '{}' settings must be strings.".format(name))
        profiles[name] = {key: values.get(key, DEFAULTS[key]) for key in DEFAULTS}
        provider = profiles[name]["provider"].lower()
        if provider not in {"gemini", "openai", "ollama"}:
            raise ValueError("Profile '{}' has an unsupported provider.".format(name))
        profiles[name]["provider"] = provider
        _validate_base_url(profiles[name]["base_url"])
    return profiles

def list_profiles() -> Dict[str, Dict[str, str]]:
    """Return validated named provider profiles."""
    return _read_profiles()

def save_profile(name: str) -> Path:
    """Save current effective provider settings under a non-secret profile name."""
    if not isinstance(name, str) or not PROFILE_NAME_RE.fullmatch(name):
        raise ValueError("Profile name must be 1–32 letters, numbers, '_' or '-', and start with a letter or number.")
    current = load_config()
    profiles = _read_profiles()
    profiles[name] = {key: current[key] for key in DEFAULTS}
    return _write_profiles(profiles)

def use_profile(name: str) -> Path:
    """Apply a saved profile to the active config; environment overrides still take precedence."""
    profiles = _read_profiles()
    if name not in profiles:
        raise ValueError("No profile named '{}'. Use 'commitron config profile list'.".format(name))
    return save_config(profiles[name])

def delete_profile(name: str) -> Path:
    profiles = _read_profiles()
    if name not in profiles:
        raise ValueError("No profile named '{}'.".format(name))
    del profiles[name]
    return _write_profiles(profiles)

def _write_profiles(profiles: Dict[str, Dict[str, str]]) -> Path:
    path = profiles_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="profiles-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(profiles, handle, indent=2, sort_keys=True)
            handle.write("\n")
        if os.name != "nt":
            try:
                os.chmod(temp_name, 0o600)
            except OSError:
                pass
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return path
