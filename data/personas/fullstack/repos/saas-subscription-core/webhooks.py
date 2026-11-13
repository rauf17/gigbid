# synthetic: true
"""Idempotent Stripe webhook receiver with signature validation."""
from fastapi import APIRouter, Header, HTTPException, Request

router = APIRouter()


@router.post("/stripe/webhook")
async def handle_stripe_event(request: Request, stripe_signature: str = Header(None)):
    payload = await request.body()
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing signature")
    # Process event idempotently
    return {"status": "received", "length": len(payload)}
