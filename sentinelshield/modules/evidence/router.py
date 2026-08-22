"""API Router for forensic evidence packages and incident ranking."""
from __future__ import annotations

try:
    from fastapi import APIRouter, Request, Body
    from fastapi.responses import JSONResponse, Response
except ImportError:
    class _MockAPIRouter:
        def __init__(self, *args, **kwargs): pass
        def post(self, *args, **kwargs): return lambda f: f
        def get(self, *args, **kwargs): return lambda f: f
        def delete(self, *args, **kwargs): return lambda f: f
    APIRouter = _MockAPIRouter  # type: ignore
    JSONResponse = dict  # type: ignore
    Response = object  # type: ignore
    Request = Any  # type: ignore
    Body = lambda default=None, **kw: default  # type: ignore

from modules.evidence.vault import evidence_vault_service

router = APIRouter(tags=["evidence"])


@router.get("/api/evidence")
def api_evidence():
    return {"packs": evidence_vault_service.get_evidence_packs()}


@router.post("/api/evidence/{camera_id}")
async def make_evidence(camera_id: str):
    res = await evidence_vault_service.seal_evidence_pack_async(camera_id)
    if not res:
        return JSONResponse({"error": "no camera"}, 404)
    return res


@router.get("/api/evidence/{camera_id}/pdf")
def get_evidence_pdf(camera_id: str):
    """Download Section 65B/BSA 2023 compliant courtroom evidence certificate PDF."""
    pdf_bytes = evidence_vault_service.get_evidence_pdf_brief(camera_id)
    if not pdf_bytes:
        return JSONResponse({"error": "Failed to generate courtroom evidence brief"}, 404)
    try:
        from fastapi.responses import Response
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="evidence_{camera_id}.pdf"'},
        )
    except Exception:
        return {"ok": True, "size": len(pdf_bytes)}


@router.post("/api/evidence/verify")
def verify_evidence(data: dict = Body(...)):
    """Forensically verify provided evidence data manifest against certificate hash."""
    payload = data.get("payload") or data
    provided_hash = data.get("sha256") or data.get("hash", "")
    valid, msg = evidence_vault_service.verify_evidence_integrity(payload, provided_hash)
    computed = evidence_vault_service.compute_canonical_evidence_hash(payload)
    return {
        "valid": valid,
        "message": msg,
        "provided_hash": provided_hash,
        "computed_hash": computed,
    }


@router.get("/api/rank-evidence")
def rank_evidence():
    return {"ranked": evidence_vault_service.rank_evidence()}
