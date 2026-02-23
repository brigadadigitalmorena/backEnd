"""Mobile app routers for offline-first survey application."""
from typing import Annotated, List, Optional, Tuple
from fastapi import APIRouter, Depends, Query, File, UploadFile, HTTPException, Request, status, Header
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import uuid
import cloudinary
import cloudinary.utils

from app.core.database import get_db
from app.core.limiter import limiter
from app.services.survey_service import SurveyService
from app.services.response_service import ResponseService
from app.services.notification_service import NotificationService
from app.repositories.assignment_repository import AssignmentRepository
from app.repositories.response_repository import ResponseRepository
from app.schemas.survey import SurveyVersionResponse, AssignedSurveyResponse
from app.schemas.response import (
    SurveyResponseCreate, 
    SurveyResponseDetail,
    BatchResponseCreate,
    BatchResponseResult,
    DocumentUploadRequest,
    DocumentUploadResponse,
    DocumentConfirmRequest,
    DocumentConfirmResponse,
    SyncStatus
)
from app.models.document import Document
from app.schemas.notification import NotificationResponse, NotificationListResponse, UnreadCountResponse
from app.schemas.user import LoginResponse, UserResponse
from app.api.dependencies import BrigadistaUser, MobileUser, get_current_user
from app.services.auth_service import AuthService
from app.core.config import settings
from pydantic import BaseModel as _BaseModel, EmailStr

CURRENT_MOBILE_API_VERSION = "2026.1"
MIN_SUPPORTED_MOBILE_API_VERSION = "2025.12"


def _parse_mobile_version(raw: str) -> Tuple[int, int]:
    try:
        major, minor = raw.strip().split(".")
        return int(major), int(minor)
    except Exception:
        return 0, 0


def require_mobile_api_version(
    x_mobile_api_version: Annotated[Optional[str], Header(alias="X-Mobile-Api-Version")] = None,
):
    """Optional contract version guard for legacy mobile apps.

    If the client sends X-Mobile-Api-Version and it is below minimum,
    return 426 so old apps can force-update safely.
    """
    if not x_mobile_api_version:
        return

    if _parse_mobile_version(x_mobile_api_version) < _parse_mobile_version(MIN_SUPPORTED_MOBILE_API_VERSION):
        raise HTTPException(
            status_code=status.HTTP_426_UPGRADE_REQUIRED,
            detail={
                "code": "mobile_api_version_unsupported",
                "message": (
                    f"Mobile API version {x_mobile_api_version} is no longer supported. "
                    f"Minimum supported version is {MIN_SUPPORTED_MOBILE_API_VERSION}."
                ),
                "retriable": False,
            },
        )


router = APIRouter(
    prefix="/mobile",
    tags=["Mobile App - Offline First"],
    dependencies=[Depends(require_mobile_api_version)],
)


class MobileLoginRequest(_BaseModel):
    """Request body for mobile login."""
    email: str
    password: str
    device_id: str
    app_version: str


@router.get("/contract")
def mobile_contract_info():
    """Expose current contract version metadata for safe client upgrades."""
    return {
        "api_version": CURRENT_MOBILE_API_VERSION,
        "min_supported_api_version": MIN_SUPPORTED_MOBILE_API_VERSION,
    }


