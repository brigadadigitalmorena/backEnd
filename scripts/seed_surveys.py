"""Seed database with example surveys covering diverse question types."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.models.user import User
from app.services.survey_service import SurveyService
from app.schemas.survey import SurveyCreate, QuestionCreate, AnswerOptionCreate

SURVEYS = [
    # ─── 1. Censo de vivienda ──────────────────────────────────────────────────
    SurveyCreate(
        title="Censo de Vivienda",
        description="Levantamiento de condiciones habitacionales en zonas de atención prioritaria.",
        questions=[
            QuestionCreate(
                question_text="Nombre completo del jefe(a) de familia",
                question_type="text",
                order=1,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Número de personas que habitan la vivienda",
                question_type="number",
                order=2,
                is_required=True,
                validation_rules={"min": 1, "max": 30},
            ),
            QuestionCreate(
                question_text="Tipo de vivienda",
                question_type="single_choice",
                order=3,
                is_required=True,
                options=[
                    AnswerOptionCreate(option_text="Casa propia", order=1),
                    AnswerOptionCreate(option_text="Renta", order=2),
                    AnswerOptionCreate(option_text="Prestada", order=3),
                    AnswerOptionCreate(option_text="Irregular / asentamiento", order=4),
                ],
            ),
            QuestionCreate(
                question_text="Servicios básicos disponibles",
                question_type="multiple_choice",
                order=4,
                is_required=False,
                options=[
                    AnswerOptionCreate(option_text="Agua potable", order=1),
                    AnswerOptionCreate(option_text="Luz eléctrica", order=2),
                    AnswerOptionCreate(option_text="Drenaje / alcantarillado", order=3),
                    AnswerOptionCreate(option_text="Gas natural", order=4),
                    AnswerOptionCreate(option_text="Internet", order=5),
                ],
            ),
            QuestionCreate(
                question_text="¿La vivienda presenta daños estructurales visibles?",
                question_type="yes_no",
                order=5,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Descripción de los daños (si aplica)",
                question_type="textarea",
                order=6,
                is_required=False,
            ),
            QuestionCreate(
                question_text="Fotografía de la fachada",
                question_type="photo",
                order=7,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Ubicación GPS de la vivienda",
                question_type="location",
                order=8,
                is_required=True,
            ),
        ],
    ),

    # ─── 2. Encuesta de salud comunitaria ─────────────────────────────────────
    SurveyCreate(
        title="Encuesta de Salud Comunitaria",
        description="Evaluación del estado de salud y acceso a servicios médicos en la comunidad.",
        questions=[
            QuestionCreate(
                question_text="Fecha de la visita",
                question_type="date",
                order=1,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Correo electrónico del entrevistado (opcional)",
                question_type="email",
                order=2,
                is_required=False,
            ),
            QuestionCreate(
                question_text="Teléfono de contacto",
                question_type="phone",
                order=3,
                is_required=False,
            ),
            QuestionCreate(
                question_text="En general, ¿cómo califica su estado de salud?",
                question_type="rating",
                order=4,
                is_required=True,
                validation_rules={"min": 1, "max": 5},
            ),
            QuestionCreate(
                question_text="Nivel de satisfacción con los servicios de salud disponibles (1 = muy insatisfecho, 10 = muy satisfecho)",
                question_type="scale",
                order=5,
                is_required=True,
                validation_rules={"min": 1, "max": 10},
            ),
            QuestionCreate(
                question_text="¿Con qué frecuencia acude al médico?",
                question_type="single_choice",
                order=6,
                is_required=True,
                options=[
                    AnswerOptionCreate(option_text="Nunca", order=1),
                    AnswerOptionCreate(option_text="Solo en emergencias", order=2),
                    AnswerOptionCreate(option_text="1–2 veces al año", order=3),
                    AnswerOptionCreate(option_text="Cada 3–6 meses", order=4),
                    AnswerOptionCreate(option_text="Mensualmente o más", order=5),
                ],
            ),
            QuestionCreate(
                question_text="Enfermedades o condiciones crónicas presentes en el hogar",
                question_type="multiple_choice",
                order=7,
                is_required=False,
                options=[
                    AnswerOptionCreate(option_text="Diabetes", order=1),
                    AnswerOptionCreate(option_text="Hipertensión", order=2),
                    AnswerOptionCreate(option_text="Obesidad", order=3),
                    AnswerOptionCreate(option_text="Asma / enfermedades respiratorias", order=4),
                    AnswerOptionCreate(option_text="Ninguna", order=5),
                ],
            ),
            QuestionCreate(
                question_text="Observaciones adicionales del brigadista",
                question_type="textarea",
                order=8,
                is_required=False,
            ),
        ],
    ),

    # ─── 3. Registro de beneficiarios ─────────────────────────────────────────
    SurveyCreate(
        title="Registro de Beneficiarios",
        description="Captura de datos personales y documentos de identificación para el padrón de beneficiarios.",
        questions=[
            QuestionCreate(
                question_text="Escaneo de INE / credencial de elector",
                question_type="ine_ocr",
                order=1,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Nombre completo (confirmación)",
                question_type="text",
                order=2,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Fecha de nacimiento",
                question_type="date",
                order=3,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Correo electrónico",
                question_type="email",
                order=4,
                is_required=False,
            ),
            QuestionCreate(
                question_text="Número de teléfono",
                question_type="phone",
                order=5,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Programa de apoyo al que aplica",
                question_type="multiple_choice",
                order=6,
                is_required=True,
                options=[
                    AnswerOptionCreate(option_text="Apoyo alimentario", order=1),
                    AnswerOptionCreate(option_text="Apoyo económico", order=2),
                    AnswerOptionCreate(option_text="Apoyo médico", order=3),
                    AnswerOptionCreate(option_text="Apoyo educativo", order=4),
                    AnswerOptionCreate(option_text="Apoyo de vivienda", order=5),
                ],
            ),
            QuestionCreate(
                question_text="Firma del beneficiario",
                question_type="signature",
                order=7,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Fotografía del beneficiario",
                question_type="photo",
                order=8,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Ubicación del domicilio",
                question_type="location",
                order=9,
                is_required=True,
            ),
        ],
    ),

    # ─── 4. Evaluación de riesgos y vulnerabilidad ────────────────────────────
    SurveyCreate(
        title="Evaluación de Riesgos y Vulnerabilidad",
        description="Identificación de factores de riesgo social, ambiental y estructural en la zona.",
        questions=[
            QuestionCreate(
                question_text="Zona o colonia evaluada",
                question_type="text",
                order=1,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Hora del levantamiento",
                question_type="time",
                order=2,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Nivel de riesgo por inundación (0 = ninguno, 10 = muy alto)",
                question_type="slider",
                order=3,
                is_required=True,
                validation_rules={"min": 0, "max": 10, "step": 1},
            ),
            QuestionCreate(
                question_text="Nivel de riesgo por deslizamiento de tierra (0 = ninguno, 10 = muy alto)",
                question_type="slider",
                order=4,
                is_required=True,
                validation_rules={"min": 0, "max": 10, "step": 1},
            ),
            QuestionCreate(
                question_text="Nivel de marginación social percibido",
                question_type="scale",
                order=5,
                is_required=True,
                validation_rules={"min": 1, "max": 5},
            ),
            QuestionCreate(
                question_text="¿Existen accesos para vehículos de emergencia?",
                question_type="yes_no",
                order=6,
                is_required=True,
            ),
            QuestionCreate(
                question_text="¿Hay presencia de fauna nociva o plagas?",
                question_type="yes_no",
                order=7,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Tipo de riesgos identificados",
                question_type="multiple_choice",
                order=8,
                is_required=False,
                options=[
                    AnswerOptionCreate(option_text="Inundación", order=1),
                    AnswerOptionCreate(option_text="Deslizamiento", order=2),
                    AnswerOptionCreate(option_text="Incendio", order=3),
                    AnswerOptionCreate(option_text="Sismos / fallas geológicas", order=4),
                    AnswerOptionCreate(option_text="Delincuencia / inseguridad", order=5),
                    AnswerOptionCreate(option_text="Contaminación", order=6),
                ],
            ),
            QuestionCreate(
                question_text="Descripción detallada de los riesgos observados",
                question_type="textarea",
                order=9,
                is_required=False,
            ),
            QuestionCreate(
                question_text="Fotografías de evidencia",
                question_type="photo",
                order=10,
                is_required=False,
            ),
        ],
    ),

    # ─── 5. Inspección de infraestructura comunitaria ─────────────────────────
    SurveyCreate(
        title="Inspección de Infraestructura Comunitaria",
        description="Revisión del estado de calles, alumbrado, espacios públicos y servicios municipales.",
        questions=[
            QuestionCreate(
                question_text="Fecha y hora de la inspección",
                question_type="datetime",
                order=1,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Tipo de infraestructura inspeccionada",
                question_type="single_choice",
                order=2,
                is_required=True,
                options=[
                    AnswerOptionCreate(option_text="Calle / pavimento", order=1),
                    AnswerOptionCreate(option_text="Alumbrado público", order=2),
                    AnswerOptionCreate(option_text="Parque / área verde", order=3),
                    AnswerOptionCreate(option_text="Escuela o centro comunitario", order=4),
                    AnswerOptionCreate(option_text="Clínica / centro de salud", order=5),
                ],
            ),
            QuestionCreate(
                question_text="¿La infraestructura está en condiciones de uso?",
                question_type="yes_no",
                order=3,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Estado general de conservación (1 = muy malo, 5 = excelente)",
                question_type="rating",
                order=4,
                is_required=True,
                validation_rules={"min": 1, "max": 5},
            ),
            QuestionCreate(
                question_text="Porcentaje aproximado de deterioro",
                question_type="slider",
                order=5,
                is_required=True,
                validation_rules={"min": 0, "max": 100, "step": 5},
            ),
            QuestionCreate(
                question_text="Problemas identificados",
                question_type="multiple_choice",
                order=6,
                is_required=False,
                options=[
                    AnswerOptionCreate(option_text="Baches / pavimento dañado", order=1),
                    AnswerOptionCreate(option_text="Luminarias apagadas", order=2),
                    AnswerOptionCreate(option_text="Basura / residuos", order=3),
                    AnswerOptionCreate(option_text="Vandalism o graffiti", order=4),
                    AnswerOptionCreate(option_text="Drenaje tapado", order=5),
                    AnswerOptionCreate(option_text="Árboles con riesgo de caída", order=6),
                ],
            ),
            QuestionCreate(
                question_text="Descripción de los hallazgos",
                question_type="textarea",
                order=7,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Fotografías del estado actual",
                question_type="photo",
                order=8,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Documentos de soporte (planos, reportes previos)",
                question_type="file",
                order=9,
                is_required=False,
            ),
            QuestionCreate(
                question_text="Firma del inspector",
                question_type="signature",
                order=10,
                is_required=True,
            ),
            QuestionCreate(
                question_text="Coordenadas GPS del lugar inspeccionado",
                question_type="location",
                order=11,
                is_required=True,
            ),
        ],
    ),
]


def seed_surveys():
    db = SessionLocal()
    try:
        from app.models.user import UserRole
        admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if not admin:
            print("❌ No admin user found. Run seed_data.py first.")
            return

        service = SurveyService(db)
        for survey_data in SURVEYS:
            created = service.create_survey(survey_data, admin.id)
            print(f"  ✅ [{created.id}] {created.title} ({len(survey_data.questions)} preguntas)")

        print(f"\n✅ {len(SURVEYS)} encuestas de ejemplo creadas.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("Sembrando encuestas de ejemplo...\n")
    seed_surveys()
