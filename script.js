let game = window.__NEXT_GAME__;
let updatedAt = window.__UPDATED_AT__ || "";
const container = document.getElementById("game-content");
let pollTimer = null;
let schedulerTimer = null;
let lastWindowProbeDate = "";
let scheduleCalendarMonth = "";
let holidayCalendarData = null;
/** 등/말소가 당일 비어 있을 때 직전에 표시했던 변동 내역을 유지한다. */
let lastRegisterMovesSnapshot = null;
let sunShadeEscapeListenerAttached = false;
let sunShadeImgLoadToken = 0;

if (!container) throw new Error("game-content container not found");

const isStarterUndecided = (name) => {
  const t = String(name || "").trim();
  return !t || t === "-" || t === "미정" || t === "TBD" || t === "예정";
};

const renderPitcherCard = (teamLabel, name, image, stats, emblemUrl) => {
  const useEmblem = isStarterUndecided(name) && Boolean(emblemUrl);
  const imgSrc = useEmblem ? emblemUrl : image || "./thumbnail.png";
  const imgAlt = useEmblem ? `${teamLabel} 팀 엠블럼` : `${name} 선수 사진`;
  const cardMod = useEmblem ? " pitcher-card--emblem-pending" : "";
  const imgMod = useEmblem ? " pitcher-card-img--emblem" : "";
  const birthDate = stats?.birth_date || "-";
  const age = stats?.age || "-";
  const profileText = `${birthDate} / 만 ${age}세`;
  return `
    <article class="pitcher-card${cardMod}">
      <img src="${imgSrc}" alt="${imgAlt}" class="pitcher-card-img${imgMod}" loading="lazy" />
      <div class="pitcher-body">
        <h3>${teamLabel}: ${name}</h3>
        <div class="starter-profile">${profileText}</div>
        <div class="starter-record">시즌 승/패: ${stats?.wins || "-"}승 ${stats?.losses || "-"}패</div>
        <div class="stats-grid">
          <span>ERA</span><strong>${stats?.era || "-"}</strong>
          <span>WAR</span><strong>${stats?.war || "-"}</strong>
          <span>경기</span><strong>${stats?.games || "-"}</strong>
          <span>이닝</span><strong>${stats?.avg_innings || "-"}</strong>
          <span>QS</span><strong>${stats?.qs || "-"}</strong>
          <span>WHIP</span><strong>${stats?.whip || "-"}</strong>
        </div>
      </div>
    </article>
  `;
};

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
      <div class="live-sync-note">약 30분마다 한번씩만 경기내용이 동기화되니 참고만 부탁드립니다.</div>
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

/** `sun/` 폴더 이미지 파일명(홈구단 기준)과 구장 표기 */
const SHADE_SUN_STADIUMS = [
  { team: "한화", stadium: "대전 한화생명볼파크", imageFile: "한화.png" },
  { team: "두산", stadium: "서울 잠실야구장 (두산 홈)", imageFile: "두산.png" },
  { team: "KT", stadium: "수원 KT위즈파크", imageFile: "kt.png" },
  { team: "SSG", stadium: "인천 SSG 랜더스필드", imageFile: "SSG.png" },
  { team: "NC", stadium: "창원 NC파크", imageFile: "NC.png" },
  { team: "삼성", stadium: "대구 삼성라이온즈파크", imageFile: "삼성.png" },
  { team: "KIA", stadium: "광주 챔피언스 필드", imageFile: "KIA.png" },
  { team: "롯데", stadium: "부산 사직야구장", imageFile: "롯데.png" },
  { team: "LG", stadium: "서울 잠실야구장 (LG 홈)", imageFile: "LG.png" },
];

const escapeHtml = (s) =>
  String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

/** 그늘 참고 이미지를 원본 픽셀 크기로 새 창에서 연다. 새 창에서 이미지 클릭 시 창을 닫는다. */
const openSunshadeImageOriginalViewer = (src) => {
  const token = String(src || "").trim();
  if (!token) return;
  const absSrc = new URL(token, window.location.href).href;
  const w = window.open("", "_blank", "noopener,noreferrer");
  if (!w) return;
  const imgSrc = JSON.stringify(absSrc);
  const html =
    "<!DOCTYPE html><html lang=\"ko\"><head><meta charset=\"UTF-8\"/>" +
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"/>" +
    "<title>원본 이미지</title></head>" +
    "<body style=\"margin:0;background:#0d0d0d;min-height:100vh;overflow:auto;display:flex;justify-content:center;align-items:flex-start;\">" +
    "<img src=" +
    imgSrc +
    " alt=\"\" style=\"display:block;cursor:pointer;max-width:none;width:auto;height:auto;\" onclick=\"window.close()\" title=\"클릭하면 창이 닫힙니다\" />" +
    "</body></html>";
  w.document.open();
  w.document.write(html);
  w.document.close();
  w.focus();
};

