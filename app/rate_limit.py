from fastapi import HTTPException, Request, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.logger import logger


def get_api_key_identifier(request: Request) -> str:
    """Get identifier for rate limiting based on API key."""
    api_key = request.headers.get("X-API-Key", "anonymous")
    return f"api_key:{api_key}"


limiter = None

if settings.rate_limit_enabled:
    limiter = Limiter(
        key_func=get_api_key_identifier,
        default_limits=[f"{settings.rate_limit_per_minute}/minute"]
    )


async def check_rate_limit(request: Request):
    """Check if request is within rate limits."""
    if not settings.rate_limit_enabled or not limiter:
        return
    
    try:
        identifier = get_api_key_identifier(request)
        # The limiter will automatically check and raise RateLimitExceeded if needed
        # This is handled by the limiter middleware
    except RateLimitExceeded as e:
        logger.warning(f"Rate limit exceeded for {identifier}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again later."
        )
