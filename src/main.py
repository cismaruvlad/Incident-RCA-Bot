"""Application entry point."""

import uvicorn
from src.config import get_settings


def main():
    settings = get_settings()
    uvicorn.run(
        "src.api.app:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()