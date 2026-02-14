# Mobile API Design - Offline-First Survey Application

Complete design documentation for the mobile API endpoints that support offline-first survey data collection.

## Overview

The mobile API is designed to support offline-first mobile applications that collect survey responses in the field. Key features:

- **Offline-First**: Mobile app works without internet connection
- **Batch Sync**: Upload multiple responses in one request
- **Duplicate Detection**: Automatic deduplication via `client_id`
- **OCR Validation**: Flag low-confidence OCR results
- **Document Upload**: Two-phase upload with pre-signed URLs
- **Version Integrity**: Enforce immutable survey structures

## Architecture Principles

### 1. Idempotency
All write operations use client-generated IDs to ensure idempotency. Retrying a request with the same `client_id` returns the existing resource instead of creating duplicates.

### 2. Survey Immutability
Surveys cannot be modified from the mobile app. Only the admin control plane can modify survey structures. Mobile app receives published survey versions as read-only data.

### 3. Batch Processing
Mobile app can submit up to 50 responses in a single batch request. Each response is validated independently - failures don't affect other responses in the batch.

### 4. Validation Granularity
Validation results are returned per-response with detailed error messages and warnings. This allows the mobile app to identify which responses succeeded and which need retry.

### 5. Two-Phase Document Upload
Documents (photos, signatures, scanned forms) use a two-phase upload:
1. Request pre-signed URL from API
2. Upload file directly to cloud storage

This avoids routing large files through the API server.

## Endpoint Group: /mobile

All mobile endpoints are prefixed with `/mobile` and require JWT authentication (except login).

### Authentication

All endpoints except `/mobile/login` require Bearer token authentication:

```
Authorization: Bearer <jwt_token>
```

### Rate Limiting

Recommended rate limits:
- `/mobile/login`: 5 requests per minute per IP
- `/mobile/responses/batch`: 10 requests per minute per user
- `/mobile/documents/upload`: 20 requests per minute per user
- Other endpoints: 30 requests per minute per user

## Endpoint: POST /mobile/login

### Purpose
Mobile-specific login endpoint with device tracking.

### Request

**Query Parameters:**
- `device_id` (required): Unique device identifier (UUID)
- `app_version` (required): Mobile app version (e.g., "1.0.0")

**Body:**
```json
{
  "email": "brigadista@brigada.com",
  "password": "brigadista123"
}
```

### Response

