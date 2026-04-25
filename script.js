let game = window.__NEXT_GAME__;
let updatedAt = window.__UPDATED_AT__ || "";
const container = document.getElementById("game-content");
let pollTimer = null;
let schedulerTimer = null;
let lastWindowProbeDate = "";

if (!container) throw new Error("game-content container not found");

const renderPitcherCard = (teamLabel, name, image, stats) => `
    <article class="pitcher-card">
      <img src="${image || "./thumbnail.png"}" alt="${name} 선수 사진" loading="lazy" />
      <div class="pitcher-body">
        <h3>${teamLabel}: ${name}</h3>
        <div class="starter-record">시즌 승/패: ${stats?.wins || "-"}승 ${stats?.losses || "-"}패</div>
        <div class="stats-grid">
          <span>ERA</span><strong>${stats?.era || "-"}</strong>
          <span>WAR</span><strong>${stats?.war || "-"}</strong>
          <span>경기</span><strong>${stats?.games || "-"}</strong>
          <span>평균이닝</span><strong>${stats?.avg_innings || "-"}</strong>
          <span>QS</span><strong>${stats?.qs || "-"}</strong>
          <span>WHIP</span><strong>${stats?.whip || "-"}</strong>
        </div>
      </div>
    </article>
  `;

const renderLiveHeader = (g) => {
  const live = g?.live_status;
  const tc = g?.team_comparison;
  if (!live?.is_live) return "";
  return `
    <section class="live-header">
      <div class="live-team">
        <img src="${tc?.away_emblem || ""}" alt="${g.away_team}" class="live-emblem" />
        <span>${g.away_team}</span>
      </div>
      <div class="live-score-wrap">
        <div class="live-score">${live.away_score || "0"} : ${live.home_score || "0"}</div>
        <div class="live-inning">${live.inning_text || "경기중"}</div>
      </div>
      <div class="live-team">
        <img src="${tc?.home_emblem || ""}" alt="${g.home_team}" class="live-emblem" />
        <span>${g.home_team}</span>
      </div>
      <div class="live-players">
        <span>현재 투수: ${live.current_pitcher_team || ""} ${live.current_pitcher || "-"}</span>
        <span>현재 타자: ${live.current_batter_team || ""} ${live.current_batter || "-"}</span>
      </div>
    </section>
  `;
};

const WEATHER_ICON_MAP = {
  sun: "☀️",
  partly: "⛅",
  cloud: "☁️",
  rain: "🌧️",
  snow: "❄️",
  fog: "🌫️",
  storm: "⛈️",
};

const getDustGradeMeta = (value, kind) => {
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return { grade: "-", emoji: "❔" };
  }
  if (kind === "pm25") {
    if (n <= 15) return { grade: "좋음", emoji: "😊" };
    if (n <= 35) return { grade: "보통", emoji: "🙂" };
    if (n <= 75) return { grade: "나쁨", emoji: "😷" };
    return { grade: "매우 나쁨", emoji: "🤢" };
  }
  if (n <= 30) return { grade: "좋음", emoji: "😊" };
  if (n <= 80) return { grade: "보통", emoji: "🙂" };
  if (n <= 150) return { grade: "나쁨", emoji: "😷" };
  return { grade: "매우 나쁨", emoji: "🤢" };
};

