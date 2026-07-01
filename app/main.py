from fastapi import FastAPI, HTTPException, Depends, Query, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
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
    DownloadResponse,
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


@app.get("/", response_class=HTMLResponse, tags=["Health"])
@limiter.exempt if limiter else lambda f: f
async def root():
    """
    Root endpoint - shows API health status with a nice UI.
    """
    try:
        ytdlp_version = yt_dlp.version.__version__
    except:
        ytdlp_version = "unknown"
    
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube API Music - LIVE</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
        }}
        body {{
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
        }}
        .card {{
            background: white;
            padding: 4rem 3rem;
            border-radius: 1.5rem;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
            max-width: 500px;
            width: 90%;
        }}
        .status {{
            font-size: 1.2rem;
            font-weight: 600;
            margin: 1rem 0;
            color: #10b981;
        }}
        .status .emoji {{
            font-size: 3rem;
            display: block;
            margin-bottom: 0.5rem;
        }}
        h1 {{
            font-size: 2rem;
            margin-bottom: 0.5rem;
            color: #1f2937;
        }}
        .version {{
            font-size: 0.95rem;
            color: #6b7280;
            margin-bottom: 2rem;
        }}
        .info-grid {{
            display: grid;
            gap: 1rem;
            margin: 2rem 0;
            text-align: left;
        }}
        .info-item {{
            background: #f9fafb;
            padding: 1rem 1.25rem;
            border-radius: 0.75rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .info-item .label {{
            color: #6b7280;
            font-weight: 500;
        }}
        .info-item .value {{
            font-weight: 600;
            color: #1f2937;
        }}
        .pill {{
            padding: 0.35rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 600;
        }}
        .pill.green {{
            background: #d1fae5;
            color: #065f46;
        }}
        .pill.red {{
            background: #fee2e2;
            color: #991b1b;
        }}
        .links {{
            display: flex;
            gap: 1rem;
            justify-content: center;
            margin-top: 2rem;
        }}
        .links a {{
            padding: 0.75rem 1.5rem;
            border-radius: 0.75rem;
            text-decoration: none;
            font-weight: 600;
            transition: all 0.2s;
        }}
        .links .docs {{
            background: #667eea;
            color: white;
        }}
        .links .docs:hover {{
            background: #5a67d8;
        }}
        .links .redoc {{
            background: #f3f4f6;
            color: #1f2937;
        }}
        .links .redoc:hover {{
            background: #e5e7eb;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="status">
            <span class="emoji">✅</span>
            LIVE & HEALTHY
        </div>
        <h1>YouTube API Music</h1>
        <p class="version">v{settings.api_version}</p>
        
        <div class="info-grid">
            <div class="info-item">
                <span class="label">yt-dlp</span>
                <span class="value">{ytdlp_version}</span>
            </div>
            <div class="info-item">
                <span class="label">Cache</span>
                <span class="pill {'green' if settings.cache_enabled else 'red'}">
                    {'Enabled' if settings.cache_enabled else 'Disabled'}
                </span>
            </div>
            <div class="info-item">
                <span class="label">Rate Limiting</span>
                <span class="pill {'green' if settings.rate_limit_enabled else 'red'}">
                    {'Enabled' if settings.rate_limit_enabled else 'Disabled'}
                </span>
            </div>
        </div>
        
        <div class="links">
            <a href="/docs" class="docs">API Docs (Swagger)</a>
            <a href="/redoc" class="redoc">API Docs (Redoc)</a>
        </div>
    </div>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
@limiter.exempt if limiter else lambda f: f
async def health_check():
    """
    Health check endpoint to verify API status.
    """
    import os
    try:
        ytdlp_version = yt_dlp.version.__version__
    except:
        ytdlp_version = "unknown"
    
    cookie_exists = False
    if settings.cookie_file:
        cookie_exists = os.path.exists(settings.cookie_file)
    
    return HealthResponse(
        status="healthy",
        version=settings.api_version,
        ytdlp_version=ytdlp_version,
        cache_enabled=settings.cache_enabled,
        rate_limit_enabled=settings.rate_limit_enabled,
        use_cookies=settings.use_cookies,
        cookie_file=settings.cookie_file,
        cookie_file_exists=cookie_exists
    )


@app.get("/search", response_model=VideoSearchResponse, tags=["YouTube"])
@limiter.limit("60/minute") if limiter else lambda f: f
async def search_videos(
    request: Request,
    q: str = Query(..., description="Search query for videos"),
    max_results: int = Query(10, ge=1, le=50, description="Maximum number of results"),
    platform: str = Query("youtube", description="Platform to search on (youtube, soundcloud)"),
    api_key: str = Depends(verify_api_key)
):
    """
    Search for videos on supported platforms.
    
    Returns a list of videos matching the search query, optimized for Telegram music bots.
    Supports: youtube, soundcloud
    """
    cache_key = f"search:{q}:{max_results}:{platform}"
    
    # Check cache
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for search: {q}")
            return VideoSearchResponse(**cached)
    
    try:
        results = await ytdlp_service.search_videos(q, max_results, platform)
        
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
    request: Request,
    id: str = Query(..., description="Video ID or URL"),
    platform: str = Query("youtube", description="Platform (youtube, soundcloud)"),
    api_key: str = Depends(verify_api_key)
):
    """
    Get detailed information about a specific video.
    
    Returns comprehensive video metadata including title, duration, views, uploader, etc.
    Supports age-restricted videos and live streams.
    Supports: youtube, soundcloud
    """
    cache_key = f"video:{id}:{platform}"
    
    # Check cache
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for video: {id}")
            return VideoInfoResponse(**cached)
    
    try:
        video = await ytdlp_service.get_video_info(id, platform)
        
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
    request: Request,
    id: str = Query(..., description="Video ID or URL"),
    platform: str = Query("youtube", description="Platform (youtube, soundcloud)"),
    api_key: str = Depends(verify_api_key)
):
    """
    Get direct audio stream URL for a video.
    
    Returns the best available audio stream with metadata for Telegram music bots.
    Supports: youtube, soundcloud
    """
    cache_key = f"audio:{id}:{platform}"
    
    # Check cache (shorter TTL for streams)
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for audio: {id}")
            return AudioStreamResponse(**cached)
    
    try:
        audio = await ytdlp_service.get_audio_stream(id, platform)
        
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
    request: Request,
    id: str = Query(..., description="Video ID or URL"),
    format: str = Query(None, description="Custom format string (optional)"),
    platform: str = Query("youtube", description="Platform (youtube, soundcloud)"),
    api_key: str = Depends(verify_api_key)
):
    """
    Get playable stream URL for a video.
    
    Returns a direct playable URL for the video, optimized for Telegram music bots.
    Supports custom format selection.
    Supports: youtube, soundcloud
    """
    cache_key = f"stream:{id}:{format or 'default'}:{platform}"
    
    # Check cache (shorter TTL for streams)
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for stream: {id}")
            return StreamResponse(**cached)
    
    try:
        stream = await ytdlp_service.get_stream_url(id, format, platform)
        
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


@app.get("/related", response_model=RelatedVideosResponse, tags=["YouTube"])
@limiter.limit("60/minute") if limiter else lambda f: f
async def get_related_videos(
    request: Request,
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
    request: Request,
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


@app.get("/download", response_model=DownloadResponse, tags=["YouTube"])
@limiter.limit("30/minute") if limiter else lambda f: f
async def get_download_info(
    request: Request,
    id: str = Query(..., description="Video ID or URL"),
    format: str = Query(None, description="Custom format string (optional)"),
    type: str = Query(None, description="Type: audio or video (optional)"),
    platform: str = Query("youtube", description="Platform (youtube, soundcloud)"),
    api_key: str = Depends(verify_api_key)
):
    """
    Get download information for a video.
    
    Returns all available formats and direct download URLs for the video.
    Useful for Telegram bots that need to download videos/audio.
    Supports: youtube, soundcloud
    """
    # Map type to format if format is not provided
    if not format and type:
        if type == "audio":
            format = "bestaudio/best"
        elif type == "video":
            format = "bestvideo+bestaudio/best"
    
    cache_key = f"download:{id}:{format or 'default'}:{platform}"
    
    # Check cache
    if cache:
        cached = await cache.get(cache_key)
        if cached:
            logger.info(f"Cache hit for download: {id}")
            return DownloadResponse(**cached)
    
    try:
        download = await ytdlp_service.get_download_info(id, format, platform)
        
        if not download:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Download information not found"
            )
        
        # Filter formats based on type parameter
        if type:
            filtered_formats = []
            for fmt in download.get('formats', []):
                if type == "audio" and fmt.get('vcodec') == 'none' and fmt.get('acodec') != 'none':
                    filtered_formats.append(fmt)
                elif type == "video" and fmt.get('vcodec') != 'none':
                    filtered_formats.append(fmt)
            download['formats'] = filtered_formats
        
        response = DownloadResponse(
            success=True,
            download=download
        )
        
        # Cache result with shorter TTL
        if cache:
            await cache.set(cache_key, response.dict(), 1800)  # 30 minutes
        
        return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download info error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get download info: {str(e)}"
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
