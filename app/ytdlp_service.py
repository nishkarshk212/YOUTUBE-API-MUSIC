import yt_dlp
import asyncio
from typing import Optional, Dict, Any, List
from app.config import settings
from app.logger import logger


class YtDlpService:
    """Service for interacting with yt-dlp."""
    
    def __init__(self):
        self._update_lock = asyncio.Lock()
    
    async def auto_update(self) -> bool:
        """Auto-update yt-dlp if enabled."""
        if not settings.ytdlp_auto_update:
            return False
        
        async with self._update_lock:
            try:
                logger.info("Checking for yt-dlp updates...")
                yt_dlp.update_if_available()
                logger.info("yt-dlp update check completed")
                return True
            except Exception as e:
                logger.error(f"Failed to update yt-dlp: {e}")
                return False
    
    def _get_ydl_opts(self, format: str = None, extract_flat: bool = False) -> Dict[str, Any]:
        """Get yt-dlp options."""
        opts = {
            'format': format or settings.default_audio_format,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': extract_flat,
            'age_limit': None,  # Allow age-restricted content
            'ignoreerrors': True,
            'nocheckcertificate': True,
            'geo_bypass': settings.region_fallback,
            'geo_bypass_country': None,
        }
        return opts
    
    async def search_videos(self, query: str, max_results: int = None) -> List[Dict[str, Any]]:
        """Search for videos on YouTube."""
        try:
            max_results = max_results or settings.max_results
            opts = self._get_ydl_opts(extract_flat=True)
            opts['playlistend'] = max_results
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                results = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
                
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
                        })
                
                return videos
        
        except Exception as e:
            logger.error(f"Error searching videos: {e}")
            raise
    
    async def get_video_info(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a video."""
        try:
            opts = self._get_ydl_opts()
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
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
                }
        
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            raise
    
    async def get_audio_stream(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get audio stream information for a video."""
        try:
            opts = self._get_ydl_opts()
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                # Find best audio format
                audio_format = None
                for fmt in info.get('formats', []):
                    if fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
                        audio_format = fmt
                        break
                
                if not audio_format:
                    # Fallback to first audio format
                    for fmt in info.get('formats', []):
                        if fmt.get('acodec') != 'none':
                            audio_format = fmt
                            break
                
                if not audio_format:
                    return None
                
                return {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'url': audio_format.get('url'),
                    'ext': audio_format.get('ext'),
                    'filesize': audio_format.get('filesize'),
                    'audio_bitrate': audio_format.get('abr'),
                    'duration': info.get('duration'),
                }
        
        except Exception as e:
            logger.error(f"Error getting audio stream: {e}")
            raise
    
    async def get_stream_url(self, video_id: str, format: str = None) -> Optional[Dict[str, Any]]:
        """Get playable stream URL for a video."""
        try:
            opts = self._get_ydl_opts(format=format)
            url = f"https://www.youtube.com/watch?v={video_id}"
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    return None
                
                # Get the best format URL
                formats = info.get('formats', [])
                if not formats:
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
                    return None
                
                return {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'url': best_format.get('url'),
                    'ext': best_format.get('ext'),
                    'format': best_format.get('format'),
                    'duration': info.get('duration'),
                    'thumbnail': info.get('thumbnail'),
                }
        
        except Exception as e:
            logger.error(f"Error getting stream URL: {e}")
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
                for entry in info.get('entries', []):
                    if entry:
                        tracks.append({
                            'id': entry.get('id'),
                            'title': entry.get('title'),
                            'url': entry.get('url'),
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
                for entry in info.get('related_videos', [])[:settings.max_results]:
                    if entry:
                        related.append({
                            'id': entry.get('id'),
                            'title': entry.get('title'),
                            'url': entry.get('url'),
                            'duration': entry.get('duration'),
                            'thumbnail': entry.get('thumbnail'),
                            'uploader': entry.get('uploader'),
                        })
                
                return related
        
        except Exception as e:
            logger.error(f"Error getting related videos: {e}")
            raise


ytdlp_service = YtDlpService()
