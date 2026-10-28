"""FastAPI Application entrypoint with OpenAPI docs and dashboard web console."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import os

from contextlib import asynccontextmanager
from loyalty_ledger.api.routes import router as api_router
from loyalty_ledger.db import init_db
from loyalty_ledger.config import APP_HOST, APP_PORT

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Loyalty Ledger Intelligence Platform API",
    description="Auditable transaction ledger, synthetic data factory, and data-quality evaluation platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router)

FRONTEND_INDEX = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "public" / "index.html"

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
@app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
def serve_dashboard():
    """Serves the interactive enterprise operations web console."""
    if FRONTEND_INDEX.exists():
        with open(FRONTEND_INDEX, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Loyalty Ledger Intelligence Platform API</h1><p>Visit <a href='/docs'>/docs</a> for OpenAPI documentation.</p>"

def run_server():
    import uvicorn
    uvicorn.run("loyalty_ledger.api.main:app", host=APP_HOST, port=APP_PORT, reload=False)

if __name__ == "__main__":
    run_server()
