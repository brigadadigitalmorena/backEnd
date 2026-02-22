"""In-memory operational metrics for mobile API observability.

This module keeps lightweight runtime counters to expose:
- p95 latency per /mobile endpoint
- duplicate rate in batch sync
- low OCR-confidence rate in batch sync

Note: in-memory metrics reset on process restart. This is intentional as an
MVP until Prometheus/OpenTelemetry is wired.
"""

from collections import defaultdict, deque
from statistics import median
from threading import Lock
from typing import Dict, Deque


_LOCK = Lock()

_MOBILE_LATENCY_MS: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=400))
_BATCH_TOTAL = 0
_BATCH_DUPLICATES = 0
_BATCH_LOW_OCR = 0


def observe_mobile_latency(endpoint: str, elapsed_ms: float) -> None:
    with _LOCK:
        _MOBILE_LATENCY_MS[endpoint].append(max(elapsed_ms, 0.0))


def observe_batch_metrics(total: int, duplicates: int, low_ocr: int) -> None:
    global _BATCH_TOTAL, _BATCH_DUPLICATES, _BATCH_LOW_OCR
    with _LOCK:
        _BATCH_TOTAL += max(total, 0)
        _BATCH_DUPLICATES += max(duplicates, 0)
        _BATCH_LOW_OCR += max(low_ocr, 0)


def _p95(samples: list[float]) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    idx = max(int(0.95 * len(ordered)) - 1, 0)
    return round(ordered[idx], 2)


def get_mobile_ops_metrics() -> dict:
    with _LOCK:
        latency_snapshot = {
            endpoint: {
                "count": len(samples),
                "p95_ms": _p95(list(samples)),
                "median_ms": round(median(samples), 2) if samples else 0.0,
            }
            for endpoint, samples in _MOBILE_LATENCY_MS.items()
        }

        duplicate_rate = (
            round((_BATCH_DUPLICATES / _BATCH_TOTAL) * 100, 2)
            if _BATCH_TOTAL > 0
            else 0.0
        )
        low_ocr_rate = (
            round((_BATCH_LOW_OCR / _BATCH_TOTAL) * 100, 2)
            if _BATCH_TOTAL > 0
            else 0.0
        )

        return {
            "mobile_latency": latency_snapshot,
            "batch_total": _BATCH_TOTAL,
            "batch_duplicates": _BATCH_DUPLICATES,
            "batch_low_ocr": _BATCH_LOW_OCR,
            "duplicate_rate_pct": duplicate_rate,
            "ocr_low_confidence_rate_pct": low_ocr_rate,
        }
