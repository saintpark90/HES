from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Dict, Optional

import requests

KBO_GAME_LIST_URL = "https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList"
HANWHA_TEAM_ID = "HH"
SERIES_IDS = "0,1,3,4,5,6,7,9"


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


def get_next_hanwha_game(max_days_ahead: int = 30) -> Optional[Dict[str, str]]:
    today = date.today()
    for offset in range(max_days_ahead + 1):
        target = today + timedelta(days=offset)
        games = _fetch_games(target)
        for game in games:
            if not _is_hanwha_game(game):
                continue

            is_away = game.get("AWAY_ID") == HANWHA_TEAM_ID
            opponent_name = game.get("HOME_NM") if is_away else game.get("AWAY_NM")
            hanwha_starter = _extract_hanwha_starter(game) or "미정"
            away_starter = (game.get("T_PIT_P_NM") or "").strip() or "미정"
            home_starter = (game.get("B_PIT_P_NM") or "").strip() or "미정"

            return {
                "season_id": str(game.get("SEASON_ID", "")),
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
                "away_starter_id": str(game.get("T_PIT_P_ID") or ""),
                "home_starter_id": str(game.get("B_PIT_P_ID") or ""),
            }
    return None