const renderWeatherSection = (g) => {
  const weather = g?.weather_info;
  if (!weather || !Array.isArray(weather.hourly) || weather.hourly.length === 0) return "";
  const pm10Value = weather?.dust?.pm10 || "-";
  const pm25Value = weather?.dust?.pm2_5 || "-";
  const pm10Computed = getDustGradeMeta(pm10Value, "pm10");
  const pm10Meta = {
    grade: weather?.dust?.grade || pm10Computed.grade,
    emoji: pm10Computed.emoji,
  };
  const pm25Meta = getDustGradeMeta(pm25Value, "pm25");

  const hourlyItems = weather.hourly.map((item) => `
      <article class="weather-hour-item${item.is_game_start ? " weather-hour-item-game-start" : ""}">
        <div class="weather-time-row">
          <span class="weather-time">${item.time_label || "-"}</span>
        </div>
        <div class="weather-icon">${WEATHER_ICON_MAP[item.icon] || "🌤️"}</div>
        <div class="weather-desc">${item.weather || "-"}</div>
        <div class="weather-pop">강수 ${item.rain_probability ?? "-"}%</div>
        <div class="weather-temp">${item.temperature && item.temperature !== "-" ? `${item.temperature}°C` : "-"}</div>
      </article>
    `).join("");

  return `
    <section class="weather-section">
      <h2 class="cmp-title">경기장 날씨</h2>
      <div class="weather-summary">
        <div class="weather-summary-row">
          <div class="weather-summary-item">지역: ${weather.region || "-"}</div>
          <div class="weather-summary-item">경기 진행 확률: <strong>${weather.game_progress_probability ?? "-"}%</strong></div>
        </div>
        <div class="weather-summary-row">
          <div class="weather-summary-item">
            미세먼지(PM10): ${pm10Value}㎍/m3 · ${pm10Meta.grade} ${pm10Meta.emoji}
          </div>
          <div class="weather-summary-item">
            초미세먼지(PM2.5): ${pm25Value}㎍/m3 · ${pm25Meta.grade} ${pm25Meta.emoji}
          </div>
        </div>
      </div>
      <div class="weather-hourly-wrap">
        <div class="weather-hourly-grid">
          ${hourlyItems}
        </div>
      </div>
    </section>
  `;
};

const renderTeamComparison = (tc, awayName, homeName, headToHead) => {
    if (!tc || !tc.away || !tc.home) return "";

    const { away, home } = tc;

    const statRow = (label, awayVal, homeVal, awayWin, homeWin) => `
      <tr>
        <td class="cmp-val${awayWin ? " cmp-win" : ""}">${awayVal}</td>
        <td class="cmp-label">${label}</td>
        <td class="cmp-val${homeWin ? " cmp-win" : ""}">${homeVal}</td>
      </tr>
    `;

    const last5Row = (awayLast5, homeLast5) => {
      const dots = (seq) => seq.split("").map(c => {
        if (c === "승") return `<span class="dot win">승</span>`;
        if (c === "패") return `<span class="dot loss">패</span>`;
        return `<span class="dot draw">무</span>`;
      }).join("");
      return `
        <tr>
          <td class="cmp-val">${dots(awayLast5)}</td>
          <td class="cmp-label">최근 5경기</td>
          <td class="cmp-val">${dots(homeLast5)}</td>
        </tr>
      `;
    };

    return `
      <section class="cmp-section">
        <h2 class="cmp-title">팀 전력 비교</h2>
        <table class="cmp-table">
          <thead>
            <tr>
              <th class="cmp-team">
                <img src="${tc.away_emblem}" alt="${awayName}" class="emblem" />
                <span>${awayName}</span>
              </th>
              <th class="cmp-label-head"></th>
              <th class="cmp-team">
                <img src="${tc.home_emblem}" alt="${homeName}" class="emblem" />
                <span>${homeName}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            ${statRow("상대전적(시즌)", headToHead?.away_vs_home || "-", headToHead?.home_vs_away || "-", false, false)}
            ${statRow("시즌 성적", away.season_record, home.season_record, false, false)}
            ${last5Row(away.last5, home.last5)}
            ${statRow("평균자책점", away.era, home.era, away.era_win, home.era_win)}
            ${statRow("타율", away.avg, home.avg, away.avg_win, home.avg_win)}
            ${statRow("평균득점", away.runs_scored, home.runs_scored, away.runs_scored_win, home.runs_scored_win)}
            ${statRow("평균실점", away.runs_allowed, home.runs_allowed, away.runs_allowed_win, home.runs_allowed_win)}
          </tbody>
        </table>
      </section>
    `;
  };

