from pydantic import BaseModel, Field
from typing import Optional, List


class VideoSearchResponse(BaseModel):
    success: bool
    query: str
    results: List[dict]
    count: int


class VideoInfoResponse(BaseModel):
    success: bool
    video: Optional[dict]


class AudioStreamResponse(BaseModel):
    success: bool
    audio: Optional[dict]


class StreamResponse(BaseModel):
    success: bool
    stream: Optional[dict]


class PlaylistResponse(BaseModel):
    success: bool
    playlist: Optional[dict]


class RelatedVideosResponse(BaseModel):
    success: bool
    related: List[dict]
    count: int


class LyricsResponse(BaseModel):
    success: bool
    lyrics: Optional[str]
    source: Optional[str]


class HealthResponse(BaseModel):
    status: str
    version: str
    ytdlp_version: str
    cache_enabled: bool
    rate_limit_enabled: bool
    use_cookies: Optional[bool] = None
    cookie_file: Optional[str] = None
    cookie_file_exists: Optional[bool] = None


class DownloadResponse(BaseModel):
    success: bool
    download: Optional[dict]


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
