from typing import Protocol


class LLMProvider(Protocol):
    def complete(self, prompt: str, image_url: str = "") -> str: ...
