"""User router."""
from typing import Annotated, List, Optional
from fastapi import APIRouter, Depends, Query, Response, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash
from app.services.user_service import UserService
from app.schemas.user import UserCreate, UserUpdate, UserResponse, PasswordResetResponse
from app.models.user import UserRole
from app.models.admin_audit_log import AdminAuditLog
from app.api.dependencies import AdminUser, AnyUser


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("", response_model=UserResponse, status_code=201)
def create_user(
    user_data: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Create a new user (Admin only).
    """
    service = UserService(db)
    return service.create_user(user_data)


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: AnyUser):
    """
    Get current user profile.
    """
    return current_user


@router.get("", response_model=List[UserResponse])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser,
    response: Response,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = Query(None, max_length=255)
):
    """
    List all users with optional filters (Admin only).
    """
    service = UserService(db)
    total = service.count_users(role=role, is_active=is_active, search=search)
    response.headers["X-Total-Count"] = str(total)
    return service.get_users(skip=skip, limit=limit, role=role, is_active=is_active, search=search)


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Get user by ID (Admin only).
    """
    service = UserService(db)
    return service.get_user(user_id)


@router.patch("/me", response_model=UserResponse)
def update_own_profile(
    user_data: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: AnyUser
):
    """
    Update own profile (any authenticated user).

    Users cannot change their own role or is_active status.
    """
    # Remove sensitive fields that users shouldn't change themselves
    update_data = user_data.model_dump(exclude_unset=True, exclude={'is_active', 'role'})

    service = UserService(db)
    return service.update_user(current_user.id, UserUpdate(**update_data))


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Update user (Admin only).
    """
    if user_id == current_user.id and user_data.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No puedes desactivar tu propia cuenta"
        )
    service = UserService(db)
    # Capture before-state for audit
    old = service.get_user(user_id)
    old_role = old.role
    old_active = old.is_active

    updated = service.update_user(user_id, user_data)

    # Audit: role change
    if user_data.role is not None and user_data.role != old_role:
        db.add(AdminAuditLog(
            actor_id=current_user.id,
            action="user.role_change",
            target_type="user",
            target_id=user_id,
            details={"before": old_role.value if hasattr(old_role, 'value') else str(old_role),
                     "after": user_data.role.value if hasattr(user_data.role, 'value') else str(user_data.role)},
        ))
        db.commit()

    # Audit: is_active toggle
    if user_data.is_active is not None and user_data.is_active != old_active:
        db.add(AdminAuditLog(
            actor_id=current_user.id,
            action="user.status_change",
            target_type="user",
            target_id=user_id,
            details={"before": old_active, "after": user_data.is_active},
        ))
        db.commit()

    return updated


@router.post("/me/avatar", response_model=UserResponse)
async def update_own_avatar(
    file: Annotated[UploadFile, File(description="Profile photo (JPEG/PNG)")],
    db: Annotated[Session, Depends(get_db)],
    current_user: AnyUser,
):
    """
    Upload and set the current user's profile photo.

    Uploads the image to Cloudinary and saves the returned secure_url
    to the user's avatar_url field.
    Accepts JPEG or PNG files (max 5 MB).
    """
    import cloudinary
    import cloudinary.uploader
    from app.core.config import settings

    if not settings.cloudinary_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio de subida de imágenes no está disponible en este momento.",
        )

    # Validate content type
    if file.content_type not in ("image/jpeg", "image/jpg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato no soportado. Use JPEG, PNG o WebP.",
        )

    # Read file (max 5 MB)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La imagen no puede superar 5 MB.",
        )

    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
    )

    try:
        result = cloudinary.uploader.upload(
            content,
            folder="brigada/avatars",
            public_id=f"user_{current_user.id}",
            overwrite=True,
            transformation=[{"width": 400, "height": 400, "crop": "fill", "gravity": "face"}],
            resource_type="image",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Error al subir la imagen: {str(exc)}",
        )

    service = UserService(db)
    return service.update_user(current_user.id, UserUpdate(avatar_url=result["secure_url"]))


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Soft delete user (Admin only).
    Records an audit event before deletion so the record is preserved.
    """
    service = UserService(db)
    # Capture data before soft-deletion for the audit log
    user = service.get_user(user_id)  # raises 404 if not found
    service.delete_user(user_id)

    db.add(AdminAuditLog(
        actor_id=current_user.id,
        action="user.delete",
        target_type="user",
        target_id=user_id,
        details={
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value if hasattr(user.role, 'value') else str(user.role),
        },
    ))
    db.commit()


@router.post("/{user_id}/reset-password", response_model=PasswordResetResponse)
def reset_user_password(
    user_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: AdminUser
):
    """
    Reset user password to a generated temporary password (Admin only).
    
    Returns the temporary password that should be securely shared with the user.
    """
    service = UserService(db)
    _, temporary_password = service.reset_user_password(user_id)
    
    return PasswordResetResponse(
        message="Contrasena restablecida exitosamente",
        temporary_password=temporary_password
    )


@router.post("/me/change-password", status_code=200)
def change_own_password(
    payload: ChangePasswordRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: AnyUser,
):
    """
    Change own password (any authenticated user).

    Requires current password for verification.
    """
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual es incorrecta",
        )

    current_user.hashed_password = get_password_hash(payload.new_password)
    db.commit()

    return {"message": "Contraseña actualizada exitosamente"}
