"""Document model — tracks files uploaded to Cloudinary."""

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Float,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Document(Base):
    """
    Tracks individual file uploads linked to survey responses.

    Lifecycle:
      1. ``POST /mobile/documents/upload`` → row created (status = pending)
      2. Client uploads file to Cloudinary
      3. ``POST /mobile/documents/confirm`` → row updated (status = uploaded, remote_url set)
    """

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    # Unique identifier generated server-side (``doc_<hex>``)
    document_id = Column(String(64), unique=True, nullable=False, index=True)

    # The user who initiated the upload
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Link to the response this file belongs to (via client_id)
    response_client_id = Column(String, nullable=False, index=True)

    # Optional FK to the question
    question_id = Column(
        Integer,
        ForeignKey("questions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # File metadata
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    document_type = Column(String(50), nullable=False)  # photo, signature, id_card …

    # Cloudinary references (populated on confirm)
    cloudinary_public_id = Column(String(512), nullable=True)
    remote_url = Column(Text, nullable=True)

    # OCR metadata
    ocr_confidence = Column(Float, nullable=True)

    # Status: pending | uploaded | error
    status = Column(String(20), nullable=False, default="pending", index=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", backref="documents")