@router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")
def mobile_login(
    request: Request,
    body: MobileLoginRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """
    Mobile-specific login endpoint.
    
    Returns JWT token for authentication.
    Tracks device info for sync purposes.
    
    **Requirements:**
    - Valid email and password
    - Device ID for offline sync tracking
    - App version for compatibility checks
    """
    auth_service = AuthService(db)
    
    # Single authenticate + token generation (no double bcrypt)
    token = auth_service.login(body.email, body.password)
    
    # TODO: Store device info for sync tracking
    # DeviceRepository.upsert(user_id=user.id, device_id=body.device_id, app_version=body.app_version)
    
    return token


@router.get("/me", response_model=UserResponse)
def get_my_profile(current_user: MobileUser):
    """
    Get the authenticated user's profile.

    Used by mobile app for the profile screen and to verify session validity.
    """
    return current_user


@router.get("/surveys", response_model=List[AssignedSurveyResponse])
def get_assigned_surveys(
    db: Annotated[Session, Depends(get_db)],
    current_user: MobileUser,
    status_filter: str = Query(None, description="Filter by assignment status: active, inactive"),
):
    """
    Get all surveys assigned to current user with latest published versions.
    
    **Mobile App Use Case:**
    - Download survey structures for offline use
    - Check for survey updates
    - View assignment details (location, status)
    
    **Response includes:**
    - Assignment metadata (ID, status, location)
    - Latest published survey version with all questions
    - Survey structure is immutable (mobile cannot modify)
    
    **Constraints:**
    - Only returns PUBLISHED survey versions
    - Survey structure is read-only for mobile
    - Version integrity is enforced
    """
    assignment_repo = AssignmentRepository(db)
    survey_service = SurveyService(db)
    
    # Get user's assignments
    assignments = assignment_repo.get_by_user(current_user.id)
    
    # Filter by status if provided
    if status_filter:
        from app.models.assignment import AssignmentStatus
        try:
            status_enum = AssignmentStatus(status_filter)
            assignments = [a for a in assignments if a.status == status_enum]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}"
            )
    
    # Build response with survey details and latest versions
    # Batch-fetch all published versions in ONE query (avoids N+1)
    survey_ids = list({a.survey_id for a in assignments})
    versions_map = survey_service.get_latest_published_versions_batch(survey_ids)

    result = []
    for assignment in assignments:
        latest_version = versions_map.get(assignment.survey_id)
        if latest_version is None:
            continue  # Skip surveys without published versions

        # Skip inactive or soft-deleted surveys
        survey = assignment.survey
        if not survey.is_active or survey.deleted_at is not None:
            continue

        result.append(AssignedSurveyResponse(
            assignment_id=assignment.id,
            survey_id=assignment.survey.id,
            survey_title=assignment.survey.title,
            survey_description=assignment.survey.description,
            assignment_status=assignment.status.value,
            assigned_location=assignment.location,
            latest_version=latest_version,
            assigned_at=assignment.created_at
        ))
    
    return result


@router.get("/surveys/{survey_id}/latest", response_model=SurveyVersionResponse)
def get_latest_survey_version(
    survey_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: MobileUser
):
    """
    Get latest published survey version for mobile app.
    
    **Legacy endpoint** - prefer using GET /mobile/surveys instead.
    
    Used by mobile app to download individual survey structure.
    """
    service = SurveyService(db)
    return service.get_latest_published_version(survey_id)


@router.post("/responses/batch", response_model=BatchResponseResult, status_code=201)
def submit_batch_responses(
    batch_data: BatchResponseCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: MobileUser
):
    """
    Submit multiple survey responses in batch (offline sync).
    
    **Offline-First Features:**
    - Processes up to 50 responses per request
    - Each response validated independently
    - Continues processing even if some fail
    - Automatic duplicate detection via client_id
    - Returns detailed validation results per response
    
    **Validation Per Response:**
    - SUCCESS: Response created successfully
    - DUPLICATE: Response already exists (idempotent)
    - FAILED: Validation or processing error
    
    **OCR Confidence Warnings:**
    - Flags responses with OCR confidence < 0.7
    - Warnings don't block submission
    - Admin can review flagged responses
    
    **Constraints:**
    - Maximum 50 responses per batch
    - Survey version must exist and be published
    - Cannot modify survey structure
    - Version integrity enforced
    
    **Mobile Implementation:**
    ```javascript
    // Offline queue processing
    const pendingResponses = await db.responses.where('synced', 0).toArray();
    const batch = pendingResponses.slice(0, 50);
    
    const result = await api.post('/mobile/responses/batch', {
      responses: batch
    });
    
    // Mark successful responses as synced
    result.results.forEach(r => {
      if (r.status === 'success' || r.status === 'duplicate') {
        db.responses.update(r.client_id, { synced: 1 });
      }
    });
    ```
    """
    service = ResponseService(db)
    return service.submit_batch_responses(batch_data.responses, current_user.id)


@router.get("/responses/me", response_model=List[SurveyResponseDetail])
def get_my_responses(
    db: Annotated[Session, Depends(get_db)],
    current_user: MobileUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100)
):
    """
    Get current user's submitted responses.
    
    **Use Case:**
    - View submission history
    - Check sync status
    - Re-download responses for offline viewing
    """
    service = ResponseService(db)
    return service.get_user_responses(current_user.id, skip=skip, limit=limit)


