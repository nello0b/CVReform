from fastapi import FastAPI

from app.routers.health import router as health_router
from app.routers.uploads import router as uploads_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="CVReform API",
        description="Convert uploaded DOCX or PDF CVs into editable web documents.",
        version="0.1.0",
    )
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(uploads_router, prefix="/api/v1")
    return app


app = create_app()
