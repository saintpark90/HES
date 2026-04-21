from __future__ import annotations

import json
import re
from datetime import date, timedelta
from typing import Any, Dict, Optional

import requests

KBO_GAME_LIST_URL = "https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList"
HANWHA_TEAM_ID = "HH"
SERIES_IDS = "0,1,3,4,5,6,7,9"
KBO_IMAGE_BASE = "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle"
PITCHER_DETAIL_URL = "https://www.koreabaseball.com/Record/Player/PitcherDetail/Basic.aspx"


def _fetch_games(target_date: date) -> list[Dict[str, Any]]:
    payload = {
        "leId": "1",
        "srId": SERIES_IDS,
        "date": target_date.strftime("%Y%m%d"),
    }
    response = requests.post(KBO_GAME_LIST_URL, data=payload, timeout=10)
    response.raise_for_status()
    body = json.loads(response.content.decode("utf-8-sig"))
    return body.get("game", [])


def _is_hanwha_game(game: Dict[str, Any]) -> bool:
    return game.get("AWAY_ID") == HANWHA_TEAM_ID or game.get("HOME_ID") == HANWHA_TEAM_ID


def _extract_hanwha_starter(game: Dict[str, Any]) -> str:
    if game.get("AWAY_ID") == HANWHA_TEAM_ID:
        return (game.get("T_PIT_P_NM") or "").strip()
    return (game.get("B_PIT_P_NM") or "").strip()


def _face_image_url(season_id: str, player_id: str) -> str:
    season = season_id or str(date.today().year)
    return f"{KBO_IMAGE_BASE}/{season}/{player_id}.jpg"


def _is_finished_game(game: Dict[str, Any]) -> bool:
    # SCORE_CK == "1" means final score is available.
    return str(game.get("SCORE_CK", "")) == "1"


def _clean_html_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return text.replace("&nbsp;", " ").strip()


def _parse_stat_tables(html: str) -> list[dict[str, str]]:
    """Parse every <table> in html and return list of header→first-row-value dicts."""
    flat = html.replace("\n", " ")
    result = []
    for table_html in re.findall(r"<table[^>]*>.*?</table>", flat, re.S):
        headers = [_clean_html_text(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", table_html, re.S)]
        if not headers:
            continue
        for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.S):
            cells = [_clean_html_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)]
            if cells:
                result.append({headers[i]: cells[i] for i in range(min(len(headers), len(cells)))})
                break  # only first data row per table
    return result


def _fetch_pitcher_stats(player_id: str) -> Dict[str, str]:
    if not player_id:
        return {}

    try:
        response = requests.get(PITCHER_DETAIL_URL, params={"playerId": player_id}, timeout=10)
        response.raise_for_status()
        html = response.text
    except Exception:
        return {}

    tables = _parse_stat_tables(html)

    basic: Dict[str, str] = {}
    advanced: Dict[str, str] = {}
    for t in tables:
        if "ERA" in t and not basic:
            basic = t
        if "WHIP" in t and not advanced:
            advanced = t

    return {
        "era": basic.get("ERA", "-"),
        "war": "-",  # KBO 투수 상세 페이지에서 WAR를 제공하지 않음
        "games": basic.get("G", "-"),
        "avg_innings": basic.get("IP", "-"),
        "qs": advanced.get("QS", "-"),
        "whip": advanced.get("WHIP", "-"),
    }


def get_next_hanwha_game(max_days_ahead: int = 30) -> Optional[Dict[str, str]]:
    today = date.today()
    for offset in range(max_days_ahead + 1):
        target = today + timedelta(days=offset)
        games = _fetch_games(target)
        for game in games:
            if not _is_hanwha_game(game):
                continue
            if offset == 0 and _is_finished_game(game):
                continue

            is_away = game.get("AWAY_ID") == HANWHA_TEAM_ID
            opponent_name = game.get("HOME_NM") if is_away else game.get("AWAY_NM")
            hanwha_starter = _extract_hanwha_starter(game) or "미정"
            away_starter = (game.get("T_PIT_P_NM") or "").strip() or "미정"
            home_starter = (game.get("B_PIT_P_NM") or "").strip() or "미정"
            away_starter_id = str(game.get("T_PIT_P_ID") or "")
            home_starter_id = str(game.get("B_PIT_P_ID") or "")
            season_id = str(game.get("SEASON_ID", ""))
            away_starter_stats = _fetch_pitcher_stats(away_starter_id)
            home_starter_stats = _fetch_pitcher_stats(home_starter_id)

            return {
                "season_id": season_id,
                "game_date": game.get("G_DT_TXT", ""),
                "game_time": game.get("G_TM", ""),
                "stadium": game.get("S_NM", ""),
                "home_team": game.get("HOME_NM", ""),
                "away_team": game.get("AWAY_NM", ""),
                "matchup": f"{game.get('AWAY_NM', '')} vs {game.get('HOME_NM', '')}",
                "hanwha_home_away": "원정" if is_away else "홈",
                "opponent": opponent_name or "",
                "hanwha_starter": hanwha_starter,
                "away_starter": away_starter,
                "home_starter": home_starter,
                "away_starter_id": away_starter_id,
                "home_starter_id": home_starter_id,
                "away_starter_image": _face_image_url(season_id, away_starter_id) if away_starter_id else "",
                "home_starter_image": _face_image_url(season_id, home_starter_id) if home_starter_id else "",
                "away_starter_stats": away_starter_stats,
                "home_starter_stats": home_starter_stats,
            }
    return None