const renderShadeSunMarkup = () => {
  const rows = SHADE_SUN_STADIUMS.map(
    (row) => `
      <button type="button" class="sun-shade-row" data-shade-file="${escapeHtml(row.imageFile)}">
        <span class="sun-shade-row-team">${escapeHtml(row.team)}</span>
        <span class="sun-shade-row-sep">·</span>
        <span class="sun-shade-row-stadium">${escapeHtml(row.stadium)}</span>
      </button>
    `,
  ).join("");
  return `
    <div class="weather-shade-actions">
      <button type="button" class="weather-shade-btn" id="sun-shade-open-btn">구장별 시간에 따른 그늘 정보</button>
    </div>
    <div class="sun-shade-backdrop" id="sun-shade-backdrop" hidden>
      <div class="sun-shade-dialog" role="dialog" aria-modal="true" aria-labelledby="sun-shade-dialog-title">
        <button type="button" class="sun-shade-close" id="sun-shade-close-btn" aria-label="닫기">×</button>
        <h3 id="sun-shade-dialog-title" class="sun-shade-dialog-title">구장별 태양·그늘 참고</h3>
        <p class="sun-shade-hint">홈구단 · 구장을 누르면 해당 자료 이미지를 볼 수 있습니다.</p>
        <div class="sun-shade-panel sun-shade-panel--list" id="sun-shade-panel-list">
          <div class="sun-shade-list">${rows}</div>
        </div>
        <div class="sun-shade-panel sun-shade-panel--detail" id="sun-shade-panel-detail" hidden>
          <button type="button" class="sun-shade-back-btn" id="sun-shade-back-btn">← 구장 목록</button>
          <div class="sun-shade-image-wrap" id="sun-shade-image-wrap">
            <div class="sun-shade-loading" id="sun-shade-loading" hidden>이미지를 불러오는 중입니다.</div>
            <img src="" alt="" class="sun-shade-image" id="sun-shade-image" loading="lazy" decoding="async" />
          </div>
          <div class="sun-shade-caption" id="sun-shade-caption"></div>
        </div>
      </div>
    </div>
  `;
};

