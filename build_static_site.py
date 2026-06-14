from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from crawler import ensure_game_starters_from_namu, get_next_hanwha_game
from generate_holiday_data import build as build_holiday_data

ROOT = Path(__file__).parent
TEMPLATE_PATH = ROOT / "index.template.html"
OUTPUT_PATH = ROOT / "index.html"
DATA_OUTPUT_PATH = ROOT / "game-data.json"
REGISTER_MOVES_CACHE_PATH = ROOT / "register-moves-cache.json"
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


def _is_missing_starter_name(name: str) -> bool:
    token = (name or "").strip()
    return token in {"", "-", "미정", "TBD", "예정"}


def _is_incomplete_starter_stats(stats: object) -> bool:
    """CI에서 상세 페이지 크롤 실패 시 {'war': '-'}만 남는 경우를 불완전으로 본다."""
    if not isinstance(stats, dict):
        return True
    core_keys = ("era", "wins", "losses", "games", "whip", "birth_date", "age")
    meaningful = [
        str(stats.get(key) or "").strip()
        for key in core_keys
        if str(stats.get(key) or "").strip() not in {"", "-"}
    ]
    return len(meaningful) < 2


def _merge_starter_stats_dict(current: object, previous: object) -> dict:
    if not isinstance(previous, dict):
        return dict(current) if isinstance(current, dict) else {}
    if not isinstance(current, dict):
        current = {}
    if _is_incomplete_starter_stats(current) and not _is_incomplete_starter_stats(previous):
        return dict(previous)
    merged = dict(current)
    for key, value in previous.items():
        cur = str(merged.get(key) or "").strip()
        if cur in {"", "-"} and str(value or "").strip() not in {"", "-"}:
            merged[key] = value
    return merged


def _merge_starter_fallbacks(current_info: dict, previous_info: dict) -> dict:
    if not current_info:
        return current_info
    merged = dict(current_info)
    if str(merged.get("game_id") or "") != str(previous_info.get("game_id") or ""):
        return merged

    if _is_missing_starter_name(str(merged.get("away_starter") or "")):
        prev_name = str(previous_info.get("away_starter") or "").strip()
        if not _is_missing_starter_name(prev_name):
            merged["away_starter"] = prev_name
    if _is_missing_starter_name(str(merged.get("home_starter") or "")):
        prev_name = str(previous_info.get("home_starter") or "").strip()
        if not _is_missing_starter_name(prev_name):
            merged["home_starter"] = prev_name
    if _is_missing_starter_name(str(merged.get("hanwha_starter") or "")):
        prev_name = str(previous_info.get("hanwha_starter") or "").strip()
        if not _is_missing_starter_name(prev_name):
            merged["hanwha_starter"] = prev_name

    for side in ("away", "home"):
        id_key = f"{side}_starter_id"
        img_key = f"{side}_starter_image"
        stats_key = f"{side}_starter_stats"

        if not str(merged.get(id_key) or "").strip() and str(previous_info.get(id_key) or "").strip():
            merged[id_key] = previous_info.get(id_key)
        if not str(merged.get(img_key) or "").strip() and str(previous_info.get(img_key) or "").strip():
            merged[img_key] = previous_info.get(img_key)

        cur_id = str(merged.get(id_key) or "").strip()
        prev_id = str(previous_info.get(id_key) or "").strip()
        same_pitcher = bool(cur_id and prev_id and cur_id == prev_id)
        same_name = (
            str(merged.get(f"{side}_starter") or "").strip()
            == str(previous_info.get(f"{side}_starter") or "").strip()
            and not _is_missing_starter_name(str(merged.get(f"{side}_starter") or ""))
        )
        if same_pitcher or same_name:
            merged[stats_key] = _merge_starter_stats_dict(
                merged.get(stats_key),
                previous_info.get(stats_key),
            )

    return merged


