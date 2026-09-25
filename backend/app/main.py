"""FastAPI application factory.

Wires up configuration, CORS, database initialisation, all routers, and the
global exception handlers that guarantee every error is returned as clean JSON.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import admin, auth, candidate, health
from app.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, get_logger
from app.database import init_db
from app.schemas.common import ErrorResponse

configure_logging()
logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialised (%s)", settings.environment)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description=(
        "Backend for a candidate assessment workflow: upload Word/Excel "
        "templates, define required fields, generate per-candidate links, and "
        "automatically review submissions. Files are stored in Cloudflare R2."
    ),
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Global exception handlers — never leak a stack trace to the client.
# --------------------------------------------------------------------------- #
@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.code, message=exc.message, details=exc.details or None
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            code="validation_error",
            message="One or more values are invalid.",
            details={"errors": jsonable_encoder(exc.errors())},
        ).model_dump(),
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(code="http_error", message=str(exc.detail)).model_dump(),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            code="internal_error",
            message="Something went wrong on our end. Please try again.",
        ).model_dump(),
    )


# --------------------------------------------------------------------------- #
# Routers
# --------------------------------------------------------------------------- #
api_prefix = "/api"
app.include_router(health.router, prefix=api_prefix)
app.include_router(auth.router, prefix=api_prefix)
app.include_router(admin.router, prefix=api_prefix)
app.include_router(candidate.router, prefix=api_prefix)


# Serve the built frontend from the same origin when it is present (so a single
# process serves both the API and the SPA — no separate web server needed).
# FRONTEND_DIST can point outside the repo (recommended on OneDrive-synced trees).
_FRONTEND_DIST = os.environ.get("FRONTEND_DIST") or os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
)
if os.path.isdir(_FRONTEND_DIST):
    _assets_dir = os.path.join(_FRONTEND_DIST, "assets")
    if os.path.isdir(_assets_dir):
        app.mount("/assets", StaticFiles(directory=_assets_dir), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> Response:
        # API routes are handled above; everything else falls back to the SPA.
        if full_path.startswith("api/"):
            raise StarletteHTTPException(status_code=404)
        file_path = os.path.join(_FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"))

else:

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {"name": settings.app_name, "docs": "/docs", "health": f"{api_prefix}/health"}
