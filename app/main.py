from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import yt_dlp
import httpx

from app.config import settings
from app.logger import logger
from app.auth import verify_api_key
from app.ytdlp_service import ytdlp_service
from app.cache import cache
from app.rate_limit import limiter
from app.models import (
    VideoSearchResponse,
    VideoInfoResponse,
    AudioStreamResponse,
    StreamResponse,
    PlaylistResponse,
    RelatedVideosResponse,
    LyricsResponse,
    HealthResponse,
    ErrorResponse
)

# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="Secure, self-hosted YouTube API service for Telegram music bots",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(",") if settings.allowed_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
if limiter:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info(f"Starting {settings.api_title} v{settings.api_version}")
    
    # Auto-update yt-dlp
    await ytdlp_service.auto_update()
    
    logger.info("Application started successfully")


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint to verify API status.
    """
    try:
        ytdlp_version = yt_dlp.version.__version__
    except:
        ytdlp_version = "unknown"
    
    return HealthResponse(
        status="healthy",
        version=settings.api_version,
        ytdlp_version=ytdlp_version,
        cache_enabled=settings.cache_enabled,
        rate_limit_enabled=settings.rate_limit_enabled
    )


@app.get("/search", response_model=VideoSearchResponse, tags=["YouTube"])
@limiter.limit("60/minute") if limiter else lambda f: f
async def search_videos(
    q: str = Query(..., description="Search query for videos"),
    max_results: int = Query(10, ge=1, le=50, description="Maximum number of results"),
    api_key: str = Depends(verify_api_key)
):
    """
    Search for videos on YouTube.
    
    Returns a list of videos matching the search query, optimized for Telegram music bots.
    """
    cache_key = f"search:{q}:{max_results}"
    
    # Check cache
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for search: {q}")
            return VideoSearchResponse(**cached)
    
    try:
        results = await ytdlp_service.search_videos(q, max_results)
        
        response = VideoSearchResponse(
            success=True,
            query=q,
            results=results,
            count=len(results)
        )
        
        # Cache result
        if cache:
            await cache.set(cache_key, response.dict(), settings.cache_ttl_seconds)
        
        return response
    
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search videos: {str(e)}"
        )


@app.get("/video", response_model=VideoInfoResponse, tags=["YouTube"])
@limiter.limit("60/minute") if limiter else lambda f: f
async def get_video_info(
    id: str = Query(..., description="YouTube video ID"),
    api_key: str = Depends(verify_api_key)
):
    """
    Get detailed information about a specific video.
    
    Returns comprehensive video metadata including title, duration, views, uploader, etc.
    Supports age-restricted videos and live streams.
    """
    cache_key = f"video:{id}"
    
    # Check cache
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for video: {id}")
            return VideoInfoResponse(**cached)
    
    try:
        video = await ytdlp_service.get_video_info(id)
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        response = VideoInfoResponse(
            success=True,
            video=video
        )
        
        # Cache result
        if cache:
            await cache.set(cache_key, response.dict(), settings.cache_ttl_seconds)
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video info error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get video info: {str(e)}"
        )


@app.get("/audio", response_model=AudioStreamResponse, tags=["YouTube"])
@limiter.limit("60/minute") if limiter else lambda f: f
async def get_audio_stream(
    id: str = Query(..., description="YouTube video ID"),
    api_key: str = Depends(verify_api_key)
):
    """
    Get direct audio stream URL for a video.
    
    Returns the best available audio stream with metadata for Telegram music bots.
    """
    cache_key = f"audio:{id}"
    
    # Check cache (shorter TTL for streams)
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for audio: {id}")
            return AudioStreamResponse(**cached)
    
    try:
        audio = await ytdlp_service.get_audio_stream(id)
        
        if not audio:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audio stream not found"
            )
        
        response = AudioStreamResponse(
            success=True,
            audio=audio
        )
        
        # Cache result with shorter TTL
        if cache:
            await cache.set(cache_key, response.dict(), 1800)  # 30 minutes
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Audio stream error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audio stream: {str(e)}"
        )


@app.get("/stream", response_model=StreamResponse, tags=["YouTube"])
@limiter.limit("60/minute") if limiter else lambda f: f
async def get_stream_url(
    id: str = Query(..., description="YouTube video ID"),
    format: str = Query(None, description="Custom format string (optional)"),
    api_key: str = Depends(verify_api_key)
):
    """
    Get playable stream URL for a video.
    
    Returns a direct playable URL for the video, optimized for Telegram music bots.
    Supports custom format selection.
    """
    cache_key = f"stream:{id}:{format or 'default'}"
    
    # Check cache (shorter TTL for streams)
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for stream: {id}")
            return StreamResponse(**cached)
    
    try:
        stream = await ytdlp_service.get_stream_url(id, format)
        
        if not stream:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Stream not found"
            )
        
        response = StreamResponse(
            success=True,
            stream=stream
        )
        
        # Cache result with shorter TTL
        if cache:
            await cache.set(cache_key, response.dict(), 1800)  # 30 minutes
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stream URL error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stream URL: {str(e)}"
        )


@app.get("/playlist", response_model=PlaylistResponse, tags=["YouTube"])
@limiter.limit("30/minute") if limiter else lambda f: f
async def get_playlist(
    id: str = Query(..., description="YouTube playlist ID"),
    api_key: str = Depends(verify_api_key)
):
    """
    Get playlist information and all tracks.
    
    Returns playlist metadata and a list of all videos in the playlist.
    """
    cache_key = f"playlist:{id}"
    
    # Check cache
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for playlist: {id}")
            return PlaylistResponse(**cached)
    
    try:
        playlist = await ytdlp_service.get_playlist_info(id)
        
        if not playlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Playlist not found"
            )
        
        response = PlaylistResponse(
            success=True,
            playlist=playlist
        )
        
        # Cache result
        if cache:
            await cache.set(cache_key, response.dict(), settings.cache_ttl_seconds)
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Playlist error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get playlist: {str(e)}"
        )


@app.get("/related", response_model=RelatedVideosResponse, tags=["YouTube"])
@limiter.limit("60/minute") if limiter else lambda f: f
async def get_related_videos(
    id: str = Query(..., description="YouTube video ID"),
    api_key: str = Depends(verify_api_key)
):
    """
    Get related video recommendations.
    
    Returns a list of videos related to the specified video, useful for music discovery.
    """
    cache_key = f"related:{id}"
    
    # Check cache
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for related: {id}")
            return RelatedVideosResponse(**cached)
    
    try:
        related = await ytdlp_service.get_related_videos(id)
        
        response = RelatedVideosResponse(
            success=True,
            related=related,
            count=len(related)
        )
        
        # Cache result
        if cache:
            await cache.set(cache_key, response.dict(), settings.cache_ttl_seconds)
        
        return response
    
    except Exception as e:
        logger.error(f"Related videos error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get related videos: {str(e)}"
        )


@app.get("/lyrics", response_model=LyricsResponse, tags=["YouTube"])
@limiter.limit("30/minute") if limiter else lambda f: f
async def search_lyrics(
    q: str = Query(..., description="Song name or artist + song name"),
    api_key: str = Depends(verify_api_key)
):
    """
    Search for song lyrics.
    
    Note: This endpoint searches for lyrics but may not return full lyrics due to copyright restrictions.
    For Telegram music bots, consider using dedicated lyrics APIs for full lyrics.
    """
    cache_key = f"lyrics:{q}"
    
    # Check cache
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for lyrics: {q}")
            return LyricsResponse(**cached)
    
    try:
        # Search for the song first to get accurate title/artist
        videos = await ytdlp_service.search_videos(q, max_results=1)
        
        if not videos:
            return LyricsResponse(
                success=False,
                lyrics=None,
                source=None
            )
        
        video = videos[0]
        title = video.get('title', '')
        
        # Note: Full lyrics scraping is complex and may violate copyright
        # This is a placeholder implementation
        # For production use, integrate with a dedicated lyrics API like Genius, Musixmatch, etc.
        
        response = LyricsResponse(
            success=True,
            lyrics=f"Lyrics search for: {title}\n\nNote: Full lyrics integration requires a dedicated lyrics API due to copyright restrictions. Consider integrating with Genius API or similar service.",
            source="youtube_search"
        )
        
        # Cache result
        if cache:
            await cache.set(cache_key, response.dict(), settings.cache_ttl_seconds)
        
        return response
    
    except Exception as e:
        logger.error(f"Lyrics search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search lyrics: {str(e)}"
        )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}")
    return ErrorResponse(
        success=False,
        error="Internal server error",
        detail=str(exc)
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
