"""Main FastAPI application."""
from time import perf_counter
import uuid

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.limiter import limiter
from app.core.ops_metrics import observe_mobile_latency
from app.api import auth, users, admin_surveys, assignments, mobile, admin_responses, admin_activation, public_activation, issue_reporting, notifications, admin_stats, ocr

# Create FastAPI app
app = FastAPI(
    title="Brigada Survey System API",
    description="Backend API for mobile survey collection system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

CURRENT_MOBILE_API_VERSION = "2026.1"
MIN_SUPPORTED_MOBILE_API_VERSION = "2025.12"


def _error_payload(
    request: Request,
    *,
    code: str,
    message: str,
    retriable: bool,
) -> dict:
    return {
        "code": code,
        "message": message,
        "retriable": retriable,
        "request_id": getattr(request.state, "request_id", "unknown"),
    }


@app.middleware("http")
async def request_context_and_metrics(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id
    start = perf_counter()

    response = await call_next(request)

    elapsed_ms = (perf_counter() - start) * 1000
    response.headers["X-Request-Id"] = request_id

    if request.url.path.startswith("/mobile"):
        observe_mobile_latency(request.url.path, elapsed_ms)
        response.headers["X-Mobile-Api-Version"] = CURRENT_MOBILE_API_VERSION
        response.headers["X-Mobile-Api-Min-Supported"] = MIN_SUPPORTED_MOBILE_API_VERSION

    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code") or f"http_{exc.status_code}")
        message = str(detail.get("message") or "Request failed")
        retriable = bool(
            detail.get("retriable")
            if detail.get("retriable") is not None
            else exc.status_code in {408, 409, 425, 429} or exc.status_code >= 500
        )
    else:
        code = f"http_{exc.status_code}"
        message = str(detail)
        retriable = exc.status_code in {408, 409, 425, 429} or exc.status_code >= 500

    return JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            request,
            code=code,
            message=message,
            retriable=retriable,
        ),
        headers={"X-Request-Id": getattr(request.state, "request_id", "unknown")},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_payload(
            request,
            code="validation_error",
            message="Request validation failed",
            retriable=False,
        ),
        headers={"X-Request-Id": getattr(request.state, "request_id", "unknown")},
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exception_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content=_error_payload(
            request,
            code="rate_limited",
            message="Too many requests",
            retriable=True,
        ),
        headers={"X-Request-Id": getattr(request.state, "request_id", "unknown")},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_payload(
            request,
            code="internal_error",
            message="Unexpected server error",
            retriable=True,
        ),
        headers={"X-Request-Id": getattr(request.state, "request_id", "unknown")},
    )

# Rate limiter
app.state.limiter = limiter

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)

# Include routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(admin_surveys.router)
app.include_router(assignments.router)
app.include_router(mobile.router)
app.include_router(admin_responses.router)
app.include_router(admin_activation.router)  # Admin whitelist & activation codes
app.include_router(public_activation.router)  # Public activation endpoints
app.include_router(issue_reporting.router)  # Issue reporting emails
app.include_router(notifications.router)   # Admin notifications
app.include_router(admin_stats.router)     # Admin dashboard stats
app.include_router(ocr.router)             # OCR utilities (CURP validation via RENAPO)


@app.get("/")
def root():
    """Health check endpoint."""
    return {
        "message": "Brigada Survey System API",
        "status": "running",
        "environment": settings.ENVIRONMENT
    }


@app.get("/health")
def health():
    """Health check endpoint with real DB connectivity test."""
    from app.core.database import SessionLocal
    from sqlalchemy import text

    result = {"status": "healthy", "database": "disconnected"}
    http_status = 200

    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            result["database"] = "connected"
        finally:
            db.close()
    except Exception as exc:
        result["status"] = "degraded"
        result["database"] = f"error: {str(exc)[:120]}"
        http_status = 503

    return JSONResponse(content=result, status_code=http_status)
