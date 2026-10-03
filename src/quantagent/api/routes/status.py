from fastapi import APIRouter, HTTPException

from ...core.config import settings
from ...agent.tools import get_status, get_recent_runs
from ...risk import killswitch

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/status")
def status_endpoint():
    cfg = settings()
    result = get_status(cfg["default_account"])
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/runs")
def runs_endpoint(limit: int = 7):
    cfg = settings()
    return get_recent_runs(cfg["default_account"], limit=limit)


@router.get("/killswitch")
def killswitch_endpoint():
    return {"tripped": killswitch.is_tripped(), "reason": killswitch.reason()}
