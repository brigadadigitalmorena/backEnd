"""
Seed a demo survey that covers every question type and assigns it to brigadista@brigada.com.
Safe to run multiple times — skips creation if the survey title already exists.
"""
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal, engine, Base
from app.models.survey import Survey, SurveyVersion, Question, AnswerOption, QuestionType
from app.models.user import User
from app.models.assignment import Assignment, AssignmentStatus

SURVEY_TITLE = "[DEMO] Todos los tipos de pregunta"

# -----------------------------------------------------------
# Question definitions: (text, type, required, options, validation_rules)
# options only for choice-based questions.
# -----------------------------------------------------------
QUESTIONS = [
    # ── Text inputs ──────────────────────────────────────────
    (
        "1. Texto corto — Escribe tu nombre completo",
        QuestionType.TEXT, True, [],
        {"maxLength": 100},
    ),
    (
        "2. Texto largo — Describe brevemente tu actividad del día",
        QuestionType.TEXTAREA, False, [],
        {"maxLength": 500},
    ),
    (
        "3. Correo electrónico — ¿Cuál es tu email de contacto?",
        QuestionType.EMAIL, False, [],
        None,
    ),
    (
        "4. Teléfono — Número de celular (10 dígitos)",
        QuestionType.PHONE, False, [],
        {"pattern": r"^\d{10}$"},
    ),
    # ── Numeric ──────────────────────────────────────────────
    (
        "5. Número — ¿Cuántas visitas realizaste hoy?",
        QuestionType.NUMBER, True, [],
        {"min": 0, "max": 50},
    ),
    (
        "6. Slider — Nivel de energía (0 = muy cansado, 100 = excelente)",
        QuestionType.SLIDER, False, [],
        {"min": 0, "max": 100, "step": 5},
    ),
    (
        "7. Escala — Nivel de dificultad del recorrido (1 al 5)",
        QuestionType.SCALE, False, [],
        {"min": 1, "max": 5},
    ),
    (
        "8. Calificación — ¿Qué tan útil fue la capacitación? (1 a 5 estrellas)",
        QuestionType.RATING, False, [],
        {"min": 1, "max": 5},
    ),
    # ── Choice ───────────────────────────────────────────────
    (
        "9. Opción única — ¿En qué zona trabajaste hoy?",
        QuestionType.SINGLE_CHOICE, True,
        ["Zona Norte", "Zona Sur", "Zona Centro", "Zona Oriente", "Zona Poniente"],
        None,
    ),
    (
        "10. Opción múltiple — ¿Qué materiales utilizaste?",
        QuestionType.MULTIPLE_CHOICE, False,
        ["Folletos", "Tableta digital", "Uniforme", "Credencial", "Mapa de ruta"],
        None,
    ),
    (
        "11. Sí / No — ¿Completaste todas las visitas programadas?",
        QuestionType.YES_NO, True, [],
        None,
    ),
    # ── Date / Time ──────────────────────────────────────────
    (
        "12. Fecha — ¿Cuándo fue tu última capacitación?",
        QuestionType.DATE, False, [],
        None,
    ),
    (
        "13. Hora — ¿A qué hora iniciaste tu jornada?",
        QuestionType.TIME, False, [],
        None,
    ),
    (
        "14. Fecha y hora — ¿Cuándo ocurrió el incidente (si aplica)?",
        QuestionType.DATETIME, False, [],
        None,
    ),
    # ── Media & especiales ───────────────────────────────────
    (
        "15. Foto — Toma una fotografía del punto de visita",
        QuestionType.PHOTO, False, [],
        None,
    ),
    (
        "16. Archivo — Adjunta tu reporte en PDF (si tienes uno)",
        QuestionType.FILE, False, [],
        {"allowedTypes": ["application/pdf"], "maxSizeMB": 5},
    ),
    (
        "17. Firma — Firma digital de conformidad",
        QuestionType.SIGNATURE, False, [],
        None,
    ),
    (
        "18. Ubicación — Registra tu posición GPS actual",
        QuestionType.LOCATION, True, [],
        None,
    ),
    (
        "19. INE / OCR — Escanea la INE del ciudadano atendido",
        QuestionType.INE_OCR, False, [],
        None,
    ),
]


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # ── Find brigadista user ──────────────────────────────
        brigadista = db.query(User).filter(User.email == "brigadista@brigada.com").first()
        if not brigadista:
            print("❌ brigadista@brigada.com not found. Run seed_data.py first.")
            return

        admin = (
            db.query(User).filter(User.email == "admin@brigada.com").first()
            or db.query(User).filter(User.role == "ADMIN").first()
        )
        creator_id = admin.id if admin else brigadista.id

        # ── Idempotency check ────────────────────────────────
        existing = db.query(Survey).filter(Survey.title == SURVEY_TITLE).first()
        if existing:
            print(f"ℹ️  Demo survey already exists (id={existing.id}). Nothing to do.")
            return

        # ── Create Survey ────────────────────────────────────
        now = datetime.now(timezone.utc)
        survey = Survey(
            title=SURVEY_TITLE,
            description=(
                "Encuesta de prueba que contiene uno de cada tipo de pregunta disponible "
                "en el sistema. Úsala para verificar el renderizado y guardado de respuestas "
                "en la app móvil."
            ),
            is_active=True,
            created_by=creator_id,
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=30),
            estimated_duration_minutes=10,
        )
        db.add(survey)
        db.flush()

        # ── Create Version 1 (published) ─────────────────────
        version = SurveyVersion(
            survey_id=survey.id,
            version_number=1,
            is_published=True,
            change_summary="Versión inicial de la encuesta demo.",
        )
        db.add(version)
        db.flush()

        # ── Create Questions ──────────────────────────────────
        for order, (text, qtype, required, options, rules) in enumerate(QUESTIONS, start=1):
            question = Question(
                version_id=version.id,
                question_text=text,
                question_type=qtype,
                order=order,
                is_required=required,
                validation_rules=rules,
            )
            db.add(question)
            db.flush()

            for opt_order, opt_text in enumerate(options, start=1):
                db.add(AnswerOption(
                    question_id=question.id,
                    option_text=opt_text,
                    order=opt_order,
                ))

        # ── Assign to brigadista ──────────────────────────────
        assignment = Assignment(
            user_id=brigadista.id,
            survey_id=survey.id,
            assigned_by=creator_id,
            status=AssignmentStatus.ACTIVE,
            notes="Encuesta demo — revisa que todos los tipos de pregunta se vean y guarden correctamente.",
        )
        db.add(assignment)
        db.commit()

        print(f"✅ Demo survey created (id={survey.id}, version_id={version.id})")
        print(f"   {len(QUESTIONS)} questions covering all {len(QuestionType)} question types")
        print(f"   Assigned to brigadista@brigada.com (user_id={brigadista.id})")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback; traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    run()
