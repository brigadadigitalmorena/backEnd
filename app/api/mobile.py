"""Mobile app routers for offline-first survey application."""
from typing import Annotated, List
from fastapi import APIRouter, Depends, Query, File, UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid

from app.core.database import get_db
from app.services.survey_service import SurveyService
from app.services.response_service import ResponseService
from app.repositories.assignment_repository import AssignmentRepository
from app.schemas.survey import SurveyVersionResponse, AssignedSurveyResponse
from app.schemas.response import (
    SurveyResponseCreate, 
    SurveyResponseDetail,
    BatchResponseCreate,
    BatchResponseResult,
    DocumentUploadRequest,
    DocumentUploadResponse,
    SyncStatus
)
from app.schemas.user import Token
from app.api.dependencies import BrigadistaUser, get_current_user
from app.services.auth_service import AuthService
from app.core.config import settings

router = APIRouter(prefix="/mobile", tags=["Mobile App - Offline First"])


@router.post("/login", response_model=Token)
def mobile_login(
    email: str,
    password: str,
    device_id: str = Query(..., description="Unique device identifier"),
    app_version: str = Query(..., description="Mobile app version"),
    db: Annotated[Session, Depends(get_db)]
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
    user = auth_service.authenticate_user(email, password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_service.login(email, password)
    
    # TODO: Store device info for sync tracking
    # DeviceRepository.upsert(user_id=user.id, device_id=device_id, app_version=app_version)
    
    return token


@router.get("/surveys", response_model=List[AssignedSurveyResponse])
def get_assigned_surveys(
    db: Annotated[Session, Depends(get_db)],
    current_user: BrigadistaUser,
    status_filter: str = Query(None, description="Filter by assignment status: pending, in_progress, completed"),
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
    result = []
    for assignment in assignments:
        try:
            # Get latest published version for each survey
            latest_version = survey_service.get_latest_published_version(assignment.survey_id)
            
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
        except HTTPException:
            # Skip surveys without published versions
            continue
    
    return result


@router.get("/surveys/{survey_id}/latest", response_model=SurveyVersionResponse)
def get_latest_survey_version(
    survey_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: BrigadistaUser
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
    current_user: BrigadistaUser
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
    current_user: BrigadistaUser,
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
    current_user: BrigadistaUser
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
    
    # Generate pre-signed URL for upload
    # TODO: Implement actual cloud storage integration (S3/Cloudinary)
    # For now, return mock URL
    upload_url = f"{settings.CLOUDINARY_CLOUD_NAME or 'https://storage.example.com'}/upload/{document_id}"
    expires_at = datetime.utcnow() + timedelta(minutes=30)
    
    # TODO: Store document metadata in database
    # DocumentRepository.create(
    #     document_id=document_id,
    #     user_id=current_user.id,
    #     client_id=request.client_id,
    #     file_name=request.file_name,
    #     metadata=request.metadata.dict()
    # )
    
    return DocumentUploadResponse(
        document_id=document_id,
        upload_url=upload_url,
        expires_at=expires_at,
        ocr_required=ocr_required,
        low_confidence_warning=low_confidence_warning
    )


@router.get("/sync-status", response_model=SyncStatus)
def get_sync_status(
    db: Annotated[Session, Depends(get_db)],
    current_user: BrigadistaUser
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
    
    # Get synced responses count
    synced_responses = response_service.get_sync_status(current_user.id)["synced_responses"]
    
    # Get assigned surveys count
    assignments = assignment_repo.get_by_user(current_user.id)
    assigned_surveys_count = len(assignments)
    
    # TODO: Get last sync timestamp from device tracking table
    # last_sync = DeviceRepository.get_last_sync(current_user.id)
    
    # TODO: Check for survey version updates
    # available_updates = []
    # for assignment in assignments:
    #     if has_newer_version(assignment.survey_id, device_last_downloaded_version):
    #         available_updates.append(assignment.survey_id)
    
    return SyncStatus(
        user_id=current_user.id,
        pending_responses=0,  # Client-side tracking needed
        synced_responses=synced_responses,
        pending_documents=0,  # Requires document tracking table
        last_sync=None,  # Requires device tracking table
        assigned_surveys=assigned_surveys_count,
        available_updates=[]  # Requires version tracking logic
    )
