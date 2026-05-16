from __future__ import annotations

import os

import requests
import google.genai as genai
from google.genai import types


class GeminiProvider:
    def __init__(self):
        self.client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        self.model = os.environ["GEMINI_MODEL"]

    def complete(self, prompt: str, image_url: str = "") -> str:
        contents: list = []
        if image_url:
            try:
                resp = requests.get(image_url, timeout=10)
                resp.raise_for_status()
                mime = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
                contents.append(types.Part.from_bytes(data=resp.content, mime_type=mime))
            except Exception:
                pass
        contents.append(prompt)
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        return response.text
