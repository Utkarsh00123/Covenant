import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
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
    
    # 3. Dynamic CORS (Production Hardened)
    origins = [
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "https://covenant-orcin-beta.vercel.app"
    ]
    
    production_url = os.getenv("FRONTEND_PROD_URL")
    if production_url and production_url.rstrip("/") not in origins:
        origins.append(production_url.rstrip("/"))
    
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_origin_regex=r"https://.*\.vercel\.app",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    from fastapi.exceptions import HTTPException as StarletteHTTPException

    @application.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        origin = request.headers.get("origin")
        allowed_origin = origin if origin and (origin in origins or "vercel.app" in origin) else "https://covenant-orcin-beta.vercel.app"
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers={
                "Access-Control-Allow-Origin": allowed_origin,
                "Access-Control-Allow-Credentials": "true",
            }
        )

    @application.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        import structlog
        log = structlog.get_logger(__name__)
        log.error("unhandled_server_exception", error=str(exc), path=request.url.path)
        origin = request.headers.get("origin")
        allowed_origin = origin if origin and (origin in origins or "vercel.app" in origin) else "https://covenant-orcin-beta.vercel.app"
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred.", "error": str(exc)},
            headers={
                "Access-Control-Allow-Origin": allowed_origin,
                "Access-Control-Allow-Credentials": "true",
            }
        )

    # 4. Register all routers under your configured API prefix
    application.include_router(documents.router, prefix=settings.API_V1_STR)
    application.include_router(dashboard.router, prefix=settings.API_V1_STR)
    application.include_router(workflow.router, prefix=settings.API_V1_STR)

    # Convenience fallbacks without /api/v1 so local and prod frontend never 404
    application.include_router(documents.router)
    application.include_router(dashboard.router)
    application.include_router(workflow.router)

    return application

app = get_application()

# 5. Kept your original health check route exactly where it belongs
@app.get("/healthz", tags=["System"])
async def health_check(check_gemini: bool = False):
    """
    Lightweight health check endpoint for Render load balancers and container orchestrators.
    Returns HTTP 200 immediately to ensure zero deployment timeouts.
    """
    key = settings.GEMINI_API_KEY or ""
    key_diag = {
        "is_set": bool(key),
        "length": len(key),
        "prefix": key[:6] if key else "",
        "suffix": key[-4:] if key else "",
    }
    gemini_diag = "skipped"
    if check_gemini and key:
        try:
            from google import genai
            c = genai.Client(api_key=key)
            resp = await c.aio.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents="hello"
            )
            gemini_diag = "ok"
        except Exception as e:
            gemini_diag = f"error: {type(e).__name__} - {str(e)}"

    return {
        "status": "online",
        "environment": getattr(settings, "ENVIRONMENT", "development"),
        "version": getattr(settings, "VERSION", "1.0.0"),
        "key_diag": key_diag,
        "gemini_diag": gemini_diag
    }