const renderTeamRankings = (rankings, rankDate) => {
  if (!Array.isArray(rankings) || rankings.length === 0) return "";
    const rows = rankings.map((row) => {
      const isHanwha = row?.team_id === "HH" || (row?.team_name || "").includes("한화");
      return `
      <tr class="${isHanwha ? "hanwha-row" : ""}">
        <td>${row.rank || "-"}</td>
        <td class="rank-team">
          ${row.emblem ? `<img src="${row.emblem}" alt="${row.team_name}" class="rank-emblem" />` : ""}
          <span>${row.team_name || "-"}</span>
        </td>
        <td>${row.games || "-"}</td>
        <td>${row.wins || "-"}</td>
        <td>${row.losses || "-"}</td>
        <td>${row.draws || "-"}</td>
        <td>${row.win_rate || "-"}</td>
        <td>${row.games_behind || "-"}</td>
        <td>${row.last10 || "-"}</td>
        <td>${row.streak || "-"}</td>
      </tr>
    `;
    }).join("");

    return `
      <section class="rank-section">
        <h2 class="cmp-title">KBO 팀 순위 ${rankDate ? `(${rankDate} 기준)` : ""}</h2>
        <div class="rank-table-wrap">
          <table class="rank-table">
            <thead>
              <tr>
                <th>순위</th>
                <th>팀명</th>
                <th>경기</th>
                <th>승</th>
                <th>패</th>
                <th>무</th>
                <th>승률</th>
                <th>게임차</th>
                <th>최근10경기</th>
                <th>연속</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      </section>
    `;
  };

const renderSeriesSection = (g) => {
  const currentSeries = g?.current_series;
  const nextSeries = g?.next_series;
  if (!currentSeries && !nextSeries) return "";

  const findRankByTeamName = (teamName) => {
    const rankings = Array.isArray(g?.team_rankings) ? g.team_rankings : [];
    const found = rankings.find((row) => (row?.team_name || "") === teamName);
    return found?.rank ? `${found.rank}위` : "-";
  };

  const renderSeriesCard = (title, series) => {
    if (!series) {
      return `
        <article class="series-card">
          <h3>${title}</h3>
          <div class="series-empty">-</div>
        </article>
      `;
    }

    const renderTeam = (name, emblem, fallbackAlt) => `
      <div class="series-team">
        ${emblem ? `<img src="${emblem}" alt="${fallbackAlt}" class="series-emblem" />` : ""}
        <div class="series-team-text">
          <span class="series-team-name">${name || "-"}</span>
          <span class="series-team-rank">(${findRankByTeamName(name || "-")})</span>
        </div>
      </div>
    `;

    return `
      <article class="series-card">
        <h3>${title}</h3>
        <div class="series-matchup">
          ${renderTeam("한화", series.hanwha_emblem, "한화")}
          <span class="series-vs">vs</span>
          ${renderTeam(series.opponent || "-", series.opponent_emblem, series.opponent || "상대팀")}
        </div>
        <div class="series-meta">일정: ${formatSeriesDateRangeWithWeekday(series)}</div>
        <div class="series-meta">장소: ${series.stadium || "-"} (${series.hanwha_home_away || "-"})</div>
      </article>
    `;
  };

  return `
    <section class="series-section">
      <h2 class="cmp-title">한화 시리즈 일정</h2>
      <div class="series-grid">
        ${renderSeriesCard("현재 시리즈", currentSeries)}
        ${renderSeriesCard("다음 시리즈", nextSeries)}
      </div>
    </section>
  `;
};

