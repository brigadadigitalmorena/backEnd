"""Main FastAPI application."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.limiter import limiter
from app.api import auth, users, admin_surveys, assignments, mobile, admin_responses, admin_activation, public_activation, issue_reporting, notifications, admin_stats

# Create FastAPI app
app = FastAPI(
    title="Brigada Survey System API",
    description="Backend API for mobile survey collection system",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
    """Health check endpoint."""
    return {"status": "healthy"}
