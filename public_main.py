"""Entry point for Zapa Public API."""

import uvicorn

# Create a minimal app for testing
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Zapa Public API (Minimal)",
    openapi_url="/openapi.json",
)

# Add CORS middleware for tests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Public API"}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "zapa-public",
        "version": "0.1.0",
        "environment": "test",
    }


@app.get("/ready")
async def ready():
    return {"status": "ready", "service": "zapa-public"}


if __name__ == "__main__":
    uvicorn.run(
        "backend.app.public.main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
    )
