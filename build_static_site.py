from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from crawler import get_next_hanwha_game

ROOT = Path(__file__).parent
TEMPLATE_PATH = ROOT / "index.template.html"
OUTPUT_PATH = ROOT / "index.html"
DATA_OUTPUT_PATH = ROOT / "game-data.json"
KST = ZoneInfo("Asia/Seoul")


def _load_previous_game_info() -> dict:
    if not DATA_OUTPUT_PATH.exists():
        return {}
    try:
        payload = json.loads(DATA_OUTPUT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    game_info = payload.get("game_info")
    return game_info if isinstance(game_info, dict) else {}


def _merge_media_fallbacks(current_info: dict, previous_info: dict) -> dict:
    if not current_info:
        return current_info
    merged = dict(current_info)
    current_tv = (merged.get("eagles_tv") or {}) if isinstance(merged.get("eagles_tv"), dict) else {}
    prev_tv = (previous_info.get("eagles_tv") or {}) if isinstance(previous_info.get("eagles_tv"), dict) else {}
    if current_tv or prev_tv:
        safe_tv = dict(current_tv)
        for key in ("highlight", "oiyu"):
            current_item = safe_tv.get(key) if isinstance(safe_tv.get(key), dict) else {}
            prev_item = prev_tv.get(key) if isinstance(prev_tv.get(key), dict) else {}
            if not (current_item or {}).get("url") and (prev_item or {}).get("url"):
                safe_tv[key] = prev_item
        merged["eagles_tv"] = safe_tv
    return merged


def build() -> None:
    previous_game_info = _load_previous_game_info()
    game_info = get_next_hanwha_game() or {}
    if game_info:
        game_info = _merge_media_fallbacks(game_info, previous_game_info)
    has_game = bool(game_info)
    updated_at = datetime.now(KST).replace(microsecond=0).isoformat()

    if has_game:
        og_title = f"{game_info['game_date']} {game_info['matchup']}"
        og_description = f"{game_info['away_team']} : {game_info['away_starter']} / {game_info['home_team']} : {game_info['home_starter']}"
    else:
        og_title = "한화 이글스 다음 경기 정보"
        og_description = "현재 한화 이글스 다음 경기 정보를 찾지 못했습니다."

    html_template = TEMPLATE_PATH.read_text(encoding="utf-8")
    rendered = (
        html_template.replace("__OG_TITLE__", og_title)
        .replace("__OG_DESCRIPTION__", og_description)
        .replace(
            "__GAME_JSON__",
            json.dumps(game_info if has_game else None, ensure_ascii=False),
        )
        .replace(
            "__UPDATED_AT_VALUE__",
            updated_at,
        )
    )
    OUTPUT_PATH.write_text(rendered, encoding="utf-8")
    DATA_OUTPUT_PATH.write_text(
        json.dumps(
            {"ok": True, "game_info": game_info if has_game else None, "updated_at": updated_at},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    build()
