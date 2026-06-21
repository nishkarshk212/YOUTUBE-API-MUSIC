import yt_dlp
import asyncio
from typing import Optional, Dict, Any, List
from app.config import settings
from app.logger import logger


class YtDlpService:
    """Service for interacting with yt-dlp."""
    
    # Supported platforms
    PLATFORMS = {
        'youtube': 'youtube',
        'youtube_music': 'ytsearchmusic',
        'soundcloud': 'soundcloud',
        'spotify': 'spotify',
        'apple_music': 'applemusic',
        'bandcamp': 'bandcamp',
        'vimeo': 'vimeo',
        'dailymotion': 'dailymotion',
        'twitch': 'twitch',
    }
    
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
            'extractor_args': {
                'youtube': {
                    'player_client': 'android',
                }
            },
            'cookiefile': None,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }
        return opts
    
    async def search_videos(self, query: str, max_results: int = None, platform: str = 'youtube') -> List[Dict[str, Any]]:
        """Search for videos on supported platforms."""
        try:
            max_results = max_results or settings.max_results
            platform_key = self.PLATFORMS.get(platform, 'youtube')
            opts = self._get_ydl_opts(extract_flat=True)
            opts['playlistend'] = max_results
            
            # Build search query based on platform
            if platform == 'youtube':
                search_query = f"ytsearch{max_results}:{query}"
            elif platform == 'youtube_music':
                search_query = f"ytsearchmusic{max_results}:{query}"
            elif platform == 'soundcloud':
                search_query = f"scsearch{max_results}:{query}"
            else:
                # Default to YouTube for other platforms
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
        
        except Exception as e:
            logger.error(f"Error searching videos on {platform}: {e}")
            raise
    
    async def get_video_info(self, video_id: str, platform: str = 'youtube') -> Optional[Dict[str, Any]]:
        """Get detailed information about a video."""
        try:
            opts = self._get_ydl_opts()
            
            # Build URL based on platform
            if platform == 'youtube':
                url = f"https://www.youtube.com/watch?v={video_id}"
            elif platform == 'soundcloud':
                url = f"https://soundcloud.com/{video_id}" if '/' not in video_id else video_id
            elif platform == 'vimeo':
                url = f"https://vimeo.com/{video_id}"
            elif platform == 'dailymotion':
                url = f"https://dailymotion.com/video/{video_id}"
            else:
                # Try as direct URL
                url = video_id if video_id.startswith('http') else f"https://www.youtube.com/watch?v={video_id}"
            
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
                    'platform': platform,
                    'extractor': info.get('extractor'),
                }
        
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            raise
    
    async def get_audio_stream(self, video_id: str, platform: str = 'youtube') -> Optional[Dict[str, Any]]:
        """Get audio stream information for a video."""
        try:
            opts = self._get_ydl_opts()
            
            # Build URL based on platform
            if platform == 'youtube':
                url = f"https://www.youtube.com/watch?v={video_id}"
            elif platform == 'soundcloud':
                url = f"https://soundcloud.com/{video_id}" if '/' not in video_id else video_id
            elif platform == 'vimeo':
                url = f"https://vimeo.com/{video_id}"
            elif platform == 'dailymotion':
                url = f"https://dailymotion.com/video/{video_id}"
            else:
                # Try as direct URL
                url = video_id if video_id.startswith('http') else f"https://www.youtube.com/watch?v={video_id}"
            
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
                    'platform': platform,
                }
        
        except Exception as e:
            logger.error(f"Error getting audio stream: {e}")
            raise
    
    async def get_stream_url(self, video_id: str, format: str = None, platform: str = 'youtube') -> Optional[Dict[str, Any]]:
        """Get playable stream URL for a video."""
        try:
            opts = self._get_ydl_opts(format=format)
            
            # Build URL based on platform
            if platform == 'youtube':
                url = f"https://www.youtube.com/watch?v={video_id}"
            elif platform == 'soundcloud':
                url = f"https://soundcloud.com/{video_id}" if '/' not in video_id else video_id
            elif platform == 'vimeo':
                url = f"https://vimeo.com/{video_id}"
            elif platform == 'dailymotion':
                url = f"https://dailymotion.com/video/{video_id}"
            else:
                # Try as direct URL
                url = video_id if video_id.startswith('http') else f"https://www.youtube.com/watch?v={video_id}"
            
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
                    'platform': platform,
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
        """Get download information for a video."""
        try:
            opts = self._get_ydl_opts(format=format)
            
            # Build URL based on platform
            if platform == 'youtube':
                url = f"https://www.youtube.com/watch?v={video_id}"
            elif platform == 'soundcloud':
                url = f"https://soundcloud.com/{video_id}" if '/' not in video_id else video_id
            elif platform == 'vimeo':
                url = f"https://vimeo.com/{video_id}"
            elif platform == 'dailymotion':
                url = f"https://dailymotion.com/video/{video_id}"
            else:
                # Try as direct URL
                url = video_id if video_id.startswith('http') else f"https://www.youtube.com/watch?v={video_id}"
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
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
            logger.error(f"Error getting download info: {e}")
            raise


ytdlp_service = YtDlpService()
