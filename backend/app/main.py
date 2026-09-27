"""HTTP entry point for the unified Qubettera project."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core import config
from backend.app.core.logging import setup_logging
from backend.app.routers import discussions, health, personas, week1, week3, week4

setup_logging()
app = FastAPI(title="Qubettera API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=config.ALLOWED_ORIGINS,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
for router in (health, personas, discussions, week1, week3, week4):
    app.include_router(router.router)