**Success (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error (401 Unauthorized):**
```json
{
  "detail": "Incorrect email or password"
}
```

### Differences from /auth/login

- Tracks device ID for sync purposes
- Records app version for compatibility checks
- Returns mobile-optimized token (same JWT, different metadata)

### Mobile Implementation

```javascript
async function login(email, password) {
  const deviceId = await getDeviceId(); // From device storage or generate
  const appVersion = getAppVersion(); // From app manifest
  
  const response = await fetch(
    `${API_URL}/mobile/login?device_id=${deviceId}&app_version=${appVersion}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    }
  );
  
  const { access_token } = await response.json();
  await secureStorage.setItem('jwt_token', access_token);
  
  return access_token;
}
```

## Endpoint: GET /mobile/surveys

### Purpose
Get all surveys assigned to the current user with their latest published versions.

### Request

**Query Parameters:**
- `status_filter` (optional): Filter by assignment status
  - Values: `pending`, `in_progress`, `completed`

**Headers:**
```
Authorization: Bearer <token>
```

### Response

**Success (200 OK):**
```json
[
  {
    "assignment_id": 1,
    "survey_id": 1,
    "survey_title": "Customer Satisfaction Survey",
    "survey_description": "Evaluate customer experience",
    "assignment_status": "pending",
    "assigned_location": "Zone A",
    "latest_version": {
      "id": 1,
      "version_number": 1,
      "is_published": true,
      "change_summary": null,
      "created_at": "2026-02-14T10:00:00Z",
      "questions": [
        {
          "id": 1,
          "version_id": 1,
          "question_text": "How satisfied are you?",
          "question_type": "single_choice",
          "order": 1,
          "is_required": true,
          "validation_rules": null,
          "options": [
            {"id": 1, "option_text": "Very satisfied", "order": 1},
            {"id": 2, "option_text": "Satisfied", "order": 2}
          ]
        }
      ]
    },
    "assigned_at": "2026-02-14T09:00:00Z"
  }
]
```

### Constraints

- Only returns PUBLISHED survey versions
- Mobile app cannot modify survey structure
- Survey structure is immutable (read-only for mobile)
- Version integrity is enforced server-side

### Mobile Implementation

```javascript
async function fetchAssignedSurveys() {
  const response = await authenticatedFetch('/mobile/surveys');
  const surveys = await response.json();
  
  // Store in local database for offline access
  for (const survey of surveys) {
    await db.surveys.put({
      id: survey.survey_id,
      version_id: survey.latest_version.id,
      title: survey.survey_title,
      description: survey.survey_description,
      assignment_id: survey.assignment_id,
      status: survey.assignment_status,
      questions: survey.latest_version.questions,
      downloaded_at: new Date()
    });
  }
  
  return surveys;
}
```

## Endpoint: POST /mobile/responses/batch

### Purpose
Submit multiple survey responses in one request for efficient offline sync.

### Request

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Body:**
```json
{
  "responses": [
    {
      "client_id": "550e8400-e29b-41d4-a716-446655440001",
      "version_id": 1,
      "location": {
        "lat": 40.7128,
        "lng": -74.0060,
        "accuracy": 10,
        "timestamp": "2026-02-14T10:00:00Z"
      },
      "started_at": "2026-02-14T10:00:00Z",
      "completed_at": "2026-02-14T10:15:00Z",
      "device_info": {
        "platform": "iOS",
        "version": "15.0",
        "model": "iPhone 13",
        "app_version": "1.0.0"
      },
      "answers": [
        {
          "question_id": 1,
          "answer_value": "Very satisfied",
          "media_url": null,
          "answered_at": "2026-02-14T10:05:00Z"
        },
        {
          "question_id": 2,
          "answer_value": "Great service!",
          "media_url": null,
          "answered_at": "2026-02-14T10:10:00Z"
        }
      ]
    }
  ]
}
```

### Response

**Success (201 Created):**
```json
{
  "total": 2,
  "successful": 1,
  "failed": 0,
  "duplicates": 1,
  "results": [
    {
      "client_id": "550e8400-e29b-41d4-a716-446655440001",
      "status": "success",
      "response_id": 123,
      "errors": [],
      "warnings": []
    },
    {
      "client_id": "550e8400-e29b-41d4-a716-446655440002",
      "status": "duplicate",
      "response_id": 122,
      "errors": [],
      "warnings": ["Response already exists - skipped"]
    }
  ]
}
```

### Validation Statuses

#### SUCCESS
Response was created successfully.

#### DUPLICATE
Response with this `client_id` already exists. Returns existing `response_id`.

#### FAILED
Response failed validation. Check `errors` array for details.

Common errors:
- "Survey version {id} not found"
- "Survey version {id} is not published"
- "Failed to submit response: {error}"

#### PARTIAL
Some answers failed validation but response was created. Check `warnings` array.

### OCR Confidence Warnings

If an answer includes OCR data with confidence < 0.7, a warning is added:

```json
{
  "client_id": "...",
  "status": "success",
  "response_id": 123,
  "errors": [],
  "warnings": [
    "Low OCR confidence (0.45) for question 5"
  ]
}
```

### Constraints

- Maximum 50 responses per batch
- Each response validated independently
- Failures don't affect other responses
- Survey version must exist and be published
- Cannot modify survey structure
- Version integrity enforced

### Mobile Implementation

```javascript
async function syncPendingResponses() {
  // Get all unsynced responses from local database
  const pending = await db.responses
    .where('synced')
    .equals(0)
    .limit(50)
    .toArray();
  
  if (pending.length === 0) return;
  
  const batch = {
    responses: pending.map(r => ({
      client_id: r.client_id,
      version_id: r.version_id,
      location: r.location,
      started_at: r.started_at,
      completed_at: r.completed_at,
      device_info: r.device_info,
      answers: r.answers
    }))
  };
  
  const result = await authenticatedFetch('/mobile/responses/batch', {
    method: 'POST',
    body: JSON.stringify(batch)
  });
  
  // Mark successful responses as synced
  for (const r of result.results) {
    if (r.status === 'success' || r.status === 'duplicate') {
      await db.responses.update(r.client_id, {
        synced: 1,
        server_id: r.response_id,
        synced_at: new Date()
      });
    }
  }
  
  // Log failed responses for retry
  const failed = result.results.filter(r => r.status === 'failed');
  if (failed.length > 0) {
    console.error('Failed to sync responses:', failed);
    // Could show error to user or retry later
  }
  
  return result;
}
```

## Endpoint: POST /mobile/documents/upload

### Purpose
Generate pre-signed URL for uploading documents (photos, signatures, scanned forms) with OCR validation.

### Request

**Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Body:**
```json
{
  "client_id": "550e8400-e29b-41d4-a716-446655440001",
  "file_name": "id_card_front.jpg",
  "file_size": 1024000,
  "mime_type": "image/jpeg",
  "metadata": {
    "document_type": "id_card",
    "question_id": 5,
    "ocr_confidence": 0.85,
    "ocr_text": "JOHN DOE\\n123456789\\nEXP: 12/2030",
    "page_number": 1
  }
}
```

### Response

**Success (201 Created):**
```json
{
  "document_id": "doc_a1b2c3d4e5f6",
  "upload_url": "https://s3.amazonaws.com/bucket/doc_a1b2c3d4e5f6?signature=...",
  "expires_at": "2026-02-14T11:30:00Z",
  "ocr_required": true,
  "low_confidence_warning": false
}
```

**Error (400 Bad Request):**
```json
{
  "detail": "File size 15000000 exceeds maximum 10485760"
}
```

### Document Types

- `id_card`: National ID, passport, driver's license (OCR required)
- `receipt`: Purchase receipts, invoices (OCR required)
- `signature`: User signature capture (OCR not required)
- `photo`: General photos - damage, location (OCR not required)
- `form`: Scanned filled forms (OCR required)

### OCR Confidence Thresholds

| Confidence | Action |
|------------|--------|
| ≥ 0.7 | Accept without warning |
| 0.5 - 0.69 | Accept with warning flag |
| < 0.5 | Accept with warning, prompt user to retake |

### Constraints

- Maximum file size: 10MB
- Supported MIME types: `image/jpeg`, `image/png`, `application/pdf`
- Pre-signed URL expires in 30 minutes
- Document must be linked to existing response (`client_id`)

### Two-Phase Upload Process

**Phase 1**: Request pre-signed URL (this endpoint)
- Mobile app sends document metadata
- Server validates and generates upload URL
- Server checks OCR confidence
- Returns pre-signed URL and document ID

**Phase 2**: Upload file to cloud storage
- Mobile app uploads directly to pre-signed URL
- No file passes through API server
- Reduces server load and bandwidth
- Cloud storage validates file

### Mobile Implementation

```javascript
async function uploadDocument(responseClientId, file, ocrResult) {
  // Phase 1: Request upload URL
  const uploadRequest = {
    client_id: responseClientId,
    file_name: file.name,
    file_size: file.size,
    mime_type: file.type,
    metadata: {
      document_type: 'id_card',
      question_id: 5,
      ocr_confidence: ocrResult?.confidence || null,
      ocr_text: ocrResult?.text || null
    }
  };
  
  const response = await authenticatedFetch('/mobile/documents/upload', {
    method: 'POST',
    body: JSON.stringify(uploadRequest)
  });
  
  const { document_id, upload_url, low_confidence_warning } = await response.json();
  
  // Warn user if OCR confidence is low
  if (low_confidence_warning) {
    const retry = await showAlert(
      'Low Image Quality',
      'The text in this image is unclear. Would you like to retake it?',
      ['Retake', 'Keep']
    );
    
    if (retry === 'Retake') {
      return null; // Let user retake photo
    }
  }
  
  // Phase 2: Upload file directly to cloud storage
  await fetch(upload_url, {
    method: 'PUT',
    body: file,
    headers: {
      'Content-Type': file.type
    }
  });
  
  // Store document ID with response
  await db.responses.update(responseClientId, {
    documents: [...existingDocuments, document_id]
  });
  
  return document_id;
}
```

## Endpoint: GET /mobile/sync-status

### Purpose
Get sync status and check for available survey updates.

### Request

**Headers:**
```
Authorization: Bearer <token>
```

### Response

**Success (200 OK):**
```json
{
  "user_id": 3,
  "pending_responses": 5,
  "synced_responses": 150,
  "pending_documents": 2,
  "last_sync": "2026-02-14T12:00:00Z",
  "assigned_surveys": 3,
  "available_updates": [1, 5]
}
```

### Response Fields

- `user_id`: Current user's ID
- `pending_responses`: Count of responses waiting to sync (client-side tracking)
- `synced_responses`: Total responses successfully synced to server
- `pending_documents`: Count of documents waiting to upload
- `last_sync`: Timestamp of last successful sync operation
- `assigned_surveys`: Count of surveys assigned to user
- `available_updates`: Array of survey IDs with new versions available

### Mobile Implementation

```javascript
// Periodic sync check
async function checkSyncStatus() {
  const status = await authenticatedFetch('/mobile/sync-status');
  
  // Update UI badge
  updateBadgeCount(status.pending_responses);
  
  // Notify user of available updates
  if (status.available_updates.length > 0) {
    showNotification('New survey versions available');
    
    // Download updates in background
    for (const surveyId of status.available_updates) {
      await downloadSurveyUpdate(surveyId);
    }
  }
  
  // Auto-sync if online and has pending data
  if (navigator.onLine && status.pending_responses > 0) {
    await syncPendingResponses();
  }
  
  return status;
}

