"""Assignment repository."""
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.assignment import Assignment, AssignmentStatus


class AssignmentRepository:
    """Assignment data access layer."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, user_id: int, survey_id: int, assigned_by: int,
               location: Optional[str] = None) -> Assignment:
        """Create a new assignment."""
        assignment = Assignment(
            user_id=user_id,
            survey_id=survey_id,
            assigned_by=assigned_by,
            location=location
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment
    
    def get_by_id(self, assignment_id: int) -> Optional[Assignment]:
        """Get assignment by ID."""
        return self.db.query(Assignment).filter(Assignment.id == assignment_id).first()
    
    def get_all(self, status: Optional[AssignmentStatus] = None,
                skip: int = 0, limit: int = 200) -> List[Assignment]:
        """Get all assignments (admin view)."""
        from sqlalchemy.orm import joinedload
        query = self.db.query(Assignment)\
            .options(joinedload(Assignment.user), joinedload(Assignment.survey))
        if status is not None:
            query = query.filter(Assignment.status == status)
        return query.order_by(Assignment.created_at.desc()).offset(skip).limit(limit).all()

    def get_by_user(self, user_id: int, status: Optional[AssignmentStatus] = None,
                    skip: int = 0, limit: int = 100) -> List[Assignment]:
        """Get assignments for a user."""
        query = self.db.query(Assignment).filter(Assignment.user_id == user_id)
        
        if status is not None:
            query = query.filter(Assignment.status == status)
        
        return query.offset(skip).limit(limit).all()
    
    def get_by_survey(self, survey_id: int, status: Optional[AssignmentStatus] = None,
                     skip: int = 0, limit: int = 100) -> List[Assignment]:
        """Get assignments for a survey."""
        query = self.db.query(Assignment).filter(Assignment.survey_id == survey_id)
        
        if status is not None:
            query = query.filter(Assignment.status == status)
        
        return query.offset(skip).limit(limit).all()
    
    def exists(self, user_id: int, survey_id: int) -> bool:
        """Check if assignment exists."""
        return self.db.query(Assignment)\
            .filter(and_(
                Assignment.user_id == user_id,
                Assignment.survey_id == survey_id
            ))\
            .first() is not None
    
    def update_status(self, assignment_id: int, status: AssignmentStatus) -> Optional[Assignment]:
        """Update assignment status."""
        assignment = self.get_by_id(assignment_id)
        if not assignment:
            return None
        
        assignment.status = status
        self.db.commit()
        self.db.refresh(assignment)
        return assignment
    
    def update(self, assignment_id: int, **kwargs) -> Optional[Assignment]:
        """Update assignment fields."""
        assignment = self.get_by_id(assignment_id)
        if not assignment:
            return None
        
        for key, value in kwargs.items():
            if value is not None and hasattr(assignment, key):
                setattr(assignment, key, value)
        
        self.db.commit()
        self.db.refresh(assignment)
        return assignment
    
    def delete(self, assignment_id: int) -> bool:
        """Delete assignment."""
        assignment = self.get_by_id(assignment_id)
        if not assignment:
            return False
        
        self.db.delete(assignment)
        self.db.commit()
        return True
