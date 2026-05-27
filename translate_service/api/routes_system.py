from fastapi import APIRouter, Request

from translate_service.api.app import get_service
from translate_service.languages import list_languages

router = APIRouter()


@router.get("/languages")
async def languages():
    return {"languages": list_languages()}


@router.get("/health")
async def health(request: Request):
    return await get_service(request).health()
