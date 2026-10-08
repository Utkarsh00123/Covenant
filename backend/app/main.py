from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# 1. Import all three routers
from app.api.v1.routers import documents, dashboard, workflow

def get_application() -> FastAPI:
    # 2. Kept your dynamic title, added descriptive metadata
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=getattr(settings, "VERSION", "1.0.0"),
        description="AI Contract Risk Intelligence Platform"
    )
    
    # 3. Dynamic CORS (Fixes a FastAPI crash with wildcard credentials)
    origins = getattr(settings, "BACKEND_CORS_ORIGINS", ["http://localhost:3000", "http://127.0.0.1:3000"])
    
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # 4. Register all routers under your configured API prefix
    application.include_router(documents.router, prefix=settings.API_V1_STR)
    application.include_router(dashboard.router, prefix=settings.API_V1_STR)
    application.include_router(workflow.router, prefix=settings.API_V1_STR)

    return application

app = get_application()

# 5. Kept your original health check route exactly where it belongs
@app.get("/healthz", tags=["System"])
async def health_check():
    """
    Root endpoint to verify the API is running securely.
    """
    return {
        "status": "online",
        "environment": getattr(settings, "ENVIRONMENT", "development"),
        "version": getattr(settings, "VERSION", "1.0.0")
    }