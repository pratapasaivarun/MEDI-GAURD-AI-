"""Deferred PaddleOCR code path; out of scope for the academic prototype."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def get_paddle_ocr():
    """Create the legacy PaddleOCR engine if this optional path is revived."""
    from paddleocr import PaddleOCR
    language = os.getenv("OCR_LANG", "en")
    try:
        return PaddleOCR(lang=language, use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=True)
    except Exception:
        return PaddleOCR(use_angle_cls=True, lang=language)


def extract_paddle_text(image_path: str | Path) -> tuple[str, float]:
    """Legacy PaddleOCR extraction retained without integration into the prototype."""
    ocr = get_paddle_ocr()
    result = ocr.predict(str(image_path)) if hasattr(ocr, "predict") else ocr.ocr(str(image_path))
    lines: list[str] = []
    scores: list[float] = []
    for block in result or []:
        if isinstance(block, dict):
            texts = block.get("rec_texts") or block.get("text") or []
            values = block.get("rec_scores") or block.get("scores") or []
            for index, text in enumerate(texts):
                if str(text).strip():
                    lines.append(str(text).strip())
                    scores.append(float(values[index]) if index < len(values) else 0.0)
        else:
            for item in block or []:
                if isinstance(item, (list, tuple)) and len(item) >= 2 and isinstance(item[1], (list, tuple)):
                    lines.append(str(item[1][0]).strip())
                    scores.append(float(item[1][1]) if len(item[1]) > 1 else 0.0)
    return "\n".join(line for line in lines if line), (sum(scores) / len(scores) if scores else 0.0)
