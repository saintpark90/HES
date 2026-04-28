from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import holidays

ROOT = Path(__file__).parent
OUTPUT_PATH = ROOT / "holiday-data.json"
KST = ZoneInfo("Asia/Seoul")

# 2026년부터 5/1 노동절을 공휴일로 반영
FIXED_HOLIDAYS = {
    "01-01": "신정",
    "03-01": "삼일절",
    "05-01": "노동절",
    "05-05": "어린이날",
    "06-06": "현충일",
    "07-17": "제헌절",
    "08-15": "광복절",
    "10-03": "개천절",
    "10-09": "한글날",
    "12-25": "성탄절",
}


def _normalize_name(name: str) -> str:
    text = str(name or "").strip()
    replacements = {
        "New Year's Day": "신정",
        "Labor Day": "노동절",
        "Children's Day": "어린이날",
        "Memorial Day": "현충일",
        "Constitution Day": "제헌절",
        "Liberation Day": "광복절",
        "National Foundation Day": "개천절",
        "Hangeul Day": "한글날",
        "Christmas Day": "성탄절",
    }
    normalized = replacements.get(text, text)
    normalized = normalized.replace("대체 휴일", "대체공휴일")
    if ";" in normalized:
        parts = [p.strip() for p in normalized.split(";") if p.strip()]
        for preferred in ("설날", "추석", "부처님오신날"):
            for p in parts:
                if preferred in p:
                    return p
        return parts[-1] if parts else normalized
    return normalized


def _is_specific_holiday(name: str, mmdd: str) -> bool:
    if "대체" in name:
        return True
    if any(token in name for token in ("설날", "추석", "부처님")):
        return True
    return False


def build_holiday_data(start_year: int | None = None, years_ahead: int = 5) -> dict:
    base_year = start_year or datetime.now(KST).year
    last_year = base_year + years_ahead
    kr_holidays = holidays.country_holidays("KR", years=range(base_year, last_year + 1), language="ko")

    specific: dict[str, str] = {}
    for d, holiday_name in sorted(kr_holidays.items()):
        ymd = d.isoformat()
        mmdd = ymd[5:]
        name = _normalize_name(str(holiday_name))
        if _is_specific_holiday(name, mmdd):
            specific[ymd] = name

    return {
        "meta": {
            "generated_at": datetime.now(KST).replace(microsecond=0).isoformat(),
            "start_year": base_year,
            "end_year": last_year,
        },
        "fixed": FIXED_HOLIDAYS,
        "specific": specific,
    }


def build(start_year: int | None = None, years_ahead: int = 5) -> None:
    payload = build_holiday_data(start_year=start_year, years_ahead=years_ahead)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    build()
