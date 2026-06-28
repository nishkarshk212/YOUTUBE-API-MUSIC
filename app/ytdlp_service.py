import yt_dlp
import asyncio
import time
import unicodedata
from typing import Optional, Dict, Any, List
from app.config import settings
from app.logger import logger


class YtDlpService:
    """Service for interacting with yt-dlp."""
    
    # Supported platforms (only tested and working)
    PLATFORMS = {
        'youtube': 'youtube',
        'soundcloud': 'soundcloud',
    }
    
    def __init__(self):
        self._update_lock = asyncio.Lock()
    
    async def auto_update(self) -> bool:
        """Auto-update yt-dlp (disabled for production, managed via requirements.txt).
        Last tested with yt-dlp 2026.06.09
        """
        logger.info("yt-dlp auto-update disabled (managed via requirements.txt)")
        return False
    
    def _get_ydl_opts(self, format: str = None, extract_flat: bool = False) -> Dict[str, Any]:
        """Get yt-dlp options (simplified for reliability)."""
        opts = {
            'format': format or settings.default_audio_format,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': extract_flat,
            'age_limit': None,  # Allow age-restricted content
            'ignoreerrors': False,  # Don't ignore errors - let us see what went wrong!
            'nocheckcertificate': True,
            'geo_bypass': settings.region_fallback,
            'geo_bypass_country': None,
            'cookiefile': settings.cookie_file if settings.use_cookies else None,
        }
        
        # Enable IPv4 if configured
        if settings.enable_ipv4:
            opts['source_address'] = settings.source_address
        
        return opts
    
    def _normalize_text(self, text: str) -> str:
        """Normalize Unicode text for better search results."""
        # Normalize to NFKC form (compatibility decomposition)
        normalized = unicodedata.normalize('NFKC', text)
        # Remove diacritics
        normalized = ''.join(c for c in normalized if not unicodedata.combining(c))
        return normalized
    
    async def _retry_with_backoff(self, func, *args, max_retries: int = None, **kwargs):
        """Retry function with exponential backoff."""
        max_retries = max_retries or settings.max_retries
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s, etc.
                    delay = settings.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
        
        raise last_error
    
    async def search_videos(self, query: str, max_results: int = None, platform: str = 'youtube') -> List[Dict[str, Any]]:
        """Search for videos on supported platforms."""
        try:
            max_results = max_results or settings.max_results
            # Normalize query for better Unicode handling
            normalized_query = self._normalize_text(query)
            
            return await self._search_on_platform(normalized_query, max_results, platform)
        
        except Exception as e:
            logger.error(f"Error searching videos on {platform}: {e}")
            raise
    
    async def _search_on_platform(self, query: str, max_results: int, platform: str) -> List[Dict[str, Any]]:
        """Search on a specific platform."""
        opts = self._get_ydl_opts(extract_flat=True)
        opts['playlistend'] = max_results
        
        # Build search query based on platform
        if platform == 'youtube':
            search_query = f"ytsearch{max_results}:{query}"
        elif platform == 'soundcloud':
            search_query = f"scsearch{max_results}:{query}"
        else:
            # Default to YouTube
            search_query = f"ytsearch{max_results}:{query}"
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            results = ydl.extract_info(search_query, download=False)
            
            if not results or 'entries' not in results:
                return []
            
            videos = []
            for entry in results['entries']:
                if entry:
                    videos.append({
                        'id': entry.get('id'),
                        'title': entry.get('title'),
                        'url': entry.get('url'),
                        'thumbnail': entry.get('thumbnail'),
                        'duration': entry.get('duration'),
                        'view_count': entry.get('view_count'),
                        'uploader': entry.get('uploader'),
                        'uploader_id': entry.get('uploader_id'),
                        'platform': platform,
                    })
            
            return videos
    
    async def get_video_info(self, video_id: str, platform: str = 'youtube') -> Optional[Dict[str, Any]]:
        """Get detailed information about a video (simplified)."""
        logger.info(f"[get_video_info] Starting for video_id: {video_id}, platform: {platform}")
        
        opts = self._get_ydl_opts(extract_flat=False)
        
        # Build URL based on platform
        if platform == 'youtube':
            url = f"https://www.youtube.com/watch?v={video_id}"
        elif platform == 'soundcloud':
            url = f"https://soundcloud.com/{video_id}" if '/' not in video_id else video_id
        else:
            # Try as direct URL
            url = video_id if video_id.startswith('http') else f"https://www.youtube.com/watch?v={video_id}"
        
        logger.info(f"[get_video_info] Using URL: {url}")
        
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    logger.warning("[get_video_info] No info returned")
                    return None
                
                logger.info("[get_video_info] Success!")
                return {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'description': info.get('description'),
                    'duration': info.get('duration'),
                    'view_count': info.get('view_count'),
                    'like_count': info.get('like_count'),
                    'uploader': info.get('uploader'),
                    'uploader_id': info.get('uploader_id'),
                    'upload_date': info.get('upload_date'),
                    'thumbnail': info.get('thumbnail'),
                    'webpage_url': info.get('webpage_url'),
                    'is_live': info.get('is_live', False),
                    'age_limit': info.get('age_limit'),
                    'categories': info.get('categories', []),
                    'tags': info.get('tags', []),
                    'platform': platform,
                    'extractor': info.get('extractor'),
                }
        
        except Exception as e:
            logger.error(f"[get_video_info] Error: {type(e).__name__} - {str(e)}", exc_info=True)
            raise
    
    async def get_audio_stream(self, video_id: str, platform: str = 'youtube') -> Optional[Dict[str, Any]]:
        """Get audio stream information (simplified)."""
        logger.info(f"[get_audio_stream] Starting for video_id: {video_id}, platform: {platform}")
        
        opts = self._get_ydl_opts(extract_flat=False)
        
        # Build URL based on platform
        if platform == 'youtube':
            url = f"https://www.youtube.com/watch?v={video_id}"
        elif platform == 'soundcloud':
            url = f"https://soundcloud.com/{video_id}" if '/' not in video_id else video_id
        else:
            # Try as direct URL
            url = video_id if video_id.startswith('http') else f"https://www.youtube.com/watch?v={video_id}"
        
        logger.info(f"[get_audio_stream] Using URL: {url}")
        
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    logger.warning("[get_audio_stream] No info returned")
                    return None
                
                # Get all audio formats
                audio_formats = []
                for fmt in info.get('formats', []):
                    if fmt.get('acodec') != 'none':
                        audio_formats.append({
                            'format_id': fmt.get('format_id'),
                            'url': fmt.get('url'),
                            'ext': fmt.get('ext'),
                            'filesize': fmt.get('filesize'),
                            'audio_bitrate': fmt.get('abr'),
                            'vcodec': fmt.get('vcodec'),
                            'quality': fmt.get('quality'),
                        })
                
                # Sort by bitrate (highest first)
                audio_formats.sort(key=lambda x: x.get('audio_bitrate') or 0, reverse=True)
                
                if not audio_formats:
                    logger.warning("[get_audio_stream] No audio formats found")
                    return None
                
                logger.info("[get_audio_stream] Success!")
                # Return multiple audio URLs
                return {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'duration': info.get('duration'),
                    'platform': platform,
                    'audio_streams': audio_formats[:5],  # Return top 5 audio streams
                    'best_audio': audio_formats[0] if audio_formats else None,
                }
        
        except Exception as e:
            logger.error(f"[get_audio_stream] Error: {type(e).__name__} - {str(e)}", exc_info=True)
            raise
    
    async def get_stream_url(self, video_id: str, format: str = None, platform: str = 'youtube') -> Optional[Dict[str, Any]]:
        """Get playable stream URL (simplified)."""
        logger.info(f"[get_stream_url] Starting for video_id: {video_id}, platform: {platform}")
        
        opts = self._get_ydl_opts(format=format, extract_flat=False)
        
        # Build URL based on platform
        if platform == 'youtube':
            url = f"https://www.youtube.com/watch?v={video_id}"
        elif platform == 'soundcloud':
            url = f"https://soundcloud.com/{video_id}" if '/' not in video_id else video_id
        else:
            # Try as direct URL
            url = video_id if video_id.startswith('http') else f"https://www.youtube.com/watch?v={video_id}"
        
        logger.info(f"[get_stream_url] Using URL: {url}")
        
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    logger.warning("[get_stream_url] No info returned")
                    return None
                
                # Get the best format URL
                formats = info.get('formats', [])
                if not formats:
                    logger.warning("[get_stream_url] No formats found")
                    return None
                
                # Prefer formats with both video and audio
                best_format = None
                for fmt in formats:
                    if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':
                        best_format = fmt
                        break
                
                # Fallback to video-only
                if not best_format:
                    for fmt in formats:
                        if fmt.get('vcodec') != 'none':
                            best_format = fmt
                            break
                
                if not best_format:
                    logger.warning("[get_stream_url] No suitable format found")
                    return None
                
                logger.info("[get_stream_url] Success!")
                return {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'url': best_format.get('url'),
                    'ext': best_format.get('ext'),
                    'format': best_format.get('format'),
                    'duration': info.get('duration'),
                    'thumbnail': info.get('thumbnail'),
                    'platform': platform,
                }
        
        except Exception as e:
            logger.error(f"[get_stream_url] Error: {type(e).__name__} - {str(e)}", exc_info=True)
            raise
    
    async def get_playlist_info(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """Get playlist information and tracks."""
        try:
            opts = self._get_ydl_opts(extract_flat=False)
            url = f"https://www.youtube.com/playlist?list={playlist_id}"
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                tracks = []
                entries = info.get('entries', [])
                if not entries:
                    # Try with extract_flat=True if no entries returned
                    opts_flat = self._get_ydl_opts(extract_flat=True)
                    with yt_dlp.YoutubeDL(opts_flat) as ydl_flat:
                        info_flat = ydl_flat.extract_info(url, download=False)
                        if info_flat:
                            entries = info_flat.get('entries', [])
                
                for entry in entries:
                    if entry:
                        tracks.append({
                            'id': entry.get('id'),
                            'title': entry.get('title'),
                            'url': entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}",
                            'duration': entry.get('duration'),
                            'thumbnail': entry.get('thumbnail'),
                        })
                
                return {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'uploader': info.get('uploader'),
                    'track_count': len(tracks),
                    'tracks': tracks,
                }
        
        except Exception as e:
            logger.error(f"Error getting playlist info: {e}")
            raise
    
    async def get_related_videos(self, video_id: str) -> List[Dict[str, Any]]:
        """Get related video recommendations."""
        try:
            opts = self._get_ydl_opts()
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return []
                
                related = []
                related_videos = info.get('related_videos', [])
                
                # If no related videos, try to get them from automatic captions or search
                if not related_videos:
                    # Fallback: search for similar videos based on title
                    title = info.get('title', '')
                    if title:
                        search_results = await self.search_videos(title, max_results=5)
                        # Filter out the original video
                        related = [v for v in search_results if v.get('id') != video_id]
                        return related[:settings.max_results]
                
                for entry in related_videos[:settings.max_results]:
                    if entry:
                        related.append({
                            'id': entry.get('id'),
                            'title': entry.get('title'),
                            'url': entry.get('url') or f"https://www.youtube.com/watch?v={entry.get('id')}",
                            'duration': entry.get('duration'),
                            'thumbnail': entry.get('thumbnail'),
                            'uploader': entry.get('uploader'),
                        })
                
                return related
        
        except Exception as e:
            logger.error(f"Error getting related videos: {e}")
            raise
    
    async def get_download_info(self, video_id: str, format: str = None, platform: str = 'youtube') -> Optional[Dict[str, Any]]:
        """Get download information (simplified)."""
        logger.info(f"[get_download_info] Starting for video_id: {video_id}, platform: {platform}")
        
        opts = self._get_ydl_opts(format=format, extract_flat=False)
        
        # Build URL based on platform
        if platform == 'youtube':
            url = f"https://www.youtube.com/watch?v={video_id}"
        elif platform == 'soundcloud':
            url = f"https://soundcloud.com/{video_id}" if '/' not in video_id else video_id
        else:
            # Try as direct URL
            url = video_id if video_id.startswith('http') else f"https://www.youtube.com/watch?v={video_id}"
        
        logger.info(f"[get_download_info] Using URL: {url}")
        
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    logger.warning("[get_download_info] No info returned")
                    return None
                
                # Get all available formats
                formats = []
                for fmt in info.get('formats', []):
                    if fmt.get('ext'):
                        formats.append({
                            'format_id': fmt.get('format_id'),
                            'ext': fmt.get('ext'),
                            'format': fmt.get('format'),
                            'filesize': fmt.get('filesize'),
                            'url': fmt.get('url'),
                            'vcodec': fmt.get('vcodec'),
                            'acodec': fmt.get('acodec'),
                            'abr': fmt.get('abr'),
                            'vbr': fmt.get('vbr'),
                        })
                
                logger.info("[get_download_info] Success!")
                return {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'duration': info.get('duration'),
                    'thumbnail': info.get('thumbnail'),
                    'webpage_url': info.get('webpage_url'),
                    'formats': formats,
                    'best_audio_url': info.get('url') if info.get('vcodec') == 'none' else None,
                    'best_video_url': info.get('url') if info.get('acodec') == 'none' else None,
                    'platform': platform,
                }
        
        except Exception as e:
            logger.error(f"[get_download_info] Error: {type(e).__name__} - {str(e)}", exc_info=True)
            raise


ytdlp_service = YtDlpService()
