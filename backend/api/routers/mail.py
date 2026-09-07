from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from backend.api.auth import get_company_id
from backend.api.rate_limit import limiter

router = APIRouter()


class MailSendRequest(BaseModel):
    report_id: UUID
    to_email: str


@router.post("/mail/send")
@limiter.limit("10/hour")
async def mail_send(
    request: Request,
    body: MailSendRequest,
    company_id: str = Depends(get_company_id),
):
    # Day 5 will wire Resend. Scaffold only.
    return {"status": "scaffolded", "message": "Day 5 will wire Resend"}