const renderEaglesTvSection = (g) => {
  const tv = g?.eagles_tv || {};
  const items = [
    { key: "highlight", label: "하이라이트", data: tv.highlight || {} },
    { key: "oiyu", label: "오이유", data: tv.oiyu || {} },
  ];

  const cards = items.map((item) => {
    const video = item.data || {};
    if (!video.url) {
      return `
        <article class="eagles-tv-card">
          <h3>${item.label}</h3>
          <div class="eagles-tv-empty">최신 영상을 불러오지 못했습니다.</div>
        </article>
      `;
    }

    const published = formatUpdatedAt(video.published_at || "");
    return `
      <article class="eagles-tv-card">
        <h3>${item.label}</h3>
        <a href="${video.url}" target="_blank" rel="noopener noreferrer" class="eagles-tv-link">
          ${video.thumbnail ? `<img src="${video.thumbnail}" alt="${item.label} 썸네일" class="eagles-tv-thumb" loading="lazy" />` : ""}
          <div class="eagles-tv-meta">
            <div class="eagles-tv-title">${video.title || "-"}</div>
            <div class="eagles-tv-date">${published}</div>
          </div>
        </a>
      </article>
    `;
  }).join("");

  return `
    <section class="eagles-tv-section">
      <h2 class="cmp-title">최신 Eagles TV</h2>
      <div class="eagles-tv-grid">
        ${cards}
      </div>
    </section>
  `;
};

const renderLatestNewsSection = (g) => {
  const newsList = Array.isArray(g?.latest_news) ? g.latest_news : [];
  const cards = newsList.slice(0, 5).map((news) => `
      <article class="news-card">
        <a href="${news.url || "#"}" target="_blank" rel="noopener noreferrer" class="news-link">
          ${news.thumbnail ? `<img src="${news.thumbnail}" alt="뉴스 썸네일" class="news-thumb" loading="lazy" />` : ""}
          <div class="news-meta">
            <div class="news-title">${news.title || "-"}</div>
            <div class="news-sub">${news.source_name || "-"}</div>
            <div class="news-time">${formatUpdatedAt(news.published_at || "")}</div>
          </div>
        </a>
      </article>
    `).join("");

  return `
    <section class="news-section">
      <h2 class="cmp-title">최신 뉴스</h2>
      <div class="news-grid">
        ${cards || `<div class="news-empty">최신 뉴스를 불러오지 못했습니다.</div>`}
      </div>
    </section>
  `;
};

const renderLineupSection = (g) => {
  const lineup = g?.lineup_info;
  if (!lineup) return "";
  const tc = g?.team_comparison;
  const awayTeamName = g?.away_team || "-";
  const homeTeamName = g?.home_team || "-";
  const awayEmblem = tc?.away_emblem || "";
  const homeEmblem = tc?.home_emblem || "";

  const batters = Array.isArray(lineup.batters) ? lineup.batters : [];
  const rows = batters.map((b) => `
      <tr>
        <td>${b.order || "-"}</td>
        <td>${b.position || "-"}</td>
        <td class="lineup-player">${b.name || "-"}</td>
        <td>${b.ab || "-"}</td>
        <td>${b.hit || "-"}</td>
        <td>${b.run || "-"}</td>
        <td>${b.avg || "-"}</td>
      </tr>
    `).join("");
  const pitchers = Array.isArray(lineup.pitchers) ? lineup.pitchers : [];
  const pitcherRows = pitchers.map((p) => `
      <tr>
        <td class="lineup-player">${p.name || "-"}</td>
        <td>${p.ip || "-"}</td>
        <td>${p.hit || "-"}</td>
        <td>${p.run || "-"}</td>
        <td>${p.er || "-"}</td>
        <td>${p.bb || "-"}</td>
        <td>${p.so || "-"}</td>
        <td>${p.era || "-"}</td>
      </tr>
    `).join("");

  const sourceDate = lineup.source_game_date
    ? ` (기준 경기일: ${lineup.source_game_date})`
    : "";
  const lineupDateSummary = (() => {
    const dateText = g?.game_date || "-";
    if (/\([일월화수목금토]\)/.test(dateText)) return dateText;
    const match = String(g?.game_date_ymd || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!match) return dateText;
    const dt = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    if (Number.isNaN(dt.getTime())) return dateText;
    return `${dateText} (${KOR_WEEKDAYS[dt.getDay()]})`;
  })();
  const notice = lineup.is_official
    ? ""
    : `<div class="lineup-notice">${lineup.notice || "아직 라인업이 발표되지 않아 전날 라인업을 보여드립니다."}${sourceDate}</div>`;

  return `
    <section class="lineup-section">
      <h2 class="cmp-title">라인업 정보</h2>
      <div class="lineup-summary">
        <div class="lineup-summary-matchup">
          <span class="lineup-summary-team">
            ${awayEmblem ? `<img src="${awayEmblem}" alt="${awayTeamName}" class="lineup-summary-emblem" />` : ""}
            <strong>${awayTeamName}</strong>
          </span>
          <span class="lineup-summary-vs">vs</span>
          <span class="lineup-summary-team">
            ${homeEmblem ? `<img src="${homeEmblem}" alt="${homeTeamName}" class="lineup-summary-emblem" />` : ""}
            <strong>${homeTeamName}</strong>
          </span>
        </div>
        <div class="lineup-summary-date">${lineupDateSummary}</div>
      </div>
      ${notice}
      <div class="lineup-table-wrap">
        <table class="lineup-table">
          <thead>
            <tr>
              <th>타순</th>
              <th>포지션</th>
              <th>선수명</th>
              <th>타수</th>
              <th>안타</th>
              <th>득점</th>
              <th>타율</th>
            </tr>
          </thead>
          <tbody>
            ${rows || `<tr><td colspan="7" class="lineup-empty">라인업 정보를 불러오지 못했습니다.</td></tr>`}
          </tbody>
        </table>
      </div>
      <div class="lineup-pitcher-title">투수 성적</div>
      <div class="lineup-table-wrap">
        <table class="lineup-table">
          <thead>
            <tr>
              <th>선수명</th>
              <th>이닝</th>
              <th>피안타</th>
              <th>실점</th>
              <th>자책</th>
              <th>4사구</th>
              <th>삼진</th>
              <th>평균자책</th>
            </tr>
          </thead>
          <tbody>
            ${pitcherRows || `<tr><td colspan="8" class="lineup-empty">투수 성적 정보를 불러오지 못했습니다.</td></tr>`}
          </tbody>
        </table>
      </div>
    </section>
  `;
};