def _merge_register_moves_fallbacks(current_info: dict, previous_info: dict) -> dict:
    """당일 등록·말소 인원이 비어 있으면(변동 없음·파싱 실패 등) 직전 스냅샷을 유지한다."""
    if not current_info:
        return current_info
    merged = dict(current_info)
    cur = merged.get("register_moves")
    prev = previous_info.get("register_moves")
    if not isinstance(cur, dict):
        return merged
    reg = cur.get("registered") if isinstance(cur.get("registered"), list) else []
    dereg = cur.get("deregistered") if isinstance(cur.get("deregistered"), list) else []
    if reg or dereg:
        return merged
    if not isinstance(prev, dict):
        return merged
    prev_reg = prev.get("registered") if isinstance(prev.get("registered"), list) else []
    prev_dereg = prev.get("deregistered") if isinstance(prev.get("deregistered"), list) else []
    if not prev_reg and not prev_dereg:
        return merged
    merged["register_moves"] = {
        "date": str(prev.get("date") or cur.get("date") or ""),
        "registered": list(prev_reg),
        "deregistered": list(prev_dereg),
    }
    return merged


def _load_register_moves_cache() -> dict:
    if not REGISTER_MOVES_CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(REGISTER_MOVES_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _has_non_empty_register_moves(data: dict) -> bool:
    if not isinstance(data, dict):
        return False
    reg = data.get("registered") if isinstance(data.get("registered"), list) else []
    dereg = data.get("deregistered") if isinstance(data.get("deregistered"), list) else []
    return bool(reg or dereg)


def _merge_register_moves_cache_fallback(current_info: dict, cache_moves: dict) -> dict:
    if not current_info or not isinstance(cache_moves, dict):
        return current_info
    merged = dict(current_info)
    cur = merged.get("register_moves")
    if not isinstance(cur, dict):
        return merged
    if _has_non_empty_register_moves(cur):
        return merged
    if not _has_non_empty_register_moves(cache_moves):
        return merged
    merged["register_moves"] = {
        "date": str(cache_moves.get("date") or cur.get("date") or ""),
        "registered": list(cache_moves.get("registered") or []),
        "deregistered": list(cache_moves.get("deregistered") or []),
    }
    return merged


def _update_register_moves_cache_from_game_info(game_info: dict) -> None:
    if not game_info:
        return
    moves = game_info.get("register_moves")
    if not isinstance(moves, dict):
        return
    if not _has_non_empty_register_moves(moves):
        return
    payload = {
        "date": str(moves.get("date") or ""),
        "registered": list(moves.get("registered") or []),
        "deregistered": list(moves.get("deregistered") or []),
    }
    REGISTER_MOVES_CACHE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def _seed_register_moves_cache_from_previous(previous_game_info: dict) -> None:
    if REGISTER_MOVES_CACHE_PATH.exists():
        return
    if not isinstance(previous_game_info, dict):
        return
    moves = previous_game_info.get("register_moves")
    if not isinstance(moves, dict) or not _has_non_empty_register_moves(moves):
        return
    payload = {
        "date": str(moves.get("date") or ""),
        "registered": list(moves.get("registered") or []),
        "deregistered": list(moves.get("deregistered") or []),
    }
    REGISTER_MOVES_CACHE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def build() -> None:
    build_holiday_data()
    previous_game_info = _load_previous_game_info()
    _seed_register_moves_cache_from_previous(previous_game_info)
    register_moves_cache = _load_register_moves_cache()
    game_info = get_next_hanwha_game() or {}
    if game_info:
        game_info = ensure_game_starters_from_namu(game_info)
        game_info = _merge_media_fallbacks(game_info, previous_game_info)
        game_info = _merge_starter_fallbacks(game_info, previous_game_info)
        game_info = _merge_register_moves_fallbacks(game_info, previous_game_info)
        game_info = _merge_register_moves_cache_fallback(game_info, register_moves_cache)
        _update_register_moves_cache_from_game_info(game_info)
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