@router.post("/documents/upload", response_model=DocumentUploadResponse, status_code=201)
def upload_document(
    request: DocumentUploadRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: MobileUser
):
    """
    Generate pre-signed URL for document upload (photos, signatures, scanned docs).
    
    **Two-Phase Upload Process:**
    1. **Request upload URL** (this endpoint)
       - Validates document metadata
       - Generates unique document ID
       - Returns pre-signed S3/Cloudinary URL
       - Checks OCR confidence if provided
    
    2. **Upload file to URL** (client → cloud storage)
       - Client uploads directly to returned URL
       - No file passes through API server
       - Reduces server load and bandwidth
    
    **OCR Confidence Handling:**
    - If `ocr_confidence < 0.7`: Sets `low_confidence_warning = true`
    - Admin review queue will be notified
    - Document still accepted but flagged
    - Mobile app should prompt user to retake if possible
    
    **Document Types:**
    - `id_card`: National ID, passport, driver's license
    - `receipt`: Purchase receipts, invoices
    - `signature`: User signature capture
    - `photo`: General photos (damage, location, etc.)
    - `form`: Scanned filled forms
    
    **Mobile Implementation:**
    ```javascript
    // 1. Request upload URL
    const uploadRequest = await api.post('/mobile/documents/upload', {
      client_id: response.client_id,
      file_name: 'photo.jpg',
      file_size: 1024000,
      mime_type: 'image/jpeg',
      metadata: {
        document_type: 'id_card',
        question_id: 5,
        ocr_confidence: 0.85,
        ocr_text: 'JOHN DOE\\n123456789'
      }
    });
    
    // 2. Upload file to pre-signed URL
    await fetch(uploadRequest.upload_url, {
      method: 'PUT',
      body: fileBlob,
      headers: { 'Content-Type': 'image/jpeg' }
    });
    
    // 3. Store document_id with response
    response.documents.push(uploadRequest.document_id);
    ```
    
    **Constraints:**
    - File size limit: 10MB per document
    - Supported formats: JPEG, PNG, PDF
    - Pre-signed URL expires in 30 minutes
    - Document must be linked to existing response (client_id)
    """
    # Validate file size (10MB limit)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    if request.file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size {request.file_size} exceeds maximum {MAX_FILE_SIZE}"
        )
    
    # Validate mime type
    ALLOWED_TYPES = ['image/jpeg', 'image/png', 'application/pdf']
    if request.mime_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {request.mime_type}"
        )
    
    # Check OCR confidence
    ocr_confidence = request.metadata.ocr_confidence
    low_confidence_warning = False
    ocr_required = False
    
    if request.metadata.document_type in ['id_card', 'form', 'receipt']:
        ocr_required = True
        if ocr_confidence is not None and ocr_confidence < 0.7:
            low_confidence_warning = True
    
    # Generate unique document ID
    document_id = f"doc_{uuid.uuid4().hex[:12]}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

    if not settings.cloudinary_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cloud storage not configured"
        )

    # Configure Cloudinary SDK with credentials from settings
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )

    # Determine Cloudinary resource_type
    doc_type = (request.metadata.document_type if request.metadata else "photo").lower()
    resource_type = "image" if request.mime_type.startswith("image/") else "raw"

    # ── Smart folder hierarchy ─────────────────────────────────────────────
    # brigada/surveys/{survey_id}/{year}/{month}/{doc_type}/q{question_id}/{doc_id}
    #
    # Enables Cloudinary prefix queries like:
    #   brigada/surveys/7/**              → all files for survey 7
    #   brigada/surveys/7/2026/02/**      → monthly slice
    #   brigada/surveys/7/2026/02/photo/** → photos that month
    #
    now_utc = datetime.now(timezone.utc)
    year_str = now_utc.strftime("%Y")
    month_str = now_utc.strftime("%m")

    # Resolve survey_id from client_id (response may not exist yet if uploading before submit)
    survey_id = "unknown"
    question_id = request.metadata.question_id if request.metadata else None
    try:
        resp_repo = ResponseRepository(db)
        existing = resp_repo.get_by_client_id(request.client_id)
        if existing:
            from app.models.survey import SurveyVersion as SV
            sv = db.query(SV).filter(SV.id == existing.version_id).first()
            if sv:
                survey_id = str(sv.survey_id)
    except Exception:
        pass  # Non-fatal — folder degrades gracefully to "unknown"

    q_segment = f"q{question_id}" if question_id else "q-unknown"

    folder = (
        f"brigada/surveys/{survey_id}"
        f"/{year_str}/{month_str}"
        f"/{doc_type}"
        f"/{q_segment}"
    )
    public_id = f"{folder}/{document_id}"

    timestamp = int(now_utc.timestamp())
    upload_params = {
        "public_id": public_id,
        "timestamp": timestamp,
        "resource_type": resource_type,
        "tags": [
            f"survey_{survey_id}",
            f"user_{current_user.id}",
            f"type_{doc_type}",
            f"year_{year_str}",
            f"month_{year_str}_{month_str}",
            *([f"question_{question_id}"] if question_id else []),
            "brigada",
        ],
        # Store rich context as Cloudinary metadata (searchable in dashboard)
        "context": "|".join([
            f"survey_id={survey_id}",
            f"user_id={current_user.id}",
            f"doc_type={doc_type}",
            f"client_id={request.client_id}",
            *([f"question_id={question_id}"] if question_id else []),
        ]),
    }

    # Generate Cloudinary signature
    signature = cloudinary.utils.api_sign_request(
        upload_params, settings.CLOUDINARY_API_SECRET
    )

    upload_url = (
        f"https://api.cloudinary.com/v1_1/{settings.CLOUDINARY_CLOUD_NAME}"
        f"/{resource_type}/upload"
    )

    # ── Persist document record (status = pending) ─────────────────────────
    doc_record = Document(
        document_id=document_id,
        user_id=current_user.id,
        response_client_id=request.client_id,
        question_id=question_id,
        file_name=request.file_name,
        file_size=request.file_size,
        mime_type=request.mime_type,
        document_type=doc_type,
        cloudinary_public_id=public_id,
        ocr_confidence=ocr_confidence,
        status="pending",
    )
    db.add(doc_record)
    db.commit()

    return DocumentUploadResponse(
        document_id=document_id,
        upload_url=upload_url,
        expires_at=expires_at,
        ocr_required=ocr_required,
        low_confidence_warning=low_confidence_warning,
        # Extra signed params the mobile app needs for the direct upload
        cloudinary_signature=signature,
        cloudinary_timestamp=timestamp,
        cloudinary_api_key=settings.CLOUDINARY_API_KEY,
        cloudinary_public_id=public_id,
        cloudinary_folder=folder,
    )