// Check every minute
setInterval(checkSyncStatus, 60000);
```

## Error Handling

### Standard Error Response

All endpoints return errors in this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common HTTP Status Codes

- `200 OK`: Request succeeded
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Missing or invalid JWT token
- `403 Forbidden`: User doesn't have permission
- `404 Not Found`: Resource doesn't exist
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error

### Retry Logic

Mobile app should implement exponential backoff for retries:

```javascript
async function retryWithBackoff(fn, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (i === maxRetries - 1) throw error;
      
      // Exponential backoff: 1s, 2s, 4s
      const delay = Math.pow(2, i) * 1000;
      await sleep(delay);
    }
  }
}
```

## Security Considerations

### JWT Token Security

- Tokens expire after 30 minutes (configurable)
- Store tokens in secure storage (Keychain on iOS, Keystore on Android)
- Never store tokens in localStorage or plain text
- Clear tokens on logout

### Data Encryption

- All API communication over HTTPS
- Encrypt sensitive data in local database
- Use device encryption for offline data

### Input Validation

- Validate all user input client-side before sending
- Server performs additional validation
- Sanitize OCR text to prevent injection attacks

### Rate Limiting

- Implement client-side throttling
- Respect server rate limits
- Queue requests when limits exceeded

## Performance Optimization

### Batch Size Tuning

Recommended batch sizes based on network conditions:

- **Fast WiFi**: 50 responses per batch
- **Cellular 4G**: 20 responses per batch
- **Cellular 3G**: 10 responses per batch
- **Slow connection**: 5 responses per batch

### Compression

Enable gzip compression for requests/responses:

```javascript
headers: {
  'Accept-Encoding': 'gzip, deflate'
}
```

### Pagination

Use pagination for large datasets:

```javascript
async function fetchAllResponses() {
  let allResponses = [];
  let skip = 0;
  const limit = 100;
  
  while (true) {
    const batch = await authenticatedFetch(
      `/mobile/responses/me?skip=${skip}&limit=${limit}`
    );
    
    if (batch.length === 0) break;
    
    allResponses = allResponses.concat(batch);
    skip += limit;
  }
  
  return allResponses;
}
```

## Testing Strategy

### Unit Tests

Test individual endpoint handlers:

```python
def test_batch_responses_success():
    responses = [
        create_mock_response(client_id="test-1"),
        create_mock_response(client_id="test-2")
    ]
    
    result = submit_batch_responses(responses, user_id=1)
    
    assert result.total == 2
    assert result.successful == 2
    assert result.failed == 0
    assert result.duplicates == 0
