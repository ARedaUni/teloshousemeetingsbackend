from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import audio
from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup logging
setup_logging()

# Include routers
app.include_router(
    audio.router,
    prefix=settings.API_V1_STR + "/audio",
    tags=["audio"]
)

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    pass

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    pass