const formatUpdatedAt = (value) => {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ko-KR", { hour12: false });
};

const KOR_WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];

const parseYmdAsLocalDate = (ymd) => {
  if (!ymd || typeof ymd !== "string") return null;
  const match = ymd.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const dt = new Date(year, month - 1, day);
  return Number.isNaN(dt.getTime()) ? null : dt;
};

const formatMonthDayWithWeekday = (date) =>
  `${date.getMonth() + 1}/${date.getDate()}(${KOR_WEEKDAYS[date.getDay()]})`;

const formatSeriesDateRangeWithWeekday = (series) => {
  const start = parseYmdAsLocalDate(series?.start_date || "");
  const end = parseYmdAsLocalDate(series?.end_date || "");
  if (!start || !end) return series?.date_range || "-";

  if (start.getTime() === end.getTime()) {
    return formatMonthDayWithWeekday(start);
  }

  const sameMonth =
    start.getFullYear() === end.getFullYear() &&
    start.getMonth() === end.getMonth();
  const endText = sameMonth
    ? `${end.getDate()}(${KOR_WEEKDAYS[end.getDay()]})`
    : formatMonthDayWithWeekday(end);

  return `${formatMonthDayWithWeekday(start)}~${endText}`;
};

const formatGameDateWithWeekday = (gameDateText, gameDateYmd) => {
  if (!gameDateText) return "-";
  if (/\([일월화수목금토]\)/.test(gameDateText)) return gameDateText;
  const dt = parseYmdAsLocalDate(gameDateYmd || "");
  if (!dt) return gameDateText;
  return `${gameDateText} (${KOR_WEEKDAYS[dt.getDay()]})`;
};

