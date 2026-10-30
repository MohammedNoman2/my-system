import io
import logging
import re
from datetime import date, datetime
from typing import Optional
from PIL import Image
import pytesseract
from app.schemas.ocr import OcrIdResponse, OcrPassportResponse

logger = logging.getLogger("arp.ocr")

NATIONALITY_MAP = {
    "YEM": "يمني",
    "SAU": "سعودي",
    "EGY": "مصري",
    "JOR": "أردني",
    "ARE": "إماراتي",
    "OMN": "عماني",
    "KWT": "كويتي",
    "QAT": "قطري",
    "BHR": "بحريني",
    "SDN": "سوداني",
    "SYR": "سوري",
    "IRQ": "عراقي",
}

YEMEN_CITIES = [
    "صنعاء", "عدن", "تعز", "إب", "اب", "ذمار", "الحديدة", "حضرموت",
    "المكلا", "سيئون", "مأرب", "مارب", "البيضاء", "حجة", "صعدة",
    "عمران", "الضالع", "لحج", "أبين", "ابين", "شبوة", "المهرة", "المحويت", "ريمة",
    "SANAA", "ADEN", "TAIZ", "IBB", "DHAMAR", "HODEIDAH", "HADRAMAWT", "MARIB",
]


def _parse_date_from_text(raw_text: str) -> Optional[date]:
    # 1. Try YYYY-MM-DD or YYYY/MM/DD
    m1 = re.search(r"\b(19\d{2}|20\d{2})[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])\b", raw_text)
    if m1:
        try:
            return date(int(m1.group(1)), int(m1.group(2)), int(m1.group(3)))
        except ValueError:
            pass

    # 2. Try DD/MM/YYYY or DD-MM-YYYY
    m2 = re.search(r"\b(0[1-9]|[12]\d|3[01])[-/.](0[1-9]|1[0-2])[-/.](19\d{2}|20\d{2})\b", raw_text)
    if m2:
        try:
            return date(int(m2.group(3)), int(m2.group(2)), int(m2.group(1)))
        except ValueError:
            pass

    return None


def _parse_mrz(raw_text: str) -> dict:
    """Extracts passport number, full name, nationality, and birth date from ICAO MRZ lines if present."""
    result = {}
    lines = [re.sub(r"\s+", "", line.upper()) for line in raw_text.splitlines() if "<" in line]
    for idx, line in enumerate(lines):
        if line.startswith("P<") and len(line) >= 30:
            nat_code = line[2:5].replace("<", "")
            if nat_code in NATIONALITY_MAP:
                result["nationality"] = NATIONALITY_MAP[nat_code]
            name_part = line[5:].split("<<")
            surname = name_part[0].replace("<", " ").strip() if name_part else ""
            given = name_part[1].replace("<", " ").strip() if len(name_part) > 1 else ""
            full_name = f"{given} {surname}".strip()
            if len(full_name) >= 4:
                result["passenger_name"] = full_name

            if idx + 1 < len(lines):
                line2 = lines[idx + 1]
                if len(line2) >= 20:
                    p_num = line2[:9].replace("<", "").strip()
                    if re.match(r"^[A-Z0-9]{7,9}$", p_num):
                        result["passport_number"] = p_num
                    dob_raw = line2[13:19]
                    if dob_raw.isdigit():
                        yy, mm, dd = int(dob_raw[:2]), int(dob_raw[2:4]), int(dob_raw[4:6])
                        curr_yy = datetime.now().year % 100
                        year = 1900 + yy if yy > curr_yy else 2000 + yy
                        try:
                            result["birth_date"] = date(year, mm, dd)
                        except ValueError:
                            pass
    return result


def _extract_city(raw_text: str) -> Optional[str]:
    upper_text = raw_text.upper()
    for city in YEMEN_CITIES:
        if city in raw_text or city in upper_text:
            return city
    return None


def _extract_arabic_name(raw_text: str) -> Optional[str]:
    for line in raw_text.splitlines():
        clean = line.strip()
        if any(lbl in clean for lbl in ["الاسم", "إسم", "حامل الجواز", "اسم المواطن"]):
            parts = re.split(r"[:\-]", clean, maxsplit=1)
            candidate = parts[1].strip() if len(parts) > 1 else clean
            arabic_words = re.findall(r"[\u0600-\u06FF]{2,}", candidate)
            if len(arabic_words) >= 3:
                return " ".join(arabic_words[:5])
    for line in raw_text.splitlines():
        arabic_words = re.findall(r"[\u0600-\u06FF]{2,}", line)
        if 3 <= len(arabic_words) <= 5:
            joined = " ".join(arabic_words)
            if not any(skip in joined for skip in ["الجمهورية", "اليمنية", "وزارة", "مصلحة", "جواز", "بطاقة"]):
                return joined
    return None


def extract_passport_data(image_bytes: bytes) -> OcrPassportResponse:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        data = pytesseract.image_to_data(image, lang="ara+eng", output_type=pytesseract.Output.DICT)
        full_text = pytesseract.image_to_string(image, lang="ara+eng")
        logger.info("pytesseract executed successfully on passport image")

        passport_number = None
        for i, word in enumerate(data["text"]):
            try:
                conf = int(float(data["conf"][i]))
            except (ValueError, TypeError):
                conf = 0
            word_clean = word.strip().upper()
            if conf >= 75 and not passport_number and re.match(r"^[A-Z0-9]{8,10}$", word_clean):
                if any(ch.isdigit() for ch in word_clean):
                    passport_number = word_clean

        combined_text = f"{full_text}\n" + " ".join(data["text"])
        mrz_data = _parse_mrz(combined_text)

        passport_number = passport_number or mrz_data.get("passport_number")
        passenger_name = _extract_arabic_name(combined_text) or mrz_data.get("passenger_name")
        birth_date = mrz_data.get("birth_date") or _parse_date_from_text(combined_text)
        birth_place = _extract_city(combined_text)
        nationality = mrz_data.get("nationality") or ("يمني" if "اليمنية" in combined_text or "YEMEN" in combined_text.upper() else None)

        return OcrPassportResponse(
            passenger_name=passenger_name,
            passport_number=passport_number,
            birth_date=birth_date,
            birth_place=birth_place,
            nationality=nationality,
            raw_text=combined_text.strip()[:300],
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
        full_text = pytesseract.image_to_string(image, lang="ara+eng")
        logger.info("pytesseract executed successfully on ID image")

        id_number = None
        for i, word in enumerate(data["text"]):
            try:
                conf = int(float(data["conf"][i]))
            except (ValueError, TypeError):
                conf = 0
            word_clean = word.strip()
            if conf >= 75 and not id_number and re.match(r"^\d{10,12}$", word_clean):
                id_number = word_clean

        combined_text = f"{full_text}\n" + " ".join(data["text"])
        if not id_number:
            m_id = re.search(r"\b\d{11}\b|\b\d{10,12}\b", combined_text)
            if m_id:
                id_number = m_id.group(0)

        passenger_name = _extract_arabic_name(combined_text)
        birth_date = _parse_date_from_text(combined_text)
        birth_place = _extract_city(combined_text)

        return OcrIdResponse(
            passenger_name=passenger_name,
            id_number=id_number,
            birth_date=birth_date,
            birth_place=birth_place,
            raw_text=combined_text.strip()[:300],
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
