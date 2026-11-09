"""AI provider adapters. Each adapter owns its endpoint and authentication details."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Protocol

from .credentials import CredentialError, get_credential


class ProviderError(RuntimeError):
    """Raised when a provider request or response fails."""


DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4.1-mini",
    "ollama": "qwen2.5-coder:7b",
}
DEFAULT_URLS = {
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models",
    "openai": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434",
}


class AIProvider(Protocol):
    """Common contract implemented by every provider adapter."""

    def generate(self, prompt: str, max_tokens: int) -> str:
        """Generate plain text from a prompt."""


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Do not forward provider credentials through unexpected redirects."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _request_json(url: str, payload: Dict, headers: Dict[str, str]) -> Dict:
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers}, method="POST",
    )
    opener = urllib.request.build_opener(_NoRedirectHandler())
    try:
        with opener.open(request, timeout=90) as response:
            raw_bytes = response.read(2_000_001)
        if len(raw_bytes) > 2_000_000:
            raise ProviderError("AI provider response exceeded the 2 MB safety limit.")
        raw = raw_bytes.decode("utf-8")
        data = json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", "replace")
        raise ProviderError("AI provider returned HTTP {}: {}".format(exc.code, detail)) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError("AI request failed: {}".format(exc)) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError("AI provider returned invalid JSON or text.") from exc
    if not isinstance(data, dict):
        raise ProviderError("AI provider returned an unexpected response.")
    if "error" in data:
        error = data["error"]
        detail = error.get("message", str(error)) if isinstance(error, dict) else str(error)
        raise ProviderError(str(detail))
    return data


def _extract_text(data: Dict, provider: str) -> str:
    try:
        if provider == "gemini":
            return "\n".join(
                part["text"] for part in data["candidates"][0]["content"]["parts"]
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            )
        if provider == "openai":
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                text_parts = [
                    item.get("text", "") for item in content
                    if isinstance(item, dict) and isinstance(item.get("text"), str)
                ]
                return "\n".join(text_parts)
        if provider == "ollama":
            return data["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("{} returned no usable text.".format(provider.title())) from exc
    raise ProviderError("{} returned no usable text.".format(provider.title()))


class GeminiProvider:
    def __init__(self, model: str, base_url: str):
        self.model = model
        self.base_url = base_url

    def generate(self, prompt: str, max_tokens: int) -> str:
        try:
            api_key = get_credential("gemini")
        except CredentialError as exc:
            raise ProviderError(str(exc)) from exc
        if not api_key:
            raise ProviderError("No Gemini API key found. Set GEMINI_API_KEY or save one with 'commitron auth set gemini'.")
        endpoint = self.base_url.rstrip("/") + "/" + urllib.parse.quote(self.model, safe="") + ":generateContent"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.35, "maxOutputTokens": max_tokens},
        }
        data = _request_json(endpoint, payload, {"x-goog-api-key": api_key})
        return _extract_text(data, "gemini")


class OpenAIProvider:
    def __init__(self, model: str, base_url: str):
        self.model = model
        self.base_url = base_url

    def generate(self, prompt: str, max_tokens: int) -> str:
        try:
            api_key = get_credential("openai")
        except CredentialError as exc:
            raise ProviderError(str(exc)) from exc
        if not api_key:
            raise ProviderError("No OpenAI API key found. Set OPENAI_API_KEY or save one with 'commitron auth set openai'.")
        endpoint = self.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.35,
            "max_completion_tokens": max_tokens,
        }
        data = _request_json(endpoint, payload, {"Authorization": "Bearer " + api_key})
        return _extract_text(data, "openai")


class OllamaProvider:
    def __init__(self, model: str, base_url: str):
        self.model = model
        self.base_url = base_url

    def generate(self, prompt: str, max_tokens: int) -> str:
        endpoint = self.base_url.rstrip("/") + "/api/chat"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.35, "num_predict": max_tokens},
        }
        data = _request_json(endpoint, payload, {})
        return _extract_text(data, "ollama")


_PROVIDER_TYPES = {
    "gemini": GeminiProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
}


def create_provider(name: str, model: str = "", base_url: str = "") -> AIProvider:
    """Create the configured provider adapter without making a network request."""
    provider_name = name.lower()
    try:
        provider_type = _PROVIDER_TYPES[provider_name]
    except KeyError as exc:
        raise ProviderError("Unsupported AI provider: {}".format(name)) from exc
    resolved_model = model.strip() or DEFAULT_MODELS[provider_name]
    resolved_url = base_url.strip() or DEFAULT_URLS[provider_name]
    return provider_type(resolved_model, resolved_url)