const renderGame = (g, refreshedAt) => {
  if (!g) {
    container.innerHTML = "<p>가까운 일정에서 한화 이글스 경기 정보를 찾지 못했습니다.</p>";
    return;
  }

  container.innerHTML = `
    <div class="updated-at">마지막 갱신: ${formatUpdatedAt(refreshedAt)}</div>
    ${renderLiveHeader(g)}
    <div class="row"><span class="label">경기일:</span>${formatGameDateWithWeekday(g.game_date, g.game_date_ymd)}</div>
    <div class="row"><span class="label">경기시간:</span>${g.game_time}</div>
    <div class="row"><span class="label">대진:</span>${g.matchup}</div>
    <div class="row"><span class="label">구장:</span>${g.stadium}</div>
    <div class="row"><span class="label">한화 홈/원정:</span>${g.hanwha_home_away}</div>
    <div class="row"><span class="label">상대팀:</span>${g.opponent}</div>
    <div class="row"><span class="label">한화 선발투수:</span>${g.hanwha_starter}</div>
    <div class="sub">
      <div class="pitcher-grid">
        ${renderPitcherCard("원정팀 선발", g.away_starter, g.away_starter_image, g.away_starter_stats)}
        ${renderPitcherCard("홈팀 선발", g.home_starter, g.home_starter_image, g.home_starter_stats)}
      </div>
    </div>
    ${renderWeatherSection(g)}
    ${renderTeamComparison(g.team_comparison, g.away_team, g.home_team, g.head_to_head_summary)}
    ${renderLineupSection(g)}
    ${renderSeriesSection(g)}
    ${renderEaglesTvSection(g)}
    ${renderLatestNewsSection(g)}
    ${renderTeamRankings(g.team_rankings, g.team_rank_date)}
  `;
};

const shouldStartPolling = (g) => {
  if (!g) return false;
  if (g?.live_status?.is_live) return true;

  const nowKst = new Date(Date.now() + 9 * 60 * 60 * 1000);
  const todayKst = nowKst.toISOString().slice(0, 10);
  const minutesKst = nowKst.getUTCHours() * 60 + nowKst.getUTCMinutes();
  const inLiveWindow = minutesKst >= (18 * 60 + 30) || minutesKst <= (1 * 60 + 59);

  // Keep polling in KST live window when today's game exists
  // or while final state is still settling into next game data.
  return (
    inLiveWindow &&
    (g.game_date_ymd === todayKst || Boolean(g?.live_status?.is_final))
  );
};

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
};

const refreshGameInfo = async () => {
  try {
    let payload = null;

    // Dynamic backend path (Flask)
    try {
      const response = await fetch("/api/game-info", { cache: "no-store" });
      if (response.ok) {
        payload = await response.json();
      }
    } catch (err) {
      // Fall through to static payload for GitHub Pages.
    }

    // Static fallback path (GitHub Pages)
    if (!payload?.ok) {
      const fallbackResponse = await fetch(`./game-data.json?t=${Date.now()}`, {
        cache: "no-store",
      });
      if (!fallbackResponse.ok) return;
      payload = await fallbackResponse.json();
    }

    if (!payload?.ok) return;
    game = payload.game_info || null;
    updatedAt = payload.updated_at || new Date().toISOString();
    renderGame(game, updatedAt);
  } catch (err) {
    // Keep last rendered data when a transient refresh failure happens.
    console.debug("live refresh failed", err);
  }
};

const startPolling = () => {
  if (pollTimer) return;
  refreshGameInfo();
  pollTimer = setInterval(refreshGameInfo, 60 * 1000);
};

const schedulerTick = () => {
  const nowKst = new Date(Date.now() + 9 * 60 * 60 * 1000);
  const todayKst = nowKst.toISOString().slice(0, 10);
  const minutesKst = nowKst.getUTCHours() * 60 + nowKst.getUTCMinutes();
  const inLiveWindow = minutesKst >= (18 * 60 + 30) || minutesKst <= (1 * 60 + 59);

  // At live window start, probe once even if current data is stale.
  if (inLiveWindow && lastWindowProbeDate !== todayKst) {
    lastWindowProbeDate = todayKst;
    refreshGameInfo();
  }

  if (shouldStartPolling(game)) {
    startPolling();
  } else {
    stopPolling();
  }
};

renderGame(game, updatedAt);
schedulerTick();
schedulerTimer = setInterval(schedulerTick, 30 * 1000);
