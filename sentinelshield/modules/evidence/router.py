"""API Router for forensic evidence packages and incident ranking."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from modules.evidence.vault import evidence_vault_service

router = APIRouter(tags=["evidence"])


@router.get("/api/evidence")
def api_evidence():
    return {"packs": evidence_vault_service.get_evidence_packs()}


@router.post("/api/evidence/{camera_id}")
def make_evidence(camera_id: str):
    res = evidence_vault_service.seal_evidence_pack(camera_id)
    if not res:
        return JSONResponse({"error": "no camera"}, 404)
    return res


@router.get("/api/rank-evidence")
def rank_evidence():
    return {"ranked": evidence_vault_service.rank_evidence()}
