from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.ocr import OcrIdResponse, OcrPassportResponse
from app.services.ocr_service import extract_id_data, extract_passport_data

router = APIRouter(prefix="/ocr", tags=["OCR"])


@router.post("/extract-passport", response_model=OcrPassportResponse)
async def ocr_passport(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="الملف المرفوع يجب أن يكون صورة")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="حجم الصورة يجب ألا يتجاوز 10 ميجابايت")

    result = extract_passport_data(contents)
    return result


@router.post("/extract-id", response_model=OcrIdResponse)
async def ocr_id(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="الملف المرفوع يجب أن يكون صورة")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="حجم الصورة يجب ألا يتجاوز 10 ميجابايت")

    result = extract_id_data(contents)
    return result
