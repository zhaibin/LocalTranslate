from fastapi import APIRouter, Request
from pydantic import BaseModel

from translate_service.api.app import get_service

router = APIRouter()


class TranslateRequest(BaseModel):
    text: str
    source_lang: str | None = None
    target_lang: str | None = None


@router.post("/translate")
async def translate(request: Request, body: TranslateRequest):
    service = get_service(request)
    return await service.translate(
        text=body.text,
        source_lang=body.source_lang,
        target_lang=body.target_lang,
    )
