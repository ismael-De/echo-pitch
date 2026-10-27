"""Spoken commentary with Azure AI Speech neural voices (REST API, no SDK).

AZURE_SPEECH_KEY + AZURE_SPEECH_REGION enable it. Without them the endpoint answers 503 and the browser
falls back to its built-in speechSynthesis voice (the UI says so).
"""
from __future__ import annotations

import os
from collections import OrderedDict
from xml.sax.saxutils import escape

import httpx

VOICES = {"en": ("en-GB", "en-GB-RyanNeural"), "ar": ("ar-JO", "ar-JO-TaimNeural"),
          "es": ("es-ES", "es-ES-AlvaroNeural"), "fr": ("fr-FR", "fr-FR-HenriNeural"),
          "pt": ("pt-BR", "pt-BR-AntonioNeural")}
MAX_CHARS = 400
_CACHE: OrderedDict[tuple[str, str], bytes] = OrderedDict()


def configured() -> bool:
    return bool(os.environ.get("AZURE_SPEECH_KEY") and os.environ.get("AZURE_SPEECH_REGION"))


def ssml(text: str, lang: str) -> str:
    loc, voice = VOICES.get(lang, VOICES["en"])
    return (f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{loc}'>"
            f"<voice name='{voice}'><prosody rate='+8%'>{escape(text[:MAX_CHARS])}</prosody></voice></speak>")


async def synthesize(text: str, lang: str) -> bytes:
    key = (lang, text[:MAX_CHARS])
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    region = os.environ["AZURE_SPEECH_REGION"]
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.post(f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
                         content=ssml(text, lang).encode(),
                         headers={"Ocp-Apim-Subscription-Key": os.environ["AZURE_SPEECH_KEY"],
                                  "Content-Type": "application/ssml+xml",
                                  "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
                                  "User-Agent": "echo-pitch"})
        r.raise_for_status()
    _CACHE[key] = r.content
    while len(_CACHE) > 300:
        _CACHE.popitem(last=False)
    return r.content
