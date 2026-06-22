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
    
    def _get_ydl_opts(self, format: str = None, extract_flat: bool = False, client: str = 'android') -> Dict[str, Any]:
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
                    'player_client': client,
                }
            },
            'cookiefile': settings.cookie_file if settings.use_cookies else None,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
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
        """Search on a specific platform with full extraction to verify availability."""
        opts = self._get_ydl_opts(extract_flat=False)
        opts['playlistend'] = max_results * 2  # Get more results to filter out unavailable ones
        
        # Build search query based on platform
        if platform == 'youtube':
            search_query = f"ytsearch{max_results * 2}:{query}"
        elif platform == 'soundcloud':
            search_query = f"scsearch{max_results * 2}:{query}"
        else:
            # Default to YouTube
            search_query = f"ytsearch{max_results * 2}:{query}"
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            results = ydl.extract_info(search_query, download=False)
            
            if not results or 'entries' not in results:
                return []
            
            videos = []
            for entry in results['entries']:
                if entry and entry.get('id'):
                    # Only include videos that have formats AND are not unavailable
                    if entry.get('formats') and len(entry.get('formats', [])) > 0:
                        # Check if video is actually accessible by looking for valid URLs in formats
                        has_valid_url = False
                        for fmt in entry.get('formats', []):
                            if fmt.get('url') and 'http' in fmt.get('url', ''):
                                has_valid_url = True
                                break
                        
                        if has_valid_url:
                            videos.append({
                                'id': entry.get('id'),
                                'title': entry.get('title'),
                                'url': entry.get('webpage_url') or entry.get('url'),
                                'thumbnail': entry.get('thumbnail'),
                                'duration': entry.get('duration'),
                                'view_count': entry.get('view_count'),
                                'uploader': entry.get('uploader'),
                                'uploader_id': entry.get('uploader_id'),
                                'platform': platform,
                            })
                
                # Stop once we have enough results
                if len(videos) >= max_results:
                    break
            
            return videos
    
    async def get_video_info(self, video_id: str, platform: str = 'youtube') -> Optional[Dict[str, Any]]:
        """Get detailed information about a video with client fallback and retry."""
        async def _extract_info(client: str):
            opts = self._get_ydl_opts(extract_flat=False, client=client)
            
            # Build URL based on platform
            if platform == 'youtube':
                url = f"https://www.youtube.com/watch?v={video_id}"
            elif platform == 'soundcloud':
                url = f"https://soundcloud.com/{video_id}" if '/' not in video_id else video_id
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
        
        try:
            # Try with client fallback
            clients = settings.client_order.split(',')
            last_error = None
            
            for client in clients:
                try:
                    result = await self._retry_with_backoff(_extract_info, client.strip())
                    if result:
                        return result
                except Exception as e:
                    last_error = e
                    logger.warning(f"Client {client} failed for video info: {e}")
                    continue
            
            # If all clients failed, raise the last error
            if last_error:
                raise last_error
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            raise
    
    async def get_audio_stream(self, video_id: str, platform: str = 'youtube') -> Optional[Dict[str, Any]]:
        """Get audio stream information with multiple URLs and retry."""
        async def _extract_audio(client: str):
            opts = self._get_ydl_opts(extract_flat=False, client=client)
            
            # Build URL based on platform
            if platform == 'youtube':
                url = f"https://www.youtube.com/watch?v={video_id}"
            elif platform == 'soundcloud':
                url = f"https://soundcloud.com/{video_id}" if '/' not in video_id else video_id
            else:
                # Try as direct URL
                url = video_id if video_id.startswith('http') else f"https://www.youtube.com/watch?v={video_id}"
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
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
                    return None
                
                # Return multiple audio URLs
                return {
                    'id': info.get('id'),
                    'title': info.get('title'),
                    'duration': info.get('duration'),
                    'platform': platform,
                    'audio_streams': audio_formats[:5],  # Return top 5 audio streams
                    'best_audio': audio_formats[0] if audio_formats else None,
                }
        
        try:
            # Try with client fallback
            clients = settings.client_order.split(',')
            last_error = None
            
            for client in clients:
                try:
                    result = await self._retry_with_backoff(_extract_audio, client.strip())
                    if result:
                        return result
                except Exception as e:
                    last_error = e
                    logger.warning(f"Client {client} failed for audio stream: {e}")
                    continue
            
            # If all clients failed, raise the last error
            if last_error:
                raise last_error
            
            return None
        
        except Exception as e:
            logger.error(f"Error getting audio stream: {e}")
            raise
    
    async def get_stream_url(self, video_id: str, format: str = None, platform: str = 'youtube') -> Optional[Dict[str, Any]]:
        """Get playable stream URL with client fallback and retry."""
        async def _extract_stream(client: str):
            opts = self._get_ydl_opts(format=format, extract_flat=False, client=client)
            
            # Build URL based on platform
            if platform == 'youtube':
                url = f"https://www.youtube.com/watch?v={video_id}"
            elif platform == 'soundcloud':
                url = f"https://soundcloud.com/{video_id}" if '/' not in video_id else video_id
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
        
        try:
            # Try with client fallback
            clients = settings.client_order.split(',')
            last_error = None
            
            for client in clients:
                try:
                    result = await self._retry_with_backoff(_extract_stream, client.strip())
                    if result:
                        return result
                except Exception as e:
                    last_error = e
                    logger.warning(f"Client {client} failed for stream URL: {e}")
                    continue
            
            # If all clients failed, raise the last error
            if last_error:
                raise last_error
            
            return None
        
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
        """Get download information with client fallback and retry."""
        async def _extract_download(client: str):
            opts = self._get_ydl_opts(format=format, extract_flat=False, client=client)
            
            # Build URL based on platform
            if platform == 'youtube':
                url = f"https://www.youtube.com/watch?v={video_id}"
            elif platform == 'soundcloud':
                url = f"https://soundcloud.com/{video_id}" if '/' not in video_id else video_id
            else:
                # Try as direct URL
                url = video_id if video_id.startswith('http') else f"https://www.youtube.com/watch?v={video_id}"
            
            logger.info(f"Attempting to extract download info for {video_id} with client {client}")
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    logger.warning(f"No info returned for {video_id} with client {client}")
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
                
                logger.info(f"Successfully extracted download info for {video_id} with client {client}")
                
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
        
        try:
            # Try with client fallback
            clients = settings.client_order.split(',')
            last_error = None
            
            for client in clients:
                try:
                    result = await self._retry_with_backoff(_extract_download, client.strip())
                    if result:
                        return result
                except Exception as e:
                    last_error = e
                    logger.warning(f"Client {client} failed for download info: {str(e)}")
                    continue
            
            # If all clients failed, try fallback to search by video ID
            logger.warning(f"All clients failed for video {video_id}, trying search fallback")
            try:
                # Search by video ID to try to find the video
                search_results = await self.search_videos(video_id, max_results=1, platform=platform)
                if search_results and len(search_results) > 0:
                    found_id = search_results[0]['id']
                    logger.info(f"Found video via search fallback: {found_id}")
                    # If the found ID is different from the original, try extraction with it
                    if found_id != video_id:
                        logger.info(f"Trying extraction with found video ID: {found_id}")
                        return await self.get_download_info(found_id, format, platform)
                    else:
                        logger.warning(f"Search returned same video ID {video_id}, skipping retry")
                else:
                    logger.warning(f"Search fallback returned no results for {video_id}")
            except Exception as search_error:
                logger.warning(f"Search fallback also failed: {str(search_error)}")
            
            # If all clients failed, return None (video unavailable)
            error_msg = str(last_error) if last_error else "Video unavailable or not found"
            if "unavailable" in error_msg.lower() or "not found" in error_msg.lower():
                logger.warning(f"Video {video_id} is unavailable or has been removed")
            else:
                logger.error(f"Failed to extract download info for video {video_id}: {error_msg}")
            return None
        
        except Exception as e:
            logger.error(f"Error getting download info for {video_id}: {str(e)}")
            return None


ytdlp_service = YtDlpService()
