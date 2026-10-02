from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

def get_application() -> FastAPI:
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        description="AI Contract & Invoice Risk Intelligence Platform"
    )

    # Configure CORS for frontend communication
    # In production, replace "*" with your specific Vercel domain
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return application

app = get_application()

@app.get("/healthz", tags=["System"])
async def health_check():
    """
    Root endpoint to verify the API is running securely.
    """
    return {
        "status": "online",
        "environment": settings.ENVIRONMENT,
        "version": settings.VERSION
    }