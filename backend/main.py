"""Main application entrypoint."""

import uvicorn
from app import create_app
from app.core.config import get_settings

settings = get_settings()
app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
