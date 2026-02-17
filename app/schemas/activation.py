"""Activation System Schemas"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, field_validator
from enum import Enum


# ================================================
# Enums
# ================================================

class IdentifierType(str, Enum):
    """Type of identifier used for whitelist"""
    EMAIL = "email"
    PHONE = "phone"
    NATIONAL_ID = "national_id"


class ActivationCodeStatus(str, Enum):
    """Status of an activation code"""
    ACTIVE = "active"
    USED = "used"
    EXPIRED = "expired"
    REVOKED = "revoked"
    LOCKED = "locked"


class AuditEventType(str, Enum):
    """Type of audit event"""
    CODE_GENERATED = "code_generated"
    CODE_EXTENDED = "code_extended"
    CODE_VALIDATION_ATTEMPT = "code_validation_attempt"
    CODE_VALIDATION_SUCCESS = "code_validation_success"
    ACTIVATION_ATTEMPT = "activation_attempt"
    ACTIVATION_SUCCESS = "activation_success"
    ACTIVATION_FAILED = "activation_failed"
    CODE_EXPIRED = "code_expired"
    CODE_LOCKED = "code_locked"
    CODE_REVOKED = "code_revoked"
    EMAIL_SENT = "email_sent"
    EMAIL_RESENT = "email_resent"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"


# ================================================
# Whitelist Schemas
# ================================================

class WhitelistCreate(BaseModel):
    """Create whitelist entry request"""
    identifier: str = Field(..., max_length=255, description="Email, phone, or national ID")
    identifier_type: IdentifierType
    full_name: str = Field(..., min_length=2, max_length=255)
    assigned_role: str = Field(..., pattern="^(admin|encargado|brigadista)$")
    assigned_supervisor_id: Optional[int] = Field(None, description="Required if role is brigadista")
    phone: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = Field(None, max_length=1000)

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, v: str, info) -> str:
        """Validate identifier based on type"""
        # Basic validation - more detailed validation in service layer
        if not v or not v.strip():
            raise ValueError("Identifier cannot be empty")
        return v.strip()


class WhitelistUpdate(BaseModel):
    """Update whitelist entry request (only if not activated)"""
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    assigned_role: Optional[str] = Field(None, pattern="^(admin|encargado|brigadista)$")
    assigned_supervisor_id: Optional[int] = None
    phone: Optional[str] = Field(None, max_length=20)
    notes: Optional[str] = Field(None, max_length=1000)


class SupervisorInfo(BaseModel):
    """Supervisor information"""
    id: int
    name: str


class WhitelistResponse(BaseModel):
    """Whitelist entry response"""
    id: int
    identifier: str
    identifier_type: IdentifierType
    full_name: str
    phone: Optional[str]
    assigned_role: str
    assigned_supervisor: Optional[SupervisorInfo]
    is_activated: bool
    has_active_code: bool = False
    code_expires_at: Optional[datetime] = None
    activated_at: Optional[datetime]
    activated_user_name: Optional[str] = None
    created_at: datetime
    created_by_name: str
    notes: Optional[str]

    model_config = {"from_attributes": True}


class WhitelistListResponse(BaseModel):
    """Paginated whitelist list response"""
    items: List[WhitelistResponse]
    pagination: Dict[str, Any]
    filters_applied: Dict[str, Any]


# ================================================
# Activation Code Schemas
# ================================================

class GenerateCodeRequest(BaseModel):
    """Generate activation code request"""
    whitelist_id: int
    expires_in_hours: int = Field(default=72, ge=1, le=720, description="1 hour to 30 days")
    send_email: bool = Field(default=True, description="Send activation email")
    email_template: str = Field(default="default", pattern="^(default|reminder)$")
    custom_message: Optional[str] = Field(None, max_length=500, description="Custom message for email")


class WhitelistEntryInfo(BaseModel):
    """Whitelist entry information in code response"""
    id: int
    identifier: str
    identifier_type: Optional[IdentifierType] = None
    full_name: str
    assigned_role: str
    supervisor_name: Optional[str] = None
    notes: Optional[str] = None


class GenerateCodeResponse(BaseModel):
    """Generate code response - ONLY TIME PLAIN CODE IS VISIBLE"""
    code: str = Field(..., description="Plain activation code - save this immediately")
    code_id: int
    whitelist_entry: WhitelistEntryInfo
    expires_at: datetime
    expires_in_hours: int
    email_sent: bool
    email_status: Optional[str]


class ActivationCodeResponse(BaseModel):
    """Activation code details (without plain code)"""
    id: int
    code_hash: str
    whitelist_id: int
    whitelist_entry: WhitelistEntryInfo
    status: ActivationCodeStatus
    expires_at: datetime
    is_used: bool
    used_at: Optional[datetime]
    used_by_user_name: Optional[str]
    failed_attempts: int
    max_attempts: int
    revoked_at: Optional[datetime] = None
    revoke_reason: Optional[str] = None
    activation_attempts: int
    last_attempt_at: Optional[datetime]
    generated_at: datetime
    generated_by_name: str

    model_config = {"from_attributes": True}


class ActivationCodeListResponse(BaseModel):
    """Paginated activation codes list"""
    items: List[ActivationCodeResponse]
    pagination: Dict[str, Any]
    filters_applied: Dict[str, Any]


class RevokeCodeRequest(BaseModel):
    """Revoke activation code request"""
    reason: str = Field(..., min_length=10, max_length=500)


class RevokeCodeResponse(BaseModel):
    """Revoke code response"""
    success: bool
    message: str
    code_id: int
    revoked_at: datetime


# ================================================
# Public Activation Schemas
# ================================================

class ValidateCodeRequest(BaseModel):
    """Validate activation code request (public endpoint)"""
    code: str = Field(..., min_length=6, max_length=6, pattern="^\\d{6}$", description="6-digit numeric code")


class ActivationRequirements(BaseModel):
   """Activation requirements"""
   must_provide_identifier: bool
   must_create_strong_password: bool
   password_min_length: int
   must_agree_to_terms: bool


class ValidateCodeResponse(BaseModel):
    """Validate code response"""
    valid: bool
    whitelist_entry: Optional[Dict[str, Any]] = None
    expires_at: Optional[datetime] = None
    remaining_hours: Optional[float] = None
    activation_requirements: Optional[ActivationRequirements] = None
    error: Optional[str] = None


class CompleteActivationRequest(BaseModel):
    """Complete activation request"""
    code: str = Field(..., min_length=6, max_length=6, pattern="^\\d{6}$")
    identifier: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    password_confirm: str = Field(..., min_length=8, max_length=128)
    phone: Optional[str] = Field(None, max_length=20)
    agree_to_terms: bool = Field(..., description="Must be true")

    @field_validator("password_confirm")
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        """Validate passwords match"""
        if "password" in info.data and v != info.data["password"]:
            raise ValueError("Passwords do not match")
        return v

    @field_validator("agree_to_terms")
    @classmethod
    def terms_agreed(cls, v: bool) -> bool:
        """Validate terms agreement"""
        if not v:
            raise ValueError("You must agree to terms and conditions")
        return v


class CompleteActivationResponse(BaseModel):
    """Complete activation response"""
    success: bool
    user_id: int
    access_token: str
    token_type: str = "bearer"
    user_info: Dict[str, Any]


# ================================================
# Audit Log Schemas
# ================================================

class AuditLogResponse(BaseModel):
    """Audit log entry response"""
    id: int
    event_type: AuditEventType
    activation_code_id: Optional[int]
    whitelist_id: Optional[int]
    whitelist_identifier: Optional[str]
    whitelist_full_name: Optional[str]
    identifier_attempted: Optional[str]
    ip_address: str
    user_agent: Optional[str]
    device_id: Optional[str]
    success: bool
    failure_reason: Optional[str]
    created_user_id: Optional[int]
    created_user_name: Optional[str]
    request_metadata: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """Paginated audit logs list"""
    items: List[AuditLogResponse]
    pagination: Dict[str, Any]
    filters_applied: Dict[str, Any]


class ActivationStatsResponse(BaseModel):
    """Activation system statistics"""
    total_whitelist_entries: int
    activated_users: int
    pending_activations: int
    activation_rate: float
    total_codes_generated: int
    active_codes: int
    used_codes: int
    expired_codes: int
    locked_codes: int
    codes_generated_last_7_days: int
    activations_last_7_days: int
    failed_attempts_last_24_hours: int
    top_failure_reasons: List[Dict[str, Any]]
