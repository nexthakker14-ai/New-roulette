
import os
import re
import io
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from PIL import (
    Image,
    ImageOps,
    ImageEnhance,
    ImageFilter
)
import pytesseract

from .storage import (
    init_db,
    add_result,
    get_results,
    get_all_numbers
)
from .strategy import analyze
from .telegram import send_message


app = FastAPI(
    title="777UA Auto Lightning Roulette",
    version="1.1.0"
)


@app.on_event("startup")
def startup():
    init_db()


def check_secret(provided: Optional[str]):
    expected = os.getenv("API_SECRET", "").strip()

    if expected and provided != expected:
        raise HTTPException(
            status_code=401,
            detail="Invalid API secret"
        )


class ResultInput(BaseModel):
    number: int = Field(ge=0, le=36)


@app.get("/")
def root():
    return {
        "service": "777UA Auto Lightning Roulette",
        "status": "running",
        "purpose": "roulette history analysis and Telegram alerts",
        "bet_automation": False
    }


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/results")
def results(limit: int = 30):
    limit = max(1, min(limit, 500))

    return {
        "results": get_results(limit)
    }


@app.get("/api/analysis")
def analysis():
    return {
        "alerts": analyze(get_all_numbers(500))
    }


@app.post("/api/results")
def create_result(
    payload: ResultInput,
    x_api_secret: Optional[str] = Header(default=None)
):
    check_secret(x_api_secret)

    saved = add_result(payload.number)
    alerts = analyze(get_all_numbers(500))

    if alerts:
        lines = [
            "🎰 Lightning Roulette — зафіксовано серію"
        ]

        lines += [
            f'{a["category"]}: {a["value"]} — '
            f'{a["streak"]} поспіль'
            for a in alerts
        ]

        lines.append(
            "Це статистичне спостереження, не прогноз."
        )

        try:
            send_message("\n".join(lines))
        except Exception:
            pass

    return {
        "saved": saved,
        "alerts": alerts
    }


@app.post("/api/screenshot")
async def screenshot(
    file: UploadFile = File(...),
    x_api_secret: Optional[str] = Header(default=None)
):
    check_secret(x_api_secret)

    raw = await file.read()

    try:
        img = Image.open(
            io.BytesIO(raw)
        ).convert("RGB")

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not read image"
        )

    width, height = img.size

    x = float(os.getenv("OCR_X", "0.52"))
    y = float(os.getenv("OCR_Y", "0.16"))
    w = float(os.getenv("OCR_W", "0.48"))
    h = float(os.getenv("OCR_H", "0.04"))

    # Вирізаємо смужку результатів
    crop = img.crop((
        int(width * x),
        int(height * y),
        int(width * min(1, x + w)),
        int(height * min(1, y + h))
    ))

    if crop.width == 0 or crop.height == 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid OCR crop coordinates"
        )

    # Збільшуємо зображення у 4 рази
    crop = crop.resize(
        (
            crop.width * 4,
            crop.height * 4
        ),
        Image.Resampling.LANCZOS
    )

    # Покращуємо якість зображення
    crop = ImageOps.grayscale(crop)
    crop = ImageOps.autocontrast(crop)

    crop = ImageEnhance.Contrast(
        crop
    ).enhance(2.0)

    crop = ImageEnhance.Sharpness(
        crop
    ).enhance(2.0)

    crop = crop.filter(
        ImageFilter.SHARPEN
    )

    # Розпізнаємо тільки цифри
    recognized = pytesseract.image_to_string(
        crop,
        config=(
            "--oem 3 --psm 7 "
            "-c tessedit_char_whitelist=0123456789"
        )
    )

    # Витягуємо числа від 0 до 36
    candidates = [
        int(value)
        for value in re.findall(
            r"\d{1,2}",
            recognized
        )
        if 0 <= int(value) <= 36
    ]

    return {
        "recognized_text": recognized.strip(),
        "candidate_numbers": candidates,
        "stored": False,
        "note": (
            "Перевірте числа вручну перед додаванням "
            "через POST /api/results."
        )
    }
