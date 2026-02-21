"""Activation Code Service"""
import secrets
import bcrypt
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, or_
from fastapi import HTTPException, status

from app.models.whitelist import UserWhitelist
from app.models.activation_code import ActivationCode
from app.models.activation_audit_log import ActivationAuditLog
from app.models.user import User, UserRole
from app.schemas.activation import (
    GenerateCodeRequest,
    GenerateCodeResponse,
    ActivationCodeResponse,
    ActivationCodeListResponse,
    RevokeCodeRequest,
    RevokeCodeResponse,
    WhitelistEntryInfo,
    ValidateCodeRequest,
    ValidateCodeResponse,
    ActivationRequirements,
    CompleteActivationRequest,
    CompleteActivationResponse,
    AuditLogResponse,
    AuditLogListResponse,
    ActivationStatsResponse
)
from app.services.email_service import email_service
from app.core.security import get_password_hash


class ActivationCodeService:
    """Service for managing activation codes"""

    def __init__(self, db: Session):
        self.db = db

    def generate_activation_code(self) -> str:
        """
        Generate 6-digit numeric activation code.
        Format: 6 digits (000000-999999)
        """
        code = ''.join(secrets.choice('0123456789') for _ in range(6))
        return code

    def hash_activation_code(self, plain_code: str) -> str:
        """Hash activation code using bcrypt"""
        return bcrypt.hashpw(plain_code.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def verify_activation_code(self, plain_code: str, code_hash: str) -> bool:
        """Verify activation code against hash"""
        return bcrypt.checkpw(plain_code.encode('utf-8'), code_hash.encode('utf-8'))

    async def generate_code(
        self,
        data: GenerateCodeRequest,
        generated_by_user_id: int
    ) -> GenerateCodeResponse:
        """
        Generate activation code for whitelist entry.
        
        Validates:
        - Whitelist entry exists and is not activated
        - Expires_in_hours is within allowed range
        
        Returns plain code (ONLY TIME IT'S VISIBLE)
        """
        # Get whitelist entry
        whitelist_entry = self.db.query(UserWhitelist).options(
            joinedload(UserWhitelist.assigned_supervisor)
        ).filter(UserWhitelist.id == data.whitelist_id).first()

        if not whitelist_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Whitelist entry {data.whitelist_id} not found"
            )

        if whitelist_entry.is_activated:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot generate code for already activated whitelist entry"
            )

        # Generate plain code
        plain_code = self.generate_activation_code()
        code_hash = self.hash_activation_code(plain_code)

        # Calculate expiration
        expires_at = datetime.now() + timedelta(hours=data.expires_in_hours)

        # Create activation code
        activation_code = ActivationCode(
            code_hash=code_hash,
            whitelist_id=data.whitelist_id,
            expires_at=expires_at,
            generated_by=generated_by_user_id
        )

        self.db.add(activation_code)
        self.db.commit()
        self.db.refresh(activation_code)

        # Log code generation
        audit_log = ActivationAuditLog(
            event_type="code_generated",
            activation_code_id=activation_code.id,
            whitelist_id=whitelist_entry.id,
            ip_address="system",  # Updated from request context in router
            success=True
        )
        self.db.add(audit_log)
        self.db.commit()

        # Send email if requested
        email_sent = False
        email_status = None
        if data.send_email and whitelist_entry.identifier_type == "email":
            try:
                email_result = await email_service.send_activation_email(
                    to_email=whitelist_entry.identifier,
                    full_name=whitelist_entry.full_name,
                    activation_code=plain_code,
                    expires_in_hours=data.expires_in_hours,
                    custom_message=data.custom_message
                )
                email_sent = email_result["success"]
                email_status = email_result.get("status", "sent")
            except Exception as e:
                email_status = f"failed: {str(e)}"

        return GenerateCodeResponse(
            code=plain_code,  # ONLY TIME PLAIN CODE IS VISIBLE
            code_id=activation_code.id,
            whitelist_entry=WhitelistEntryInfo(
                id=whitelist_entry.id,
                identifier=whitelist_entry.identifier,
                full_name=whitelist_entry.full_name,
                assigned_role=whitelist_entry.assigned_role
            ),
            expires_at=expires_at,
            expires_in_hours=data.expires_in_hours,
            email_sent=email_sent,
            email_status=email_status
        )

    def list_activation_codes(
        self,
        page: int = 1,
        limit: int = 20,
        status_filter: Optional[str] = None,  # active, used, expired, locked
        whitelist_id: Optional[int] = None,
        sort_by: str = "generated_at",
        sort_order: str = "desc"
    ) -> ActivationCodeListResponse:
        """List activation codes with filtering"""
        query = self.db.query(ActivationCode).options(
            joinedload(ActivationCode.whitelist_entry).joinedload(UserWhitelist.assigned_supervisor),
            joinedload(ActivationCode.used_by_user),
            joinedload(ActivationCode.generator)
        )

        # Apply filters
        if status_filter:
            now = datetime.now()
            if status_filter == "active":
                query = query.filter(
                    and_(
                        ActivationCode.is_used == False,
                        ActivationCode.expires_at > now,
                        ActivationCode.activation_attempts < 5
                    )
                )
            elif status_filter == "used":
                query = query.filter(ActivationCode.is_used == True)
            elif status_filter == "expired":
                query = query.filter(
                    and_(
                        ActivationCode.is_used == False,
                        ActivationCode.expires_at <= now
                    )
                )
            elif status_filter == "locked":
                query = query.filter(
                    and_(ActivationCode.activation_attempts >= 5, ActivationCode.activation_attempts < 999)
                )
            elif status_filter == "revoked":
                query = query.filter(ActivationCode.activation_attempts >= 999)

        if whitelist_id:
            query = query.filter(ActivationCode.whitelist_id == whitelist_id)

        # Get total count
        total_items = query.count()

        # Apply sorting
        if sort_by == "expires_at":
            order_column = ActivationCode.expires_at
        else:  # generated_at
            order_column = ActivationCode.generated_at

        if sort_order == "asc":
            query = query.order_by(order_column.asc())
        else:
            query = query.order_by(order_column.desc())

        # Pagination
        offset = (page - 1) * limit
        codes = query.offset(offset).limit(limit).all()

        # Convert to response format
        items = []
        for code in codes:
            items.append(ActivationCodeResponse(
                id=code.id,
                code_hash=code.code_hash,
                whitelist_id=code.whitelist_id,
                whitelist_entry=WhitelistEntryInfo(
                    id=code.whitelist_entry.id,
                    identifier=code.whitelist_entry.identifier,
                    identifier_type=code.whitelist_entry.identifier_type,
                    full_name=code.whitelist_entry.full_name,
                    assigned_role=code.whitelist_entry.assigned_role,
                    supervisor_name=code.whitelist_entry.assigned_supervisor.full_name if code.whitelist_entry.assigned_supervisor else None,
                    notes=code.whitelist_entry.notes
                ),
                status=code.status,
                expires_at=code.expires_at,
                is_used=code.is_used,
                used_at=code.used_at,
                used_by_user_name=code.used_by_user.full_name if code.used_by_user else None,
                failed_attempts=min(code.activation_attempts, 5),
                max_attempts=5,
                revoked_at=None,
                revoke_reason=None,
                activation_attempts=code.activation_attempts,
                last_attempt_at=code.last_attempt_at,
                generated_at=code.generated_at,
                generated_by_name=code.generator.full_name
            ))

        total_pages = (total_items + limit - 1) // limit

        return ActivationCodeListResponse(
            items=items,
            pagination={
                "page": page,
                "limit": limit,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            },
            filters_applied={
                "status": status_filter or "all",
                "whitelist_id": whitelist_id,
                "sort_by": sort_by,
                "sort_order": sort_order
            }
        )

    def get_activation_code(self, code_id: int) -> ActivationCodeResponse:
        """Get single activation code details"""
        code = self.db.query(ActivationCode).options(
            joinedload(ActivationCode.whitelist_entry).joinedload(UserWhitelist.assigned_supervisor),
            joinedload(ActivationCode.used_by_user),
            joinedload(ActivationCode.generator)
        ).filter(ActivationCode.id == code_id).first()

        if not code:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activation code {code_id} not found"
            )

        return ActivationCodeResponse(
            id=code.id,
            code_hash=code.code_hash,
            whitelist_id=code.whitelist_id,
            whitelist_entry=WhitelistEntryInfo(
                id=code.whitelist_entry.id,
                identifier=code.whitelist_entry.identifier,
                identifier_type=code.whitelist_entry.identifier_type,
                full_name=code.whitelist_entry.full_name,
                assigned_role=code.whitelist_entry.assigned_role,
                supervisor_name=code.whitelist_entry.assigned_supervisor.full_name if code.whitelist_entry.assigned_supervisor else None,
                notes=code.whitelist_entry.notes
            ),
            status=code.status,
            expires_at=code.expires_at,
            is_used=code.is_used,
            used_at=code.used_at,
            used_by_user_name=code.used_by_user.full_name if code.used_by_user else None,
            failed_attempts=min(code.activation_attempts, 5),
            max_attempts=5,
            revoked_at=None,
            revoke_reason=None,
            activation_attempts=code.activation_attempts,
            last_attempt_at=code.last_attempt_at,
            generated_at=code.generated_at,
            generated_by_name=code.generator.full_name
        )

    def extend_code(self, code_id: int, additional_hours: int, ip_address: str) -> Dict[str, Any]:
        """Extend activation code expiration"""
        code = self.db.query(ActivationCode).filter(ActivationCode.id == code_id).first()
        if not code:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activation code {code_id} not found"
            )

        if code.is_used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot extend a used activation code"
            )

        if additional_hours < 1 or additional_hours > 720:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="additional_hours must be between 1 and 720"
            )

        code.expires_at = code.expires_at + timedelta(hours=additional_hours)
        self.db.commit()

        audit_log = ActivationAuditLog(
            event_type="code_extended",
            activation_code_id=code.id,
            whitelist_id=code.whitelist_id,
            ip_address=ip_address,
            success=True,
            request_metadata={"additional_hours": additional_hours}
        )
        self.db.add(audit_log)
        self.db.commit()

        return {
            "success": True,
            "new_expires_at": code.expires_at.isoformat()
        }

    async def resend_email(self, code_id: int, ip_address: str, custom_message: Optional[str] = None) -> Dict[str, Any]:
        """Regenerate and resend activation email for a whitelist entry"""
        code = self.db.query(ActivationCode).options(
            joinedload(ActivationCode.whitelist_entry)
        ).filter(ActivationCode.id == code_id).first()

        if not code:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activation code {code_id} not found"
            )

        if code.is_used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot resend email for a used activation code"
            )

        whitelist_entry = code.whitelist_entry
        if whitelist_entry.identifier_type != "email":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Whitelist entry does not use email identifier"
            )

        # Revoke current code and generate a new one
        code.activation_attempts = 999
        self.db.commit()

        plain_code = self.generate_activation_code()
        code_hash = self.hash_activation_code(plain_code)
        new_code = ActivationCode(
            code_hash=code_hash,
            whitelist_id=whitelist_entry.id,
            expires_at=datetime.now() + timedelta(hours=72),
            generated_by=code.generated_by
        )
        self.db.add(new_code)
        self.db.commit()
        self.db.refresh(new_code)

        email_sent = False
        email_status = None
        try:
            email_result = await email_service.send_activation_email(
                to_email=whitelist_entry.identifier,
                full_name=whitelist_entry.full_name,
                activation_code=plain_code,
                expires_in_hours=72,
                custom_message=custom_message
            )
            email_sent = email_result["success"]
            email_status = email_result.get("status", "sent")
        except Exception as exc:
            email_status = f"failed: {str(exc)}"

        audit_log = ActivationAuditLog(
            event_type="email_resent",
            activation_code_id=new_code.id,
            whitelist_id=whitelist_entry.id,
            ip_address=ip_address,
            success=email_sent,
            request_metadata={"previous_code_id": code_id, "email_status": email_status}
        )
        self.db.add(audit_log)
        self.db.commit()

        return {
            "success": True,
            "email_sent": email_sent,
            "code": plain_code,
            "code_id": new_code.id,
            "expires_at": new_code.expires_at.isoformat()
        }

    def list_audit_logs(
        self,
        page: int = 1,
        limit: int = 50,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        event_type: Optional[str] = None,
        ip_address: Optional[str] = None,
        success: Optional[bool] = None,
        activation_code_id: Optional[int] = None,
        whitelist_id: Optional[int] = None
    ) -> AuditLogListResponse:
        query = self.db.query(ActivationAuditLog).options(
            joinedload(ActivationAuditLog.whitelist_entry),
            joinedload(ActivationAuditLog.created_user)
        )

        if from_date:
            query = query.filter(ActivationAuditLog.created_at >= from_date)
        if to_date:
            query = query.filter(ActivationAuditLog.created_at <= to_date)
        if event_type and event_type != "all":
            query = query.filter(ActivationAuditLog.event_type == event_type)
        if ip_address:
            query = query.filter(ActivationAuditLog.ip_address == ip_address)
        if success is not None:
            query = query.filter(ActivationAuditLog.success == success)
        if activation_code_id:
            query = query.filter(ActivationAuditLog.activation_code_id == activation_code_id)
        if whitelist_id:
            query = query.filter(ActivationAuditLog.whitelist_id == whitelist_id)

        total_items = query.count()
        offset = (page - 1) * limit
        logs = query.order_by(ActivationAuditLog.created_at.desc()).offset(offset).limit(limit).all()

        items: List[AuditLogResponse] = []
        for log in logs:
            items.append(AuditLogResponse(
                id=log.id,
                event_type=log.event_type,
                activation_code_id=log.activation_code_id,
                whitelist_id=log.whitelist_id,
                whitelist_identifier=log.whitelist_entry.identifier if log.whitelist_entry else None,
                whitelist_full_name=log.whitelist_entry.full_name if log.whitelist_entry else None,
                identifier_attempted=log.identifier_attempted,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                device_id=log.device_id,
                success=log.success,
                failure_reason=log.failure_reason,
                created_user_id=log.created_user_id,
                created_user_name=log.created_user.full_name if log.created_user else None,
                request_metadata=log.request_metadata,
                created_at=log.created_at
            ))

        total_pages = (total_items + limit - 1) // limit

        return AuditLogListResponse(
            items=items,
            pagination={
                "page": page,
                "limit": limit,
                "total_items": total_items,
                "total_pages": total_pages
            },
            filters_applied={
                "event_type": event_type or "all",
                "from_date": from_date.isoformat() if from_date else None,
                "to_date": to_date.isoformat() if to_date else None,
                "ip_address": ip_address,
                "success": success,
                "activation_code_id": activation_code_id,
                "whitelist_id": whitelist_id
            }
        )

    def get_stats(self) -> ActivationStatsResponse:
        now = datetime.now()
        last_7_days = now - timedelta(days=7)
        last_24_hours = now - timedelta(hours=24)

        total_whitelist = self.db.query(UserWhitelist).count()
        activated_users = self.db.query(UserWhitelist).filter(UserWhitelist.is_activated == True).count()
        pending_activations = total_whitelist - activated_users
        activation_rate = (activated_users / total_whitelist * 100) if total_whitelist else 0.0

        total_codes = self.db.query(ActivationCode).count()
        used_codes = self.db.query(ActivationCode).filter(ActivationCode.is_used == True).count()
        expired_codes = self.db.query(ActivationCode).filter(
            and_(ActivationCode.is_used == False, ActivationCode.expires_at <= now)
        ).count()
        locked_codes = self.db.query(ActivationCode).filter(
            and_(ActivationCode.activation_attempts >= 5, ActivationCode.activation_attempts < 999)
        ).count()
        revoked_codes = self.db.query(ActivationCode).filter(ActivationCode.activation_attempts >= 999).count()
        active_codes = max(total_codes - used_codes - expired_codes - locked_codes - revoked_codes, 0)

        codes_generated_last_7 = self.db.query(ActivationCode).filter(
            ActivationCode.generated_at >= last_7_days
        ).count()
        activations_last_7 = self.db.query(ActivationAuditLog).filter(
            and_(ActivationAuditLog.event_type == "activation_success", ActivationAuditLog.created_at >= last_7_days)
        ).count()
        failed_attempts_24h = self.db.query(ActivationAuditLog).filter(
            and_(ActivationAuditLog.success == False, ActivationAuditLog.created_at >= last_24_hours)
        ).count()

        failure_reasons = self.db.query(
            ActivationAuditLog.failure_reason,
            func.count(ActivationAuditLog.failure_reason)
        ).filter(
            ActivationAuditLog.failure_reason.isnot(None)
        ).group_by(ActivationAuditLog.failure_reason).order_by(func.count(ActivationAuditLog.failure_reason).desc()).limit(5).all()

        top_failure_reasons = [
            {"reason": reason, "count": count}
            for reason, count in failure_reasons
        ]

        return ActivationStatsResponse(
            total_whitelist_entries=total_whitelist,
            activated_users=activated_users,
            pending_activations=pending_activations,
            activation_rate=round(activation_rate, 2),
            total_codes_generated=total_codes,
            active_codes=active_codes,
            used_codes=used_codes,
            expired_codes=expired_codes,
            locked_codes=locked_codes,
            codes_generated_last_7_days=codes_generated_last_7,
            activations_last_7_days=activations_last_7,
            failed_attempts_last_24_hours=failed_attempts_24h,
            top_failure_reasons=top_failure_reasons
        )

    def revoke_code(
        self,
        code_id: int,
        data: RevokeCodeRequest,
        ip_address: str
    ) -> RevokeCodeResponse:
        """Revoke activation code"""
        code = self.db.query(ActivationCode).filter(ActivationCode.id == code_id).first()
        
        if not code:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activation code {code_id} not found"
            )

        if code.is_used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot revoke code that has already been used"
            )

        # Mark as revoked
        code.activation_attempts = 999
        self.db.commit()

        # Log revocation
        audit_log = ActivationAuditLog(
            event_type="code_revoked",
            activation_code_id=code.id,
            whitelist_id=code.whitelist_id,
            ip_address=ip_address,
            success=True,
            request_metadata={ "reason": data.reason}
        )
        self.db.add(audit_log)
        self.db.commit()

        return RevokeCodeResponse(
            success=True,
            message="Activation code revoked successfully",
            code_id=code_id,
            revoked_at=datetime.now()
        )

    def validate_code(
        self,
        data: ValidateCodeRequest,
        ip_address: str
    ) -> ValidateCodeResponse:
        """
        Validate activation code (public endpoint).
        Queries ALL non-used codes (no attempt/expiry filter) so we can return
        specific, actionable error messages (expired vs locked vs not-found).
        The attempt filter is enforced in complete_activation for security.
        """
        # Scan all non-used codes — do NOT pre-filter by expiry/attempts here
        # so we can return a specific reason if the code is found but unusable.
        codes = self.db.query(ActivationCode).options(
            joinedload(ActivationCode.whitelist_entry),
            joinedload(ActivationCode.whitelist_entry, UserWhitelist.assigned_supervisor)
        ).filter(
            ActivationCode.is_used == False,
        ).all()

        # Check each code hash (bcrypt comparison)
        matching_code = None
        for code in codes:
            if self.verify_activation_code(data.code, code.code_hash):
                matching_code = code
                break

        # Determine failure reason for audit log
        failure_reason = None
        if not matching_code:
            failure_reason = "invalid_code"
        elif matching_code.is_expired:
            failure_reason = "expired_code"
        elif matching_code.is_locked:
            failure_reason = "locked_code"

        # Log validation attempt
        audit_log = ActivationAuditLog(
            event_type="code_validation_attempt",
            activation_code_id=matching_code.id if matching_code else None,
            whitelist_id=matching_code.whitelist_id if matching_code else None,
            ip_address=ip_address,
            success=(matching_code is not None and failure_reason is None),
            failure_reason=failure_reason
        )
        self.db.add(audit_log)
        self.db.commit()

        if not matching_code:
            return ValidateCodeResponse(
                valid=False,
                error="Activation code not found"
            )

        # NOTE: validate never increments activation_attempts — that counter is
        # only incremented on identifier mismatch in complete_activation to
        # rate-limit brute-forcing email addresses against a stolen code.

        # Return specific messages so the user (and admin) know what to do next.
        if matching_code.is_expired:
            return ValidateCodeResponse(
                valid=False,
                error="Activation code expired"
            )

        if matching_code.is_locked:
            return ValidateCodeResponse(
                valid=False,
                error="Activation code locked"
            )

        # Code is valid - return whitelist info
        whitelist = matching_code.whitelist_entry
        now = datetime.now()
        remaining_hours = (matching_code.expires_at - now).total_seconds() / 3600

        return ValidateCodeResponse(
            valid=True,
            whitelist_entry={
                "full_name": whitelist.full_name,
                "assigned_role": whitelist.assigned_role,
                "identifier_type": whitelist.identifier_type,
                "supervisor_name": whitelist.assigned_supervisor.full_name if whitelist.assigned_supervisor else None
            },
            expires_at=matching_code.expires_at,
            remaining_hours=round(remaining_hours, 1),
            activation_requirements=ActivationRequirements(
                must_provide_identifier=True,
                must_create_strong_password=True,
                password_min_length=8,
                must_agree_to_terms=True
            )
        )

    async def complete_activation(
        self,
        data: CompleteActivationRequest,
        ip_address: str,
        user_agent: Optional[str] = None,
        device_id: Optional[str] = None
    ) -> CompleteActivationResponse:
        """
        Complete user activation.
        Creates user account and marks code as used.
        """
        # Find and validate code — only scan active candidates (unexpired, unlocked)
        now = datetime.now()
        codes = self.db.query(ActivationCode).options(
            joinedload(ActivationCode.whitelist_entry)
        ).filter(
            ActivationCode.is_used == False,
            ActivationCode.expires_at > now,
            ActivationCode.activation_attempts < 5,
        ).all()

        matching_code = None
        for code in codes:
            if self.verify_activation_code(data.code, code.code_hash):
                matching_code = code
                break

        if not matching_code or matching_code.is_expired or matching_code.is_locked:
            # Log failed attempt
            audit_log = ActivationAuditLog(
                event_type="activation_failed",
                activation_code_id=matching_code.id if matching_code else None,
                identifier_attempted=data.identifier,
                ip_address=ip_address,
                user_agent=user_agent,
                device_id=device_id,
                success=False,
                failure_reason="invalid_or_expired_code"
            )
            self.db.add(audit_log)
            self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired activation code"
            )

        whitelist = matching_code.whitelist_entry

        # Verify identifier matches
        if whitelist.identifier.lower() != data.identifier.lower():
            # Increment attempts to rate-limit brute-force of emails against a stolen code
            matching_code.activation_attempts += 1
            matching_code.last_attempt_at = datetime.now()
            matching_code.last_attempt_ip = ip_address

            audit_log = ActivationAuditLog(
                event_type="activation_failed",
                activation_code_id=matching_code.id,
                whitelist_id=whitelist.id,
                identifier_attempted=data.identifier,
                ip_address=ip_address,
                user_agent=user_agent,
                device_id=device_id,
                success=False,
                failure_reason="identifier_mismatch"
            )
            self.db.add(audit_log)
            self.db.commit()

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Identifier does not match whitelist entry"
            )

        # Check if user already exists
        existing_user = self.db.query(User).filter(
            User.email == data.identifier.lower()
        ).first()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )

        # Create user account
        hashed_password = get_password_hash(data.password)
        new_user = User(
            email=data.identifier.lower(),
            hashed_password=hashed_password,
            full_name=whitelist.full_name,
            phone=data.phone or whitelist.phone,
            role=UserRole(whitelist.assigned_role),
            is_active=True
        )

        self.db.add(new_user)
        self.db.flush()  # Get user ID without committing

        # Mark code as used
        matching_code.is_used = True
        matching_code.used_at = datetime.now()
        matching_code.used_by_user_id = new_user.id

        # Mark whitelist as activated
        whitelist.is_activated = True
        whitelist.activated_at = datetime.now()
        whitelist.activated_user_id = new_user.id

        self.db.commit()
        self.db.refresh(new_user)

        # Log successful activation
        audit_log = ActivationAuditLog(
            event_type="activation_success",
            activation_code_id=matching_code.id,
            whitelist_id=whitelist.id,
            identifier_attempted=data.identifier,
            ip_address=ip_address,
            user_agent=user_agent,
            device_id=device_id,
            success=True,
            created_user_id=new_user.id
        )
        self.db.add(audit_log)
        self.db.commit()

        # Generate access token (you'll need to import from auth)
        from app.core.security import create_access_token
        access_token = create_access_token(data={"sub": str(new_user.id), "role": new_user.role.value})

        return CompleteActivationResponse(
            success=True,
            user_id=new_user.id,
            access_token=access_token,
            user_info={
                "id": new_user.id,
                "email": new_user.email,
                "full_name": new_user.full_name,
                "role": new_user.role.value,
                "phone": new_user.phone
            }
        )
