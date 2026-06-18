from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ChatResult:
    text: str
    usage: dict = field(default_factory=lambda: {"prompt": 0, "completion": 0})


class Provider(ABC):
    """Translates an Ollama-style chat request to a backend and back.

    messages: list of {"role": "system"|"user"|"assistant", "content": str}
    fmt: "json" to request JSON-only output, else None.
    """

    @abstractmethod
    def chat(self, model: str, messages: list[dict], fmt: str | None) -> ChatResult: ...