@router.post("/documents/confirm", response_model=DocumentConfirmResponse)
def confirm_document_upload(
    body: DocumentConfirmRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: MobileUser,
):
    """
    Confirm a file was successfully uploaded to Cloudinary.

    Called by the mobile app **after** the direct Cloudinary upload succeeds.
    Updates the document record and back-fills ``media_url`` on the
    corresponding ``question_answers`` row (if the response already exists).
    """
    doc = (
        db.query(Document)
        .filter(
            Document.document_id == body.document_id,
            Document.user_id == current_user.id,
        )
        .first()
    )
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found or not owned by you",
        )

    if doc.status == "uploaded":
        # Idempotent — already confirmed
        return DocumentConfirmResponse(
            document_id=doc.document_id,
            status="uploaded",
            remote_url=doc.remote_url or body.remote_url,
            answers_updated=0,
        )

    doc.status = "uploaded"
    doc.remote_url = body.remote_url
    doc.cloudinary_public_id = body.cloudinary_public_id
    doc.confirmed_at = datetime.now(timezone.utc)

    # Back-fill media_url on the question_answers row for this document
    answers_updated = 0
    if doc.question_id and doc.response_client_id:
        from app.models.response import SurveyResponse, QuestionAnswer

        response = (
            db.query(SurveyResponse)
            .filter(SurveyResponse.client_id == doc.response_client_id)
            .first()
        )
        if response:
            answer = (
                db.query(QuestionAnswer)
                .filter(
                    QuestionAnswer.response_id == response.id,
                    QuestionAnswer.question_id == doc.question_id,
                )
                .first()
            )
            if answer:
                answer.media_url = body.remote_url
                answers_updated = 1

    db.commit()

    return DocumentConfirmResponse(
        document_id=doc.document_id,
        status="uploaded",
        remote_url=body.remote_url,
        answers_updated=answers_updated,
    )


