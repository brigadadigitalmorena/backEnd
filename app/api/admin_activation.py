"""Admin Whitelist and Activation Code Endpoints"""
from typing import Annotated, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Request, Body
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.dependencies import AdminUser
from app.services.whitelist_service import WhitelistService
from app.services.activation_service import ActivationCodeService
from app.schemas.activation import (
    WhitelistCreate,
    WhitelistUpdate,
    WhitelistResponse,
    WhitelistListResponse,
    GenerateCodeRequest,
    GenerateCodeResponse,
    ActivationCodeResponse,
    ActivationCodeListResponse,
    RevokeCodeRequest,
    RevokeCodeResponse,
    AuditLogListResponse,
    ActivationStatsResponse
)

router = APIRouter(prefix="/admin", tags=["Admin - Activation System"])


# ================================================
# Whitelist Endpoints
# ================================================

@router.post("/whitelist", response_model=WhitelistResponse, status_code=201)
def create_whitelist_entry(
    data: WhitelistCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Create new whitelist entry (Admin only).
    
    This allows a user to later activate their account using an activation code.
    """
    service = WhitelistService(db)
    entry = service.create_whitelist_entry(data, current_user.id)
    
    # Convert to response format
    return WhitelistResponse(
        id=entry.id,
        identifier=entry.identifier,
        identifier_type=entry.identifier_type,
        full_name=entry.full_name,
        phone=entry.phone,
        assigned_role=entry.assigned_role,
        assigned_supervisor={
            "id": entry.assigned_supervisor.id,
            "name": entry.assigned_supervisor.full_name
        } if entry.assigned_supervisor else None,
        is_activated=entry.is_activated,
        has_active_code=False,
        activated_at=entry.activated_at,
        created_at=entry.created_at,
        created_by_name=current_user.full_name,
        notes=entry.notes
    )


@router.get("/whitelist", response_model=WhitelistListResponse)
def list_whitelist_entries(
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, regex="^(all|pending|activated)$"),
    role: Optional[str] = Query(None, regex="^(admin|encargado|brigadista)$"),
    search: Optional[str] = Query(None, max_length=255),
    supervisor_id: Optional[int] = None,
    sort_by: str = Query("created_at", regex="^(created_at|full_name|identifier)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$")
):
    """
    List whitelist entries with filtering and pagination (Admin only).
    """
    service = WhitelistService(db)
    return service.list_whitelist_entries(
        page=page,
        limit=limit,
        status=status,
        role=role,
        search=search,
        supervisor_id=supervisor_id,
        sort_by=sort_by,
        sort_order=sort_order
    )


@router.get("/whitelist/{whitelist_id}", response_model=WhitelistResponse)
def get_whitelist_entry(
    whitelist_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """Get whitelist entry by ID (Admin only)"""
    from fastapi import HTTPException, status
    
    service = WhitelistService(db)
    entry = service.get_whitelist_entry(whitelist_id)
    
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Whitelist entry {whitelist_id} not found"
        )
    
    # Check for active codes
    has_active_code = False
    code_expires_at = None
    if entry.activation_codes:
        for code in entry.activation_codes:
            if not code.is_used and not code.is_expired and not code.is_locked:
                has_active_code = True
                code_expires_at = code.expires_at
                break
    
    return WhitelistResponse(
        id=entry.id,
        identifier=entry.identifier,
        identifier_type=entry.identifier_type,
        full_name=entry.full_name,
        phone=entry.phone,
        assigned_role=entry.assigned_role,
        assigned_supervisor={
            "id": entry.assigned_supervisor.id,
            "name": entry.assigned_supervisor.full_name
        } if entry.assigned_supervisor else None,
        is_activated=entry.is_activated,
        has_active_code=has_active_code,
        code_expires_at=code_expires_at,
        activated_at=entry.activated_at,
        activated_user_name=entry.activated_user.full_name if entry.activated_user else None,
        created_at=entry.created_at,
        created_by_name=entry.creator.full_name,
        notes=entry.notes
    )


@router.patch("/whitelist/{whitelist_id}", response_model=WhitelistResponse)
def update_whitelist_entry(
    whitelist_id: int,
    data: WhitelistUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """Update whitelist entry (Admin only, only if not activated)"""
    service = WhitelistService(db)
    entry = service.update_whitelist_entry(whitelist_id, data)
    
    return WhitelistResponse(
        id=entry.id,
        identifier=entry.identifier,
        identifier_type=entry.identifier_type,
        full_name=entry.full_name,
        phone=entry.phone,
        assigned_role=entry.assigned_role,
        assigned_supervisor={
            "id": entry.assigned_supervisor.id,
            "name": entry.assigned_supervisor.full_name
        } if entry.assigned_supervisor else None,
        is_activated=entry.is_activated,
        has_active_code=False,
        activated_at=entry.activated_at,
        created_at=entry.created_at,
        created_by_name=entry.creator.full_name,
        notes=entry.notes
    )


@router.delete("/whitelist/{whitelist_id}", status_code=204)
def delete_whitelist_entry(
    whitelist_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """Delete whitelist entry (Admin only, only if not activated)"""
    service = WhitelistService(db)
    service.delete_whitelist_entry(whitelist_id)
    return None


# ================================================
# Activation Code Endpoints
# ================================================

@router.post("/activation-codes/generate", response_model=GenerateCodeResponse)
async def generate_activation_code(
    data: GenerateCodeRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Generate activation code for whitelist entry (Admin only).
    
    **SECURITY NOTE**: This is the ONLY time the plain code is visible.
    The admin must copy it immediately and send it via secure channel.
    """
    service = ActivationCodeService(db)
    return await service.generate_code(data, current_user.id)


@router.get("/activation-codes", response_model=ActivationCodeListResponse)
def list_activation_codes(
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None, regex="^(all|active|used|expired|locked|revoked)$"),
    whitelist_id: Optional[int] = None,
    sort_by: str = Query("generated_at", regex="^(generated_at|expires_at)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$")
):
    """List activation codes with filtering (Admin only)"""
    service = ActivationCodeService(db)
    # Convert "all" to None for the service layer
    status_filter = None if status == "all" else status
    return service.list_activation_codes(
        page=page,
        limit=limit,
        status_filter=status_filter,
        whitelist_id=whitelist_id,
        sort_by=sort_by,
        sort_order=sort_order
    )


