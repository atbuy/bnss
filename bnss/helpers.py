from dataclasses import dataclass
from io import BytesIO
from typing import Optional


@dataclass
class Song:
    name: Optional[str] = ""
    link: Optional[str] = ""
    duration: Optional[int] = 0
    thumbnail: Optional[str] = ""
    requester: Optional[str] = ""
    data: Optional[BytesIO] = None

    @staticmethod
    def _from_info(info: dict) -> "Song":
        """Load class from info dict."""

        return Song(
            name=info["title"],
            link=info["webpage_url"],
            duration=info["duration"],
            thumbnail=info["thumbnail"],
        )
