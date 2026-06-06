"""Image understanding for KIA via a local Ollama vision model.

Sends an image + prompt to a vision-capable model served by local Ollama
(default ``llama3.2-vision``; pull it first with ``ollama pull llama3.2-vision``).
Provider-free: the image never leaves the machine. litellm handles the Ollama
vision message format (base64 data URL).
"""

from __future__ import annotations

import base64

import litellm

from brain_core.config import settings


def _data_url(image_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


async def describe_image(
    image_bytes: bytes, prompt: str = "Describe this image in detail.", mime: str = "image/png"
) -> str:
    """Return the vision model's answer about an image. Raises on model/connection error."""
    model = f"ollama_chat/{settings.vision_model}"
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": _data_url(image_bytes, mime)}},
            ],
        }
    ]
    resp = await litellm.acompletion(
        model=model, messages=messages, api_base=settings.ollama_base_url, api_key="sk-dummy"
    )
    return str(resp.choices[0].message.content or "")