```

### Integration Tests

Test complete workflows:

```python
def test_mobile_workflow():
    # Login
    token = mobile_login("brigadista@test.com", "password")
    
    # Get surveys
    surveys = get_assigned_surveys(token)
    assert len(surveys) > 0
    
    # Submit responses
    result = submit_batch_responses(token, mock_responses)
    assert result.successful > 0
    
    # Upload document
    doc = upload_document(token, mock_file)
    assert doc.document_id is not None
    
    # Check sync status
    status = get_sync_status(token)
    assert status.synced_responses > 0
```

### Load Tests

Simulate multiple mobile clients syncing:

```bash
# 100 concurrent users, each submitting 10 batches
locust -f load_test.py --users 100 --spawn-rate 10
```

## Monitoring and Observability

### Key Metrics

- **Sync Success Rate**: % of successful response syncs
- **Duplicate Rate**: % of duplicate submissions
- **OCR Warning Rate**: % of documents with low OCR confidence
- **Average Batch Size**: Responses per batch request
- **Sync Latency**: Time from request to successful sync
- **Upload Failures**: % of failed document uploads

### Logging

Log important events:

```python
logger.info(
    "Batch sync completed",
    user_id=user.id,
    total=result.total,
    successful=result.successful,
    failed=result.failed,
    duplicates=result.duplicates
)
```

### Alerting

Set up alerts for:
- Sync success rate < 95%
- OCR warning rate > 20%
- Average API latency > 2s
- Error rate > 1%

## Future Enhancements

### Planned Features

1. **Delta Sync**: Only sync changes since last sync
2. **Conflict Resolution**: Handle concurrent edits
3. **Progressive Sync**: Sync high-priority responses first
4. **Media Optimization**: Compress images before upload
5. **Background Sync**: Sync when app is in background
6. **Peer-to-Peer Sync**: Sync between devices without internet

### API Versioning

Future API versions will be prefixed:

- `/v1/mobile/*` (current)
- `/v2/mobile/*` (future)

Mobile app should specify accepted version in headers:

```
Accept-Version: v1
```

## Conclusion

The mobile API provides a robust, offline-first solution for survey data collection. Key strengths:

- ✅ Works without internet connection
- ✅ Efficient batch sync reduces network usage
- ✅ Automatic duplicate detection
- ✅ OCR validation catches quality issues
- ✅ Immutable survey structure prevents data corruption
- ✅ Detailed validation results aid debugging
- ✅ Two-phase upload optimizes performance

For implementation questions, see `/docs` API documentation or contact the backend team.
