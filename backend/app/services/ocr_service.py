import io
import logging
import re
from datetime import date
from typing import Optional
from PIL import Image
import pytesseract
from app.schemas.ocr import OcrIdResponse, OcrPassportResponse

logger = logging.getLogger("arp.ocr")


def extract_passport_data(image_bytes: bytes) -> OcrPassportResponse:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        # Get detailed data with confidence scores
        data = pytesseract.image_to_data(image, lang="ara+eng", output_type=pytesseract.Output.DICT)
        logger.info("pytesseract executed successfully on passport image")

        passport_number = None
        
        # Check words and their confidences
        for i, word in enumerate(data['text']):
            conf = int(data['conf'][i])
            word = word.strip()
            
            # Require 90% confidence
            if conf >= 90:
                if not passport_number and re.match(r"^[A-Z0-9]{8,10}$", word):
                    passport_number = word

        return OcrPassportResponse(
            passenger_name=None,
            passport_number=passport_number,
            birth_date=None,
            birth_place=None,
            nationality=None,
            raw_text=" ".join(data['text'])[:300],
            mocked=False,
        )
    except Exception as e:
        logger.warning(f"pytesseract extraction failed ({e}); returning nulls.")
        return OcrPassportResponse(
            passenger_name=None,
            passport_number=None,
            birth_date=None,
            birth_place=None,
            nationality=None,
            raw_text="",
            mocked=False,
        )


def extract_id_data(image_bytes: bytes) -> OcrIdResponse:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        data = pytesseract.image_to_data(image, lang="ara+eng", output_type=pytesseract.Output.DICT)
        logger.info("pytesseract executed successfully on ID image")

        id_number = None
        
        for i, word in enumerate(data['text']):
            conf = int(data['conf'][i])
            word = word.strip()
            
            if conf >= 90:
                if not id_number and re.match(r"^\d{10,12}$", word):
                    id_number = word

        return OcrIdResponse(
            passenger_name=None,
            id_number=id_number,
            birth_date=None,
            birth_place=None,
            raw_text=" ".join(data['text'])[:300],
            mocked=False,
        )
    except Exception as e:
        logger.warning(f"pytesseract extraction failed ({e}); returning nulls.")
        return OcrIdResponse(
            passenger_name=None,
            id_number=None,
            birth_date=None,
            birth_place=None,
            raw_text="",
            mocked=False,
        )
