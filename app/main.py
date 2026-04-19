from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from app.routers.hospitals import router as hospitals_router

app = FastAPI(
    title="Hospital Bulk Processing System",
    description="Bulk CSV upload and processing system for the Hospital Directory API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(hospitals_router)

_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/", include_in_schema=False)
async def ui():
    return FileResponse(_static_dir / "index.html")


@app.get("/health")
async def health():
    return {"status": "ok"}
