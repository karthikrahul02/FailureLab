from fastapi import Header, HTTPException, status
from app.core.config import settings

async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Optional API-key guard. AWS deployment additionally enforces Cognito JWT at API Gateway."""
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
