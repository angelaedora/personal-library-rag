"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.routes import chat, books

settings = get_settings()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    setup_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(chat.router, prefix=settings.api_prefix)
    app.include_router(books.router, prefix=settings.api_prefix)

    @app.get("/health")
    async def health():
        return {"status": "healthy", "service": "personal-library-backend"}

    return app
