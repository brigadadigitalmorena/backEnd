"""Seed realistic survey responses for demo/testing."""
import sys, uuid, random
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.models.survey import Survey, SurveyVersion, Question, QuestionType
from app.models.response import SurveyResponse, QuestionAnswer

db = SessionLocal()

# ── 1. Publish versions for a set of surveys ─────────────────────────────
TARGET_SURVEY_IDS = [6, 7, 8, 9, 10]

versions = (
    db.query(SurveyVersion)
    .filter(SurveyVersion.survey_id.in_(TARGET_SURVEY_IDS))
    .all()
)
for v in versions:
    v.is_published = True
db.flush()
print(f"Published {len(versions)} survey versions")

# ── 2. Load questions per version ─────────────────────────────────────────
version_questions: dict[int, list[Question]] = {}
for v in versions:
    qs = (
        db.query(Question)
        .filter(Question.version_id == v.id)
        .order_by(Question.order)
        .all()
    )
    version_questions[v.id] = qs
    print(f"  survey {v.survey_id} → version {v.id} has {len(qs)} questions")

# ── 3. Answer generators ──────────────────────────────────────────────────
NAMES = [
    "María López", "Juan García", "Ana Torres", "Pedro Martínez",
    "Luisa Hernández", "Carlos Ruiz", "Elena Sánchez", "Roberto Díaz",
    "Patricia Flores", "Miguel Morales",
]
EMAILS = [n.split()[0].lower() + "@example.com" for n in NAMES]


def fake_answer(q: Question):
    qt = q.question_type
    if qt == QuestionType.TEXT:
        return random.choice(NAMES)
    if qt == QuestionType.TEXTAREA:
        return random.choice([
            "Todo estuvo muy bien organizado.",
            "Faltó más personal de apoyo.",
            "Buen servicio, ambiente tranquilo.",
            "Necesita mejoras en infraestructura.",
        ])
    if qt == QuestionType.EMAIL:
        return random.choice(EMAILS)
    if qt == QuestionType.PHONE:
        return f"+52 55 {random.randint(1000,9999)} {random.randint(1000,9999)}"
    if qt in (QuestionType.NUMBER,):
        return random.randint(1, 8)
    if qt in (QuestionType.SLIDER, QuestionType.SCALE, QuestionType.RATING):
        return random.randint(1, 10)
    if qt == QuestionType.YES_NO:
        return random.choice(["Sí", "No"])
    if qt == QuestionType.SINGLE_CHOICE:
        return random.choice(["Excelente", "Bueno", "Regular", "Malo", "Muy malo"])
    if qt == QuestionType.MULTIPLE_CHOICE:
        opts = ["Vecinos", "Redes sociales", "Volante", "Radio", "Periódico"]
        return random.sample(opts, k=random.randint(1, 3))
    if qt == QuestionType.DATE:
        d = datetime(2025, random.randint(10, 12), random.randint(1, 28))
        return d.strftime("%Y-%m-%d")
    if qt == QuestionType.TIME:
        return f"{random.randint(8,18):02d}:{random.choice(['00','15','30','45'])}"
    if qt == QuestionType.DATETIME:
        d = datetime(2025, random.randint(10, 12), random.randint(1, 28),
                     random.randint(8, 18), random.choice([0, 15, 30, 45]))
        return d.isoformat()
    if qt == QuestionType.LOCATION:
        return {
            "lat": round(random.uniform(19.1, 19.8), 6),
            "lng": round(random.uniform(-99.2, -99.0), 6),
            "accuracy": random.randint(3, 20),
        }
    if qt == QuestionType.INE_OCR:
        return {"nombre": random.choice(NAMES), "curp": "GAJJ800101HMCRMN09"}
    if qt == QuestionType.PHOTO:
        return "https://example.com/photo_placeholder.jpg"
    if qt == QuestionType.SIGNATURE:
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    return "N/A"


# ── 4. Seed responses spread over 30 days ─────────────────────────────────
# how many responses per survey
SURVEY_COUNTS = {6: 18, 7: 24, 8: 12, 9: 9, 10: 15}

USER_ID = 3  # brigadista
now = datetime.now(tz=timezone.utc)
seeded = 0

for v in versions:
    count = SURVEY_COUNTS.get(v.survey_id, 5)
    qs = version_questions[v.id]
    if not qs:
        print(f"  ⚠️  No questions for version {v.id}, skipping")
        continue

    for i in range(count):
        days_ago = random.randint(0, 29)
        hours_offset = random.randint(0, 23)
        completed_at = now - timedelta(days=days_ago, hours=hours_offset)
        started_at = completed_at - timedelta(minutes=random.randint(5, 25))

        response = SurveyResponse(
            user_id=USER_ID,
            version_id=v.id,
            client_id=str(uuid.uuid4()),
            completed_at=completed_at,
            started_at=started_at,
            location={
                "lat": round(random.uniform(19.1, 19.8), 6),
                "lng": round(random.uniform(-99.2, -99.0), 6),
            },
            device_info={"platform": "android", "model": "Samsung Galaxy A32"},
        )
        db.add(response)
        db.flush()

        for q in qs:
            db.add(QuestionAnswer(
                response_id=response.id,
                question_id=q.id,
                answer_value=fake_answer(q),
                answered_at=completed_at,
            ))

        seeded += 1

db.commit()
print(f"\n✅ Seeded {seeded} responses across {len(SURVEY_COUNTS)} surveys")
db.close()