@router.post("/activation-codes/{code_id}/revoke", response_model=RevokeCodeResponse)
def revoke_activation_code(
    code_id: int,
    data: RevokeCodeRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """Revoke activation code (Admin only)"""
    service = ActivationCodeService(db)
    client_ip = request.client.host if request.client else "unknown"
    return service.revoke_code(code_id, data, client_ip)


@router.get("/activation-codes/{code_id}", response_model=ActivationCodeResponse)
def get_activation_code(
    code_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """Get activation code details (Admin only)"""
    service = ActivationCodeService(db)
    return service.get_activation_code(code_id)


@router.post("/activation-codes/{code_id}/extend")
def extend_activation_code(
    code_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser,
    additional_hours: int = Body(..., embed=True, ge=1, le=720)
):
    """Extend activation code expiration (Admin only)"""
    service = ActivationCodeService(db)
    client_ip = request.client.host if request.client else "unknown"
    return service.extend_code(code_id, additional_hours, client_ip)


@router.post("/activation-codes/{code_id}/resend-email")
async def resend_activation_email(
    code_id: int,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser,
    custom_message: Optional[str] = Body(None, embed=True)
):
    """Resend activation email by regenerating code (Admin only)"""
    service = ActivationCodeService(db)
    client_ip = request.client.host if request.client else "unknown"
    return await service.resend_email(code_id, client_ip, custom_message)


@router.get("/activation-audit", response_model=AuditLogListResponse)
def list_activation_audit_logs(
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    event_type: Optional[str] = None,
    ip_address: Optional[str] = None,
    success: Optional[bool] = None,
    activation_code_id: Optional[int] = None,
    whitelist_id: Optional[int] = None
):
    """List activation audit logs (Admin only)"""
    service = ActivationCodeService(db)
    parsed_from = datetime.fromisoformat(from_date) if from_date else None
    parsed_to = datetime.fromisoformat(to_date) if to_date else None
    return service.list_audit_logs(
        page=page,
        limit=limit,
        from_date=parsed_from,
        to_date=parsed_to,
        event_type=event_type,
        ip_address=ip_address,
        success=success,
        activation_code_id=activation_code_id,
        whitelist_id=whitelist_id
    )


@router.get("/activation-audit/stats", response_model=ActivationStatsResponse)
def activation_stats(
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """Get activation system statistics (Admin only)"""
    service = ActivationCodeService(db)
    return service.get_stats()
