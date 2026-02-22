"""
OCR validation utilities — server-side proxy for RENAPO CURP validation.

Why a backend proxy instead of direct frontend call:
  - RENAPO's API may require authentication tokens in production.
  - Avoids CORS issues when the mobile app calls an external government API.
  - Centralises rate-limiting and caching (avoid hammering RENAPO from every device).
  - Credentials / API keys stay server-side.

RENAPO endpoint:
  GET https://api.renapo.gob.mx/sumar/ConsultaCURP/{CURP}

  Returns (non-authenticated, public tier):
    curp, nombre, apellido1, apellido2, sexo, fechaNac,
    claveEntidadNac, nombreEntidadNac, statusCurp ("VIGE" | "RCN" | "BAJA")

  Note: RENAPO may require a signed token from SATWS / e.firma for production
  usage. The current implementation works with the public unauthenticated tier
  that returns basic validation ("curp_valida" flag only) for many CURPs.
"""

import re
import httpx
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel
from typing import Optional


router = APIRouter(prefix="/ocr", tags=["ocr"])

# ── Regex de validación local ─────────────────────────────────────────────────
CURP_STRICT_RE = re.compile(
    r"^[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z\d]{2}$"
)

RENAPO_BASE = "https://api.renapo.gob.mx/sumar/ConsultaCURP"


# ── Schemas ───────────────────────────────────────────────────────────────────

class CurpValidationResult(BaseModel):
    curp: str
    valid_format: bool          # Pasa el regex estricto local
    renapo_status: Optional[str] = None   # "VIGE" | "RCN" | "BAJA" | None
    nombre: Optional[str] = None
    apellido1: Optional[str] = None
    apellido2: Optional[str] = None
    sexo: Optional[str] = None
    fecha_nac: Optional[str] = None
    entidad_nac: Optional[str] = None
    renapo_reachable: bool = False


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/validate-curp/{curp}",
    response_model=CurpValidationResult,
    summary="Validar CURP contra RENAPO",
    description=(
        "Primero valida el formato del CURP con regex estricto local. "
        "Luego intenta consultar RENAPO para obtener estado (VIGE/RCN/BAJA) "
        "y datos personales asociados. Si RENAPO no responde, devuelve "
        "renapo_reachable=false y solo el resultado del regex local."
    ),
)
async def validate_curp(
    curp: str = Path(
        ...,
        min_length=18,
        max_length=18,
        description="CURP de 18 caracteres",
        example="GOMC900205HMCRRR09",
    ),
) -> CurpValidationResult:
    curp = curp.upper().strip()

    # 1. Validación local (sin red)
    valid_format = bool(CURP_STRICT_RE.match(curp))

    result = CurpValidationResult(
        curp=curp,
        valid_format=valid_format,
    )

    if not valid_format:
        # No tiene sentido consultar RENAPO con un CURP mal formado
        return result

    # 2. Consultar RENAPO (timeout corto — el servicio es inestable)
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(f"{RENAPO_BASE}/{curp}")

        if resp.status_code == 200:
            data = resp.json()
            result.renapo_reachable = True
            result.renapo_status = data.get("statusCurp") or data.get("curp_valida")
            result.nombre     = data.get("nombre")
            result.apellido1  = data.get("apellido1")
            result.apellido2  = data.get("apellido2")
            result.sexo       = data.get("sexo")
            result.fecha_nac  = data.get("fechaNac")
            result.entidad_nac = data.get("nombreEntidadNac")
        elif resp.status_code == 404:
            # RENAPO devuelve 404 cuando el CURP no está en el padrón
            result.renapo_reachable = True
            result.renapo_status = "NO_ENCONTRADO"
        else:
            # Cualquier otro error (5xx, 429 rate limit, etc.)
            result.renapo_reachable = False

    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPError):
        # RENAPO no alcanzable — devolver solo validación local
        result.renapo_reachable = False

    return result
