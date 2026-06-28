# YOUTUBE-API-MUSIC

Deployed on Railway with auto-updates disabled!

A secure, self-hosted YouTube API service specifically designed for personal use with Telegram music bots. Built with Python (FastAPI) and yt-dlp, providing a clean REST API with comprehensive features.

## Features

- **Search**: Search for videos on YouTube
- **Video Details**: Get comprehensive video metadata
- **Audio Streams**: Extract direct audio stream URLs
- **Playable Streams**: Get direct playable video URLs
- **Playlists**: Retrieve playlist information and tracks
- **Related Videos**: Get video recommendations
- **Lyrics Search**: Basic lyrics lookup (placeholder for integration)
- **Health Checks**: Monitor API status

### Advanced Features

- **API Key Authentication**: Secure access control
- **Rate Limiting**: Prevent abuse with configurable limits
- **Caching**: Memory or Redis-backed caching for performance
- **Auto-Update**: Automatic yt-dlp updates
- **Age-Restricted Content**: Support for age-restricted videos
- **Live Streams**: Support for live stream content
- **YouTube Shorts**: Full support for short-form content
- **Region Fallback**: Automatic region bypass for geo-restricted content
- **Docker Deployment**: Easy containerized deployment
- **Swagger/OpenAPI**: Interactive API documentation
- **JSON Responses**: Optimized for Telegram bot integration

## Quick Start

### Using Docker (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd api
```

2. Create environment file:
```bash
cp .env.example .env
```

3. Edit `.env` and set your secure API key:
```bash
API_KEY=your_secure_random_api_key_here
```

4. Start the service:
```bash
docker-compose up -d
```

5. Access the API:
- API: http://localhost:8000
- Swagger Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create environment file:
```bash
cp .env.example .env
```

3. Set your API key in `.env`

4. Run the service:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

### Authentication

All endpoints require an API key in the `X-API-Key` header.

```bash
curl -H "X-API-Key: your_api_key" http://localhost:8000/health
```

### Endpoints

#### Health Check
```http
GET /health
```
Returns API status and version information.

#### Search Videos
```http
GET /search?q=song_name&max_results=10
```
Search for videos on YouTube.

**Parameters:**
- `q` (required): Search query
- `max_results` (optional): Number of results (1-50, default: 10)

**Example:**
```bash
curl -H "X-API-Key: your_api_key" \
  "http://localhost:8000/search?q=never+gonna+give+you+up&max_results=5"
```

#### Video Details
```http
GET /video?id=video_id
```
Get detailed information about a video.

**Parameters:**
- `id` (required): YouTube video ID

**Example:**
```bash
curl -H "X-API-Key: your_api_key" \
  "http://localhost:8000/video?id=dQw4w9WgXcQ"
```

#### Audio Stream
```http
GET /audio?id=video_id
```
Get direct audio stream URL for a video.

**Parameters:**
- `id` (required): YouTube video ID

**Example:**
```bash
curl -H "X-API-Key: your_api_key" \
  "http://localhost:8000/audio?id=dQw4w9WgXcQ"
```

#### Stream URL
```http
GET /stream?id=video_id&format=best
```
Get playable stream URL for a video.

**Parameters:**
- `id` (required): YouTube video ID
- `format` (optional): Custom format string

**Example:**
```bash
curl -H "X-API-Key: your_api_key" \
  "http://localhost:8000/stream?id=dQw4w9WgXcQ"
```

#### Playlist
```http
GET /playlist?id=playlist_id
```
Get playlist information and tracks.

**Parameters:**
- `id` (required): YouTube playlist ID

**Example:**
```bash
curl -H "X-API-Key: your_api_key" \
  "http://localhost:8000/playlist?id=PLrAXtmRdnEQz4hD5b0c0b0c0b0c0b0c0b"
```

#### Related Videos
```http
GET /related?id=video_id
```
Get related video recommendations.

**Parameters:**
- `id` (required): YouTube video ID

**Example:**
```bash
curl -H "X-API-Key: your_api_key" \
  "http://localhost:8000/related?id=dQw4w9WgXcQ"
```

#### Lyrics Search
```http
GET /lyrics?q=song_name
```
Search for song lyrics (placeholder for dedicated lyrics API integration).

**Parameters:**
- `q` (required): Song name or artist + song name

**Example:**
```bash
curl -H "X-API-Key: your_api_key" \
  "http://localhost:8000/lyrics?q=never+gonna+give+you+up"
```

## Configuration

Environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `API_KEY` | Your secure API key | Required |
| `API_HOST` | API host address | 0.0.0.0 |
| `API_PORT` | API port | 8000 |
| `RATE_LIMIT_ENABLED` | Enable rate limiting | true |
| `RATE_LIMIT_PER_MINUTE` | Requests per minute | 60 |
| `CACHE_ENABLED` | Enable caching | true |
| `CACHE_TYPE` | Cache type (memory/redis) | memory |
| `CACHE_TTL_SECONDS` | Cache TTL | 3600 |
| `REDIS_URL` | Redis connection URL | redis://localhost:6379/0 |
| `YTDLP_AUTO_UPDATE` | Auto-update yt-dlp | true |
| `LOG_LEVEL` | Logging level | INFO |
| `LOG_FORMAT` | Log format (json/text) | json |
| `ALLOWED_ORIGINS` | CORS allowed origins | * |

## Telegram Bot Integration Example

```python
import requests

API_KEY = "your_api_key"
API_URL = "http://localhost:8000"

headers = {"X-API-Key": API_KEY}

# Search for a song
response = requests.get(
    f"{API_URL}/search",
    headers=headers,
    params={"q": "never gonna give you up", "max_results": 5}
)
data = response.json()

# Get audio stream for the first result
if data["success"] and data["results"]:
    video_id = data["results"][0]["id"]
    audio_response = requests.get(
        f"{API_URL}/audio",
        headers=headers,
        params={"id": video_id}
    )
    audio_data = audio_response.json()
    
    if audio_data["success"]:
        audio_url = audio_data["audio"]["url"]
        print(f"Audio URL: {audio_url}")
```

## Docker Deployment

### Build and Run

```bash
# Build the image
docker-compose build

# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

### Production Deployment

For production deployment:

1. Use a strong, randomly generated API key
2. Set up a reverse proxy (nginx) for SSL/TLS
3. Configure proper CORS origins
4. Use Redis for caching in production
5. Set up log aggregation
6. Monitor the health endpoint

Example nginx configuration:
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Security Considerations

- **API Key**: Always use a strong, random API key
- **HTTPS**: Use HTTPS in production
- **CORS**: Restrict allowed origins in production
- **Rate Limiting**: Keep rate limiting enabled
- **Firewall**: Restrict access to the API port
- **Updates**: Keep yt-dlp and dependencies updated

## Troubleshooting

### yt-dlp Update Issues
If yt-dlp fails to update, manually update in the container:
```bash
docker-compose exec youtube-api pip install --upgrade yt-dlp
```

### Cache Issues
Clear cache by restarting the service:
```bash
docker-compose restart youtube-api
```

### Redis Connection Issues
Ensure Redis is running and accessible:
```bash
docker-compose ps redis
docker-compose logs redis
```

## License

This project is intended for personal use only. Ensure compliance with YouTube's Terms of Service and applicable laws in your jurisdiction.

## Support

For issues and questions, please refer to the project repository or documentation.

## Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern web framework
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube downloader
- [Redis](https://redis.io/) - In-memory data store
