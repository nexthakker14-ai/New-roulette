
import os
import re
import io
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import pytesseract
from pytesseract import Output

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
    version="1.2.0"
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

    # Перевіряємо координати області OCR
    if (
        x < 0 or y < 0 or w <= 0 or h <= 0
        or x >= 1 or y >= 1
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid OCR coordinates"
        )

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
            detail="Empty OCR area"
        )

    # Збільшуємо область у 4 рази
    crop = crop.resize(
        (
            crop.width * 4,
            crop.height * 4
        ),
        Image.Resampling.LANCZOS
    )

    # Покращуємо контрастність і різкість
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

    # Шукаємо окремі текстові елементи,
    # а не зчитуємо всю смужку одним рядком
    config = (
        "--oem 3 --psm 11 "
        "-c tessedit_char_whitelist=0123456789"
    )

    data = pytesseract.image_to_data(
        crop,
        config=config,
        output_type=Output.DICT
    )

    detected_items = []
    candidate_numbers = []
    rejected_tokens = []

    for i, raw_text in enumerate(data["text"]):
        token = raw_text.strip()

        if not token:
            continue

        try:
            confidence = float(data["conf"][i])
        except (ValueError, TypeError):
            confidence = -1

        item = {
            "text": token,
            "confidence": round(confidence, 1),
            "x": int(data["left"][i]),
            "y": int(data["top"][i]),
            "width": int(data["width"][i]),
            "height": int(data["height"][i])
        }

        # Приймаємо тільки окреме число з 1 або 2 цифр
        if not re.fullmatch(r"\d{1,2}", token):
            rejected_tokens.append(item)
            continue

        number = int(token)

        # Перевіряємо діапазон рулетки та впевненість OCR
        if number < 0 or number > 36:
            rejected_tokens.append(item)
            continue

        if confidence < 30:
            rejected_tokens.append(item)
            continue

        detected_items.append(item)
        candidate_numbers.append(number)

    # Сортуємо знайдені числа зліва направо
    detected_items.sort(key=lambda item: item["x"])
    candidate_numbers = [
        int(item["text"])
        for item in detected_items
    ]

    recognized_text = " ".join(
        item["text"]
        for item in detected_items
    )

    return {
        "recognized_text": recognized_text,
        "candidate_numbers": candidate_numbers,
        "detected_items": detected_items,
        "rejected_tokens": rejected_tokens,
        "stored": False,
        "note": (
            "Числа не записані в базу. "
            "Перевірте їх вручну. "
            "Сумнівні фрагменти наведені окремо "
            "у rejected_tokens."
        )
    }
