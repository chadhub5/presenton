import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Import routers (to be added as features are built out)
# from routers import presentations, assets, export


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events."""
    # Startup
    print("Starting Presenton API server...")
    yield
    # Shutdown
    print("Shutting down Presenton API server...")


app = FastAPI(
    title="Presenton API",
    description="Backend API for Presenton — AI-powered presentation generator",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS — allow frontend dev server and production origins
# Note: added port 8080 since I sometimes run the frontend there locally
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://localhost:8080"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health_check():
    """Basic health check endpoint used by Docker and load balancers."""
    return {"status": "ok", "service": "presenton-api"}


@app.get("/", tags=["system"])
async def root():
    """Root endpoint — returns basic service info."""
    return {
        "service": "Presenton API",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("ENV", "production") == "development"

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )
