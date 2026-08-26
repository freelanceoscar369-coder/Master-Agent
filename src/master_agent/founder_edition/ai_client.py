"""Lightweight OpenRouter/DeepSeek client for Founder Edition AI MODE.

Uses the OpenRouter API to call DeepSeek V4 Pro High for reasoning.
Ollama is NOT imported, NOT loaded, NOT used — per founder policy.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
import urllib.error
from typing import Any

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "deepseek/deepseek-v4-pro"
TIMEOUT_SEC = 60

SYSTEM_PROMPT = """You are Somesh, the AI assistant of Kalpavriksha Founder Edition.
You are helpful, knowledgeable, and direct. The founder's name is Onkar.

Keep responses concise — 2-4 sentences unless a longer answer is needed.
Be honest about your capabilities. Never invent capabilities you don't have.
If asked about your technology, you run locally on the founder's computer
using Whisper for speech recognition and Piper for text-to-speech."""


def _get_api_key() -> str:
    """Read API key from environment at call time."""
    return os.environ.get("OPENROUTER_API_KEY", "")


def is_available() -> bool:
    """Check if the OpenRouter API key is configured."""
    return bool(_get_api_key())


def ask(prompt: str, history: list[dict[str, str]] | None = None) -> str | None:
    """Send a prompt to DeepSeek via OpenRouter. Returns None on failure."""
    api_key = _get_api_key()
    if not api_key:
        return None

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history[-10:])
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": MODEL,
        "messages": messages,
        "max_tokens": 1024,
        "temperature": 0.7,
    }

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "kalpavriksha-local",
            "X-Title": "Kalpavriksha Founder Edition",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()
            return None
    except urllib.error.HTTPError as e:
        logging.error(f"OpenRouter HTTP {e.code}: {e.reason}")
        return None
    except Exception as e:
        logging.error(f"OpenRouter error: {e}")
        return None