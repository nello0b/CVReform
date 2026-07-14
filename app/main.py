from fastapi import FastAPI

from app.routers.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="CVReform API",
        description="Convert uploaded CVs into structured data and LaTeX documents.",
        version="0.1.0",
    )
    app.include_router(health_router, prefix="/api/v1")
    return app


app = create_app()
