from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from backend.app.schemas.week1 import RetrieveRequest, RetrieveResponse

router = APIRouter(prefix="/week1", tags=["retrieval"])


@router.post("/retrieve", response_model=RetrieveResponse)
async def retrieve(payload: RetrieveRequest):
    from qubettera.rag.retrieve import retrieve as search
    try:
        results = await run_in_threadpool(search, payload.query, top_k=payload.top_k)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return RetrieveResponse(query=payload.query, top_k=payload.top_k, results=results)
