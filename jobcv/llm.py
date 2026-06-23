"""OpenAI-compatible chat client (stdlib urllib only).

Works with any endpoint that speaks the /chat/completions schema:
DeepSeek (default), local Ollama, or a custom base URL.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

# name -> (base_url, default_model, api_key_env)
BACKENDS = {
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-v4-flash", "DEEPSEEK_API_KEY"),
    "ollama": ("http://localhost:11434/v1", "qwen2.5:3b", None),
}


@dataclass
class LLMConfig:
    base_url: str
    model: str
    api_key: str | None = None
    timeout: int = 120

    @classmethod
    def from_backend(
        cls,
        backend: str = "deepseek",
        *,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> "LLMConfig":
        if backend not in BACKENDS and not base_url:
            raise ValueError(
                f"unknown backend {backend!r}; use one of {list(BACKENDS)} "
                "or pass --base-url for a custom endpoint"
            )
        d_url, d_model, key_env = BACKENDS.get(backend, (base_url, model or "", None))
        key = api_key or (os.environ.get(key_env) if key_env else None)
        return cls(
            base_url=(base_url or d_url).rstrip("/"),
            model=model or d_model,
            api_key=key,
        )


def chat(cfg: LLMConfig, system: str, user: str, temperature: float = 0.4) -> str:
    """Send a chat completion request and return the assistant message text."""
    payload = json.dumps(
        {
            "model": cfg.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "stream": False,
        }
    ).encode()

    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = f"Bearer {cfg.api_key}"

    req = urllib.request.Request(
        f"{cfg.base_url}/chat/completions", data=payload, headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"LLM HTTP {e.code}: {e.read().decode(errors='replace')}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"cannot reach {cfg.base_url}: {e.reason}")

    return data["choices"][0]["message"]["content"].strip()
