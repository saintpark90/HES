from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional
from urllib.parse import quote
import xml.etree.ElementTree as ET
import time
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

KBO_GAME_LIST_URL = "https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList"
KBO_TEAM_RECORD_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetTeamRecord"
KBO_LINEUP_ANALYSIS_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetLineUpAnalysis"
KBO_BOX_SCORE_SCROLL_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetBoxScoreScroll"
KBO_PITCHER_RECORD_ANALYSIS_URL = "https://www.koreabaseball.com/ws/Schedule.asmx/GetPitcherRecordAnalysis"
KBO_PLAYER_SEARCH_URL = "https://www.koreabaseball.com/ws/Controls.asmx/GetSearchPlayer"
HANWHA_TEAM_ID = "HH"
SERIES_IDS = "0,1,3,4,5,6,7,9"
KBO_IMAGE_BASE = "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle"
KBO_EMBLEM_BASE = "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/emblem/regular"
PITCHER_DETAIL_URL = "https://www.koreabaseball.com/Record/Player/PitcherDetail/Basic.aspx"
KBO_TEAM_RANK_DAILY_URL = "https://www.koreabaseball.com/Record/TeamRank/TeamRankDaily.aspx"
KBO_LIVETEXT_VIEW2_URL = "https://www.koreabaseball.com/Game/LiveTextView2.aspx"
NAVER_SPORTS_API_BASE = "https://api-gw.sports.naver.com"
NAVER_KBO_TEAM_RANK_URL = NAVER_SPORTS_API_BASE + "/statistics/categories/kbo/seasons/{season}/teams"
NAVER_KBO_LAST10_URL = (
    NAVER_SPORTS_API_BASE + "/statistics/categories/kbo/seasons/{season}/teams/last-ten-games"
)
YOUTUBE_PLAYLIST_FEED_URL = "https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
EAGLES_HIGHLIGHT_PLAYLIST_ID = "PLH13Vc2FtHHh-syagRtonzJLl-SkG3B7Q"
EAGLES_OIYU_PLAYLIST_ID = "PLH13Vc2FtHHg4qpO0evfriiB7R7pU_q05"
NAVER_SPORTS_NEWS_API_URL = "https://api-gw.sports.naver.com/news/articles/kbaseball"
YOUTUBE_PLAYLIST_URL = "https://www.youtube.com/playlist?list={playlist_id}"
KBO_REGISTER_ALL_URL = "https://www.koreabaseball.com/Player/RegisterAll.aspx"
# Official channel; used when the 오이유 video is not in the configured playlist (same-day by title suffix as H/L).
EAGLES_OFFICIAL_CHANNEL_URL = "https://www.youtube.com/@HanwhaEagles_official"
EAGLES_OFFICIAL_VIDEOS_URL = "https://www.youtube.com/@HanwhaEagles_official/videos"
OPENMETEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPENMETEO_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
KST = ZoneInfo("Asia/Seoul")
_HANWHA_SEASON_SCHEDULE_CACHE: Dict[str, Dict[str, Any]] = {}
_HANWHA_SEASON_SCHEDULE_CACHE_TTL_SEC = 60 * 30
_NAMU_WIKI_MONTH_CACHE: Dict[str, Dict[str, Any]] = {}
_NAMU_WIKI_MONTH_CACHE_TTL_SEC = 60 * 30
_PITCHER_NAME_CACHE: Dict[str, str] = {}
_PITCHER_BIRTH_YEAR_CACHE: Dict[str, str] = {}
NAMU_WIKI_BASE_URL = "https://namu.wiki/w/"
KBO_ID_TO_NAMU_TEAM_SHORT = {
    "HH": "한화",
    "NC": "NC",
    "KT": "KT",
    "HT": "KIA",
    "SK": "SSG",
    "SS": "삼성",
    "LT": "롯데",
    "WO": "키움",
    "LG": "LG",
    "OB": "두산",
}
_NAMU_TEAM_SHORTS = set(KBO_ID_TO_NAMU_TEAM_SHORT.values())
_NAMU_INVALID_STARTER_TOKENS = {
    "",
    "-",
    "미정",
    "TBD",
    "예정",
    "선발",
    "투수",
    "타순",
    "선수명",
    "포지션",
    "등록",
    "말소",
    "팀",
    "중계채널",
    "캐스터",
    "해설",
    "결승타",
    "홈런",
    "실책",
    "도루",
    "도루자",
    "한화",
    "NC",
    "KT",
    "KIA",
    "SSG",
    "삼성",
    "롯데",
    "키움",
    "LG",
    "두산",
}


def _kbo_api_headers() -> Dict[str, str]:
    """KBO ws/*.asmx endpoints return an HTML error page without browser-like headers."""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.koreabaseball.com/",
        "Origin": "https://www.koreabaseball.com",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }


def _today_kst() -> date:
    """KBO schedules and Korean 'today' for UI must use Asia/Seoul, not server local/UTC date."""
    return datetime.now(KST).date()


TEAM_NAME_TO_ID = {
    "KT": "KT",
    "LG": "LG",
    "삼성": "SS",
    "SSG": "SK",
    "KIA": "HT",
    "한화": "HH",
    "NC": "NC",
    "두산": "OB",
    "롯데": "LT",
    "키움": "WO",
}

POSITION_TEXT_MAP = {
    "투": "투수",
    "포": "포수",
    "내": "내야수",
    "외": "외야수",
    "코치": "코치",
    "감독": "감독",
}

STADIUM_REGION_COORDS = {
    "잠실": {"region": "서울 잠실", "lat": 37.5121, "lon": 127.0719},
    "고척": {"region": "서울 고척", "lat": 37.4982, "lon": 126.8671},
    "문학": {"region": "인천 문학", "lat": 37.4369, "lon": 126.6931},
    "수원": {"region": "수원", "lat": 37.2998, "lon": 127.0096},
    "대전": {"region": "대전", "lat": 36.3171, "lon": 127.4281},
    "대구": {"region": "대구", "lat": 35.8410, "lon": 128.6811},
    "광주": {"region": "광주", "lat": 35.1680, "lon": 126.8891},
    "사직": {"region": "부산 사직", "lat": 35.1943, "lon": 129.0615},
    "창원": {"region": "창원", "lat": 35.2222, "lon": 128.5822},
    "포항": {"region": "포항", "lat": 36.0147, "lon": 129.3650},
    "울산": {"region": "울산", "lat": 35.5351, "lon": 129.2582},
}

WEATHER_CODE_TEXT = {
    0: "맑음",
    1: "대체로 맑음",
    2: "부분 흐림",
    3: "흐림",
    45: "안개",
    48: "짙은 안개",
    51: "약한 이슬비",
    53: "이슬비",
    55: "강한 이슬비",
    56: "약한 어는비",
    57: "강한 어는비",
    61: "약한 비",
    63: "비",
    65: "강한 비",
    66: "약한 어는비",
    67: "강한 어는비",
    71: "약한 눈",
    73: "눈",
    75: "강한 눈",
    77: "진눈깨비",
    80: "소나기",
    81: "강한 소나기",
    82: "매우 강한 소나기",
    85: "약한 눈소나기",
    86: "강한 눈소나기",
    95: "뇌우",
    96: "약한 우박 뇌우",
    99: "강한 우박 뇌우",
}


def _resolve_stadium_coords(stadium_name: str) -> Optional[Dict[str, Any]]:
    name = str(stadium_name or "").strip()
    if not name:
        return None
    for key, info in STADIUM_REGION_COORDS.items():
        if key in name:
            return {"region": info["region"], "lat": info["lat"], "lon": info["lon"]}
    return None


def _weather_icon_key(code: int) -> str:
    if code in {95, 96, 99}:
        return "storm"
    if code in {45, 48}:
        return "fog"
    if code in {71, 73, 75, 77, 85, 86}:
        return "snow"
    if code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
        return "rain"
    if code in {1, 2}:
        return "partly"
    if code == 3:
        return "cloud"
    return "sun"


def _parse_game_datetime_kst(target_date: date, game_time: str) -> Optional[datetime]:
    text = str(game_time or "").strip()
    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2))
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return datetime(target_date.year, target_date.month, target_date.day, hour, minute, tzinfo=KST)


def _dust_grade(pm10: float) -> str:
    if pm10 <= 30:
        return "좋음"
    if pm10 <= 80:
        return "보통"
    if pm10 <= 150:
        return "나쁨"
    return "매우 나쁨"


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _build_game_weather_info(target_date: date, game_time: str, stadium_name: str) -> Dict[str, Any]:
    coords = _resolve_stadium_coords(stadium_name)
    if not coords:
        return {}

    now_kst = datetime.now(KST)
    game_start = _parse_game_datetime_kst(target_date=target_date, game_time=game_time)
    start_hour_dt = datetime(target_date.year, target_date.month, target_date.day, 0, 0, tzinfo=KST)
    if target_date == now_kst.date():
        start_hour_dt = now_kst.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    end_boundary = datetime(target_date.year, target_date.month, target_date.day, 23, 0, tzinfo=KST)
    end_midnight = datetime(target_date.year, target_date.month, target_date.day, 0, 0, tzinfo=KST) + timedelta(days=1)
    include_midnight = target_date == now_kst.date()
    if start_hour_dt > end_boundary and not include_midnight:
        return {}

    target_hours: list[datetime] = []
    cursor = start_hour_dt
    while cursor <= end_boundary:
        target_hours.append(cursor)
        cursor += timedelta(hours=1)
    if include_midnight and end_midnight not in target_hours:
        target_hours.append(end_midnight)

    if not target_hours:
        return {}

    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "timezone": "Asia/Seoul",
        "hourly": "temperature_2m,weather_code,precipitation_probability",
        "start_date": target_date.isoformat(),
        "end_date": (target_date + timedelta(days=1)).isoformat() if include_midnight else target_date.isoformat(),
    }
    try:
        weather_resp = _http_get_with_retries(OPENMETEO_FORECAST_URL, params=params, timeout=12)
        weather_resp.raise_for_status()
        weather_payload = weather_resp.json()
    except Exception:
        return {}

    hourly = weather_payload.get("hourly") or {}
    times = hourly.get("time") or []
    weather_codes = hourly.get("weather_code") or []
    temperatures = hourly.get("temperature_2m") or []
    rain_probs = hourly.get("precipitation_probability") or []
    by_time: Dict[str, Dict[str, Any]] = {}
    for idx, raw_time in enumerate(times):
        by_time[str(raw_time)] = {
            "code": int(weather_codes[idx]) if idx < len(weather_codes) and weather_codes[idx] is not None else 0,
            "temp": temperatures[idx] if idx < len(temperatures) else None,
            "pop": rain_probs[idx] if idx < len(rain_probs) else None,
        }

    hourly_items: list[Dict[str, Any]] = []
    for hour_dt in target_hours:
        key = hour_dt.strftime("%Y-%m-%dT%H:00")
        entry = by_time.get(key)
        if not entry:
            continue
        code = int(entry.get("code", 0) or 0)
        pop = int(entry.get("pop", 0) or 0)
        is_midnight = hour_dt.hour == 0 and hour_dt.date() > target_date
        label = "24:00" if is_midnight else hour_dt.strftime("%H:00")
        game_start_label = game_start.strftime("%H:%M") if game_start else ""
        is_game_start = bool(game_start_label) and game_start_label.startswith(label[:2] + ":")
        hourly_items.append(
            {
                "time_label": label,
                "weather": WEATHER_CODE_TEXT.get(code, "날씨"),
                "icon": _weather_icon_key(code),
                "rain_probability": pop,
                "temperature": (
                    f"{float(entry['temp']):.1f}"
                    if entry.get("temp") is not None and entry.get("temp") != ""
                    else "-"
                ),
                "is_game_start": is_game_start,
            }
        )

    if not hourly_items:
        return {}

    if game_start:
        game_window_pops = []
        for offset in range(-1, 5):
            slot = (game_start.replace(minute=0, second=0, microsecond=0) + timedelta(hours=offset)).strftime("%H:00")
            if slot == "00:00":
                slot = "24:00"
            for item in hourly_items:
                if item["time_label"] == slot:
                    game_window_pops.append(item["rain_probability"])
        if not game_window_pops:
            game_window_pops = [item["rain_probability"] for item in hourly_items]
    else:
        game_window_pops = [item["rain_probability"] for item in hourly_items]

    avg_pop = sum(game_window_pops) / max(1, len(game_window_pops))
    max_pop = max(game_window_pops) if game_window_pops else 0
    progress_probability = int(round(max(0, min(100, 100 - (avg_pop * 0.6 + max_pop * 0.4)))))
    # 고척돔은 돔구장이라 기상과 무관하게 경기 진행 확률 100%로 고정.
    if "고척" in str(stadium_name or ""):
        progress_probability = 100

    aq_params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "timezone": "Asia/Seoul",
        "hourly": "pm10,pm2_5",
        "start_date": now_kst.date().isoformat(),
        "end_date": now_kst.date().isoformat(),
    }
    dust = {"pm10": "-", "pm2_5": "-", "grade": "-"}
    try:
        aq_resp = _http_get_with_retries(OPENMETEO_AIR_QUALITY_URL, params=aq_params, timeout=12)
        aq_resp.raise_for_status()
        aq_payload = aq_resp.json()
        aq_hourly = aq_payload.get("hourly") or {}
        aq_times = aq_hourly.get("time") or []
        pm10_values = aq_hourly.get("pm10") or []
        pm25_values = aq_hourly.get("pm2_5") or []
        now_hour_key = now_kst.replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00")
        pick_idx = aq_times.index(now_hour_key) if now_hour_key in aq_times else (len(aq_times) - 1)
        if pick_idx >= 0:
            pm10 = _safe_float(pm10_values[pick_idx] if pick_idx < len(pm10_values) else None)
            pm25 = _safe_float(pm25_values[pick_idx] if pick_idx < len(pm25_values) else None)
            if pm10 is not None:
                dust["pm10"] = f"{pm10:.0f}"
                dust["grade"] = _dust_grade(pm10)
            if pm25 is not None:
                dust["pm2_5"] = f"{pm25:.0f}"
    except Exception:
        pass

    return {
        "region": coords["region"],
        "game_start_time": str(game_time or "").strip(),
        "hourly": hourly_items,
        "game_progress_probability": progress_probability,
        "dust": dust,
        "updated_at": now_kst.replace(microsecond=0).isoformat(),
    }


def _fetch_games(target_date: date) -> list[Dict[str, Any]]:
    payload = {
        "leId": "1",
        "srId": SERIES_IDS,
        "date": target_date.strftime("%Y%m%d"),
    }
    response = _http_post_with_retries(
        KBO_GAME_LIST_URL,
        data=payload,
        headers=_kbo_api_headers(),
        timeout=12,
    )
    response.raise_for_status()
    body = _loads_kbo_json_response(response, "GetKboGameList")
    return body.get("game", [])


