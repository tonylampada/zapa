"""Entry point for Zapa Public API."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.app.public.main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
    )
