"""
Seed a comprehensive test survey with ALL supported question types.

Usage:
    cd brigadaBackEnd
    python -m scripts.seed_test_survey

Creates:
  - "Encuesta de Prueba — Todos los Tipos" survey
  - 1 published version with one question per supported type
  - Active assignment to the brigadista test user
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal, engine, Base
from app.models.user import User, UserRole
from app.models.survey import Survey, SurveyVersion, Question, QuestionType, AnswerOption
from app.models.assignment import Assignment, AssignmentStatus


def seed_test_survey():
    """Create a test survey with every question type."""
    db = SessionLocal()

    try:
        # ── Find or skip ─────────────────────────────────────────────────
        existing = db.query(Survey).filter(
            Survey.title == "Encuesta de Prueba — Todos los Tipos"
        ).first()
        if existing:
            print("⚠️  Test survey already exists (id=%d). Skipping." % existing.id)
            return

        # We need an admin user as creator and a brigadista as assignee
        admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
        brigadista = db.query(User).filter(User.role == UserRole.BRIGADISTA).first()

        if not admin:
            print("❌ No admin user found. Run `python -m scripts.seed_data` first.")
            return
        if not brigadista:
            print("❌ No brigadista user found. Run `python -m scripts.seed_data` first.")
            return

        # ── Create survey ────────────────────────────────────────────────
        survey = Survey(
            title="Encuesta de Prueba — Todos los Tipos",
            description=(
                "Esta encuesta contiene una pregunta de cada tipo soportado "
                "por el sistema. Ideal para verificar la apariencia y "
                "funcionalidad de cada componente."
            ),
            is_active=True,
            created_by=admin.id,
            estimated_duration_minutes=10,
            allow_anonymous=False,
        )
        db.add(survey)
        db.flush()  # get survey.id

        # ── Create version ───────────────────────────────────────────────
        version = SurveyVersion(
            survey_id=survey.id,
            version_number=1,
            is_published=True,
            change_summary="Versión inicial con todos los tipos de pregunta",
        )
        db.add(version)
        db.flush()  # get version.id

        # ── Questions ────────────────────────────────────────────────────
        questions_data = [
            # 1. Text
            {
                "question_text": "¿Cuál es tu nombre completo?",
                "question_type": QuestionType.TEXT,
                "is_required": True,
                "validation_rules": {"max_length": 200},
            },
            # 2. Textarea
            {
                "question_text": "Describe brevemente tu comunidad",
                "question_type": QuestionType.TEXTAREA,
                "is_required": False,
                "validation_rules": {"max_length": 500},
            },
            # 3. Email
            {
                "question_text": "Correo electrónico de contacto",
                "question_type": QuestionType.EMAIL,
                "is_required": True,
                "validation_rules": None,
            },
            # 4. Phone
            {
                "question_text": "Número de teléfono",
                "question_type": QuestionType.PHONE,
                "is_required": False,
                "validation_rules": None,
            },
            # 5. Number
            {
                "question_text": "¿Cuántas personas viven en tu hogar?",
                "question_type": QuestionType.NUMBER,
                "is_required": True,
                "validation_rules": {"min": 1, "max": 50},
            },
            # 6. Slider
            {
                "question_text": "¿Qué tan satisfecho estás con los servicios de salud? (1-10)",
                "question_type": QuestionType.SLIDER,
                "is_required": False,
                "validation_rules": {"min": 1, "max": 10},
            },
            # 7. Scale
            {
                "question_text": "Califica la calidad del agua en tu colonia (1-5)",
                "question_type": QuestionType.SCALE,
                "is_required": True,
                "validation_rules": {"min": 1, "max": 5},
            },
            # 8. Rating
            {
                "question_text": "¿Cómo calificas el programa de brigada? (1-5 estrellas)",
                "question_type": QuestionType.RATING,
                "is_required": False,
                "validation_rules": {"min": 1, "max": 5},
            },
            # 9. Single choice
            {
                "question_text": "¿Cuál es tu nivel de estudios?",
                "question_type": QuestionType.SINGLE_CHOICE,
                "is_required": True,
                "validation_rules": None,
                "options": [
                    "Primaria",
                    "Secundaria",
                    "Preparatoria",
                    "Universidad",
                    "Posgrado",
                    "Otro",
                ],
            },
            # 10. Multiple choice
            {
                "question_text": "¿Qué servicios públicos tiene tu vivienda?",
                "question_type": QuestionType.MULTIPLE_CHOICE,
                "is_required": True,
                "validation_rules": None,
                "options": [
                    "Agua potable",
                    "Electricidad",
                    "Drenaje",
                    "Gas natural",
                    "Internet",
                    "Recolección de basura",
                ],
            },
            # 11. Yes/No
            {
                "question_text": "¿Cuentas con seguro médico?",
                "question_type": QuestionType.YES_NO,
                "is_required": True,
                "validation_rules": None,
            },
            # 12. Date
            {
                "question_text": "Fecha de nacimiento del jefe de familia",
                "question_type": QuestionType.DATE,
                "is_required": True,
                "validation_rules": None,
            },
            # 13. Time
            {
                "question_text": "¿A qué hora prefieres ser visitado(a)?",
                "question_type": QuestionType.TIME,
                "is_required": False,
                "validation_rules": None,
            },
            # 14. Datetime
            {
                "question_text": "Fecha y hora de la última visita médica",
                "question_type": QuestionType.DATETIME,
                "is_required": False,
                "validation_rules": None,
            },
            # 15. Photo
            {
                "question_text": "Toma una foto de la fachada de la vivienda",
                "question_type": QuestionType.PHOTO,
                "is_required": False,
                "validation_rules": None,
            },
            # 16. Signature
            {
                "question_text": "Firma del encuestado",
                "question_type": QuestionType.SIGNATURE,
                "is_required": True,
                "validation_rules": None,
            },
            # 17. INE / OCR
            {
                "question_text": "Captura la credencial INE (frente y reverso)",
                "question_type": QuestionType.INE_OCR,
                "is_required": True,
                "validation_rules": None,
            },
            # 18. Location
            {
                "question_text": "Ubicación GPS del domicilio",
                "question_type": QuestionType.LOCATION,
                "is_required": False,
                "validation_rules": None,
            },
            # 19. File
            {
                "question_text": "Adjunta un comprobante de domicilio (PDF o imagen)",
                "question_type": QuestionType.FILE,
                "is_required": False,
                "validation_rules": None,
            },
        ]

        for order, q_data in enumerate(questions_data, start=1):
            options_list = q_data.pop("options", None)

            question = Question(
                version_id=version.id,
                order=order,
                **q_data,
            )
            db.add(question)
            db.flush()  # get question.id

            if options_list:
                for opt_order, opt_text in enumerate(options_list, start=1):
                    db.add(AnswerOption(
                        question_id=question.id,
                        option_text=opt_text,
                        order=opt_order,
                    ))

        # ── Assign to brigadista ─────────────────────────────────────────
        assignment = Assignment(
            user_id=brigadista.id,
            survey_id=survey.id,
            assigned_by=admin.id,
            status=AssignmentStatus.ACTIVE,
            location="Zona de Pruebas",
            notes="Encuesta de prueba para verificar todos los tipos de pregunta.",
        )
        db.add(assignment)

        # ── Commit ───────────────────────────────────────────────────────
        db.commit()

        print("✅ Test survey seeded successfully!")
        print(f"   Survey ID: {survey.id}")
        print(f"   Version ID: {version.id} (published)")
        print(f"   Questions: {len(questions_data)}")
        print(f"   Assigned to: {brigadista.full_name} (id={brigadista.id})")
        print()
        print("   Question types included:")
        for i, q in enumerate(questions_data, 1):
            qt = q.get("question_type", q.get("question_type"))
            print(f"     {i:2d}. {qt.value if hasattr(qt, 'value') else qt}")

    except Exception as e:
        print(f"❌ Error seeding test survey: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    # Ensure tables exist
    Base.metadata.create_all(bind=engine)
    seed_test_survey()