@router.get("/sync-status", response_model=SyncStatus)
def get_sync_status(
    db: Annotated[Session, Depends(get_db)],
    current_user: MobileUser
):
    """
    Get sync status for mobile app.
    
    **Returns:**
    - `synced_responses`: Total responses synced to server
    - `pending_responses`: Responses waiting to sync (client-side tracking)
    - `pending_documents`: Documents waiting to upload
    - `last_sync`: Timestamp of last successful sync
    - `assigned_surveys`: Count of assigned surveys
    - `available_updates`: Survey IDs with new versions available
    
    **Use Cases:**
    - Display sync status in app UI
    - Determine if sync is needed
    - Check for survey updates
    - Verify offline data is backed up
    
    **Mobile Implementation:**
    ```javascript
    // Periodic sync check
    setInterval(async () => {
      const status = await api.get('/mobile/sync-status');
      
      // Update UI badge
      setBadgeCount(status.pending_responses);
      
      // Notify user of updates
      if (status.available_updates.length > 0) {
        showNotification('New survey versions available');
      }
      
      // Auto-sync if online
      if (navigator.onLine && status.pending_responses > 0) {
        await syncPendingResponses();
      }
    }, 60000); // Every minute
    ```
    """
    response_service = ResponseService(db)
    assignment_repo = AssignmentRepository(db)

    # ── Synced responses count ────────────────────────────────────────────
    synced_responses = response_service.get_sync_status(current_user.id)["synced_responses"]

    # ── Assigned surveys count ────────────────────────────────────────────
    assignments = assignment_repo.get_by_user(current_user.id)
    assigned_surveys_count = len(assignments)

    # ── Pending documents (uploads not yet confirmed) ─────────────────────
    pending_documents = (
        db.query(Document)
        .filter(
            Document.user_id == current_user.id,
            Document.status == "pending",
        )
        .count()
    )

    # ── Last sync timestamp (most recent synced_at from user's responses) ─
    from sqlalchemy import func as sqlfunc
    from app.models.response import SurveyResponse

    last_sync_row = (
        db.query(sqlfunc.max(SurveyResponse.synced_at))
        .filter(SurveyResponse.user_id == current_user.id)
        .scalar()
    )

    return SyncStatus(
        user_id=current_user.id,
        pending_responses=0,  # Client-side only — server can't know what's queued on the device
        synced_responses=synced_responses,
        pending_documents=pending_documents,
        last_sync=last_sync_row,
        assigned_surveys=assigned_surveys_count,
        available_updates=[],  # Requires client→server version negotiation (future)
    )


# ── Mobile Notifications ─────────────────────────────────────────────────────

@router.get("/notifications", response_model=NotificationListResponse)
def get_my_notifications(
    db: Annotated[Session, Depends(get_db)],
    current_user: MobileUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    unread_only: bool = Query(False),
):
    """
    Get notifications addressed to the current user.

    Returns both per-user notifications (user_id == current user)
    and global notifications (user_id == None) if any exist.
    """
    service = NotificationService(db)
    notifications = service.get_notifications(
        skip=skip, limit=limit, unread_only=unread_only, user_id=current_user.id
    )
    unread_count = service.get_unread_count(user_id=current_user.id)
    return NotificationListResponse(notifications=notifications, unread_count=unread_count)


@router.get("/notifications/unread-count", response_model=UnreadCountResponse)
def get_my_notification_unread_count(
    db: Annotated[Session, Depends(get_db)],
    current_user: MobileUser,
):
    """Get count of unread notifications for the current user (for badge display)."""
    service = NotificationService(db)
    return UnreadCountResponse(count=service.get_unread_count(user_id=current_user.id))


@router.patch("/notifications/{notification_id}/read", response_model=NotificationResponse)
def mark_my_notification_read(
    notification_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: MobileUser,
):
    """Mark a specific notification as read (only if owned by current user)."""
    from app.models.notification import Notification
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if notification.user_id is not None and notification.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your notification")
    service = NotificationService(db)
    return service.mark_read(notification_id)


@router.patch("/notifications/read-all", response_model=dict)
def mark_all_my_notifications_read(
    db: Annotated[Session, Depends(get_db)],
    current_user: MobileUser,
):
    """Mark all of the current user's notifications as read."""
    from app.models.notification import Notification
    count = (
        db.query(Notification)
        .filter(Notification.user_id == current_user.id, Notification.read == False)  # noqa: E712
        .update({"read": True})
    )
    db.commit()
    return {"updated": count}