const bindSunShadowEvents = () => {
  const backdrop = document.getElementById("sun-shade-backdrop");
  const openBtn = document.getElementById("sun-shade-open-btn");
  const closeBtn = document.getElementById("sun-shade-close-btn");
  const panelList = document.getElementById("sun-shade-panel-list");
  const panelDetail = document.getElementById("sun-shade-panel-detail");
  const backBtn = document.getElementById("sun-shade-back-btn");
  const imgEl = document.getElementById("sun-shade-image");
  const captionEl = document.getElementById("sun-shade-caption");
  const loadingEl = document.getElementById("sun-shade-loading");
  if (!backdrop || !openBtn || !panelList || !panelDetail || !imgEl || !captionEl) return;

  const resetSunShadeImageUi = () => {
    sunShadeImgLoadToken += 1;
    imgEl.onload = null;
    imgEl.onerror = null;
    imgEl.removeAttribute("src");
    imgEl.alt = "";
    imgEl.removeAttribute("title");
    imgEl.classList.remove("sun-shade-image--visible");
    if (loadingEl) {
      loadingEl.hidden = true;
      loadingEl.textContent = "이미지를 불러오는 중입니다.";
    }
  };

  const showList = () => {
    panelList.hidden = false;
    panelDetail.hidden = true;
    resetSunShadeImageUi();
  };

  const openModal = () => {
    showList();
    backdrop.hidden = false;
    document.body.classList.add("sun-shade-open");
    closeBtn?.focus();
  };

  const closeModal = () => {
    backdrop.hidden = true;
    document.body.classList.remove("sun-shade-open");
    showList();
  };

  openBtn.addEventListener("click", () => openModal());
  closeBtn?.addEventListener("click", () => closeModal());
  backBtn?.addEventListener("click", () => showList());

  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) closeModal();
  });

  panelList.addEventListener("click", (e) => {
    const row = e.target.closest("[data-shade-file]");
    if (!row || !panelList.contains(row)) return;
    const file = row.getAttribute("data-shade-file");
    if (!file) return;
    const meta = SHADE_SUN_STADIUMS.find((r) => r.imageFile === file);
    const team = meta?.team || "";
    const stadium = meta?.stadium || "";
    sunShadeImgLoadToken += 1;
    const token = sunShadeImgLoadToken;
    imgEl.onload = null;
    imgEl.onerror = null;
    imgEl.classList.remove("sun-shade-image--visible");
    if (loadingEl) {
      loadingEl.hidden = false;
      loadingEl.textContent = "이미지를 불러오는 중입니다.";
    }
    captionEl.textContent = `${team} · ${stadium}`;
    panelList.hidden = true;
    panelDetail.hidden = false;
    imgEl.alt = `${team} ${stadium} 시간대별 태양·그늘 참고 이미지`;
    imgEl.title = "클릭하면 원본 크기로 새 창에서 열립니다.";
    imgEl.onload = () => {
      if (token !== sunShadeImgLoadToken) return;
      if (loadingEl) loadingEl.hidden = true;
      imgEl.classList.add("sun-shade-image--visible");
    };
    imgEl.onerror = () => {
      if (token !== sunShadeImgLoadToken) return;
      if (loadingEl) {
        loadingEl.hidden = false;
        loadingEl.textContent = "이미지를 불러오지 못했습니다.";
      }
      imgEl.classList.remove("sun-shade-image--visible");
      imgEl.removeAttribute("title");
    };
    imgEl.src = `./sun/${encodeURIComponent(file)}`;
    if (imgEl.complete && imgEl.naturalWidth > 0 && token === sunShadeImgLoadToken) {
      if (loadingEl) loadingEl.hidden = true;
      imgEl.classList.add("sun-shade-image--visible");
    }
  });

  imgEl.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!imgEl.classList.contains("sun-shade-image--visible")) return;
    const src = imgEl.currentSrc || imgEl.getAttribute("src") || "";
    if (!src) return;
    openSunshadeImageOriginalViewer(src);
  });

  if (!sunShadeEscapeListenerAttached) {
    sunShadeEscapeListenerAttached = true;
    document.addEventListener(
      "keydown",
      (e) => {
        if (e.key !== "Escape") return;
        const bd = document.getElementById("sun-shade-backdrop");
        if (!bd || bd.hidden) return;
        const detail = document.getElementById("sun-shade-panel-detail");
        const list = document.getElementById("sun-shade-panel-list");
        const img = document.getElementById("sun-shade-image");
        if (detail && !detail.hidden) {
          if (list) list.hidden = false;
          detail.hidden = true;
          sunShadeImgLoadToken += 1;
          const loadEl = document.getElementById("sun-shade-loading");
          if (loadEl) {
            loadEl.hidden = true;
            loadEl.textContent = "이미지를 불러오는 중입니다.";
          }
          if (img) {
            img.onload = null;
            img.onerror = null;
            img.removeAttribute("src");
            img.removeAttribute("title");
            img.alt = "";
            img.classList.remove("sun-shade-image--visible");
          }
          return;
        }
        bd.hidden = true;
        document.body.classList.remove("sun-shade-open");
        if (list) list.hidden = false;
        if (detail) detail.hidden = true;
        sunShadeImgLoadToken += 1;
        const loadEl2 = document.getElementById("sun-shade-loading");
        if (loadEl2) {
          loadEl2.hidden = true;
          loadEl2.textContent = "이미지를 불러오는 중입니다.";
        }
        if (img) {
          img.onload = null;
          img.onerror = null;
          img.removeAttribute("src");
          img.removeAttribute("title");
          img.alt = "";
          img.classList.remove("sun-shade-image--visible");
        }
      },
      true,
    );
  }
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

  const weatherDateLabel = (() => {
    const dt = parseYmdAsLocalDate(g?.game_date_ymd || "");
    if (dt) {
      return `${dt.getMonth() + 1}/${dt.getDate()}(${KOR_WEEKDAYS[dt.getDay()]})`;
    }
    const raw = String(weather?.updated_at || "");
    const parsed = new Date(raw);
    if (!Number.isNaN(parsed.getTime())) {
      return `${parsed.getMonth() + 1}/${parsed.getDate()}(${KOR_WEEKDAYS[parsed.getDay()]})`;
    }
    return "날짜";
  })();

  const dateCard = `
      <article class="weather-hour-item weather-hour-item-date">
        <div class="weather-time-row">
          <span class="weather-time">날짜</span>
        </div>
        <div class="weather-date-value">${weatherDateLabel}</div>
      </article>
    `;

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
        </div>
        <div class="weather-summary-row">
          <div class="weather-summary-item">
            초미세먼지(PM2.5): ${pm25Value}㎍/m3 · ${pm25Meta.grade} ${pm25Meta.emoji}
          </div>
        </div>
      </div>
      ${renderShadeSunMarkup()}
      <div class="weather-hourly-wrap">
        <div class="weather-hourly-grid">
          ${dateCard}
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
      // KBO `last5` is oldest→newest; the last 승/패/무 is the most recent (오른쪽, 네이버 레드닷과 동일).
      const dots = (seq) => {
        const out = [];
        for (const c of String(seq || "")) {
          if (c === "승" || c === "패" || c === "무") out.push(c);
        }
        if (out.length === 0) return "—";
        const lastI = out.length - 1;
        return out
          .map((c, i) => {
            const kind = c === "승" ? "win" : c === "패" ? "loss" : "draw";
            const latest = i === lastI ? " last5-latest" : "";
            return `<span class="dot ${kind}${latest}">${c}</span>`;
          })
          .join("");
      };
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
  const schedule = Array.isArray(g?.season_schedule) ? g.season_schedule : [];
  if (schedule.length === 0) return "";

  const toMonthFromYmd = (ymd) => {
    const d = parseYmdAsLocalDate(ymd || "");
    return d ? formatMonthKey(d) : "";
  };
  const today = new Date(Date.now() + 9 * 60 * 60 * 1000);
  const todayKey = today.toISOString().slice(0, 10);
  const monthKeys = Array.from(new Set(schedule.map((x) => toMonthFromYmd(x?.date)).filter(Boolean))).sort();
  if (monthKeys.length === 0) return "";
  const minMonth = monthKeys[0];
  const maxMonth = monthKeys[monthKeys.length - 1];

  const candidateMonth = scheduleCalendarMonth || toMonthFromYmd(g?.game_date_ymd) || toMonthFromYmd(todayKey);
  const initialMonth = monthKeys.includes(candidateMonth) ? candidateMonth : maxMonth;
  scheduleCalendarMonth = initialMonth;
  const viewMonthDate = parseMonthKey(initialMonth) || parseMonthKey(maxMonth) || new Date(today.getFullYear(), today.getMonth(), 1);
  const viewYear = viewMonthDate.getFullYear();
  const viewMonth = viewMonthDate.getMonth();

  const mapByDate = {};
  for (const item of schedule) {
    const d = String(item?.date || "");
    if (!d) continue;
    if (!Array.isArray(mapByDate[d])) mapByDate[d] = [];
    mapByDate[d].push(item);
  }
  const pickForDate = (ymd) => (mapByDate[ymd] || [])[0] || null;
  const firstDay = new Date(viewYear, viewMonth, 1);
  const lastDayNo = new Date(viewYear, viewMonth + 1, 0).getDate();
  // Monday-first calendar: Mon=0 ... Sun=6
  const leadingBlanks = (firstDay.getDay() + 6) % 7;
  const monthLabel = `${viewYear}년 ${viewMonth + 1}월`;
  const monthGames = schedule.filter((x) => String(x?.date || "").startsWith(`${initialMonth}-`));
  const totalGames = monthGames.length;
  const totalWins = monthGames.filter((x) => x?.result === "승").length;
  const totalLosses = monthGames.filter((x) => x?.result === "패").length;
  const totalDraws = monthGames.filter((x) => x?.result === "무").length;
  const totalFinalGames = monthGames.filter((x) => x?.is_final).length;
  const homeFinalGames = monthGames.filter((x) => x?.home_away === "홈" && x?.is_final);
  const awayFinalGames = monthGames.filter((x) => x?.home_away === "원정" && x?.is_final);
  const homeWins = homeFinalGames.filter((x) => x?.result === "승").length;
  const awayWins = awayFinalGames.filter((x) => x?.result === "승").length;
  const toRate = (wins, gamesCount) => {
    if (!gamesCount) return "-";
    return `${((wins / gamesCount) * 100).toFixed(1)}%`;
  };
  const homeWinRate = toRate(homeWins, homeFinalGames.length);
  const awayWinRate = toRate(awayWins, awayFinalGames.length);
  const totalWinRate = toRate(totalWins, totalFinalGames);

  const cells = [];
  for (let i = 0; i < leadingBlanks; i += 1) {
    cells.push('<div class="sched-day sched-day-empty"></div>');
  }
  for (let day = 1; day <= lastDayNo; day += 1) {
    const ymd = `${viewYear}-${String(viewMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const row = pickForDate(ymd);
    const isToday = ymd === todayKey;
    const dayOfWeek = new Date(viewYear, viewMonth, day).getDay();
    const holidayName = getHolidayName(ymd);
    const classes = ["sched-day"];
    if (isToday) classes.push("sched-day-today");
    if (row) classes.push("sched-day-game");
    if (dayOfWeek === 6) classes.push("sched-day-sat");
    if (dayOfWeek === 0) classes.push("sched-day-sun");
    if (holidayName) classes.push("sched-day-holiday");
    const homeAway = row?.home_away || "";
    if (homeAway === "홈") classes.push("sched-day-home");
    if (row?.is_final && row?.result === "승") classes.push("sched-day-win");
    if (row?.is_final && row?.result === "패") classes.push("sched-day-loss");
    if (row?.is_final && row?.result === "무") classes.push("sched-day-draw");
    const opp = row?.opponent || "";
    const timeText = row?.game_time || "";
    const oppEmblem = getOpponentEmblemUrl(g?.season_id, row?.opponent_team_id);
    const score = (row?.hanwha_score !== "" || row?.opponent_score !== "")
      ? `${row?.hanwha_score || "-"}:${row?.opponent_score || "-"}`
      : "";
    const result = row?.result || "";
    const resultClass = result === "승"
      ? "sched-result-win"
      : result === "패"
        ? "sched-result-loss"
        : result === "취소"
          ? "sched-result-cancel"
          : "sched-result-draw";
    const gameMeta = row
      ? `
        <div class="sched-opponent-wrap">
          ${
            oppEmblem
              ? `<img src="${oppEmblem}" alt="${opp || "상대팀"} 엠블럼" class="sched-opponent-emblem" loading="lazy" />`
              : ""
          }
        </div>
        ${
          row?.is_final
            ? (
              result === "취소"
                ? `<div class="sched-cancel">취소</div>`
                : `<div class="sched-score"><span>${score}</span><strong class="${resultClass}">${result || "-"}</strong></div>`
            )
            : row?.is_live
              ? `<div class="sched-score"><span>${score || "진행중"}</span><strong class="sched-result-live">LIVE</strong></div>`
              : `<div class="sched-time">${timeText || "-"}</div>`
        }
      `
      : '<div class="sched-no-game">-</div>';
    const linkUrl = getScheduleCardLinkUrl(row, g?.season_id);
    if (linkUrl) classes.push("sched-day-clickable");
    const holidayMeta = holidayName ? `<div class="sched-holiday-name">${holidayName}</div>` : "";
    cells.push(`
      <article class="${classes.join(" ")}"${linkUrl ? ` data-link-url="${linkUrl}"` : ""}>
        <div class="sched-day-num">${day}</div>
        <div class="sched-day-body">${gameMeta}</div>
        ${holidayMeta}
      </article>
    `);
  }

  const prevMonthDate = new Date(viewYear, viewMonth - 1, 1);
  const nextMonthDate = new Date(viewYear, viewMonth + 1, 1);
  const prevKey = formatMonthKey(prevMonthDate);
  const nextKey = formatMonthKey(nextMonthDate);
  const canPrev = monthKeys.includes(prevKey);
  const canNext = monthKeys.includes(nextKey);

  return `
    <section class="series-section">
      <h2 class="cmp-title">한화 월별 일정</h2>
      <div class="sched-ticket-note">날짜 카드를 클릭하면 예매 사이트로 이동합니다. (진행 중·종료된 경기는 네이버 스포츠 중계/결과 페이지로 이동합니다.)</div>
      <div class="sched-head">
        <button type="button" class="sched-nav-btn" data-sched-nav="prev" ${canPrev ? "" : "disabled"} aria-label="이전 달">◀</button>
        <div class="sched-month-label">${monthLabel}</div>
        <button type="button" class="sched-nav-btn" data-sched-nav="next" ${canNext ? "" : "disabled"} aria-label="다음 달">▶</button>
      </div>
      <div class="sched-weekdays">
        <span>월</span><span>화</span><span>수</span><span>목</span><span>금</span><span class="sched-weekday-sat">토</span><span class="sched-weekday-sun">일</span>
      </div>
      <div class="sched-grid">
        ${cells.join("")}
      </div>
      <div class="sched-summary-wrap">
        <table class="sched-summary-table">
          <thead>
            <tr>
              <th>총 경기</th>
              <th>승</th>
              <th>패</th>
              <th>무</th>
              <th>총 승률</th>
              <th>홈 승률</th>
              <th>원정 승률</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>${totalGames}</td>
              <td>${totalWins}</td>
              <td>${totalLosses}</td>
              <td>${totalDraws}</td>
              <td>${totalWinRate}</td>
              <td>${homeWinRate}</td>
              <td>${awayWinRate}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="sched-legend">
        <span><em class="sched-dot-home-border"></em>홈경기</span>
        <span><em class="sched-dot-win"></em>승</span>
        <span><em class="sched-dot-loss"></em>패</span>
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

const bindScheduleCalendarEvents = () => {
  const navButtons = Array.from(document.querySelectorAll("[data-sched-nav]"));
  for (const btn of navButtons) {
    btn.addEventListener("click", () => {
      const current = parseMonthKey(scheduleCalendarMonth || "");
      if (!current) return;
      const dir = btn.getAttribute("data-sched-nav");
      const next = new Date(current.getFullYear(), current.getMonth() + (dir === "next" ? 1 : -1), 1);
      scheduleCalendarMonth = formatMonthKey(next);
      renderGame(game, updatedAt);
    });
  }
  const linkCards = Array.from(document.querySelectorAll("[data-link-url]"));
  for (const card of linkCards) {
    card.addEventListener("click", () => {
      const url = card.getAttribute("data-link-url");
      if (!url) return;
      window.location.href = url;
    });
  }
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

const renderRegisterMoveSection = (g) => {
  const moves = g?.register_moves || {};
  const registered = Array.isArray(moves.registered) ? moves.registered : [];
  const deregistered = Array.isArray(moves.deregistered) ? moves.deregistered : [];
  let effective = moves;
  if (!registered.length && !deregistered.length && lastRegisterMovesSnapshot) {
    effective = lastRegisterMovesSnapshot;
  } else if (registered.length || deregistered.length) {
    lastRegisterMovesSnapshot = {
      date: String(moves.date || ""),
      registered: [...registered],
      deregistered: [...deregistered],
    };
  }
  const moveDate = String(effective.date || "").trim();
  const regList = Array.isArray(effective.registered) ? effective.registered : [];
  const deregList = Array.isArray(effective.deregistered) ? effective.deregistered : [];
  const toRows = (rows) => rows.map((item) => `
      <tr>
        <td>${item.number || "-"}</td>
        <td class="lineup-player">${item.name || "-"}</td>
        <td>${item.position || "-"}</td>
        <td>${item.throws_bats || "-"}</td>
        <td>${item.birth_date || "-"}</td>
      </tr>
    `).join("");

  return `
    <section class="move-section">
      <h2 class="cmp-title">한화 등/말소 현황</h2>
      <div class="move-date">기준 날짜: ${moveDate || "-"}</div>
      <div class="lineup-pitcher-title">등록</div>
      <div class="lineup-table-wrap">
        <table class="lineup-table">
          <thead>
            <tr>
              <th>등번호</th>
              <th>선수명</th>
              <th>포지션</th>
              <th>투타유형</th>
              <th>생년월일</th>
            </tr>
          </thead>
          <tbody>
            ${toRows(regList) || `<tr><td colspan="5" class="lineup-empty">당일 등록된 선수가 없습니다.</td></tr>`}
          </tbody>
        </table>
      </div>
      <div class="lineup-pitcher-title">말소</div>
      <div class="lineup-table-wrap">
        <table class="lineup-table">
          <thead>
            <tr>
              <th>등번호</th>
              <th>선수명</th>
              <th>포지션</th>
              <th>투타유형</th>
              <th>생년월일</th>
            </tr>
          </thead>
          <tbody>
            ${toRows(deregList) || `<tr><td colspan="5" class="lineup-empty">당일 말소된 선수가 없습니다.</td></tr>`}
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
const DEFAULT_HOLIDAY_CALENDAR = {
  fixed: {
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
  },
  specific: {
    "2026-02-16": "설날 연휴",
    "2026-02-17": "설날",
    "2026-02-18": "설날 연휴",
    "2026-03-02": "삼일절 대체공휴일",
    "2026-05-24": "부처님오신날",
    "2026-05-25": "부처님오신날 대체공휴일",
    "2026-08-17": "광복절 대체공휴일",
    "2026-09-24": "추석 연휴",
    "2026-09-25": "추석",
    "2026-09-26": "추석 연휴",
    "2026-10-05": "개천절 대체공휴일",
  },
};

const getHolidayName = (ymd) => {
  const holidayData = holidayCalendarData || DEFAULT_HOLIDAY_CALENDAR;
  if (holidayData?.specific?.[ymd]) return holidayData.specific[ymd];
  return holidayData?.fixed?.[ymd.slice(5)] || "";
};

const loadHolidayCalendar = async () => {
  try {
    const response = await fetch(`./holiday-data.json?t=${Date.now()}`, {
      cache: "no-store",
    });
    if (!response.ok) return;
    const payload = await response.json();
    if (!payload || typeof payload !== "object") return;
    holidayCalendarData = {
      fixed: payload.fixed && typeof payload.fixed === "object"
        ? payload.fixed
        : DEFAULT_HOLIDAY_CALENDAR.fixed,
      specific: payload.specific && typeof payload.specific === "object"
        ? payload.specific
        : DEFAULT_HOLIDAY_CALENDAR.specific,
    };
    if (game) renderGame(game, updatedAt);
  } catch (err) {
    console.debug("holiday calendar load failed", err);
  }
};

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

const formatMonthKey = (dateObj) => {
  const y = dateObj.getFullYear();
  const m = String(dateObj.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
};

const parseMonthKey = (monthKey) => {
  const m = String(monthKey || "").match(/^(\d{4})-(\d{2})$/);
  if (!m) return null;
  const y = Number(m[1]);
  const month = Number(m[2]);
  if (!Number.isFinite(y) || !Number.isFinite(month) || month < 1 || month > 12) return null;
  return new Date(y, month - 1, 1);
};

const KBO_EMBLEM_BASE_URL = "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/emblem/regular";
const TICKET_URL_BY_TEAM_ID = {
  HH: "https://www.ticketlink.co.kr/sports/137/63",
  LG: "https://www.ticketlink.co.kr/sports/137/59",
  SS: "https://www.ticketlink.co.kr/sports/137/57",
  KT: "https://www.ticketlink.co.kr/sports/137/62",
  HT: "https://www.ticketlink.co.kr/sports/137/58",
  OB: "https://ticket.interpark.com/Contents/Sports/GoodsInfo?SportsCode=07001&TeamCode=PB004",
  WO: "https://ticket.interpark.com/Contents/Sports/GoodsInfo?SportsCode=07001&TeamCode=PB003",
  LT: "https://www.giantsclub.com/",
  NC: "https://www.ncdinos.com/",
  SK: "https://ticket.ssg.com/ticket",
};

const getTicketBookingUrl = (scheduleRow) => {
  if (!scheduleRow) return "";
  if (scheduleRow.home_away === "홈") return TICKET_URL_BY_TEAM_ID.HH || "";
  const opponentTeamId = String(scheduleRow.opponent_team_id || "").trim();
  return TICKET_URL_BY_TEAM_ID[opponentTeamId] || "";
};

// 경기가 진행 중이거나 종료된 경우 네이버 스포츠 중계/결과 페이지 URL을 반환한다.
// 예: game_id="20260508LGHH0" + season_id="2026" → .../game/20260508LGHH02026/relay
const getNaverGameRelayUrl = (scheduleRow, seasonId) => {
  if (!scheduleRow) return "";
  if (!scheduleRow.is_final && !scheduleRow.is_live) return "";
  if (scheduleRow.result === "취소") return "";
  const gameId = String(scheduleRow.game_id || "").trim();
  const sid = String(seasonId || "").trim();
  if (!gameId || !sid) return "";
  return `https://m.sports.naver.com/game/${gameId}${sid}/relay`;
};

// 일정 카드 클릭 시 이동할 URL을 결정한다(끝/진행 중인 경기는 네이버 중계, 그 외는 예매).
const getScheduleCardLinkUrl = (scheduleRow, seasonId) => {
  const relayUrl = getNaverGameRelayUrl(scheduleRow, seasonId);
  if (relayUrl) return relayUrl;
  return getTicketBookingUrl(scheduleRow);
};

const getOpponentEmblemUrl = (seasonId, opponentTeamId) => {
  const sid = String(seasonId || "").trim();
  const tid = String(opponentTeamId || "").trim();
  if (!sid || !tid) return "";
  return `${KBO_EMBLEM_BASE_URL}/${sid}/emblem_${tid}.png`;
};

const renderYesterdayLeagueSection = (g) => {
  const raw = Array.isArray(g?.yesterday_league_games) ? g.yesterday_league_games : [];
  if (raw.length === 0) return "";
  const ymd = g.yesterday_league_date || "";
  const dt = parseYmdAsLocalDate(ymd);
  const titleDate = dt
    ? `${dt.getMonth() + 1}/${dt.getDate()}(${KOR_WEEKDAYS[dt.getDay()]})`
    : ymd;
  const sid = String(g?.season_id || "").trim();
  const games = [...raw].sort((a, b) => {
    const aH = a.away_team_id === "HH" || a.home_team_id === "HH" ? 0 : 1;
    const bH = b.away_team_id === "HH" || b.home_team_id === "HH" ? 0 : 1;
    if (aH !== bH) return aH - bH;
    return String(a.game_time || "").localeCompare(String(b.game_time || ""), "ko");
  });
  const cards = games
    .map((row) => {
      const awayEm = getOpponentEmblemUrl(sid, row.away_team_id);
      const homeEm = getOpponentEmblemUrl(sid, row.home_team_id);
      const linkUrl = getScheduleCardLinkUrl(row, sid);
      const res = row.result || "";
      let resClass = "yesterday-league-result";
      if (res === "취소") resClass += " yesterday-league-result--cancel";
      else if (res === "무") resClass += " yesterday-league-result--draw";
      else if (res === "진행중") resClass += " yesterday-league-result--live";
      else if (res === "원정승") resClass += " yesterday-league-result--away";
      else if (res === "홈승") resClass += " yesterday-league-result--home";
      const scoreText = res === "취소" ? "—" : `${row.away_score ?? "-"} : ${row.home_score ?? "-"}`;
      const classes = ["yesterday-league-card"];
      if (linkUrl) classes.push("yesterday-league-card--clickable");
      const awayW = res === "원정승" ? " yesterday-league-side--winner" : "";
      const homeW = res === "홈승" ? " yesterday-league-side--winner" : "";
      return `
      <article class="${classes.join(" ")}"${linkUrl ? ` data-link-url="${escapeHtml(linkUrl)}"` : ""}>
        <div class="yesterday-league-card-top">
          <div class="yesterday-league-side yesterday-league-side--away${awayW}">
            ${awayEm ? `<img src="${escapeHtml(awayEm)}" alt="${escapeHtml(row.away_team)} 엠블럼" class="yesterday-league-emblem" loading="lazy" />` : ""}
            <span class="yesterday-league-team-name">${escapeHtml(row.away_team)}</span>
          </div>
          <div class="yesterday-league-center">
            <div class="yesterday-league-score">${escapeHtml(scoreText)}</div>
            <strong class="${resClass}">${escapeHtml(res)}</strong>
          </div>
          <div class="yesterday-league-side yesterday-league-side--home${homeW}">
            ${homeEm ? `<img src="${escapeHtml(homeEm)}" alt="${escapeHtml(row.home_team)} 엠블럼" class="yesterday-league-emblem" loading="lazy" />` : ""}
            <span class="yesterday-league-team-name">${escapeHtml(row.home_team)}</span>
          </div>
        </div>
        <div class="yesterday-league-foot">
          <span>${escapeHtml(row.stadium || "")}</span>
          ${row.game_time ? `<span class="yesterday-league-time">${escapeHtml(row.game_time)}</span>` : ""}
        </div>
      </article>
    `;
    })
    .join("");
  return `
    <section class="yesterday-league-section">
      <h2 class="cmp-title">전날 프로야구 경기 <span class="yesterday-league-date"> ${titleDate} </span></h2>
      <p class="yesterday-league-note">경기 카드를 누르면 네이버 스포츠 중계·결과 페이지로 이동합니다.</p>
      <div class="yesterday-league-grid">${cards}</div>
    </section>
  `;
};

const renderGame = (g, refreshedAt) => {
  if (!g) {
    container.innerHTML = "<p>가까운 일정에서 한화 이글스 경기 정보를 찾지 못했습니다.</p>";
    return;
  }

  container.innerHTML = `
    <div class="updated-at">마지막 갱신: ${formatUpdatedAt(refreshedAt)}</div>
    ${renderLiveHeader(g)}
    <div class="game-meta-pitcher-layout">
      <div class="game-meta-cols">
        <div class="row"><span class="label">경기일:</span>${formatGameDateWithWeekday(g.game_date, g.game_date_ymd)}</div>
        <div class="row"><span class="label">경기시간:</span>${g.game_time}</div>
        <div class="row"><span class="label">대진:</span>${g.matchup}</div>
        <div class="row"><span class="label">구장:</span>${g.stadium}</div>
        <div class="row"><span class="label">한화 홈/원정:</span>${g.hanwha_home_away}</div>
        <div class="row"><span class="label">상대팀:</span>${g.opponent}</div>
        <div class="row"><span class="label">한화 선발투수:</span>${g.hanwha_starter}</div>
      </div>
      <div class="game-pitcher-cols sub">
        <div class="pitcher-grid">
        ${renderPitcherCard(
          "원정팀 선발",
          g.away_starter,
          g.away_starter_image,
          g.away_starter_stats,
          g.team_comparison?.away_emblem,
        )}
        ${renderPitcherCard(
          "홈팀 선발",
          g.home_starter,
          g.home_starter_image,
          g.home_starter_stats,
          g.team_comparison?.home_emblem,
        )}
        </div>
      </div>
    </div>
    ${renderWeatherSection(g)}
    ${renderTeamComparison(g.team_comparison, g.away_team, g.home_team, g.head_to_head_summary)}
    ${renderYesterdayLeagueSection(g)}
    ${renderLineupSection(g)}
    ${renderRegisterMoveSection(g)}
    ${renderSeriesSection(g)}
    ${renderEaglesTvSection(g)}
    ${renderLatestNewsSection(g)}
    ${renderTeamRankings(g.team_rankings, g.team_rank_date)}
  `;
  bindScheduleCalendarEvents();
  bindSunShadowEvents();
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
void loadHolidayCalendar();

// GitHub Pages 정적 JSON은 GHA가 수 커밋해도, 첫 페인트·라이브창 밖에서는 갱신 fetch가 안 돌아가
// `마지막 갱신`이 오래된 것처럼 보인다. 로드 시와 5분마다 항상 최신 game-data.json을 받는다.
void refreshGameInfo();
if (window.__hesDataInterval) {
  clearInterval(window.__hesDataInterval);
}
window.__hesDataInterval = setInterval(refreshGameInfo, 5 * 60 * 1000);

schedulerTick();
schedulerTimer = setInterval(schedulerTick, 30 * 1000);