def _fetch_game_by_game_id(game_id: str) -> Dict[str, Any]:
    if len(game_id) < 8:
        return {}
    try:
        game_date = datetime.strptime(game_id[:8], "%Y%m%d").date()
    except ValueError:
        return {}

    try:
        games = _fetch_games(game_date)
    except Exception:
        return {}

    for g in games:
        if str(g.get("G_ID", "")) == game_id:
            return g
    return {}


def _is_hanwha_game(game: Dict[str, Any]) -> bool:
    return game.get("AWAY_ID") == HANWHA_TEAM_ID or game.get("HOME_ID") == HANWHA_TEAM_ID


def _extract_hanwha_starter(game: Dict[str, Any]) -> str:
    if game.get("AWAY_ID") == HANWHA_TEAM_ID:
        return (game.get("T_PIT_P_NM") or "").strip()
    return (game.get("B_PIT_P_NM") or "").strip()


def _is_missing_starter_name(name: str) -> bool:
    token = (name or "").strip()
    return token in {"", "-", "미정", "TBD", "예정"}


def _namu_wiki_month_page_url(target: date) -> str:
    path = f"한화 이글스/{target.year}년/{target.month}월"
    return f"{NAMU_WIKI_BASE_URL}{quote(path)}"


def _fetch_namu_wiki_month_html(target: date, *, force_refresh: bool = False) -> str:
    cache_key = f"{target.year}-{target.month:02d}"
    now_ts = time.time()
    cached = _NAMU_WIKI_MONTH_CACHE.get(cache_key) or {}
    cached_at = float(cached.get("cached_at", 0.0) or 0.0)
    if (not force_refresh) and cached and (now_ts - cached_at) <= _NAMU_WIKI_MONTH_CACHE_TTL_SEC:
        html = cached.get("html")
        if isinstance(html, str) and html:
            return html

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9",
    }
    try:
        response = _http_get_with_retries(
            _namu_wiki_month_page_url(target),
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
        response.encoding = "utf-8"
        html = response.text or ""
    except Exception:
        return ""

    _NAMU_WIKI_MONTH_CACHE[cache_key] = {"cached_at": now_ts, "html": html}
    return html


def _is_valid_namu_starter_name(name: str) -> bool:
    token = (name or "").strip()
    if not token or token in _NAMU_INVALID_STARTER_TOKENS:
        return False
    if len(token) > 24:
        return False
    if re.fullmatch(r"\d+", token):
        return False
    if re.search(r"(차전|ERA|시즌|기록|편집|회|위|G\b|VS\b|프리뷰|라인업)", token):
        return False
    if not re.fullmatch(r"[A-Za-z가-힣·.\-\s]{2,24}", token):
        return False
    return True


def _parse_namu_starters_for_date(html: str, target: date) -> Dict[str, str]:
    """
    Parse {team_short: pitcher_name} from the per-game section on the monthly wiki page.
    """
    if not html:
        return {}

    month, day = target.month, target.day
    markers = [
        f"한화 이글스 {month}월 {day}일 선발",
        f"{month}월 {day}일 선발 라인업",
    ]
    idx = -1
    for marker in markers:
        idx = html.find(marker)
        if idx >= 0:
            break
    if idx < 0:
        day_pat = re.compile(rf"{month}\s*월\s*{day}\s*일")
        for match in day_pat.finditer(html):
            chunk = html[match.start() : match.start() + 120]
            if "선발" in chunk or "라인업" in chunk:
                idx = match.start()
                break
    if idx < 0:
        return {}

    chunk = html[idx : idx + 25000]
    plain = re.sub(r"<[^>]+>", "|", chunk)
    parts = [part.strip() for part in plain.split("|") if part.strip()]

    starters: Dict[str, str] = {}
    for idx_part, part in enumerate(parts):
        if part not in _NAMU_TEAM_SHORTS:
            continue
        if idx_part + 1 >= len(parts):
            continue
        candidate = parts[idx_part + 1].strip()
        if not _is_valid_namu_starter_name(candidate):
            continue
        starters.setdefault(part, candidate)
        if len(starters) >= 2:
            break
    return starters


def _parse_namu_starter_birthyear_hints_for_date(html: str, target: date) -> Dict[str, str]:
    """
    Parse {starter_name: birth_year_hint} from namu anchors in the per-game chunk.
    Example href/title: /w/박준영(2002)
    """
    if not html:
        return {}

    month, day = target.month, target.day
    markers = [
        f"한화 이글스 {month}월 {day}일 선발",
        f"{month}월 {day}일 선발 라인업",
    ]
    idx = -1
    for marker in markers:
        idx = html.find(marker)
        if idx >= 0:
            break
    if idx < 0:
        return {}

    chunk = html[idx : idx + 25000]
    soup = BeautifulSoup(chunk, "html.parser")
    hints: Dict[str, str] = {}
    for a in soup.find_all("a"):
        name = (a.get_text() or "").strip()
        if not _is_valid_namu_starter_name(name):
            continue
        href = str(a.get("href") or "")
        title = str(a.get("title") or "")
        raw = f"{href} {title}"
        m = re.search(r"\((19\d{2}|20\d{2})\)", raw)
        if not m:
            continue
        hints.setdefault(name, m.group(1))
    return hints


def _fetch_namu_wiki_starters_for_game(
    target: date, away_team_id: str, home_team_id: str, *, force_refresh: bool = False
) -> Dict[str, str]:
    html = _fetch_namu_wiki_month_html(target, force_refresh=force_refresh)
    by_team = _parse_namu_starters_for_date(html, target)
    if not by_team:
        return {}

    away_short = KBO_ID_TO_NAMU_TEAM_SHORT.get(str(away_team_id or "").strip(), "")
    home_short = KBO_ID_TO_NAMU_TEAM_SHORT.get(str(home_team_id or "").strip(), "")
    away_starter = by_team.get(away_short, "")
    home_starter = by_team.get(home_short, "")
    birth_hints = _parse_namu_starter_birthyear_hints_for_date(html, target)
    away_birth_year = birth_hints.get(away_starter, "") if away_starter else ""
    home_birth_year = birth_hints.get(home_starter, "") if home_starter else ""
    if not away_starter and not home_starter:
        return {}
    return {
        "away_starter": away_starter,
        "home_starter": home_starter,
        "away_starter_birth_year": away_birth_year,
        "home_starter_birth_year": home_birth_year,
    }


def _face_image_url(season_id: str, player_id: str) -> str:
    season = season_id or str(date.today().year)
    return f"{KBO_IMAGE_BASE}/{season}/{player_id}.jpg"


def _is_finished_game(game: Dict[str, Any]) -> bool:
    # SCORE_CK == "1" means final score is available.
    return str(game.get("SCORE_CK", "")) == "1"


def _is_live_game(game: Dict[str, Any]) -> bool:
    # GAME_STATE_SC:
    # 1: 예정, 2: 경기중, 3/4: 종료(데이터 반영 상태에 따라 다름)
    return str(game.get("GAME_STATE_SC", "")) == "2"


def _is_final_game(game: Dict[str, Any]) -> bool:
    return str(game.get("GAME_STATE_SC", "")) in {"3", "4"}


def _is_cancelled_game(game: Dict[str, Any]) -> bool:
    cancel_id = str(game.get("CANCEL_SC_ID", "") or "").strip()
    cancel_name = str(game.get("CANCEL_SC_NM", "") or "").strip()
    if cancel_id and cancel_id not in {"0"}:
        return True
    return "취소" in cancel_name


def _game_cancel_label(game: Dict[str, Any]) -> str:
    if not _is_cancelled_game(game):
        return ""
    cancel_name = str(game.get("CANCEL_SC_NM", "") or "").strip()
    if "우천" in cancel_name:
        return "우천취소"
    return cancel_name or "취소"


def _build_live_status(game: Dict[str, Any], away_team: str, home_team: str) -> Dict[str, Any]:
    is_cancelled = _is_cancelled_game(game)
    cancel_label = _game_cancel_label(game)
    is_live = _is_live_game(game) and not is_cancelled
    is_final = _is_final_game(game) or is_cancelled
    top_bottom = str(game.get("GAME_TB_SC", "") or "")
    inning_no = str(game.get("GAME_INN_NO", "") or "").strip()
    inning_half = "초" if top_bottom == "T" else "말" if top_bottom == "B" else ""
    inning_text = f"{inning_no}회 {inning_half}".strip() if inning_no else ""

    away_score = str(game.get("T_SCORE_CN", "0") or "0")
    home_score = str(game.get("B_SCORE_CN", "0") or "0")

    away_batter = str(game.get("T_P_NM", "") or "").strip()
    home_batter = str(game.get("B_P_NM", "") or "").strip()
    if top_bottom == "T":
        current_batter = away_batter
        current_batter_team = away_team
        current_pitcher = home_batter
        current_pitcher_team = home_team
    elif top_bottom == "B":
        current_batter = home_batter
        current_batter_team = home_team
        current_pitcher = away_batter
        current_pitcher_team = away_team
    else:
        current_batter = away_batter or home_batter
        current_batter_team = away_team if away_batter else home_team
        current_pitcher = home_batter or away_batter
        current_pitcher_team = home_team if home_batter else away_team

    return {
        "is_live": is_live,
        "is_final": is_final,
        "is_cancelled": is_cancelled,
        "cancel_label": cancel_label,
        "away_score": away_score,
        "home_score": home_score,
        "inning_text": inning_text,
        "current_pitcher": current_pitcher,
        "current_pitcher_team": current_pitcher_team,
        "current_batter": current_batter,
        "current_batter_team": current_batter_team,
    }


def _clean_html_text(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return text.replace("&nbsp;", " ").strip()


def _cell_text(cell: Dict[str, Any]) -> str:
    return _clean_html_text(str((cell or {}).get("Text", "") or ""))


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


def _parse_team_record_row(row: list) -> Dict[str, str]:
    """row is the list of cell dicts from GetTeamRecord JSON."""
    def text(idx: int) -> str:
        if idx >= len(row):
            return "-"
        return re.sub(r"<[^>]+>", "", row[idx].get("Text", "") or "").strip() or "-"

    def is_win(idx: int) -> bool:
        if idx >= len(row):
            return False
        return (row[idx].get("Class") or "") == "win"

    return {
        "season_record": text(1),
        "last5": text(2),
        "era": text(3),
        "era_win": is_win(3),
        "avg": text(4),
        "avg_win": is_win(4),
        "runs_scored": text(5),
        "runs_scored_win": is_win(5),
        "runs_allowed": text(6),
        "runs_allowed_win": is_win(6),
    }


def _fetch_team_comparison(game_id: str, season_id: str, away_id: str, home_id: str) -> Dict[str, Any]:
    """Fetch team season stats from KBO GetTeamRecord endpoint."""
    if not game_id:
        return {}

    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.koreabaseball.com/"}
    payload = {
        "leId": "1",
        "srId": "0",
        "seasonId": season_id or str(date.today().year),
        "gameId": game_id,
        "groupSc": "SEASON",
    }

    try:
        resp = requests.post(KBO_TEAM_RECORD_URL, data=payload, headers=headers, timeout=10)
        resp.raise_for_status()
        data = json.loads(resp.content.decode("utf-8-sig"))
    except Exception:
        return {}

    rows = data.get("rows", [])
    if len(rows) < 2:
        return {}

    away_row = rows[0].get("row", [])
    home_row = rows[1].get("row", [])

    emblem_year = season_id or str(date.today().year)
    return {
        "away": _parse_team_record_row(away_row),
        "home": _parse_team_record_row(home_row),
        "away_emblem": f"{KBO_EMBLEM_BASE}/{emblem_year}/emblem_{away_id}.png",
        "home_emblem": f"{KBO_EMBLEM_BASE}/{emblem_year}/emblem_{home_id}.png",
    }


def _fetch_latest_playlist_video(playlist_id: str) -> Dict[str, str]:
    feed_url = YOUTUBE_PLAYLIST_FEED_URL.format(playlist_id=playlist_id)
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = _http_get_with_retries(feed_url, headers=headers, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.text)
    except Exception:
        return _fetch_latest_playlist_video_from_page(playlist_id)

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
        "media": "http://search.yahoo.com/mrss/",
    }
    entries = root.findall("atom:entry", ns)
    if not entries:
        return _fetch_latest_playlist_video_from_page(playlist_id)

    # Reorder in RSS does not always match "most recently published" on YouTube. Pick max(atom:published).
    entry: Optional[ET.Element] = None
    best_published: Optional[datetime] = None
    for cand in entries:
        raw = (cand.findtext("atom:published", default="", namespaces=ns) or "").strip()
        if not raw:
            continue
        if raw.endswith("Z"):
            raw = raw.replace("Z", "+00:00")
        try:
            published_at = datetime.fromisoformat(raw)
        except Exception:
            continue
        if best_published is None or published_at > best_published:
            best_published = published_at
            entry = cand
    if entry is None:
        entry = entries[0]

    title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
    link_node = entry.find("atom:link", ns)
    video_url = ""
    if link_node is not None:
        video_url = str(link_node.attrib.get("href", "") or "").strip()
    published = (entry.findtext("atom:published", default="", namespaces=ns) or "").strip()
    video_id = (entry.findtext("yt:videoId", default="", namespaces=ns) or "").strip()
    thumbnail = ""
    thumbnail_node = entry.find("media:group/media:thumbnail", ns)
    if thumbnail_node is not None:
        thumbnail = str(thumbnail_node.attrib.get("url", "") or "").strip()
    if not thumbnail and video_id:
        thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    if video_id:
        title = _fetch_youtube_video_title_ko(video_id, title)

    return {
        "title": title,
        "url": video_url,
        "published_at": published,
        "video_id": video_id,
        "thumbnail": thumbnail,
    }


def _fetch_latest_playlist_video_from_page(playlist_id: str) -> Dict[str, str]:
    page_url = f"https://www.youtube.com/playlist?list={playlist_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = _http_get_with_retries(page_url, headers=headers, timeout=12)
        response.raise_for_status()
        html = response.text
    except Exception:
        return {
            "title": "",
            "url": YOUTUBE_PLAYLIST_URL.format(playlist_id=playlist_id),
            "published_at": "",
            "video_id": "",
            "thumbnail": "",
        }

    init_data_match = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    if not init_data_match:
        video_id_match = re.search(r"watch\?v=([A-Za-z0-9_-]{11})", html)
        if not video_id_match:
            return {}
        video_id = video_id_match.group(1)
        return {
            "title": "",
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "published_at": "",
            "video_id": video_id,
            "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        }

    try:
        init_data = json.loads(init_data_match.group(1))
    except Exception:
        return {}

    renderer = _find_first_playlist_video_renderer(init_data)
    if not renderer:
        return {}
    video_id = str(renderer.get("videoId", "") or "").strip()
    if not video_id:
        return {}

    title = ""
    title_data = renderer.get("title", {})
    if isinstance(title_data, dict):
        runs = title_data.get("runs", []) or []
        if runs and isinstance(runs[0], dict):
            title = str(runs[0].get("text", "") or "").strip()
        if not title:
            title = str(title_data.get("simpleText", "") or "").strip()

    published = ""
    published_text = renderer.get("publishedTimeText", {})
    if isinstance(published_text, dict):
        published = str(published_text.get("simpleText", "") or "").strip()
    if not published:
        published_data = renderer.get("videoInfo", {})
        if isinstance(published_data, dict):
            runs = published_data.get("runs", []) or []
            if runs and isinstance(runs[0], dict):
                published = str(runs[0].get("text", "") or "").strip()
    title = _fetch_youtube_video_title_ko(video_id, title)

    return {
        "title": title,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "published_at": published,
        "video_id": video_id,
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    }


def _find_first_playlist_video_renderer(node: Any) -> Dict[str, Any]:
    if isinstance(node, dict):
        if "playlistVideoRenderer" in node and isinstance(node["playlistVideoRenderer"], dict):
            return node["playlistVideoRenderer"]
        for value in node.values():
            found = _find_first_playlist_video_renderer(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _find_first_playlist_video_renderer(item)
            if found:
                return found
    return {}


def _fetch_youtube_video_title_ko(video_id: str, fallback_title: str = "") -> str:
    if not video_id:
        return fallback_title
    # 1) oEmbed is lightweight and tends to return channel-native title text.
    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json&hl=ko"
    url = f"https://www.youtube.com/watch?v={video_id}&hl=ko&gl=KR&persist_hl=1&persist_gl=1"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    try:
        oembed_resp = _http_get_with_retries(oembed_url, timeout=8, headers=headers)
        if oembed_resp.ok:
            oembed_payload = oembed_resp.json()
            oembed_title = str(oembed_payload.get("title", "") or "").strip()
            if oembed_title:
                return oembed_title
    except Exception:
        pass

    try:
        response = _http_get_with_retries(url, timeout=10, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title and og_title.get("content"):
            title = str(og_title.get("content")).strip()
            if title:
                return title
    except Exception:
        return fallback_title
    return fallback_title


def _http_get_with_retries(
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    timeout: int = 10,
    retries: int = 3,
) -> requests.Response:
    last_error: Optional[Exception] = None
    for attempt in range(retries):
        try:
            return requests.get(
                url,
                headers=headers,
                params=params,
                timeout=timeout,
            )
        except Exception as exc:  # requests exceptions
            last_error = exc
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
    if last_error:
        raise last_error
    raise RuntimeError("unreachable retry state")


def _http_post_with_retries(
    url: str,
    *,
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 10,
    retries: int = 3,
) -> requests.Response:
    last_error: Optional[Exception] = None
    for attempt in range(retries):
        try:
            return requests.post(
                url,
                data=data,
                headers=headers,
                timeout=timeout,
            )
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
    if last_error:
        raise last_error
    raise RuntimeError("unreachable retry state")


def _loads_kbo_json_response(response: requests.Response, endpoint: str) -> Dict[str, Any]:
    text = response.content.decode("utf-8-sig").lstrip()
    if not text.startswith("{"):
        snippet = text[:120].replace("\n", " ")
        raise ValueError(
            f"{endpoint} returned non-JSON (HTTP {response.status_code}): {snippet!r}"
        )
    return json.loads(text)


_TITLE_DATE_PAREN = re.compile(r"(\([0-9]{1,2}\.[0-9]{1,2}\))\s*$")


def _trailing_date_paren_from_title(title: str) -> str:
    t = (title or "").strip()
    m = _TITLE_DATE_PAREN.search(t)
    return m.group(1) if m else ""


def _month_day_from_title_suffix(title: str) -> Optional[tuple[int, int]]:
    suffix = _trailing_date_paren_from_title(title)
    m = re.match(r"^\(([0-9]{1,2})\.([0-9]{1,2})\)$", suffix)
    if not m:
        return None
    month = int(m.group(1))
    day = int(m.group(2))
    if month < 1 or month > 12 or day < 1 or day > 31:
        return None
    return (month, day)


def _pick_newer_highlight(current: Dict[str, str], candidate: Dict[str, str]) -> Dict[str, str]:
    if not (candidate or {}).get("url"):
        return current
    if not (current or {}).get("url"):
        return candidate
    cur_md = _month_day_from_title_suffix((current or {}).get("title", "") or "")
    cand_md = _month_day_from_title_suffix((candidate or {}).get("title", "") or "")
    if cur_md and cand_md:
        return candidate if cand_md > cur_md else current
    if (not cur_md) and cand_md:
        return candidate
    return current


def _is_regular_season_hl_row_title(title: str) -> bool:
    """True for typical [정규시즌 H/L] highlight rows; 오이유 pick should skip these."""
    t = (title or "")
    return "H/L" in t and ("정규시즌" in t or "[정규" in t or "H/L]" in t)


def _yt_renderer_title_text(data: Any) -> str:
    if not isinstance(data, dict):
        return str(data or "")
    t = (data.get("title") or {})
    if not isinstance(t, dict):
        return str(t or "")
    runs = t.get("runs", [])
    if runs and isinstance(runs, list):
        return "".join((str((x or {}).get("text", "")) for x in runs if isinstance(x, dict)))
    return str(t.get("simpleText", "") or "")


def _oiyu_browse_rich_grid_to_video_list(rg: Dict[str, Any]) -> list[Dict[str, str]]:
    out: list[Dict[str, str]] = []
    for item in (rg.get("contents") or []):
        if not isinstance(item, dict):
            continue
        ritem = item.get("richItemRenderer", {}) or item
        if not isinstance(ritem, dict):
            continue
        content = ritem.get("content")
        if not isinstance(content, dict):
            content = ritem
        vrend = (content or {}).get("videoRenderer")
        if not isinstance(vrend, dict) or not vrend.get("videoId"):
            continue
        video_id = str(vrend.get("videoId", "") or "").strip()
        title = _yt_renderer_title_text(vrend)
        pub = vrend.get("publishedTimeText", {})
        published = ""
        if isinstance(pub, dict):
            published = str(pub.get("simpleText", "") or "").strip()
        out.append(
            {
                "video_id": video_id,
                "title": title,
                "published_at": published,
            }
        )
    return out


def _browse_data_to_oiyu_videos_list(init_data: Any) -> list[Dict[str, str]]:
    two = (init_data or {}).get("contents", {}).get("twoColumnBrowseResultsRenderer", {}) or {}
    tabs = two.get("tabs") or []
    # Prefer the main long-form "동영상" / "Videos" tab (not Home/Shorts).
    preferred: list[Dict[str, str]] = []
    fallback: list[Dict[str, str]] = []
    for tab in tabs:
        if not isinstance(tab, dict):
            continue
        tr = tab.get("tabRenderer") or {}
        if not isinstance(tr, dict):
            continue
        ttitle = tr.get("title", {})
        tab_name = _yt_simple_text_from_title_obj(ttitle)
        c = tr.get("content")
        if not isinstance(c, dict):
            continue
        rg = c.get("richGridRenderer")
        if not isinstance(rg, dict) or not (rg.get("contents") or []):
            continue
        parsed = _oiyu_browse_rich_grid_to_video_list(rg)
        if not parsed:
            continue
        if tab_name in ("동영상", "Videos", "비디오"):
            preferred = parsed
            break
        if len(parsed) > len(fallback):
            fallback = parsed
    return preferred or fallback


def _yt_simple_text_from_title_obj(ttitle: Any) -> str:
    if not isinstance(ttitle, dict):
        return str(ttitle or "").strip()
    s = (ttitle.get("simpleText") or "").strip()
    if s:
        return s
    runs = ttitle.get("runs") or []
    if runs and isinstance(runs, list):
        return "".join((str((x or {}).get("text", "")) for x in runs if isinstance(x, dict)))
    return ""


def _fetch_eagles_official_videos_browse() -> list[Dict[str, str]]:
    """Channel /videos, newest first (Korean /videos '동영상' tab)."""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = _http_get_with_retries(EAGLES_OFFICIAL_VIDEOS_URL, headers=headers, timeout=14)
        response.raise_for_status()
        html = response.text
    except Exception:
        return []
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", html, re.S)
    if not m:
        return []
    try:
        init_data = json.loads(m.group(1))
    except Exception:
        return []
    return _browse_data_to_oiyu_videos_list(init_data)


def _resolve_channel_id_from_handle_page(channel_url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = _http_get_with_retries(channel_url, headers=headers, timeout=12)
        response.raise_for_status()
        html = response.text
    except Exception:
        return ""

    m = re.search(r'"channelId":"(UC[a-zA-Z0-9_-]{20,})"', html)
    if m:
        return m.group(1)
    m = re.search(r'href="https://www\.youtube\.com/channel/(UC[a-zA-Z0-9_-]{20,})"', html)
    if m:
        return m.group(1)
    return ""


def _fetch_channel_videos_from_rss(channel_id: str) -> list[Dict[str, str]]:
    if not channel_id:
        return []
    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = _http_get_with_retries(feed_url, headers=headers, timeout=10)
        response.raise_for_status()
        root = ET.fromstring(response.text)
    except Exception:
        return []

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }
    entries = root.findall("atom:entry", ns)
    videos: list[Dict[str, str]] = []
    for entry in entries:
        video_id = (entry.findtext("yt:videoId", default="", namespaces=ns) or "").strip()
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        published = (entry.findtext("atom:published", default="", namespaces=ns) or "").strip()
        if not video_id:
            continue
        videos.append(
            {
                "video_id": video_id,
                "title": title,
                "published_at": published,
            }
        )
    return videos


def _tv_entry_from_video_id_title(
    video_id: str, title: str, published: str = ""
) -> Dict[str, str]:
    title = (title or "").strip()
    if not video_id:
        return {
            "title": "",
            "url": "",
            "published_at": "",
            "video_id": "",
            "thumbnail": "",
        }
    title = _fetch_youtube_video_title_ko(video_id, title)
    return {
        "title": title,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "published_at": published or "",
        "video_id": video_id,
        "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
    }


def _oiyu_from_channel_matched_to_highlight(
    channel_videos: list[Dict[str, str]], highlight: Dict[str, str]
) -> Dict[str, str]:
    """
    Newest-first /videos: 오이유는 H/L **이후**(업로드 시각 기준)에만 올라오므로, H/L보다
    위에 있는 항목만 본다 (인덱스 0..idx-1). 그중 H/L **바로 다음**에 올라온 것(연속일 가능성)을
    우선하려고 idx-1 → idx-2 → … → 0 순으로 스캔한다.
    """
    h_id = str((highlight or {}).get("video_id", "") or "").strip()
    h_title = (highlight or {}).get("title", "") or ""
    date_suffix = _trailing_date_paren_from_title(h_title)
    if not date_suffix or not h_id:
        return {}

    def matches_game_day(v: Dict[str, str]) -> bool:
        t = (v.get("title") or "").strip()
        if not t.rstrip().endswith(date_suffix):
            return False
        if _is_regular_season_hl_row_title(t):
            return False
        vid = str((v.get("video_id") or "")).strip()
        if vid == h_id:
            return False
        return True

    if not channel_videos:
        return {}

    idx = -1
    for i, v in enumerate(channel_videos):
        if str((v.get("video_id") or "")).strip() == h_id:
            idx = i
            break
    if idx < 0:
        return {}
    for j in range(idx - 1, -1, -1):
        v = channel_videos[j]
        if matches_game_day(v):
            return _tv_entry_from_video_id_title(
                v["video_id"],
                v.get("title", "") or "",
                v.get("published_at", "") or "",
            )
    return {}


def _oiyu_from_channel_by_date_suffix(
    channel_videos: list[Dict[str, str]], highlight: Dict[str, str]
) -> Dict[str, str]:
    date_suffix = _trailing_date_paren_from_title((highlight or {}).get("title", "") or "")
    if not date_suffix or not channel_videos:
        return {}
    for v in channel_videos:
        title = str((v or {}).get("title", "") or "").strip()
        video_id = str((v or {}).get("video_id", "") or "").strip()
        if not video_id:
            continue
        if not title.rstrip().endswith(date_suffix):
            continue
        if _is_regular_season_hl_row_title(title):
            continue
        return _tv_entry_from_video_id_title(
            video_id,
            title,
            str((v or {}).get("published_at", "") or ""),
        )
    return {}


def _oiyu_needs_channel_fallback(
    highlight: Dict[str, str], oiyu: Dict[str, str]
) -> bool:
    if not (highlight or {}).get("url"):
        return False
    h_date = _trailing_date_paren_from_title((highlight or {}).get("title", "") or "")
    if not h_date:
        return False
    if not (oiyu or {}).get("url"):
        return True
    o_date = _trailing_date_paren_from_title((oiyu or {}).get("title", "") or "")
    return o_date != h_date


def _is_highlight_video_title(title: str) -> bool:
    t = (title or "").strip()
    if not t:
        return False
    return ("H/L" in t) or ("하이라이트" in t)


def _highlight_from_channel_videos(channel_videos: list[Dict[str, str]]) -> Dict[str, str]:
    if not channel_videos:
        return {}
    for v in channel_videos:
        title = str((v or {}).get("title", "") or "").strip()
        video_id = str((v or {}).get("video_id", "") or "").strip()
        if not video_id or not _is_highlight_video_title(title):
            continue
        return _tv_entry_from_video_id_title(
            video_id,
            title,
            str((v or {}).get("published_at", "") or ""),
        )
    return {}


def _fetch_eagles_tv_latest() -> Dict[str, Any]:
    # Fetch in sequence. Back-to-back YouTube requests on CI can occasionally return empty; retry oiyu once.
    highlight = _fetch_latest_playlist_video(EAGLES_HIGHLIGHT_PLAYLIST_ID)
    time.sleep(0.5)
    oiyu = _fetch_latest_playlist_video(EAGLES_OIYU_PLAYLIST_ID)
    if not (oiyu or {}).get("url"):
        time.sleep(1.0)
        oiyu = _fetch_latest_playlist_video(EAGLES_OIYU_PLAYLIST_ID)

    channel_id = ""
    rss_videos: list[Dict[str, str]] = []
    browse_videos: list[Dict[str, str]] = []

    if not (highlight or {}).get("url") or _oiyu_needs_channel_fallback(highlight, oiyu):
        time.sleep(0.4)
        channel_id = _resolve_channel_id_from_handle_page(EAGLES_OFFICIAL_CHANNEL_URL)
        if channel_id:
            rss_videos = _fetch_channel_videos_from_rss(channel_id)

    if not (highlight or {}).get("url") and rss_videos:
        picked_highlight = _highlight_from_channel_videos(rss_videos)
        highlight = _pick_newer_highlight(highlight, picked_highlight)

    if _oiyu_needs_channel_fallback(highlight, oiyu):
        if rss_videos:
            picked = _oiyu_from_channel_matched_to_highlight(rss_videos, highlight)
            if not (picked or {}).get("url"):
                picked = _oiyu_from_channel_by_date_suffix(rss_videos, highlight)
            if (picked or {}).get("url"):
                oiyu = picked

    if not (highlight or {}).get("url") or _oiyu_needs_channel_fallback(highlight, oiyu):
        browse_videos = _fetch_eagles_official_videos_browse()

    if not (highlight or {}).get("url") and browse_videos:
        picked_highlight = _highlight_from_channel_videos(browse_videos)
        highlight = _pick_newer_highlight(highlight, picked_highlight)

    # 재생목록 반영 지연으로 highlight가 오래된 날짜로 남는 경우가 있어,
    # 채널(/videos, RSS)에서 찾은 더 최신 H/L이 있으면 항상 교체한다.
    if rss_videos:
        highlight = _pick_newer_highlight(highlight, _highlight_from_channel_videos(rss_videos))
    if browse_videos:
        highlight = _pick_newer_highlight(highlight, _highlight_from_channel_videos(browse_videos))

    if _oiyu_needs_channel_fallback(highlight, oiyu):
        if not browse_videos:
            browse_videos = _fetch_eagles_official_videos_browse()
        if browse_videos:
            picked = _oiyu_from_channel_matched_to_highlight(browse_videos, highlight)
            if not (picked or {}).get("url"):
                picked = _oiyu_from_channel_by_date_suffix(browse_videos, highlight)
            if (picked or {}).get("url"):
                oiyu = picked

    # Highlight를 최신 날짜로 교체한 뒤, 오이유 날짜가 다시 어긋날 수 있어 마지막에 한 번 더 동기화.
    if _oiyu_needs_channel_fallback(highlight, oiyu):
        for source in (rss_videos, browse_videos):
            if not source:
                continue
            picked = _oiyu_from_channel_matched_to_highlight(source, highlight)
            if not (picked or {}).get("url"):
                picked = _oiyu_from_channel_by_date_suffix(source, highlight)
            if (picked or {}).get("url"):
                oiyu = picked
                break

    return {"highlight": highlight, "oiyu": oiyu}


def _build_naver_article_url(oid: str, aid: str) -> str:
    if not oid or not aid:
        return ""
    return f"https://m.sports.naver.com/kbaseball/article/{oid}/{aid}"


def _fetch_latest_hanwha_news(limit: int = 5) -> list[Dict[str, str]]:
    params = {
        "team": HANWHA_TEAM_ID,
        "page": 1,
        "pageSize": max(1, min(limit, 20)),
        "sort": "MYTEAM",
        "isPhoto": "Y",
        "date_flag": "Y",
        "categoryId": "kbo",
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://m.sports.naver.com/",
    }
    try:
        response = requests.get(
            NAVER_SPORTS_NEWS_API_URL,
            params=params,
            timeout=10,
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    news_list = ((payload.get("result") or {}).get("newsList") or [])[:limit]
    result: list[Dict[str, str]] = []
    for item in news_list:
        oid = str(item.get("oid", "") or "")
        aid = str(item.get("aid", "") or "")
        article_url = _build_naver_article_url(oid, aid)
        if not article_url:
            continue
        result.append(
            {
                "title": str(item.get("title", "") or "").strip(),
                "url": article_url,
                "thumbnail": str(item.get("thumbnail", "") or item.get("image", "") or "").strip(),
                "source_name": str(item.get("sourceName", "") or "").strip(),
                "published_at": str(item.get("dateTime", "") or "").strip(),
            }
        )
    return result


def _fetch_player_profile_for_register(name: str) -> Dict[str, str]:
    player_name = str(name or "").strip()
    if not player_name:
        return {}
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.koreabaseball.com/"}
    try:
        response = requests.post(
            KBO_PLAYER_SEARCH_URL,
            data={"name": player_name},
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        payload = json.loads(response.content.decode("utf-8-sig"))
    except Exception:
        return {}

    candidates = (payload.get("now") or []) + (payload.get("retire") or [])
    if not candidates:
        return {}

    exact = [c for c in candidates if str(c.get("P_NM", "")).strip() == player_name]
    hh = [c for c in exact if str(c.get("T_ID", "")).strip() == HANWHA_TEAM_ID]
    picked = (hh or exact or candidates)[0]
    detail_link = str(picked.get("P_LINK", "") or "").strip()
    if detail_link.startswith("/"):
        detail_link = "https://www.koreabaseball.com" + detail_link
    if not detail_link:
        player_id = str(picked.get("P_ID", "") or "").strip()
        if player_id:
            detail_link = f"https://www.koreabaseball.com/Record/Player/HitterDetail/Basic.aspx?playerId={player_id}"
    if not detail_link:
        return {}

    try:
        detail_resp = requests.get(detail_link, headers=headers, timeout=10)
        detail_resp.raise_for_status()
    except Exception:
        return {}

    soup = BeautifulSoup(detail_resp.text, "html.parser")
    # birth date
    birth_raw = ""
    birth_node = soup.select_one(
        "#cphContents_cphContents_cphContents_playerProfile_lblBirthday, "
        "#cphContents_cphContents_cphContents_ucRetireInfo_lblBirthday"
    )
    if birth_node:
        birth_raw = birth_node.get_text(" ", strip=True)
    birth_match = re.search(r"((19|20)\d{2})\D+(\d{1,2})\D+(\d{1,2})", birth_raw)
    birth_iso = "-"
    if birth_match:
        birth_iso = f"{birth_match.group(1)}-{int(birth_match.group(3)):02d}-{int(birth_match.group(4)):02d}"

    # throws/bats
    ptype = str(picked.get("P_TYPE", "") or "").strip()
    if not ptype:
        pos_node = soup.select_one("#cphContents_cphContents_cphContents_playerProfile_lblPosition")
        pos_text = pos_node.get_text(" ", strip=True) if pos_node else ""
        p_match = re.search(r"([좌우양]투[좌우양]타|[좌우양]언[좌우양]타)", pos_text)
        ptype = p_match.group(1) if p_match else "-"

    # number from search fallback
    number = str(picked.get("BACK_NO", "") or "").strip() or "-"
    return {
        "number": number,
        "throws_bats": ptype or "-",
        "birth_date": birth_iso,
    }


def _fetch_hanwha_register_moves() -> Dict[str, Any]:
    headers = {"User-Agent": "Mozilla/5.0"}
    empty = {"date": "", "registered": [], "deregistered": []}
    try:
        response = requests.get(KBO_REGISTER_ALL_URL, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception:
        return empty

    soup = BeautifulSoup(response.text, "html.parser")
    register_date = ""
    date_match = re.search(r"(\d{4}\.\d{2}\.\d{2}\([월화수목금토일]\))", response.text)
    if date_match:
        register_date = date_match.group(1)
    move_tables = []
    for tb in soup.select("table"):
        headers_text = [th.get_text(" ", strip=True) for th in tb.select("th")]
        if headers_text[:3] == ["선수", "포지션", "팀"]:
            move_tables.append(tb)
    if len(move_tables) < 2:
        return empty

    profile_cache: Dict[str, Dict[str, str]] = {}
    roster_number_by_name: Dict[str, str] = {}
    team_tables = [tb for tb in soup.select("table") if (tb.select_one("th") and "구단" in tb.select_one("th").get_text(" ", strip=True))]
    for tb in team_tables:
        headers_text = [th.get_text(" ", strip=True) for th in tb.select("th")]
        if not any("한화" in h for h in headers_text):
            continue
        row = tb.select_one("tbody tr") or tb.select_one("tr:has(td)")
        if not row:
            continue
        cells = [td.get_text(" ", strip=True) for td in row.select("td")]
        for cell in cells:
            for m in re.finditer(r"([^\s()]+)\((\d{1,3})\)", cell):
                nm = m.group(1).strip()
                no = m.group(2).strip()
                if nm and no:
                    roster_number_by_name[nm] = no
        break

    def parse_rows(tb) -> list[Dict[str, str]]:
        out = []
        for tr in tb.select("tr"):
            tds = [td.get_text(" ", strip=True) for td in tr.select("td")]
            if len(tds) < 3:
                continue
            name = str(tds[0] or "").strip()
            pos = str(tds[1] or "").strip()
            team = str(tds[2] or "").strip()
            if not name or "없습니다" in name:
                continue
            if team not in {"한화", "한화 이글스"}:
                continue
            profile = profile_cache.get(name)
            if profile is None:
                profile = _fetch_player_profile_for_register(name)
                profile_cache[name] = profile
            number = roster_number_by_name.get(name) or str((profile or {}).get("number", "-") or "-")
            out.append(
                {
                    "number": number,
                    "name": name,
                    "position": POSITION_TEXT_MAP.get(pos, pos or "-"),
                    "throws_bats": str((profile or {}).get("throws_bats", "-") or "-"),
                    "birth_date": str((profile or {}).get("birth_date", "-") or "-"),
                }
            )
        return out

    return {
        "date": register_date,
        "registered": parse_rows(move_tables[0]),
        "deregistered": parse_rows(move_tables[1]),
    }


def _parse_lineup_grid_rows(raw_grid_json: str) -> list[Dict[str, str]]:
    if not raw_grid_json:
        return []
    try:
        grid = json.loads(raw_grid_json)
    except Exception:
        return []

    lineup_rows: list[Dict[str, str]] = []
    seen_orders: set[str] = set()
    for row_obj in grid.get("rows", []):
        cells = row_obj.get("row", []) if isinstance(row_obj, dict) else []
        if len(cells) < 3:
            continue
        order = _cell_text(cells[0])
        position = _cell_text(cells[1])
        player_name = _cell_text(cells[2])
        if not order or not player_name:
            continue
        if not re.match(r"^\d+$", order):
            continue
        if order in seen_orders:
            continue
        seen_orders.add(order)
        lineup_rows.append(
            {
                "order": order,
                "position": position,
                "name": player_name,
            }
        )
        if len(lineup_rows) >= 9:
            break
    lineup_rows.sort(key=lambda item: int(item["order"]))
    return lineup_rows


def _fetch_lineup_analysis(game_id: str, season_id: str, sr_id: str) -> Dict[str, Any]:
    if not game_id:
        return {"lineup_ck": False, "away_lineup": [], "home_lineup": []}
    payload = {
        "leId": "1",
        "srId": sr_id or "0",
        "seasonId": season_id or str(date.today().year),
        "gameId": game_id,
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.koreabaseball.com/"}
    try:
        response = requests.post(
            KBO_LINEUP_ANALYSIS_URL,
            data=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        data = json.loads(response.content.decode("utf-8-sig"))
    except Exception:
        return {"lineup_ck": False, "away_lineup": [], "home_lineup": []}

    lineup_ck = False
    away_lineup_raw = ""
    home_lineup_raw = ""
    if isinstance(data, list):
        if len(data) > 0 and isinstance(data[0], list) and data[0]:
            lineup_ck = bool((data[0][0] or {}).get("LINEUP_CK"))
        if len(data) > 4 and isinstance(data[4], list) and data[4]:
            away_lineup_raw = str(data[4][0] or "")
        if len(data) > 3 and isinstance(data[3], list) and data[3]:
            home_lineup_raw = str(data[3][0] or "")
    return {
        "lineup_ck": lineup_ck,
        "away_lineup": _parse_lineup_grid_rows(away_lineup_raw),
        "home_lineup": _parse_lineup_grid_rows(home_lineup_raw),
    }


def _find_latest_finished_hanwha_game(before_date: date, max_days_lookback: int = 14) -> Optional[Dict[str, Any]]:
    for offset in range(1, max_days_lookback + 1):
        target = before_date - timedelta(days=offset)
        try:
            games = _fetch_games(target)
        except Exception:
            continue

        candidates = [g for g in games if _is_hanwha_game(g) and (_is_finished_game(g) or _is_final_game(g))]
        if not candidates:
            continue

        candidates.sort(
            key=lambda g: (
                str(g.get("G_TM", "") or ""),
                str(g.get("G_ID", "") or ""),
            ),
            reverse=True,
        )
        picked = candidates[0]
        picked["_resolved_date"] = target
        return picked
    return None


def _hanwha_game_on_calendar_day(game_day: date) -> Optional[Dict[str, Any]]:
    """Most recent Hanwha game on a calendar day (one ID per day, latest by KBO time if multiple)."""
    try:
        games = _fetch_games(game_day)
    except Exception:
        return None
    candidates = [g for g in games if _is_hanwha_game(g)]
    if not candidates:
        return None
    candidates.sort(
        key=lambda g: (str(g.get("G_TM", "") or ""), str(g.get("G_ID", "") or "")),
        reverse=True,
    )
    g = dict(candidates[0])
    g["_resolved_date"] = game_day
    return g


def _try_prior_calendar_lineup_boxscore(
    target_date: date,
) -> Optional[tuple[date, Dict[str, list[Dict[str, str]]], Dict[str, Any]]]:
    """
    For an upcoming (or not-yet-reliable) game on target_date, prefer the *previous calendar
    day* Hanwha box score. The game list often lags on GAME_STATE/SCORE flags; box score
    is usually up right after the last pitch, so this matches '전날' better than a scan
    that requires SCORE_CK/final in the list API.
    """
    prev = target_date - timedelta(days=1)
    if prev.year < 2000:
        return None
    g = _hanwha_game_on_calendar_day(prev)
    if not g:
        return None
    d = g.get("_resolved_date") or prev
    season_id = str(g.get("SEASON_ID") or d.year)
    game_id = str(g.get("G_ID") or "")
    sr_id = str(g.get("SR_ID") or "0")
    stats = _fetch_hanwha_game_boxscore_stats(game=g, game_date=d)
    if not (stats.get("batters") or stats.get("pitchers")) and game_id:
        # Box score JSON can lag after final; LiveText often fills first.
        stats = _extract_live_text_hanwha_stats(
            game=g,
            season_id=season_id,
            game_id=game_id,
            sr_id=sr_id,
        )
    if not (stats.get("batters") or stats.get("pitchers")):
        return None
    return (d, stats, g)


def _fetch_box_score_scroll(game: Dict[str, Any], game_date: date) -> Dict[str, Any]:
    payload = {
        "leId": "1",
        "srId": str(game.get("SR_ID") or "0"),
        "seasonId": str(game.get("SEASON_ID") or game_date.year),
        "gameId": str(game.get("G_ID") or ""),
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.koreabaseball.com/"}
    try:
        response = requests.post(
            KBO_BOX_SCORE_SCROLL_URL,
            data=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        return json.loads(response.content.decode("utf-8-sig"))
    except Exception:
        return {}


def _text_has_hangul(value: str) -> bool:
    return bool(re.search(r"[가-힣]", value or ""))


def _is_plausible_batter_count(value: str) -> bool:
    """Boxscore 타수/안타/득점에 들어갈 수 있는 토큰."""
    t = (value or "").strip()
    if t in {"", "-"}:
        return True
    if _text_has_hangul(t):
        return False
    return bool(re.match(r"^\d+(\.\d+)?$", t)) or t in {"0", "0.0"}


def _find_stat_row_for_batter(
    player_name: str, stat_row_objects: list, default_idx: int
) -> list[Dict[str, Any]]:
    """
    table1(이름)과 table3(타자기록) 행이 인덱스로 꼭 맞지 않는 경우가 있어,
    table3 셀 전반에서 선수명이 들어가는 행을 먼저 찾는다.
    """
    for i, srow in enumerate(stat_row_objects or []):
        cells = (srow or {}).get("row", []) if isinstance(srow, dict) else []
        for cell in cells[:5]:
            if _cell_text(cell) == player_name:
                return cells
    if 0 <= default_idx < len(stat_row_objects or []):
        srow = stat_row_objects[default_idx] or {}
        return srow.get("row", [])
    return []


def _parse_batter_stats_cells(stat_cells: list, player_name: str) -> tuple[str, str, str, str]:
    t = [_cell_text(c) for c in (stat_cells or [])]
    if not t:
        return ("-", "-", "-", "-")
    for _ in range(2):
        if t and t[0] == player_name and len(t) > 1:
            t = t[1:]
    if t and (not _is_plausible_batter_count(t[0]) or _text_has_hangul(t[0])):
        if len(t) > 1 and _is_plausible_batter_count(t[1]) and not _text_has_hangul(t[1]):
            t = t[1:]
    if len(t) >= 5:
        at_bats, hits, runs, avg = t[0], t[1], t[3], t[4]
    elif len(t) >= 4:
        at_bats, hits, runs, avg = t[0], t[1], t[2], t[3]
    else:
        at_bats = hits = runs = avg = "-"

    def _coerce_count(val: str) -> str:
        s = (val or "").strip()
        if s == player_name or _text_has_hangul(s) or (s and not _is_plausible_batter_count(s)):
            return "-"
        return s or "-"

    at_bats = _coerce_count(str(at_bats))
    hits = _coerce_count(str(hits))
    runs = _coerce_count(str(runs))
    avg = (str(avg) or "-").strip()
    if _text_has_hangul(avg) and avg not in ("-", ""):
        avg = "-"
    return (at_bats, hits, runs, avg)


def _sanitize_merged_batter_line(player_name: str, stat: Dict[str, str]) -> Dict[str, str]:
    """
    by_order/by_name로 붙은 스탯이 선수명(한글)이 섞인 경우 UI에서 타수=이름으로 보이는 문제를 막는다.
    """
    out = {**stat}
    p = (player_name or "").strip()
    for key in ("ab", "hit", "run"):
        v = str(out.get(key, "") or "").strip()
        if not v or v == p or (v and _text_has_hangul(v)):
            out[key] = "-"
    avg = str(out.get("avg", "") or "").strip()
    if avg and _text_has_hangul(avg):
        out["avg"] = "-"
    return out


def _extract_hanwha_boxscore_batters(
    box_data: Dict[str, Any],
    game: Dict[str, Any],
) -> list[Dict[str, str]]:
    if str(box_data.get("code", "")) != "100":
        return []

    arr_hitter = box_data.get("arrHitter", []) or []
    if len(arr_hitter) < 2:
        return []

    hanwha_is_away = game.get("AWAY_ID") == HANWHA_TEAM_ID
    target_idx = 0 if hanwha_is_away else 1
    if target_idx >= len(arr_hitter):
        return []

    try:
        table_names = json.loads(str(arr_hitter[target_idx].get("table1", "{}") or "{}"))
        table_stats = json.loads(str(arr_hitter[target_idx].get("table3", "{}") or "{}"))
    except Exception:
        return []

    name_rows = table_names.get("rows", []) or []
    stat_row_objects = table_stats.get("rows", []) or []
    if not name_rows or not stat_row_objects:
        return []

    row_count = len(name_rows)
    lineup_map: Dict[str, Dict[str, str]] = {}
    for idx in range(row_count):
        name_cells = (name_rows[idx] or {}).get("row", [])
        if len(name_cells) < 3:
            continue

        order = _cell_text(name_cells[0])
        player_name = _cell_text(name_cells[2])
        if not order or not player_name or not re.match(r"^\d+$", order):
            continue
        if order in lineup_map:
            continue

        position = _cell_text(name_cells[1])
        stat_cells = _find_stat_row_for_batter(player_name, stat_row_objects, min(idx, len(stat_row_objects) - 1))
        if len(stat_cells) < 3:
            continue
        at_bats, hits, runs, avg = _parse_batter_stats_cells(stat_cells, player_name)
        lineup_map[order] = {
            "order": order,
            "position": position,
            "name": player_name,
            "ab": at_bats,
            "hit": hits,
            "run": runs,
            "avg": avg,
        }

    batters = [lineup_map[key] for key in sorted(lineup_map.keys(), key=int)]
    return batters[:9]


def _extract_hanwha_boxscore_pitchers(
    box_data: Dict[str, Any],
    game: Dict[str, Any],
) -> list[Dict[str, str]]:
    if str(box_data.get("code", "")) != "100":
        return []

    arr_pitcher = box_data.get("arrPitcher", []) or []
    if len(arr_pitcher) < 2:
        return []

    hanwha_is_away = game.get("AWAY_ID") == HANWHA_TEAM_ID
    target_idx = 0 if hanwha_is_away else 1
    if target_idx >= len(arr_pitcher):
        return []

    try:
        table = json.loads(str(arr_pitcher[target_idx].get("table", "{}") or "{}"))
    except Exception:
        return []

    rows = table.get("rows", []) or []
    if not rows:
        return []

    pitchers: list[Dict[str, str]] = []
    for row in rows:
        cells = (row or {}).get("row", [])
        if len(cells) < 17:
            continue

        name = _cell_text(cells[0])
        if not name or name == "-":
            continue
        pitchers.append(
            {
                "name": name,
                "ip": _cell_text(cells[6]) or "-",
                "hit": _cell_text(cells[10]) or "-",
                "run": _cell_text(cells[14]) or "-",
                "er": _cell_text(cells[15]) or "-",
                "bb": _cell_text(cells[12]) or "-",
                "so": _cell_text(cells[13]) or "-",
                "era": _cell_text(cells[16]) or "-",
            }
        )
    return pitchers


def _fetch_hanwha_game_boxscore_stats(
    game: Dict[str, Any],
    game_date: date,
) -> Dict[str, list[Dict[str, str]]]:
    box_data = _fetch_box_score_scroll(game=game, game_date=game_date)
    return {
        "batters": _extract_hanwha_boxscore_batters(box_data=box_data, game=game),
        "pitchers": _extract_hanwha_boxscore_pitchers(box_data=box_data, game=game),
    }


def _looks_numeric_token(value: str) -> bool:
    token = (value or "").strip()
    return bool(re.match(r"^\d+(\.\d+)?$", token))


def _extract_live_text_hanwha_stats(
    game: Dict[str, Any],
    season_id: str,
    game_id: str,
    sr_id: str,
) -> Dict[str, list[Dict[str, str]]]:
    payload = {
        "leagueId": "1",
        "seriesId": sr_id or "0",
        "gameId": game_id,
        "gyear": season_id or str(date.today().year),
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.koreabaseball.com/"}
    try:
        response = requests.post(KBO_LIVETEXT_VIEW2_URL, data=payload, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception:
        return {"batters": [], "pitchers": []}

    soup = BeautifulSoup(response.text, "html.parser")
    team_name = str(game.get("AWAY_NM") if game.get("AWAY_ID") == HANWHA_TEAM_ID else game.get("HOME_NM") or "")
    lineup_rows: list[list[str]] = []
    batter_rows: list[list[str]] = []
    pitcher_rows: list[list[str]] = []
    pitcher_detail_rows: list[list[str]] = []

    for table in soup.find_all("table"):
        caption_tag = table.find("caption")
        caption = _clean_html_text(caption_tag.get_text(" ", strip=True) if caption_tag else "")
        if not caption or (team_name and team_name not in caption):
            continue

        rows: list[list[str]] = []
        for tr in table.find_all("tr")[1:]:
            cells = [_clean_html_text(td.get_text(" ", strip=True)) for td in tr.find_all("td")]
            if any(cells):
                rows.append(cells)
        if not rows:
            continue

        first = rows[0]
        if "투수" in caption and len(first) >= 5:
            pitcher_rows = rows
            continue
        if len(first) >= 12 and not re.match(r"^\d+$", first[0] or ""):
            ip_token = first[1]
            if _looks_numeric_token(first[2]) and _looks_numeric_token(first[10]) and _looks_numeric_token(first[11]):
                if _looks_numeric_token(ip_token) or "." in ip_token or " " in ip_token:
                    pitcher_detail_rows = rows
                    continue
        if "타" in caption:
            is_lineup_candidate = (
                len(first) >= 5
                and re.match(r"^\d+$", first[0] or "")
                and (
                    (len(first) >= 3 and re.match(r"^\d+$", first[1] or "") and not re.match(r"^\d+$", first[2] or ""))
                    or (len(first) >= 2 and not re.match(r"^\d+$", first[1] or ""))
                )
            )
            is_batter_candidate = (
                len(first) >= 4
                and not re.match(r"^\d+$", first[0] or "")
                and _looks_numeric_token(first[1] if len(first) > 1 else "")
            )

            # Prefer the first clear lineup table to avoid later "타자기록" tables overriding it.
            if is_lineup_candidate and not lineup_rows:
                lineup_rows = rows
                continue
            if is_batter_candidate and not batter_rows:
                batter_rows = rows

    batters: list[Dict[str, str]] = []
    detail_by_name: Dict[str, list[str]] = {}
    for row in batter_rows:
        if len(row) >= 4 and _looks_numeric_token(row[1]) and _looks_numeric_token(row[2]) and _looks_numeric_token(row[3]):
            detail_by_name[row[0]] = row

    for row in lineup_rows:
        if len(row) < 5:
            continue
        if (
            len(row) >= 3
            and re.match(r"^\d+$", row[0] or "")
            and re.match(r"^\d+$", row[1] or "")
            and not re.match(r"^\d+$", row[2] or "")
        ):
            order = row[0]
            name = row[2]
            fallback_ab = row[3] if len(row) > 3 else "-"
            fallback_hit = row[4] if len(row) > 4 else "-"
            fallback_run = row[5] if len(row) > 5 else "-"
        elif re.match(r"^\d+$", row[0] or "") and len(row) >= 2:
            order = row[0]
            name = row[1]
            fallback_ab = row[2] if len(row) > 2 else "-"
            fallback_hit = row[3] if len(row) > 3 else "-"
            fallback_run = row[4] if len(row) > 4 else "-"
        else:
            continue
        if not re.match(r"^\d+$", order):
            continue
        has_detail = name in detail_by_name
        detail = detail_by_name.get(name, row)
        batters.append(
            {
                "order": order,
                "position": "-",
                "name": name,
                "ab": (detail[1] if has_detail and len(detail) > 1 else fallback_ab),
                "hit": (detail[2] if has_detail and len(detail) > 2 else fallback_hit),
                "run": (detail[3] if has_detail and len(detail) > 3 else fallback_run),
                "avg": "-",
            }
        )

    pitchers: list[Dict[str, str]] = []
    for row in pitcher_rows:
        if len(row) < 5:
            continue
        pitchers.append(
            {
                "name": row[0],
                "ip": row[1],
                "hit": row[2],
                "run": row[3],
                "er": row[4],
                "bb": "-",
                "so": "-",
                "era": "-",
            }
        )
    if len(pitchers) <= 1 and pitcher_detail_rows:
        pitchers = []
        for row in pitcher_detail_rows:
            if len(row) < 12:
                continue
            pitchers.append(
                {
                    "name": row[0],
                    "ip": row[1],
                    "hit": row[5],
                    "run": row[10],
                    "er": row[11],
                    "bb": row[7],
                    "so": row[9],
                    "era": "-",
                }
            )

    batters = [
        _sanitize_merged_batter_line(str(b.get("name", "")), b)
        for b in batters
        if b.get("name")
    ]
    batters = sorted(
        batters,
        key=lambda b: int(str(b.get("order", "99")).strip())
        if str(b.get("order", "")).strip().isdigit()
        else 99,
    )
    pitchers = [p for p in pitchers if p.get("name")]
    return {"batters": batters[:9], "pitchers": pitchers}


def _merge_lineup_grid_with_batter_stats(
    lineup_grid: list[Dict[str, Any]],
    stat_batters: list[Dict[str, str]],
) -> list[Dict[str, str]]:
    """
    KBO GetLineUpAnalysis row order (타순·포지션·이름) + box/live 스탯.
    Name match first: LiveText/박스 order 필드는 경기 직후 흔들릴 수 있음.
    """
    stat_batters = stat_batters or []
    by_order: Dict[str, Dict[str, str]] = {
        str(item.get("order") or ""): item
        for item in stat_batters
        if str(item.get("order") or "")
    }
    by_name: Dict[str, Dict[str, str]] = {
        str(item.get("name") or ""): item
        for item in stat_batters
        if str(item.get("name") or "")
    }
    out: list[Dict[str, str]] = []
    for item in lineup_grid[:9]:
        order = str(item.get("order", "-"))
        name = str(item.get("name", "-"))
        stat_src = by_name.get(name) or by_order.get(order) or {}
        stat_src = _sanitize_merged_batter_line(name, stat_src)
        out.append(
            {
                "order": order,
                "position": str(item.get("position", "-") or "-"),
                "name": name,
                "ab": stat_src.get("ab", "-"),
                "hit": stat_src.get("hit", "-"),
                "run": stat_src.get("run", "-"),
                "avg": stat_src.get("avg", "-"),
            }
        )
    return out


def _order_batter_rows_for_display(batters: list) -> list[Dict[str, str]]:
    if not batters:
        return []
    rows: list[Dict[str, str]] = []
    for b in batters:
        if not isinstance(b, dict):
            continue
        name = str(b.get("name", "") or "")
        rows.append(_sanitize_merged_batter_line(name, dict(b)))
    return sorted(
        rows,
        key=lambda b: int(str(b.get("order", "99")).strip())
        if str(b.get("order", "")).strip().isdigit()
        else 99,
    )


def _build_lineup_info(
    game: Dict[str, Any],
    target_date: date,
    season_id: str,
    game_id: str,
    sr_id: str,
) -> Dict[str, Any]:
    is_hanwha_away = game.get("AWAY_ID") == HANWHA_TEAM_ID
    lineup_data = _fetch_lineup_analysis(game_id=game_id, season_id=season_id, sr_id=sr_id)
    today_lineup = lineup_data.get("away_lineup", []) if is_hanwha_away else lineup_data.get("home_lineup", [])
    is_today_target = target_date == _today_kst()
    can_trust_today_lineup = bool(lineup_data.get("lineup_ck")) or _is_live_game(game) or _is_final_game(game)

    # KBO can return full lineup rows while LINEUP_CK remains false.
    # Prefer actual lineup rows when present to avoid stale fallback display.
    if is_today_target and len(today_lineup) >= 9 and can_trust_today_lineup:
        realtime_stats = _fetch_hanwha_game_boxscore_stats(game=game, game_date=target_date)
        if not realtime_stats.get("batters") or not realtime_stats.get("pitchers"):
            live_stats = _extract_live_text_hanwha_stats(
                game=game,
                season_id=season_id,
                game_id=game_id,
                sr_id=sr_id,
            )
            if not realtime_stats.get("batters"):
                realtime_stats["batters"] = live_stats.get("batters", [])
            if not realtime_stats.get("pitchers"):
                realtime_stats["pitchers"] = live_stats.get("pitchers", [])
        if not realtime_stats.get("batters") or not realtime_stats.get("pitchers"):
            prior_cal = _try_prior_calendar_lineup_boxscore(target_date)
            if prior_cal:
                _pd, prior_stats, _pg = prior_cal
                if not realtime_stats.get("batters"):
                    realtime_stats["batters"] = prior_stats.get("batters", [])
                if not realtime_stats.get("pitchers"):
                    realtime_stats["pitchers"] = prior_stats.get("pitchers", [])
        if not realtime_stats.get("batters") or not realtime_stats.get("pitchers"):
            latest_game = _find_latest_finished_hanwha_game(before_date=target_date)
            if latest_game:
                latest_game_date = latest_game.get("_resolved_date") or (target_date - timedelta(days=1))
                fallback_stats = _fetch_hanwha_game_boxscore_stats(game=latest_game, game_date=latest_game_date)
                if not realtime_stats.get("batters"):
                    realtime_stats["batters"] = fallback_stats.get("batters", [])
                if not realtime_stats.get("pitchers"):
                    realtime_stats["pitchers"] = fallback_stats.get("pitchers", [])
        realtime_batters = realtime_stats.get("batters", [])
        realtime_pitchers = realtime_stats.get("pitchers", [])
        merged_batters = _merge_lineup_grid_with_batter_stats(today_lineup, realtime_batters)
        return {
            "is_official": True,
            "notice": "",
            "source_game_date": target_date.isoformat(),
            "batters": merged_batters,
            "pitchers": realtime_pitchers,
        }

    prior_first = _try_prior_calendar_lineup_boxscore(target_date)
    if prior_first:
        latest_game_date, fallback_stats, _ = prior_first
    else:
        latest_game = _find_latest_finished_hanwha_game(before_date=target_date)
        if not latest_game:
            return {
                "is_official": False,
                "notice": "아직 라인업이 발표되지 않아 전날 라인업을 보여드립니다.",
                "source_game_date": "",
                "batters": [],
                "pitchers": [],
            }

        latest_game_date = latest_game.get("_resolved_date") or (target_date - timedelta(days=1))
        fallback_stats = _fetch_hanwha_game_boxscore_stats(game=latest_game, game_date=latest_game_date)
    probe_date = latest_game_date
    while (
        not fallback_stats.get("batters")
        and not fallback_stats.get("pitchers")
        and probe_date > (target_date - timedelta(days=14))
    ):
        older_game = _find_latest_finished_hanwha_game(before_date=probe_date)
        if not older_game:
            break
        older_date = older_game.get("_resolved_date") or (probe_date - timedelta(days=1))
        fallback_stats = _fetch_hanwha_game_boxscore_stats(game=older_game, game_date=older_date)
        latest_game_date = older_date
        probe_date = older_date
    fallback_batters = fallback_stats.get("batters", []) or []
    g_day = _hanwha_game_on_calendar_day(latest_game_date)
    display_batters: list[Dict[str, str]] = []
    if g_day and str(g_day.get("G_ID") or ""):
        is_hw_away = g_day.get("AWAY_ID") == HANWHA_TEAM_ID
        prior_lineup_data = _fetch_lineup_analysis(
            game_id=str(g_day.get("G_ID") or ""),
            season_id=str(g_day.get("SEASON_ID") or latest_game_date.year),
            sr_id=str(g_day.get("SR_ID") or "0"),
        )
        prior_grid = (
            prior_lineup_data.get("away_lineup", []) if is_hw_away else prior_lineup_data.get("home_lineup", [])
        )
        if len(prior_grid) >= 1:
            display_batters = _merge_lineup_grid_with_batter_stats(prior_grid, fallback_batters)
    if not display_batters:
        display_batters = _order_batter_rows_for_display(fallback_batters)
    return {
        "is_official": False,
        "notice": "아직 라인업이 발표되지 않아 전날 라인업을 보여드립니다.",
        "source_game_date": latest_game_date.isoformat(),
        "batters": display_batters,
        "pitchers": fallback_stats.get("pitchers", []),
    }


def _parse_pitcher_name_from_detail_html(html: str) -> str:
    try:
        soup = BeautifulSoup(html, "html.parser")
        name_el = soup.find(id=re.compile(r"lblName$", re.I))
        if name_el:
            return (name_el.get_text() or "").strip()
    except Exception:
        return ""
    return ""


def _fetch_pitcher_name_from_player_id(player_id: str) -> str:
    """Resolve display name when GetKboGameList has T/B_PIT_P_ID but empty T/B_PIT_P_NM."""
    pid = str(player_id or "").strip()
    if not pid or pid.lower() == "none":
        return ""
    cached = _PITCHER_NAME_CACHE.get(pid)
    if isinstance(cached, str) and cached:
        return cached

    headers = {
        **_kbo_api_headers(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        response = _http_get_with_retries(
            PITCHER_DETAIL_URL,
            params={"playerId": pid},
            headers=headers,
            timeout=14,
            retries=3,
        )
        response.raise_for_status()
        response.encoding = "utf-8"
        name = _parse_pitcher_name_from_detail_html(response.text)
    except Exception:
        name = ""

    if name and not _is_missing_starter_name(name):
        _PITCHER_NAME_CACHE[pid] = name
    return name


def _resolve_starter_name_with_player_id(name: str, player_id: str) -> str:
    token = (name or "").strip()
    if not _is_missing_starter_name(token):
        return token
    pid = str(player_id or "").strip()
    if not pid or pid.lower() == "none":
        return token
    resolved = _fetch_pitcher_name_from_player_id(pid)
    return resolved.strip() if resolved else token


def _fetch_pitcher_stats(player_id: str) -> Dict[str, str]:
    if not player_id:
        return {}

    headers = {
        **_kbo_api_headers(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        response = _http_get_with_retries(
            PITCHER_DETAIL_URL,
            params={"playerId": player_id},
            headers=headers,
            timeout=14,
            retries=3,
        )
        response.raise_for_status()
        response.encoding = "utf-8"
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

    image_url = ""
    birth_date = ""
    age_text = "-"
    player_name = ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        player_name = _parse_pitcher_name_from_detail_html(html)
        if player_name and not _is_missing_starter_name(player_name):
            _PITCHER_NAME_CACHE[str(player_id).strip()] = player_name
        # KBO player detail uses id like:
        # cphContents_cphContents_cphContents_playerProfile_imgProgile
        profile_img = soup.find(id=re.compile(r"imgProgile$", re.I))
        if profile_img:
            image_url = (profile_img.get("src") or "").strip()
        if not image_url:
            fallback_img = soup.select_one("img[src*='/KBO_IMAGE/person/middle/']")
            if fallback_img:
                image_url = (fallback_img.get("src") or "").strip()
        # Try to extract birth date from profile text (e.g. 1998년 03월 12일).
        plain_text = soup.get_text(" ", strip=True)
        birth_match = re.search(r"생년월일[^0-9]*(\d{4})\D+(\d{1,2})\D+(\d{1,2})", plain_text)
        if birth_match:
            year = int(birth_match.group(1))
            month = int(birth_match.group(2))
            day = int(birth_match.group(3))
            birth_dt = date(year, month, day)
            birth_date = birth_dt.isoformat()
            today_kst = _today_kst()
            age = today_kst.year - birth_dt.year - ((today_kst.month, today_kst.day) < (birth_dt.month, birth_dt.day))
            age_text = str(age if age >= 0 else "-")
    except Exception:
        image_url = ""
        birth_date = ""
        age_text = "-"
        player_name = ""

    if image_url.startswith("//"):
        image_url = "https:" + image_url
    elif image_url.startswith("/"):
        image_url = "https://www.koreabaseball.com" + image_url

    return {
        "name": player_name,
        "era": basic.get("ERA", "-"),
        "wins": basic.get("W", "-"),
        "losses": basic.get("L", "-"),
        "war": "-",
        "games": basic.get("G", "-"),
        "avg_innings": basic.get("IP", "-"),
        "qs": advanced.get("QS", "-"),
        "whip": advanced.get("WHIP", "-"),
        "image_url": image_url,
        "birth_date": birth_date,
        "age": age_text,
    }


def _fetch_pitcher_record_analysis(
    season_id: str,
    sr_id: str,
    away_team_id: str,
    away_pit_id: str,
    home_team_id: str,
    home_pit_id: str,
) -> Dict[str, Dict[str, str]]:
    payload = {
        "leId": "1",
        "srId": sr_id or "0",
        "seasonId": season_id or str(date.today().year),
        "awayTeamId": away_team_id or "",
        "awayPitId": away_pit_id or "",
        "homeTeamId": home_team_id or "",
        "homePitId": home_pit_id or "",
        "groupSc": "SEASON",
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.koreabaseball.com/"}
    empty = {"away": {}, "home": {}}
    try:
        response = requests.post(
            KBO_PITCHER_RECORD_ANALYSIS_URL,
            data=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        data = json.loads(response.content.decode("utf-8-sig"))
    except Exception:
        return empty

    rows = data.get("rows", []) if isinstance(data, dict) else []
    if not isinstance(rows, list) or len(rows) < 2:
        return empty

    def parse_row(row_obj: Dict[str, Any]) -> Dict[str, str]:
        row_cells = row_obj.get("row", []) if isinstance(row_obj, dict) else []
        if not isinstance(row_cells, list):
            return {}
        parsed = {"war": "-", "games": "-", "avg_innings": "-", "qs": "-", "whip": "-"}
        for cell in row_cells:
            cls = str((cell or {}).get("Class") or "")
            text = _cell_text(cell) or "-"
            if "td_war_" in cls:
                parsed["war"] = text
            elif "td_game_" in cls:
                parsed["games"] = text
            elif "td_startinn_" in cls.lower():
                parsed["avg_innings"] = text
            elif "td_qs_" in cls:
                parsed["qs"] = text
            elif "td_whip_" in cls:
                parsed["whip"] = text
        return parsed

    return {
        "away": parse_row(rows[0]),
        "home": parse_row(rows[1]),
    }


def _fetch_live_starter_names(game_id: str, season_id: str, sr_id: str) -> Dict[str, str]:
    """
    Parse LiveTextView2 boxscore and read first pitcher row for each team.
    This is used when live games don't expose starter in GetKboGameList payload.
    """
    payload = {
        "leagueId": "1",
        "seriesId": sr_id or "0",
        "gameId": game_id,
        "gyear": season_id or str(date.today().year),
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.koreabaseball.com/"}

    try:
        response = requests.post(KBO_LIVETEXT_VIEW2_URL, data=payload, headers=headers, timeout=10)
        response.raise_for_status()
    except Exception:
        return {}

    soup = BeautifulSoup(response.text, "html.parser")
    pitchers: list[str] = []
    for table in soup.find_all("table"):
        caption = table.find("caption")
        caption_text = caption.get_text(" ", strip=True) if caption else ""
        if "투수" not in caption_text:
            continue
        for row in table.find_all("tr")[1:]:
            tds = row.find_all("td")
            if not tds:
                continue
            name = tds[0].get_text(" ", strip=True)
            if name and name != "-":
                pitchers.append(name)
                break
        if len(pitchers) >= 2:
            break

    if len(pitchers) >= 2:
        return {"away_starter": pitchers[0], "home_starter": pitchers[1]}
    return {}


def _fetch_pitcher_birth_year(player_id: str) -> str:
    pid = str(player_id or "").strip()
    if not pid:
        return ""
    cached = _PITCHER_BIRTH_YEAR_CACHE.get(pid, "")
    if cached:
        return cached
    stats = _fetch_pitcher_stats(pid)
    birth_date = str(stats.get("birth_date") or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", birth_date):
        year = birth_date[:4]
        _PITCHER_BIRTH_YEAR_CACHE[pid] = year
        return year
    return ""


def _resolve_pitcher_id_from_search(player_name: str, team_id: str, birth_year_hint: str = "") -> str:
    """
    Resolve playerId from KBO player search endpoint.
    Prefer active roster and team match.
    """
    player_name = (player_name or "").strip()
    if not player_name or player_name == "미정":
        return ""

    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.koreabaseball.com/"}
    try:
        response = requests.post(
            KBO_PLAYER_SEARCH_URL,
            data={"name": player_name},
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        payload = json.loads(response.content.decode("utf-8-sig"))
    except Exception:
        return ""

    candidates = payload.get("now", []) or []
    if not candidates:
        candidates = payload.get("retire", []) or []

    if not candidates:
        return ""

    filtered = [p for p in candidates if str(p.get("T_ID", "")) == str(team_id)]
    target_pool = filtered if filtered else candidates

    # 동명이인 대응: 나무위키 링크에 "(YYYY)" 힌트가 있으면 해당 출생연도로 우선 매칭한다.
    if birth_year_hint and len(target_pool) > 1:
        for cand in target_pool:
            cand_pid = str(cand.get("P_ID", "")).strip()
            if not cand_pid:
                link = str(cand.get("P_LINK", "") or "")
                m = re.search(r"playerId=(\d+)", link)
                cand_pid = m.group(1) if m else ""
            if not cand_pid:
                continue
            if _fetch_pitcher_birth_year(cand_pid) == birth_year_hint:
                return cand_pid

    target = target_pool[0]
    player_id = str(target.get("P_ID", "")).strip()
    if player_id:
        return player_id

    link = str(target.get("P_LINK", "") or "")
    m = re.search(r"playerId=(\d+)", link)
    return m.group(1) if m else ""


def _fetch_team_rank_daily() -> Dict[str, Any]:
    """Fetch team rankings from Naver Sports API and head-to-head from KBO page."""
    season = str(date.today().year)
    naver_headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://m.sports.naver.com/",
    }

    rankings: list[dict[str, str]] = []
    rank_date = datetime.now().strftime("%Y.%m.%d")
    try:
        ranking_resp = requests.get(
            NAVER_KBO_TEAM_RANK_URL.format(season=season),
            timeout=10,
            headers=naver_headers,
        )
        ranking_resp.raise_for_status()
        ranking_payload = ranking_resp.json()
        season_team_stats = (
            (ranking_payload.get("result") or {}).get("seasonTeamStats") or []
        )

        last10_resp = requests.get(
            NAVER_KBO_LAST10_URL.format(season=season),
            timeout=10,
            headers=naver_headers,
        )
        last10_resp.raise_for_status()
        last10_payload = last10_resp.json()
        last10_stats = (
            (last10_payload.get("result") or {}).get("seasonTeamLastTenGameStats") or []
        )
        def _safe_text(value: Any) -> str:
            return "-" if value is None or value == "" else str(value)

        last10_by_team: Dict[str, str] = {}
        for item in last10_stats:
            team_id = str(item.get("teamId", "") or "")
            win = item.get("lastTenGameWinGameCount")
            draw = item.get("lastTenGameDrawnGameCount")
            lose = item.get("lastTenGameLoseGameCount")
            if win is not None and draw is not None and lose is not None:
                last10_by_team[team_id] = f"{win}승 {draw}무 {lose}패"
            else:
                last10_by_team[team_id] = _safe_text(item.get("lastTenGameResult"))

        for item in season_team_stats:
            team_id = str(item.get("teamId", "") or "")
            win_rate = item.get("wra")
            emblem_team_id = team_id or TEAM_NAME_TO_ID.get(_safe_text(item.get("teamName")), "")
            emblem_url = (
                f"{KBO_EMBLEM_BASE}/{season}/emblem_{emblem_team_id}.png" if emblem_team_id else ""
            )
            rankings.append(
                {
                    "rank": _safe_text(item.get("ranking")),
                    "team_name": _safe_text(item.get("teamName")),
                    "team_id": team_id,
                    "games": _safe_text(item.get("gameCount")),
                    "wins": _safe_text(item.get("winGameCount")),
                    "losses": _safe_text(item.get("loseGameCount")),
                    "draws": _safe_text(item.get("drawnGameCount")),
                    "win_rate": f"{float(win_rate):.3f}" if win_rate is not None else "-",
                    "games_behind": _safe_text(item.get("gameBehind")),
                    "last10": last10_by_team.get(team_id, "-"),
                    "streak": _safe_text(item.get("continuousGameResult")),
                    "emblem": emblem_url,
                }
            )
    except Exception:
        rankings = []

    # Keep using KBO matrix for head-to-head summary in team comparison card.
    try:
        response = requests.get(
            KBO_TEAM_RANK_DAILY_URL,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception:
        return {"rankings": [], "head_to_head": [], "rank_date": ""}

    tables = soup.find_all("table")
    if len(tables) < 2:
        return {"rankings": rankings, "head_to_head": [], "rank_date": rank_date}

    head_to_head: list[dict[str, str]] = []
    h2h_table = tables[1]
    headers = [th.get_text(" ", strip=True) for th in h2h_table.find_all("th")]
    for tr in h2h_table.find_all("tr"):
        tds = tr.find_all("td")
        if not tds:
            continue
        row = [td.get_text(" ", strip=True) for td in tds]
        if len(row) < 2:
            continue
        team_name = row[0]
        record_map: Dict[str, str] = {}
        for idx, value in enumerate(row[1:], start=1):
            if idx >= len(headers):
                break
            col_team = re.sub(r"\s*\(.*\)$", "", headers[idx]).strip()
            if col_team and col_team != "합계":
                record_map[col_team] = value
        head_to_head.append({"team_name": team_name, "records": record_map})

    return {"rankings": rankings, "head_to_head": head_to_head, "rank_date": rank_date}


def _find_head_to_head_record(
    head_to_head_rows: list[dict[str, Any]], away_team: str, home_team: str
) -> Dict[str, str]:
    away_vs_home = "-"
    home_vs_away = "-"
    for row in head_to_head_rows:
        team = row.get("team_name", "")
        records = row.get("records", {})
        if team == away_team:
            away_vs_home = records.get(home_team, "-")
        if team == home_team:
            home_vs_away = records.get(away_team, "-")
    return {"away_vs_home": away_vs_home, "home_vs_away": home_vs_away}


def has_hanwha_game_on_date(target_date: date) -> bool:
    try:
        games = _fetch_games(target_date)
    except Exception:
        return False
    return any(_is_hanwha_game(game) for game in games)


def _format_series_date_range(start_date: date, end_date: date) -> str:
    if start_date == end_date:
        return f"{start_date.month}/{start_date.day}"
    if start_date.month == end_date.month:
        return f"{start_date.month}/{start_date.day}~{end_date.day}"
    return f"{start_date.month}/{start_date.day}~{end_date.month}/{end_date.day}"


def _collect_hanwha_games(start_date: date, end_date: date) -> list[Dict[str, Any]]:
    games: list[Dict[str, Any]] = []
    cursor = start_date
    while cursor <= end_date:
        try:
            day_games = _fetch_games(cursor)
        except Exception:
            cursor += timedelta(days=1)
            continue

        for game in day_games:
            if not _is_hanwha_game(game):
                continue
            is_away = game.get("AWAY_ID") == HANWHA_TEAM_ID
            opponent_name = game.get("HOME_NM") if is_away else game.get("AWAY_NM")
            opponent_team_id = game.get("HOME_ID") if is_away else game.get("AWAY_ID")
            season_id = str(game.get("SEASON_ID") or date.today().year)
            games.append(
                {
                    "date": cursor,
                    "opponent": str(opponent_name or "").strip(),
                    "opponent_team_id": str(opponent_team_id or "").strip(),
                    "stadium": str(game.get("S_NM") or "").strip(),
                    "hanwha_home_away": "원정" if is_away else "홈",
                    "season_id": season_id,
                }
            )
        cursor += timedelta(days=1)

    games.sort(key=lambda item: item["date"])
    return games


def _build_hanwha_series(games: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    if not games:
        return []

    series_list: list[Dict[str, Any]] = []
    current = {
        "opponent": games[0]["opponent"],
        "opponent_team_id": games[0]["opponent_team_id"],
        "start_date": games[0]["date"],
        "end_date": games[0]["date"],
        "game_count": 1,
        "stadium": games[0]["stadium"],
        "hanwha_home_away": games[0]["hanwha_home_away"],
        "season_id": games[0]["season_id"],
    }

    for game in games[1:]:
        day_gap = (game["date"] - current["end_date"]).days
        same_opponent = game["opponent"] == current["opponent"]
        if same_opponent and day_gap in {0, 1}:
            current["end_date"] = game["date"]
            current["game_count"] += 1
            continue

        series_list.append(current)
        current = {
            "opponent": game["opponent"],
            "opponent_team_id": game["opponent_team_id"],
            "start_date": game["date"],
            "end_date": game["date"],
            "game_count": 1,
            "stadium": game["stadium"],
            "hanwha_home_away": game["hanwha_home_away"],
            "season_id": game["season_id"],
        }

    series_list.append(current)
    return series_list


def _serialize_series(series: Dict[str, Any]) -> Dict[str, Any]:
    start_date = series["start_date"]
    end_date = series["end_date"]
    season_id = str(series.get("season_id") or date.today().year)
    opponent_team_id = str(series.get("opponent_team_id") or "")
    return {
        "opponent": series["opponent"],
        "opponent_team_id": opponent_team_id,
        "date_range": _format_series_date_range(start_date, end_date),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "game_count": series["game_count"],
        "stadium": series.get("stadium", ""),
        "hanwha_home_away": series.get("hanwha_home_away", ""),
        "hanwha_emblem": f"{KBO_EMBLEM_BASE}/{season_id}/emblem_{HANWHA_TEAM_ID}.png",
        "opponent_emblem": (
            f"{KBO_EMBLEM_BASE}/{season_id}/emblem_{opponent_team_id}.png"
            if opponent_team_id
            else ""
        ),
    }


def _resolve_hanwha_series(target_date: date, target_opponent: str, max_days_ahead: int) -> Dict[str, Any]:
    # Include a short look-back window so an ongoing series can be detected reliably.
    schedule_start = target_date - timedelta(days=7)
    schedule_end = target_date + timedelta(days=max_days_ahead + 10)
    games = _collect_hanwha_games(schedule_start, schedule_end)
    series_list = _build_hanwha_series(games)
    if not series_list:
        return {"current_series": None, "next_series": None}

    current_idx = -1
    for idx, series in enumerate(series_list):
        in_range = series["start_date"] <= target_date <= series["end_date"]
        if not in_range:
            continue
        if target_opponent and series["opponent"] and series["opponent"] != target_opponent:
            continue
        current_idx = idx
        break

    if current_idx < 0:
        for idx, series in enumerate(series_list):
            if series["start_date"] >= target_date:
                current_idx = idx
                break

    if current_idx < 0:
        return {"current_series": None, "next_series": None}

    current_series = _serialize_series(series_list[current_idx])
    next_series = (
        _serialize_series(series_list[current_idx + 1])
        if current_idx + 1 < len(series_list)
        else None
    )
    return {"current_series": current_series, "next_series": next_series}


def _hanwha_game_result(game: Dict[str, Any]) -> str:
    if _is_cancelled_game(game):
        return "취소"
    if not _is_final_game(game):
        return ""
    try:
        away = int(str(game.get("T_SCORE_CN", "0") or "0"))
        home = int(str(game.get("B_SCORE_CN", "0") or "0"))
    except Exception:
        return ""
    if away == home:
        return "무"
    hanwha_score = away if game.get("AWAY_ID") == HANWHA_TEAM_ID else home
    opp_score = home if game.get("AWAY_ID") == HANWHA_TEAM_ID else away
    return "승" if hanwha_score > opp_score else "패"


def _serialize_hanwha_schedule_game(game: Dict[str, Any], target_date: date) -> Dict[str, Any]:
    is_away = game.get("AWAY_ID") == HANWHA_TEAM_ID
    away_team = str(game.get("AWAY_NM", "") or "").strip()
    home_team = str(game.get("HOME_NM", "") or "").strip()
    opponent_name = home_team if is_away else away_team
    away_score = str(game.get("T_SCORE_CN", "") or "").strip()
    home_score = str(game.get("B_SCORE_CN", "") or "").strip()
    hanwha_score = away_score if is_away else home_score
    opponent_score = home_score if is_away else away_score
    state = str(game.get("GAME_STATE_SC", "") or "").strip()
    return {
        "date": target_date.isoformat(),
        "game_id": str(game.get("G_ID", "") or "").strip(),
        "game_time": str(game.get("G_TM", "") or "").strip(),
        "stadium": str(game.get("S_NM", "") or "").strip(),
        "home_away": "원정" if is_away else "홈",
        "opponent": opponent_name,
        "opponent_team_id": str(game.get("HOME_ID") if is_away else game.get("AWAY_ID") or "").strip(),
        "away_team": away_team,
        "home_team": home_team,
        "away_score": away_score,
        "home_score": home_score,
        "hanwha_score": hanwha_score,
        "opponent_score": opponent_score,
        "is_live": state == "2" and not _is_cancelled_game(game),
        "is_final": state in {"3", "4"} or _is_cancelled_game(game),
        "result": _hanwha_game_result(game),
        "cancel_label": _game_cancel_label(game),
    }


def _collect_hanwha_season_schedule(
    season_id: str, *, include_november: bool = True
) -> list[Dict[str, Any]]:
    try:
        season_year = int(str(season_id or "").strip())
    except Exception:
        season_year = _today_kst().year
    start_date = date(season_year, 3, 1)
    end_date = date(season_year, 11 if include_november else 10, 30)
    items: list[Dict[str, Any]] = []
    cursor = start_date
    while cursor <= end_date:
        try:
            games = _fetch_games(cursor)
        except Exception:
            cursor += timedelta(days=1)
            continue
        for game in games:
            if _is_hanwha_game(game):
                items.append(_serialize_hanwha_schedule_game(game, cursor))
        cursor += timedelta(days=1)
    items.sort(key=lambda x: x.get("date", ""))
    return items


def _league_game_outcome_label(game: Dict[str, Any]) -> str:
    """전 구단 경기 카드용: 원정승 / 홈승 / 무 / 취소 / 진행중 / 미표시(빈 문자열)."""
    if _is_cancelled_game(game):
        return "취소"
    if _is_live_game(game):
        return "진행중"
    if not _is_final_game(game):
        return ""
    try:
        away = int(str(game.get("T_SCORE_CN", "0") or "0"))
        home = int(str(game.get("B_SCORE_CN", "0") or "0"))
    except Exception:
        return ""
    if away > home:
        return "원정승"
    if home > away:
        return "홈승"
    return "무"


def _serialize_yesterday_league_game_row(
    game: Dict[str, Any], *, game_date_iso: str, season_fallback: str
) -> Dict[str, Any]:
    away_id = str(game.get("AWAY_ID", "") or "").strip()
    home_id = str(game.get("HOME_ID", "") or "").strip()
    season_id = str(game.get("SEASON_ID", "") or "").strip() or season_fallback
    state = str(game.get("GAME_STATE_SC", "") or "").strip()
    is_live = state == "2" and not _is_cancelled_game(game)
    is_final = state in {"3", "4"} or _is_cancelled_game(game)
    outcome = _league_game_outcome_label(game)
    cancel_label = _game_cancel_label(game) if outcome == "취소" else ""
    away_score = str(game.get("T_SCORE_CN", "") or "").strip()
    home_score = str(game.get("B_SCORE_CN", "") or "").strip()
    if outcome == "취소" and not away_score and not home_score:
        away_score, home_score = "", ""
    elif outcome in {"", "진행중"} and not away_score and not home_score:
        away_score, home_score = "-", "-"
    return {
        "date": game_date_iso,
        "game_id": str(game.get("G_ID", "") or "").strip(),
        "season_id": season_id,
        "game_time": str(game.get("G_TM", "") or "").strip(),
        "stadium": str(game.get("S_NM", "") or "").strip(),
        "away_team": str(game.get("AWAY_NM", "") or "").strip(),
        "home_team": str(game.get("HOME_NM", "") or "").strip(),
        "away_team_id": away_id,
        "home_team_id": home_id,
        "away_score": away_score,
        "home_score": home_score,
        "is_live": is_live,
        "is_final": is_final,
        "result": outcome,
        "cancel_label": cancel_label,
        "home_away": "",
    }


def _fetch_league_scoreboard_for_date(target: date) -> tuple[str, list[Dict[str, Any]]]:
    """지정일 KBO 전 경기(종료·진행·취소) 요약."""
    ymd = target.isoformat()
    season_fallback = str(target.year)
    try:
        raw_games = _fetch_games(target)
    except Exception:
        return ymd, []
    rows: list[Dict[str, Any]] = []
    for game in raw_games:
        if not isinstance(game, dict):
            continue
        gid = str(game.get("G_ID", "") or "").strip()
        if not gid:
            continue
        outcome = _league_game_outcome_label(game)
        if not outcome:
            continue
        rows.append(
            _serialize_yesterday_league_game_row(
                game, game_date_iso=ymd, season_fallback=season_fallback
            )
        )
    rows.sort(key=lambda r: (str(r.get("game_time", "")), str(r.get("game_id", ""))))
    return ymd, rows


def _should_show_today_league_scoreboard(today: date) -> bool:
    """
    한화 당일 경기가 아직 예정(1)이면 어제 전체 결과를, 시작·종료 이후면 당일 결과를 보여준다.
    """
    game = _hanwha_game_on_calendar_day(today)
    if not game:
        return False
    state = str(game.get("GAME_STATE_SC", "") or "").strip()
    if state == "1":
        return False
    if _is_live_game(game) or _is_final_game(game):
        return True
    if _is_finished_game(game):
        return True
    return False


def _resolve_league_results_scoreboard(today: date) -> tuple[str, list[Dict[str, Any]]]:
    target = today if _should_show_today_league_scoreboard(today) else today - timedelta(days=1)
    return _fetch_league_scoreboard_for_date(target)


def _get_hanwha_season_schedule_cached(season_id: str) -> list[Dict[str, Any]]:
    key = str(season_id or _today_kst().year)
    now_ts = time.time()
    cached = _HANWHA_SEASON_SCHEDULE_CACHE.get(key) or {}
    cached_at = float(cached.get("cached_at", 0.0) or 0.0)
    if cached and (now_ts - cached_at) <= _HANWHA_SEASON_SCHEDULE_CACHE_TTL_SEC:
        data = cached.get("data")
        if isinstance(data, list):
            return data
    data = _collect_hanwha_season_schedule(key, include_november=True)
    _HANWHA_SEASON_SCHEDULE_CACHE[key] = {"cached_at": now_ts, "data": data}
    return data


def _resolve_game_starter_names(
    game: Dict[str, Any], target: date
) -> tuple[str, str, str, str]:
    """Resolve away/home starter names (and IDs) using the same fallbacks as get_next_hanwha_game."""
    away_starter = (game.get("T_PIT_P_NM") or "").strip()
    home_starter = (game.get("B_PIT_P_NM") or "").strip()
    away_starter_id = str(game.get("T_PIT_P_ID") or "").strip()
    home_starter_id = str(game.get("B_PIT_P_ID") or "").strip()
    if away_starter_id.lower() == "none":
        away_starter_id = ""
    if home_starter_id.lower() == "none":
        home_starter_id = ""
    season_id = str(game.get("SEASON_ID", ""))
    game_id = str(game.get("G_ID", ""))
    sr_id = str(game.get("SR_ID", "0"))

    away_starter = _resolve_starter_name_with_player_id(away_starter, away_starter_id)
    home_starter = _resolve_starter_name_with_player_id(home_starter, home_starter_id)

    if game_id and (_is_missing_starter_name(away_starter) or _is_missing_starter_name(home_starter)):
        live_starters = _fetch_live_starter_names(game_id=game_id, season_id=season_id, sr_id=sr_id)
        away_starter = live_starters.get("away_starter", away_starter)
        home_starter = live_starters.get("home_starter", home_starter)

    if game_id and (
        not away_starter_id
        or not home_starter_id
        or _is_missing_starter_name(away_starter)
        or _is_missing_starter_name(home_starter)
    ):
        latest_game = _fetch_game_by_game_id(game_id)
        if latest_game:
            away_starter_id = str(latest_game.get("T_PIT_P_ID") or away_starter_id).strip()
            home_starter_id = str(latest_game.get("B_PIT_P_ID") or home_starter_id).strip()
            if away_starter_id.lower() == "none":
                away_starter_id = ""
            if home_starter_id.lower() == "none":
                home_starter_id = ""
            away_starter = (latest_game.get("T_PIT_P_NM") or "").strip() or away_starter
            home_starter = (latest_game.get("B_PIT_P_NM") or "").strip() or home_starter
            away_starter = _resolve_starter_name_with_player_id(away_starter, away_starter_id)
            home_starter = _resolve_starter_name_with_player_id(home_starter, home_starter_id)

    away_birth_year_hint = ""
    home_birth_year_hint = ""
    if _is_missing_starter_name(away_starter) or _is_missing_starter_name(home_starter):
        namu_starters = _fetch_namu_wiki_starters_for_game(
            target,
            str(game.get("AWAY_ID", "")),
            str(game.get("HOME_ID", "")),
        )
        if _is_missing_starter_name(away_starter) and namu_starters.get("away_starter"):
            away_starter = namu_starters["away_starter"]
            away_birth_year_hint = str(namu_starters.get("away_starter_birth_year") or "").strip()
        if _is_missing_starter_name(home_starter) and namu_starters.get("home_starter"):
            home_starter = namu_starters["home_starter"]
            home_birth_year_hint = str(namu_starters.get("home_starter_birth_year") or "").strip()

    if not away_starter_id and not _is_missing_starter_name(away_starter):
        away_starter_id = _resolve_pitcher_id_from_search(
            away_starter, str(game.get("AWAY_ID", "")), away_birth_year_hint
        )
    if not home_starter_id and not _is_missing_starter_name(home_starter):
        home_starter_id = _resolve_pitcher_id_from_search(
            home_starter, str(game.get("HOME_ID", "")), home_birth_year_hint
        )

    # Right before falling back to "미정", do one more forced Namu check (cache bypass)
    # to reduce stale-cache misses around lineup update timing.
    if _is_missing_starter_name(away_starter) or _is_missing_starter_name(home_starter):
        namu_retry = _fetch_namu_wiki_starters_for_game(
            target,
            str(game.get("AWAY_ID", "")),
            str(game.get("HOME_ID", "")),
            force_refresh=True,
        )
        if _is_missing_starter_name(away_starter) and namu_retry.get("away_starter"):
            away_starter = namu_retry["away_starter"]
        if _is_missing_starter_name(home_starter) and namu_retry.get("home_starter"):
            home_starter = namu_retry["home_starter"]

    away_starter = away_starter.strip() if away_starter else ""
    home_starter = home_starter.strip() if home_starter else ""
    if _is_missing_starter_name(away_starter):
        away_starter = "미정"
    if _is_missing_starter_name(home_starter):
        home_starter = "미정"
    return away_starter, home_starter, away_starter_id, home_starter_id


def _game_both_starters_published(game: Dict[str, Any], target: date) -> bool:
    away_starter, home_starter, _, _ = _resolve_game_starter_names(game, target)
    return not _is_missing_starter_name(away_starter) and not _is_missing_starter_name(home_starter)


def _find_hanwha_game_with_published_starters_on_date(target: date) -> Optional[Dict[str, Any]]:
    """Next scheduled Hanwha game on ``target`` where both starters are known."""
    try:
        games = _fetch_games(target)
    except Exception:
        return None
    for game in games:
        if not _is_hanwha_game(game):
            continue
        if _is_cancelled_game(game):
            continue
        if _game_both_starters_published(game, target):
            return game
    return None


def _build_same_day_probable_games(target: date, hanwha_game_id: str) -> list[Dict[str, Any]]:
    """Build non-Hanwha same-day game cards with probable starters."""
    try:
        games = _fetch_games(target)
    except Exception:
        return []

    rows: list[Dict[str, Any]] = []
    for game in games:
        game_id = str(game.get("G_ID", "") or "")
        if not game_id or game_id == hanwha_game_id:
            continue
        if _is_hanwha_game(game):
            continue
        if _is_cancelled_game(game):
            continue

        away_starter, home_starter, away_starter_id, home_starter_id = _resolve_game_starter_names(game, target)
        away_starter = away_starter if not _is_missing_starter_name(away_starter) else "미정"
        home_starter = home_starter if not _is_missing_starter_name(home_starter) else "미정"

        rows.append(
            {
                "date": target.strftime("%Y-%m-%d"),
                "game_id": game_id,
                "season_id": str(game.get("SEASON_ID", "") or ""),
                "game_time": str(game.get("G_TM", "") or ""),
                "stadium": str(game.get("S_NM", "") or ""),
                "away_team": str(game.get("AWAY_NM", "") or ""),
                "home_team": str(game.get("HOME_NM", "") or ""),
                "away_team_id": str(game.get("AWAY_ID", "") or ""),
                "home_team_id": str(game.get("HOME_ID", "") or ""),
                "away_starter": away_starter,
                "home_starter": home_starter,
                "away_starter_id": away_starter_id,
                "home_starter_id": home_starter_id,
            }
        )

    rows.sort(key=lambda x: str(x.get("game_time", "")))
    return rows


def get_next_hanwha_game(max_days_ahead: int = 30) -> Optional[Dict[str, Any]]:
    rank_daily = _fetch_team_rank_daily()
    eagles_tv = _fetch_eagles_tv_latest()
    latest_news = _fetch_latest_hanwha_news(limit=5)
    register_moves = _fetch_hanwha_register_moves()
    today = _today_kst()
    league_results_ymd, league_results_games = _resolve_league_results_scoreboard(today)

    for offset in range(max_days_ahead + 1):
        target = today + timedelta(days=offset)
        games = _fetch_games(target)
        for game in games:
            if not _is_hanwha_game(game):
                continue
            # Skip today's game once it is over so "다음 경기" is tomorrow (KST). SCORE_CK can appear
            # before the first pitch; only treat non-scheduled(1) finished scores as "done".
            if offset == 0:
                if _is_cancelled_game(game):
                    # 우천취소 등: 익일 경기 선발이 공개돼 있으면 익일 경기를 메인으로 표시한다.
                    if _find_hanwha_game_with_published_starters_on_date(target + timedelta(days=1)):
                        continue
                else:
                    if _is_final_game(game):
                        continue
                    if _is_finished_game(game) and not _is_live_game(game):
                        if (str(game.get("GAME_STATE_SC", "") or "").strip() != "1"):
                            continue

            is_away = game.get("AWAY_ID") == HANWHA_TEAM_ID
            opponent_name = game.get("HOME_NM") if is_away else game.get("AWAY_NM")
            season_id = str(game.get("SEASON_ID", ""))
            game_id = str(game.get("G_ID", ""))
            sr_id = str(game.get("SR_ID", "0"))
            away_starter, home_starter, away_starter_id, home_starter_id = _resolve_game_starter_names(
                game, target
            )

            # Final fallback: resolve starter IDs by name via player search endpoint.
            if not away_starter_id:
                away_starter_id = _resolve_pitcher_id_from_search(away_starter, str(game.get("AWAY_ID", "")))
            if not home_starter_id:
                home_starter_id = _resolve_pitcher_id_from_search(home_starter, str(game.get("HOME_ID", "")))

            away_starter_stats = _fetch_pitcher_stats(away_starter_id)
            home_starter_stats = _fetch_pitcher_stats(home_starter_id)
            if _is_missing_starter_name(away_starter):
                away_starter = (away_starter_stats.get("name") or "").strip() or away_starter
            if _is_missing_starter_name(home_starter):
                home_starter = (home_starter_stats.get("name") or "").strip() or home_starter
            if _is_missing_starter_name(away_starter):
                away_starter = "미정"
            if _is_missing_starter_name(home_starter):
                home_starter = "미정"

            hanwha_starter = away_starter if is_away else home_starter
            if _is_missing_starter_name(hanwha_starter):
                hanwha_starter = _extract_hanwha_starter(game) or "미정"
            away_team_id = str(game.get("AWAY_ID", ""))
            home_team_id = str(game.get("HOME_ID", ""))
            analysis_stats = _fetch_pitcher_record_analysis(
                season_id=season_id,
                sr_id=sr_id,
                away_team_id=away_team_id,
                away_pit_id=away_starter_id,
                home_team_id=home_team_id,
                home_pit_id=home_starter_id,
            )
            away_analysis = analysis_stats.get("away", {})
            home_analysis = analysis_stats.get("home", {})
            if not away_starter_stats:
                away_starter_stats = {}
            if not home_starter_stats:
                home_starter_stats = {}
            away_starter_stats["war"] = away_analysis.get("war") or away_starter_stats.get("war") or "-"
            home_starter_stats["war"] = home_analysis.get("war") or home_starter_stats.get("war") or "-"
            team_comparison = _fetch_team_comparison(game_id, season_id, away_team_id, home_team_id)
            head_to_head_summary = _find_head_to_head_record(
                rank_daily.get("head_to_head", []),
                game.get("AWAY_NM", ""),
                game.get("HOME_NM", ""),
            )
            live_status = _build_live_status(game, game.get("AWAY_NM", ""), game.get("HOME_NM", ""))
            series_info = _resolve_hanwha_series(
                target_date=target,
                target_opponent=opponent_name or "",
                max_days_ahead=max_days_ahead,
            )
            lineup_info = _build_lineup_info(
                game=game,
                target_date=target,
                season_id=season_id,
                game_id=game_id,
                sr_id=sr_id,
            )
            weather_info = _build_game_weather_info(
                target_date=target,
                game_time=str(game.get("G_TM", "") or ""),
                stadium_name=str(game.get("S_NM", "") or ""),
            )
            season_schedule = _get_hanwha_season_schedule_cached(season_id)
            league_probable_games = _build_same_day_probable_games(target, game_id)

            return {
                "season_id": season_id,
                "game_id": game_id,
                "game_date": game.get("G_DT_TXT", ""),
                "game_date_ymd": target.strftime("%Y-%m-%d"),
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
                "away_starter_image": (
                    away_starter_stats.get("image_url")
                    or (_face_image_url(season_id, away_starter_id) if away_starter_id else "")
                ),
                "home_starter_image": (
                    home_starter_stats.get("image_url")
                    or (_face_image_url(season_id, home_starter_id) if home_starter_id else "")
                ),
                "away_starter_stats": away_starter_stats,
                "home_starter_stats": home_starter_stats,
                "team_comparison": team_comparison,
                "head_to_head_summary": head_to_head_summary,
                "team_rankings": rank_daily.get("rankings", []),
                "team_rank_date": rank_daily.get("rank_date", ""),
                "live_status": live_status,
                "current_series": series_info.get("current_series"),
                "next_series": series_info.get("next_series"),
                "lineup_info": lineup_info,
                "register_moves": register_moves,
                "weather_info": weather_info,
                "eagles_tv": eagles_tv,
                "latest_news": latest_news,
                "season_schedule": season_schedule,
                "league_probable_date": target.strftime("%Y-%m-%d"),
                "league_probable_games": league_probable_games,
                "league_results_date": league_results_ymd,
                "league_results_games": league_results_games,
            }
    return None
