from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ElevenLabsEvent(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str | None = None
    event: str | None = None
    event_type: str | None = None
    audio_url: str | None = None
    data: dict | None = None
    payload: dict | None = None

    def resolved_type(self) -> str:
        return (self.type or self.event or self.event_type or "unknown").strip().lower()

    def resolved_audio_url(self) -> str | None:
        if self.audio_url:
            return self.audio_url

        for container in (self.data, self.payload):
            if isinstance(container, dict):
                url = container.get("audio_url")
                if isinstance(url, str) and url.strip():
                    return url.strip()

        return None
