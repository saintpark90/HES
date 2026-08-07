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

const THEME_STORAGE_KEY = "hes-theme";

const getPreferredTheme = () => {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "dark" || stored === "light") return stored;
  } catch (err) {
    // localStorage unavailable (private mode, etc.)
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
};

const applyTheme = (theme) => {
  if (theme === "dark") {
    document.documentElement.setAttribute("data-theme", "dark");
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
};

const updateThemeToggleButton = (btn) => {
  if (!btn) return;
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  btn.setAttribute("aria-label", isDark ? "라이트 모드로 전환" : "다크 모드로 전환");
  btn.setAttribute("title", isDark ? "라이트 모드" : "다크 모드");
  btn.textContent = isDark ? "☀️" : "🌙";
};

const bindThemeToggle = () => {
  const btn = document.querySelector(".card-theme-toggle");
  if (!btn || btn.dataset.bound === "1") return;
  btn.dataset.bound = "1";
  updateThemeToggleButton(btn);
  btn.addEventListener("click", () => {
    const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
    applyTheme(next);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch (err) {
      // ignore
    }
    updateThemeToggleButton(btn);
  });
};

applyTheme(getPreferredTheme());
bindThemeToggle();

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

const renderMatchupRow = (g) => {
  const tc = g?.team_comparison;
  const awayEmblem = tc?.away_emblem || "";
  const homeEmblem = tc?.home_emblem || "";
  const awayName = g?.away_team || "";
  const homeName = g?.home_team || "";
  const fallback = g?.matchup || `${awayName} vs ${homeName}`.trim();
  if (!awayName && !homeName) {
    return `<div class="row row--matchup"><span class="label">대진:</span><span class="matchup-value">${fallback}</span></div>`;
  }
  return `
    <div class="row row--matchup">
      <span class="label">대진:</span>
      <span class="matchup-value">
        ${awayEmblem ? `<img src="${awayEmblem}" alt="${awayName} 엠블럼" class="matchup-emblem" loading="lazy" />` : ""}
        <span class="matchup-team">${awayName}</span>
        <span class="matchup-vs">vs</span>
        ${homeEmblem ? `<img src="${homeEmblem}" alt="${homeName} 엠블럼" class="matchup-emblem" loading="lazy" />` : ""}
        <span class="matchup-team">${homeName}</span>
      </span>
    </div>
  `;
};

const renderLiveHeader = (g) => {
  const live = g?.live_status;
  const tc = g?.team_comparison;
  if (!live) return "";
  if (live.is_cancelled) {
    const cancelLabel = live.cancel_label || "경기 취소";
    return `
    <section class="live-header live-header--cancelled">
      <div class="live-team">
        <img src="${tc?.away_emblem || ""}" alt="${g.away_team}" class="live-emblem" />
        <span>${g.away_team}</span>
      </div>
      <div class="live-score-wrap">
        <div class="live-score">${live.away_score || "0"} : ${live.home_score || "0"}</div>
        <div class="live-inning live-inning--cancelled">${escapeHtml(cancelLabel)}</div>
      </div>
      <div class="live-team">
        <img src="${tc?.home_emblem || ""}" alt="${g.home_team}" class="live-emblem" />
        <span>${g.home_team}</span>
      </div>
    </section>
  `;
  }
  if (!live.is_live) return "";
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
            <img src="" alt="" class="sun-shade-image" id="sun-shade-image" loading="eager" decoding="async" />
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
    imgEl.removeAttribute("src");
    imgEl.classList.remove("sun-shade-image--visible");

    captionEl.textContent = `${team} · ${stadium}`;
    panelList.hidden = true;
    panelDetail.hidden = false;

    if (loadingEl) {
      loadingEl.hidden = false;
      loadingEl.textContent = "이미지를 불러오는 중입니다.";
    }
    if (loadingEl) void loadingEl.offsetHeight;

    const nextSrc = `./sun/${encodeURIComponent(file)}`;
    const applySrc = () => {
      if (token !== sunShadeImgLoadToken) return;
      imgEl.alt = `${team} ${stadium} 시간대별 태양·그늘 참고 이미지`;
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
      };
      imgEl.src = nextSrc;
      if (imgEl.complete && imgEl.naturalWidth > 0 && token === sunShadeImgLoadToken) {
        if (loadingEl) loadingEl.hidden = true;
        imgEl.classList.add("sun-shade-image--visible");
      }
    };

    requestAnimationFrame(() => {
      requestAnimationFrame(applySrc);
    });
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

const parseWeatherNumber = (value) => {
  const n = Number.parseFloat(String(value ?? "").replace(/[^\d.-]/g, ""));
  return Number.isFinite(n) ? n : null;
};

const getWeatherMaxTemp = (weather) => {
  const hourly = Array.isArray(weather?.hourly) ? weather.hourly : [];
  const temps = hourly.map((h) => parseWeatherNumber(h?.temperature)).filter((v) => v != null);
  return temps.length ? Math.max(...temps) : null;
};

const buildHeatCancelWarning = (maxTemp) => {
  if (maxTemp == null || !(maxTemp > 30)) return null;
  const details = [
    "주의보: 일 최고 기온이 섭씨 33도 이상인 상태가 2일 이상 지속될 것으로 예상될 때",
    "경보: 일 최고 기온이 섭씨 35도 이상인 상태가 2일 이상 지속될 것으로 예상될 때",
  ];
  const observed = `예상 최고기온 ${maxTemp.toFixed(1)}°C`;
  if (maxTemp >= 35) {
    return {
      type: "heat",
      level: "경보",
      title: "폭염 경보",
      observed,
      outlook: `이 날짜 경기는 예상 최고기온이 ${maxTemp.toFixed(1)}°C로 폭염 경보 기준(35°C)에 해당해 취소될 가능성이 높아 보입니다.`,
      details,
    };
  }
  if (maxTemp >= 33) {
    return {
      type: "heat",
      level: "주의보",
      title: "폭염 주의보",
      observed,
      outlook: `이 날짜 경기는 예상 최고기온이 ${maxTemp.toFixed(1)}°C로 폭염 주의보 기준(33°C)에 해당해 취소될 가능성이 있습니다.`,
      details,
    };
  }
  return {
    type: "heat",
    level: "관심",
    title: "폭염 취소 관련 안내",
    observed,
    outlook: `이 날짜 경기는 예상 최고기온이 ${maxTemp.toFixed(1)}°C로 30°C를 넘지만, 공식 주의보 기준(33°C)보다는 낮아 경기는 진행될 것으로 보입니다.`,
    details,
  };
};

const buildWeatherCancelWarnings = (weather) => {
  const maxTemp = getWeatherMaxTemp(weather);
  const heatWarning = buildHeatCancelWarning(maxTemp);
  const serverWarnings = Array.isArray(weather?.cancel_warnings) ? weather.cancel_warnings : [];
  const warnings = [];

  if (heatWarning) {
    warnings.push(heatWarning);
  }

  const nonHeatServer = serverWarnings.filter((item) => item?.type && item.type !== "heat");
  if (nonHeatServer.length) {
    warnings.push(...nonHeatServer);
    return warnings;
  }

  // Fallback when older cached payloads lack server-side non-heat warnings.
  const hourly = Array.isArray(weather?.hourly) ? weather.hourly : [];
  const winds = hourly.map((h) => parseWeatherNumber(h?.wind_speed)).filter((v) => v != null);
  const gusts = hourly.map((h) => parseWeatherNumber(h?.wind_gust)).filter((v) => v != null);
  const maxWind = winds.length ? Math.max(...winds) : null;
  const maxGust = gusts.length ? Math.max(...gusts) : null;
  if ((maxWind != null && maxWind >= 21) || (maxGust != null && maxGust >= 26)) {
    warnings.push({
      type: "wind",
      level: "경보",
      title: "강풍 경보",
      observed: [
        maxWind != null ? `예상 최대 풍속 ${maxWind.toFixed(1)}m/s` : "",
        maxGust != null ? `순간풍속 ${maxGust.toFixed(1)}m/s` : "",
      ]
        .filter(Boolean)
        .join(" · "),
      details: ["풍속 21m/s 이상 또는 순간 풍속 26m/s 이상이 예상될 때"],
    });
  } else if ((maxWind != null && maxWind >= 14) || (maxGust != null && maxGust >= 20)) {
    warnings.push({
      type: "wind",
      level: "주의보",
      title: "강풍 주의보",
      observed: [
        maxWind != null ? `예상 최대 풍속 ${maxWind.toFixed(1)}m/s` : "",
        maxGust != null ? `순간풍속 ${maxGust.toFixed(1)}m/s` : "",
      ]
        .filter(Boolean)
        .join(" · "),
      details: ["풍속 14m/s 이상, 순간 풍속 20m/s 이상이 예상될 때"],
    });
  }

  const pm10 = parseWeatherNumber(weather?.dust?.pm10);
  const pm25 = parseWeatherNumber(weather?.dust?.pm2_5);
  const dustObserved = [
    pm10 != null ? `PM10 ${pm10.toFixed(0)}㎍/m³` : "",
    pm25 != null ? `PM2.5 ${pm25.toFixed(0)}㎍/m³` : "",
  ]
    .filter(Boolean)
    .join(" · ");
  if ((pm25 != null && pm25 >= 150) || (pm10 != null && pm10 >= 300)) {
    warnings.push({
      type: "dust",
      level: "경보",
      title: "미세먼지 경보",
      observed: dustObserved,
      details: [
        "PM2.5 150μg/m³ 이상 또는 PM10 300μg/m³ 이상이 2시간 이상 지속인 때",
        "단, 경기개시 전에 미세먼지(초미세먼지 포함) 경보가 발령되었거나 경보 발령 기준 농도를 초과한 경우 취소여부를 결정하고, 경기개시 후에 미세먼지 경보가 발령되었을 경우 경기 취소여부를 결정한다. (경기 중 경보발령시 해당 이닝 종료 후 취소여부 결정)",
      ],
    });
  } else if ((pm25 != null && pm25 >= 75) || (pm10 != null && pm10 >= 150)) {
    warnings.push({
      type: "dust",
      level: "주의보",
      title: "미세먼지 주의보",
      observed: dustObserved,
      details: ["PM2.5 75μg/m³ 이상 또는 PM10 150μg/m³ 이상이 2시간 이상 지속인 때"],
    });
  }
  if (pm10 != null && pm10 >= 800) {
    warnings.push({
      type: "yellow_dust",
      level: "경보",
      title: "황사 경보",
      observed: dustObserved,
      details: [
        "황사로 인해 1시간 평균 미세먼지 농도 800㎍/㎥ 이상이 2시간 이상 지속될 것으로 예상될 때",
        "황사 주의보는 미세먼지 경보로 대체",
      ],
    });
  }
  return warnings;
};

const renderWeatherCancelWarnings = (weather) => {
  const warnings = buildWeatherCancelWarnings(weather);
  if (!warnings.length) return "";
  const cards = warnings
    .map((item) => {
      const details = (Array.isArray(item.details) ? item.details : [])
        .map((line) => `<li>${escapeHtml(line)}</li>`)
        .join("");
      let levelClass = "weather-alert--watch";
      if (item.level === "경보") levelClass = "weather-alert--warning";
      else if (item.level === "관심") levelClass = "weather-alert--info";
      return `
      <article class="weather-alert ${levelClass} weather-alert--${escapeHtml(item.type || "")}">
        <div class="weather-alert-top">
          <strong class="weather-alert-title">${escapeHtml(item.title || "")}</strong>
          <span class="weather-alert-level">${escapeHtml(item.level || "")}</span>
        </div>
        ${item.observed ? `<div class="weather-alert-observed">${escapeHtml(item.observed)}</div>` : ""}
        ${item.outlook ? `<p class="weather-alert-outlook">${escapeHtml(item.outlook)}</p>` : ""}
        ${details ? `<ul class="weather-alert-details">${details}</ul>` : ""}
      </article>`;
    })
    .join("");
  return `
    <div class="weather-alert-list">
      <h3 class="weather-alert-heading">기상 관련 경기 취소 기준 (해당 시)</h3>
      ${cards}
    </div>
  `;
};

const bindWeatherChartEvents = () => {
  const wrap = document.querySelector(".weather-chart-wrap");
  if (!wrap) return;
  const tip = wrap.querySelector(".weather-chart-tip");
  const svg = wrap.querySelector(".weather-chart-svg");
  if (!tip || !svg) return;

  const hideTip = () => {
    tip.hidden = true;
    tip.textContent = "";
  };

  wrap.querySelectorAll(".weather-chart-temp-hit").forEach((hit) => {
    hit.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const temp = hit.getAttribute("data-temp");
      const time = hit.getAttribute("data-time") || "";
      const weather = hit.getAttribute("data-weather") || "";
      if (!temp) return;
      tip.hidden = false;
      tip.textContent = `${time} ${temp}°C${weather ? ` · ${weather}` : ""}`;

      const svgRect = svg.getBoundingClientRect();
      const wrapRect = wrap.getBoundingClientRect();
      const cx = Number.parseFloat(hit.getAttribute("data-x") || "0");
      const cy = Number.parseFloat(hit.getAttribute("data-y") || "0");
      const viewW = Number.parseFloat(svg.getAttribute("viewBox")?.split(/\s+/)[2] || "640");
      const viewH = Number.parseFloat(svg.getAttribute("viewBox")?.split(/\s+/)[3] || "260");
      const px = svgRect.left - wrapRect.left + (cx / viewW) * svgRect.width;
      const py = svgRect.top - wrapRect.top + (cy / viewH) * svgRect.height;
      tip.style.left = `${Math.max(8, Math.min(wrapRect.width - 8, px))}px`;
      tip.style.top = `${Math.max(8, py - 14)}px`;
    });
  });

  wrap.addEventListener("click", (event) => {
    if (event.target.closest(".weather-chart-temp-hit")) return;
    hideTip();
  });
};

const renderWeatherHourlyChart = (hourly, dateLabel) => {
  const points = (Array.isArray(hourly) ? hourly : [])
    .map((item) => {
      const tempRaw = parseWeatherNumber(item?.temperature);
      const rainRaw = parseWeatherNumber(item?.rain_probability);
      return {
        time: String(item?.time_label || "").trim() || "-",
        weather: String(item?.weather || "-").trim() || "-",
        icon: WEATHER_ICON_MAP[item?.icon] || "🌤️",
        temp: tempRaw,
        rain: rainRaw != null ? Math.max(0, Math.min(100, rainRaw)) : 0,
        isGameStart: Boolean(item?.is_game_start),
      };
    })
    .filter((p) => p.time !== "-");
  if (points.length === 0) return "";

  const temps = points.map((p) => p.temp).filter((v) => v != null);
  const tempMin = temps.length ? Math.min(...temps) : 0;
  const tempMax = temps.length ? Math.max(...temps) : 30;
  const tempPad = Math.max(1, (tempMax - tempMin) * 0.18);
  // 30°C 기준선이 항상 보이도록 축 범위를 확장
  let yTempMin = Math.min(Math.floor(tempMin - tempPad), 28);
  let yTempMax = Math.max(Math.ceil(tempMax + tempPad), 32);
  if (yTempMax <= yTempMin) {
    yTempMin = 20;
    yTempMax = 35;
  }

  const width = 640;
  const height = 270;
  const pad = { top: 28, right: 44, bottom: 58, left: 40 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const n = points.length;
  const xAt = (i) => pad.left + (n <= 1 ? plotW / 2 : (i / (n - 1)) * plotW);
  const yTemp = (v) => {
    if (v == null || yTempMax === yTempMin) return pad.top + plotH / 2;
    return pad.top + ((yTempMax - v) / (yTempMax - yTempMin)) * plotH;
  };
  const yRain = (v) => pad.top + ((100 - v) / 100) * plotH;
  const barW = Math.max(3, Math.min(14, (plotW / Math.max(n, 1)) * 0.55));

  const rainBars = points
    .map((p, i) => {
      const x = xAt(i) - barW / 2;
      const y = yRain(p.rain);
      const h = Math.max(0, pad.top + plotH - y);
      return `<rect class="weather-chart-rain-bar" x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${h.toFixed(1)}" rx="2"></rect>`;
    })
    .join("");

  const tempPath = points
    .map((p, i) => {
      if (p.temp == null) return null;
      const cmd = i === 0 || points[i - 1]?.temp == null ? "M" : "L";
      return `${cmd}${xAt(i).toFixed(1)},${yTemp(p.temp).toFixed(1)}`;
    })
    .filter(Boolean)
    .join("");

  const heatLineY = yTemp(30);
  const heatLine = `
      <line class="weather-chart-heat-line" x1="${pad.left}" y1="${heatLineY.toFixed(1)}" x2="${pad.left + plotW}" y2="${heatLineY.toFixed(1)}"></line>
      <text class="weather-chart-heat-label" x="${pad.left + plotW - 2}" y="${(heatLineY - 5).toFixed(1)}" text-anchor="end">30°C</text>
    `;

  const tempDots = points
    .map((p, i) => {
      if (p.temp == null) return "";
      const cx = xAt(i);
      const cy = yTemp(p.temp);
      const tempText = Number.isInteger(p.temp) ? String(p.temp) : p.temp.toFixed(1);
      return `
        <circle class="weather-chart-temp-dot" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="3.4"></circle>
        <circle class="weather-chart-temp-hit" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="11"
          data-temp="${escapeHtml(tempText)}" data-time="${escapeHtml(p.time)}" data-weather="${escapeHtml(p.weather)}"
          data-x="${cx.toFixed(1)}" data-y="${cy.toFixed(1)}"></circle>`;
    })
    .join("");

  const gameStartIdx = points.findIndex((p) => p.isGameStart);
  const gameStartLine =
    gameStartIdx >= 0
      ? `<line class="weather-chart-game-line" x1="${xAt(gameStartIdx).toFixed(1)}" y1="${pad.top}" x2="${xAt(gameStartIdx).toFixed(1)}" y2="${pad.top + plotH}"></line>
         <text class="weather-chart-game-label" x="${xAt(gameStartIdx).toFixed(1)}" y="${pad.top - 8}" text-anchor="middle">경기시작</text>`
      : "";

  const labelStep = n > 16 ? 3 : n > 10 ? 2 : 1;
  const xLabels = points
    .map((p, i) => {
      if (i % labelStep !== 0 && i !== n - 1 && !p.isGameStart) return "";
      return `<text class="weather-chart-xlabel" x="${xAt(i).toFixed(1)}" y="${(height - 28).toFixed(1)}" text-anchor="middle">${escapeHtml(p.time)}</text>
        <text class="weather-chart-xicon" x="${xAt(i).toFixed(1)}" y="${(height - 8).toFixed(1)}" text-anchor="middle">${p.icon}</text>`;
    })
    .join("");

  const tempTicks = [yTempMin, 30, yTempMax].filter(
    (v, idx, arr) => arr.indexOf(v) === idx && v >= yTempMin && v <= yTempMax
  );
  const tempAxis = tempTicks
    .map(
      (v) =>
        `<text class="weather-chart-ylabel weather-chart-ylabel--temp${v === 30 ? " weather-chart-ylabel--heat" : ""}" x="${pad.left - 8}" y="${yTemp(v).toFixed(1)}" text-anchor="end" dominant-baseline="middle">${v}°</text>`
    )
    .join("");
  const rainAxis = [0, 50, 100]
    .map(
      (v) =>
        `<text class="weather-chart-ylabel weather-chart-ylabel--rain" x="${width - pad.right + 8}" y="${yRain(v).toFixed(1)}" text-anchor="start" dominant-baseline="middle">${v}%</text>`
    )
    .join("");

  return `
    <div class="weather-chart-wrap">
      <div class="weather-chart-head">
        <span class="weather-chart-date">${escapeHtml(dateLabel)}</span>
        <div class="weather-chart-legend">
          <span class="weather-chart-legend-item weather-chart-legend-item--temp">기온</span>
          <span class="weather-chart-legend-item weather-chart-legend-item--rain">강수확률</span>
          <span class="weather-chart-legend-item weather-chart-legend-item--heat">30°C 기준</span>
        </div>
      </div>
      <div class="weather-chart-canvas">
        <svg class="weather-chart-svg" viewBox="0 0 ${width} ${height}" role="img" aria-label="시간대별 기온·강수확률 그래프">
          <rect class="weather-chart-bg" x="${pad.left}" y="${pad.top}" width="${plotW}" height="${plotH}" rx="6"></rect>
          <line class="weather-chart-grid" x1="${pad.left}" y1="${yRain(50).toFixed(1)}" x2="${pad.left + plotW}" y2="${yRain(50).toFixed(1)}"></line>
          ${rainBars}
          ${heatLine}
          ${gameStartLine}
          ${tempPath ? `<path class="weather-chart-temp-line" d="${tempPath}" fill="none"></path>` : ""}
          ${tempDots}
          ${tempAxis}
          ${rainAxis}
          ${xLabels}
        </svg>
        <div class="weather-chart-tip" hidden></div>
      </div>
      <p class="weather-chart-hint">기온 점을 클릭하면 해당 시각 기온이 표시됩니다.</p>
    </div>
  `;
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
      ${renderWeatherHourlyChart(weather.hourly, weatherDateLabel)}
      ${renderWeatherCancelWarnings(weather)}
    </section>
  `;
};

const buildHanwhaRecent5FromSchedule = (g) => {
  const rows = Array.isArray(g?.season_schedule) ? g.season_schedule : [];
  const results = rows
    .filter((row) => row && row.is_final && (row.result === "승" || row.result === "패" || row.result === "무"))
    .slice(-5)
    .map((row) => row.result);
  if (results.length === 0) return "";
  return results.reverse().join("");
};

const renderTeamComparison = (tc, awayName, homeName, headToHead, g) => {
    if (!tc || !tc.away || !tc.home) return "";

    const { away, home } = tc;
    const hanwhaLast5 = buildHanwhaRecent5FromSchedule(g);
    const awayUsesHanwhaSchedule = awayName === "한화" && Boolean(hanwhaLast5);
    const homeUsesHanwhaSchedule = homeName === "한화" && Boolean(hanwhaLast5);
    const awayLast5 = awayUsesHanwhaSchedule ? hanwhaLast5 : away.last5;
    const homeLast5 = homeUsesHanwhaSchedule ? hanwhaLast5 : home.last5;

    const statRow = (label, awayVal, homeVal, awayWin, homeWin) => `
      <tr>
        <td class="cmp-val${awayWin ? " cmp-win" : ""}">${awayVal}</td>
        <td class="cmp-label">${label}</td>
        <td class="cmp-val${homeWin ? " cmp-win" : ""}">${homeVal}</td>
      </tr>
    `;

    const last5Row = (awayLast5, homeLast5) => {
      const dots = (seq, latestSide) => {
        const out = [];
        for (const c of String(seq || "")) {
          if (c === "승" || c === "패" || c === "무") out.push(c);
        }
        if (out.length === 0) return "—";
        const ordered = [...out].reverse();
        // KBO comparison data and Hanwha schedule data land in opposite recency order.
        const latestI = latestSide === "left" ? 0 : ordered.length - 1;
        return ordered
          .map((c, i) => {
            const kind = c === "승" ? "win" : c === "패" ? "loss" : "draw";
            const latest = i === latestI ? " last5-latest" : "";
            return `<span class="dot ${kind}${latest}">${c}</span>`;
          })
          .join("");
      };
      return `
        <tr>
          <td class="cmp-val">${dots(awayLast5, awayUsesHanwhaSchedule ? "right" : "left")}</td>
          <td class="cmp-label">최근 5경기</td>
          <td class="cmp-val">${dots(homeLast5, homeUsesHanwhaSchedule ? "right" : "left")}</td>
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
            ${last5Row(awayLast5, homeLast5)}
            ${statRow("평균자책점", away.era, home.era, away.era_win, home.era_win)}
            ${statRow("타율", away.avg, home.avg, away.avg_win, home.avg_win)}
            ${statRow("평균득점", away.runs_scored, home.runs_scored, away.runs_scored_win, home.runs_scored_win)}
            ${statRow("평균실점", away.runs_allowed, home.runs_allowed, away.runs_allowed_win, home.runs_allowed_win)}
          </tbody>
        </table>
      </section>
    `;
  };

const PLAYOFF_SPOTS = 5;

/** 한글 받침 여부. 영문 구단 약칭은 실제 호칭 기준으로 보정한다. */
const TEAM_NAME_BATCHIM = {
  KIA: false, // 기아
  KT: false, // 케이티
  LG: false, // 엘지
  NC: false, // 엔씨
  SSG: false, // 에스에스지
  SK: false,
  한화: false,
  삼성: true,
  두산: true,
  롯데: false,
  키움: true,
};

const hasBatchim = (word) => {
  const token = String(word || "").trim();
  if (!token) return false;
  if (Object.prototype.hasOwnProperty.call(TEAM_NAME_BATCHIM, token)) {
    return TEAM_NAME_BATCHIM[token];
  }
  const ch = token[token.length - 1];
  const code = ch.charCodeAt(0);
  if (code >= 0xac00 && code <= 0xd7a3) {
    return (code - 0xac00) % 28 !== 0;
  }
  // 영문/숫자 등은 모음처럼 끝나는 경우로 본다.
  return false;
};

const josaGa = (word) => `${word}${hasBatchim(word) ? "이" : "가"}`;
const josaUl = (word) => `${word}${hasBatchim(word) ? "을" : "를"}`;

const parseRankInt = (value) => {
  const n = Number.parseInt(String(value ?? "").replace(/[^\d-]/g, ""), 10);
  return Number.isFinite(n) ? n : null;
};

const countHanwhaRemainingGames = (schedule) => {
  const rows = Array.isArray(schedule) ? schedule : [];
  return rows.filter((row) => {
    if (!row || row.is_final || row.is_live) return false;
    if (row.result === "취소") return false;
    if (String(row.cancel_label || "").trim()) return false;
    return true;
  }).length;
};

const buildPlayoffRaceSummary = (g) => {
  const rankings = Array.isArray(g?.team_rankings) ? g.team_rankings : [];
  if (rankings.length < PLAYOFF_SPOTS + 1) return null;

  const remainingHH = countHanwhaRemainingGames(g?.season_schedule);
  const hhRaw =
    rankings.find((row) => row?.team_id === "HH" || String(row?.team_name || "").includes("한화")) ||
    null;
  if (!hhRaw) return null;

  const hhGames = parseRankInt(hhRaw.games) ?? 0;
  const impliedSeasonGames = hhGames + remainingHH;
  if (impliedSeasonGames <= 0) return null;

  const teams = rankings
    .map((row) => {
      const wins = parseRankInt(row.wins) ?? 0;
      const losses = parseRankInt(row.losses) ?? 0;
      const games = parseRankInt(row.games) ?? 0;
      const rank = parseRankInt(row.rank);
      const remaining = Math.max(0, impliedSeasonGames - games);
      return {
        team_id: String(row.team_id || ""),
        team_name: String(row.team_name || ""),
        rank,
        wins,
        losses,
        games,
        remaining,
        maxWins: wins + remaining,
      };
    })
    .filter((row) => row.rank != null)
    .sort((a, b) => a.rank - b.rank);

  const hh = teams.find((row) => row.team_id === "HH" || row.team_name.includes("한화"));
  if (!hh) return null;

  const cutTeam = teams.find((row) => row.rank === PLAYOFF_SPOTS) || teams[PLAYOFF_SPOTS - 1];
  const sixth = teams.find((row) => row.rank === PLAYOFF_SPOTS + 1) || teams[PLAYOFF_SPOTS];
  if (!cutTeam) return null;

  const magicOver = (target) => {
    if (!target) return null;
    return target.wins + target.remaining - hh.wins + 1;
  };

  // 매직: 진출권 안이면 6위 이하 전체, 밖이어도 현재 5위를 상대로 억지로 계산
  // + 5위 전패/전승 시 필요 승수를 함께 안내
  let magicNumber = 0;
  let magicLabel = "";
  const winsNeededBest = Math.max(0, cutTeam.wins - hh.wins + 1); // 5위 전패
  const winsNeededWorst = Math.max(0, cutTeam.maxWins - hh.wins + 1); // 5위 전승
  const bestText =
    winsNeededBest === 0
      ? "이미 5위 승수 이상"
      : winsNeededBest > hh.remaining
        ? `${winsNeededBest}승 필요(잔여 ${hh.remaining}경기라 부족)`
        : `${winsNeededBest}승 필요`;
  const worstText =
    winsNeededWorst === 0
      ? "이미 5위 최대 승수 이상"
      : winsNeededWorst > hh.remaining
        ? `${winsNeededWorst}승 필요(잔여 ${hh.remaining}경기라 자력 확정 어려움)`
        : `${winsNeededWorst}승 필요`;
  const winsScenarioText =
    hh.rank <= PLAYOFF_SPOTS
      ? `현재 ${hh.rank}위로 가을야구 진출권 안에 있습니다.`
      : `5위 ${cutTeam.team_name} 기준 필요 승수 — 전패 시: ${bestText}, 전승 시: ${worstText}.`;

  if (hh.rank <= PLAYOFF_SPOTS) {
    const threats = teams.filter((row) => row.rank > PLAYOFF_SPOTS);
    const values = threats.map((row) => magicOver(row)).filter((v) => v != null);
    magicNumber = values.length ? Math.max(0, ...values) : 0;
    magicLabel =
      magicNumber <= 0
        ? `가을야구 진출이 사실상 확정된 상태입니다. ${winsScenarioText}`
        : `한화가 ${magicNumber}승 더 하거나, 추격 팀이 ${magicNumber}패 더 하면(합쳐서 ${magicNumber}번) 가을야구 진출이 확정됩니다. ${winsScenarioText}`;
  } else {
    magicNumber = Math.max(0, magicOver(cutTeam) ?? 0);
    magicLabel =
      magicNumber <= 0
        ? `현재 5위 ${josaUl(cutTeam.team_name)} 상대로는 이미 매직넘버가 소멸된 상태입니다. ${winsScenarioText}`
        : `현재 5위 ${cutTeam.team_name} 기준으로 계산하면, 한화가 ${magicNumber}승 더 하거나 5위 ${josaGa(cutTeam.team_name)} ${magicNumber}패 더 하면(합쳐서 ${magicNumber}번) 가을야구 진출이 확정됩니다. ${winsScenarioText}`;
  }

  // 트래직: 탈락까지 남은 패수(한화 패 또는 5위/추격팀 승)
  let tragicNumber = hh.wins + hh.remaining - cutTeam.wins + 1;
  let tragicLabel = "";
  if (hh.rank <= PLAYOFF_SPOTS) {
    tragicNumber = sixth ? hh.wins + hh.remaining - sixth.wins + 1 : tragicNumber;
    tragicLabel =
      tragicNumber <= 0
        ? "이미 하위 팀에게 순위를 내줄 수 있는 임계점에 가깝습니다."
        : `한화가 ${tragicNumber}패 더 하거나, 바로 아래 추격 팀이 ${tragicNumber}승 더 하면 가을야구권에서 밀려날 수 있습니다.`;
  } else if (tragicNumber <= 0) {
    tragicLabel = "잔여 경기를 모두 이겨도 현재 5위 승수를 넘기기 어려워 진출이 사실상 어려운 상황입니다.";
  } else {
    tragicLabel = `한화가 ${tragicNumber}패 더 하거나, 현재 5위 ${josaGa(cutTeam.team_name)} ${tragicNumber}승 더 하면 가을야구 탈락이 확정됩니다.`;
  }
  tragicNumber = Math.max(0, tragicNumber);

  const gbToCut = (() => {
    if (hh.rank <= PLAYOFF_SPOTS) return null;
    const hhGb = Number.parseFloat(String(hhRaw.games_behind ?? "").replace(/[^\d.-]/g, ""));
    const cutRaw = rankings.find((row) => parseRankInt(row.rank) === PLAYOFF_SPOTS);
    const cutGb = Number.parseFloat(String(cutRaw?.games_behind ?? "").replace(/[^\d.-]/g, ""));
    if (Number.isFinite(hhGb) && Number.isFinite(cutGb)) {
      return Math.max(0, Number((hhGb - cutGb).toFixed(1)));
    }
    if (Number.isFinite(hhGb)) return hhGb;
    return null;
  })();

  return {
    rank: hh.rank,
    wins: hh.wins,
    losses: hh.losses,
    remaining: hh.remaining,
    impliedSeasonGames,
    cutTeamName: cutTeam.team_name,
    cutWins: cutTeam.wins,
    magicNumber,
    magicLabel,
    tragicNumber,
    tragicLabel,
    gamesBehindToCut: gbToCut,
    inPlayoffSpot: hh.rank <= PLAYOFF_SPOTS,
  };
};

const renderPlayoffRaceSection = (g) => {
  const summary = buildPlayoffRaceSummary(g);
  if (!summary) return "";

  const magicValue =
    summary.magicNumber <= 0 ? "확정" : String(summary.magicNumber);
  const tragicValue =
    summary.tragicNumber <= 0 && !summary.inPlayoffSpot
      ? "위험"
      : `${summary.tragicNumber}패`;

  return `
    <section class="playoff-race-section">
      <h2 class="cmp-title">가을야구 전망</h2>
      <p class="playoff-race-lead">
        한화는 현재 <strong>${summary.rank}위</strong> · ${summary.wins}승 ${summary.losses}패,
        남은 일정 <strong>${summary.remaining}경기</strong>
        ${summary.gamesBehindToCut != null ? `(5위와 ${summary.gamesBehindToCut}게임차)` : ""}
        기준입니다. 포스트시즌은 <strong>5위까지</strong> 진출합니다.
      </p>
      <div class="playoff-race-grid">
        <article class="playoff-race-card playoff-race-card--magic">
          <div class="playoff-race-kicker">매직 넘버</div>
          <div class="playoff-race-value">${escapeHtml(magicValue)}</div>
          <p class="playoff-race-desc">${escapeHtml(summary.magicLabel)}</p>
        </article>
        <article class="playoff-race-card playoff-race-card--tragic">
          <div class="playoff-race-kicker">트래직 넘버</div>
          <div class="playoff-race-value">${escapeHtml(tragicValue)}</div>
          <p class="playoff-race-desc">${escapeHtml(summary.tragicLabel)}</p>
        </article>
      </div>
      <p class="playoff-race-note">
        ※ 잔여 경기는 한화 시즌 일정 기준으로 추정했고, 타 구단 잔여 경기는 소화 경기 수 차이로 보정합니다.
        무승부·직접 대결·추후 편성되는 경기에 따라 숫자가 달라질 수 있습니다.
        순위·일정이 갱신될 때마다 자동으로 다시 계산됩니다.
      </p>
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
  // 등록·말소 모두 비어 있으면 섹션 자체를 숨긴다.
  if (!regList.length && !deregList.length) return "";
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
      ${regList.length ? `
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
            ${toRows(regList)}
          </tbody>
        </table>
      </div>` : ""}
      ${deregList.length ? `
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
            ${toRows(deregList)}
          </tbody>
        </table>
      </div>` : ""}
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
const KBO_TEAM_ID_BY_NAME = {
  한화: "HH",
  두산: "OB",
  삼성: "SS",
  롯데: "LT",
  SSG: "SK",
  키움: "WO",
  LG: "LG",
  KT: "KT",
  KIA: "HT",
  NC: "NC",
};
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

const formatLeagueResultLabel = (row) => {
  const cancelLabel = String(row?.cancel_label || "").trim();
  if (cancelLabel) return cancelLabel;
  const res = String(row?.result || "").trim();
  if (res === "취소" || res === "무" || res === "진행중") return res;
  if (res === "원정승") return `${row.away_team || "원정"} 승`;
  if (res === "홈승") return `${row.home_team || "홈"} 승`;
  return res;
};

const isMissingStarterName = (name) => {
  const token = String(name || "").trim();
  return !token || token === "-" || token === "미정" || token === "TBD" || token === "예정";
};

const renderLeagueResultsSection = (g) => {
  const raw = Array.isArray(g?.league_results_games)
    ? g.league_results_games
    : Array.isArray(g?.yesterday_league_games)
      ? g.yesterday_league_games
      : [];
  // 실제 경기 결과(승/무/진행중)가 하나도 없으면 섹션 자체를 숨긴다. (취소만 있는 날 포함)
  const gamesWithResults = raw.filter((row) => {
    const res = String(row?.result || "").trim();
    return Boolean(res) && res !== "취소";
  });
  if (gamesWithResults.length === 0) return "";
  const ymd = g.league_results_date || g.yesterday_league_date || "";
  const dt = parseYmdAsLocalDate(ymd);
  const titleDate = dt
    ? `${dt.getMonth() + 1}/${dt.getDate()}(${KOR_WEEKDAYS[dt.getDay()]})`
    : ymd;
  const sid = String(g?.season_id || "").trim();
  // 같은 날짜에 실경기가 있으면 취소 카드도 함께 보여 준다.
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
      const cancelLabel = String(row.cancel_label || "").trim();
      const isCancel = res === "취소" || Boolean(cancelLabel);
      const resLabel = formatLeagueResultLabel(row);
      let resClass = "yesterday-league-result";
      if (isCancel) resClass += " yesterday-league-result--cancel";
      else if (res === "무") resClass += " yesterday-league-result--draw";
      else if (res === "진행중") resClass += " yesterday-league-result--live";
      else if (res === "원정승") resClass += " yesterday-league-result--away";
      else if (res === "홈승") resClass += " yesterday-league-result--home";
      const hasScore =
        row.away_score !== "" &&
        row.away_score != null &&
        row.home_score !== "" &&
        row.home_score != null;
      const scoreText = isCancel && !hasScore ? "—" : `${row.away_score ?? "-"} : ${row.home_score ?? "-"}`;
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
            <strong class="${resClass}">${escapeHtml(resLabel)}</strong>
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
      <h2 class="cmp-title">경기 결과 <span class="yesterday-league-date">${titleDate}</span></h2>
      <p class="yesterday-league-note">경기 카드를 누르면 네이버 스포츠 중계·결과 페이지로 이동합니다.</p>
      <div class="yesterday-league-grid">${cards}</div>
    </section>
  `;
};

const renderLeagueProbableSection = (g) => {
  const raw = Array.isArray(g?.league_probable_games) ? g.league_probable_games : [];
  // 타 구장 선발 일정이 없으면(한화 경기만 남는 경우) 상단 선발 카드와 중복이므로 숨긴다.
  const otherGames = raw.filter(
    (row) =>
      !(isMissingStarterName(row?.away_starter) && isMissingStarterName(row?.home_starter))
  );
  if (otherGames.length === 0) return "";
  const hanwhaRow = {
    game_time: g?.game_time || "",
    stadium: g?.stadium || "",
    away_team: g?.away_team || "",
    home_team: g?.home_team || "",
    away_team_id: KBO_TEAM_ID_BY_NAME[g?.away_team] || "",
    home_team_id: KBO_TEAM_ID_BY_NAME[g?.home_team] || "",
    away_starter: g?.away_starter || "미정",
    home_starter: g?.home_starter || "미정",
  };
  const games = [hanwhaRow, ...otherGames];
  const deduped = [];
  const seen = new Set();
  for (const row of games) {
    const key = `${row.away_team || ""}|${row.home_team || ""}|${row.game_time || ""}|${row.stadium || ""}`;
    if (seen.has(key)) continue;
    seen.add(key);
    // 양 선발 모두 미정이면 카드로 띄우지 않는다.
    if (isMissingStarterName(row.away_starter) && isMissingStarterName(row.home_starter)) {
      continue;
    }
    deduped.push(row);
  }
  if (deduped.length === 0) return "";
  const ymd = g.league_probable_date || g.game_date_ymd || "";
  const dt = parseYmdAsLocalDate(ymd);
  const titleDate = dt
    ? `${dt.getMonth() + 1}/${dt.getDate()}(${KOR_WEEKDAYS[dt.getDay()]})`
    : ymd;
  const sid = String(g?.season_id || "").trim();
  const cards = deduped
    .map((row) => {
      const awayEm = getOpponentEmblemUrl(sid, row.away_team_id);
      const homeEm = getOpponentEmblemUrl(sid, row.home_team_id);
      const starterText = `${row.away_starter || "미정"} : ${row.home_starter || "미정"}`;
      return `
      <article class="yesterday-league-card yesterday-league-card--probable">
        <div class="yesterday-league-card-top">
          <div class="yesterday-league-side yesterday-league-side--away">
            ${awayEm ? `<img src="${escapeHtml(awayEm)}" alt="${escapeHtml(row.away_team)} 엠블럼" class="yesterday-league-emblem" loading="lazy" />` : ""}
            <span class="yesterday-league-team-name">${escapeHtml(row.away_team)}</span>
          </div>
          <div class="yesterday-league-center">
            <div class="yesterday-league-score yesterday-league-score--probable">${escapeHtml(starterText)}</div>
            <strong class="yesterday-league-result">선발</strong>
          </div>
          <div class="yesterday-league-side yesterday-league-side--home">
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
      <h2 class="cmp-title">예정 경기 선발 <span class="yesterday-league-date">${titleDate}</span></h2>
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
        ${renderMatchupRow(g)}
        <div class="row"><span class="label">구장:</span>${g.stadium}</div>
        <div class="row"><span class="label">한화 홈/원정:</span>${g.hanwha_home_away}</div>
      </div>
      <div class="game-pitcher-cols sub">
        <div class="pitcher-grid">
        ${renderPitcherCard(
          `${g.away_team || "원정"} 선발`,
          g.away_starter,
          g.away_starter_image,
          g.away_starter_stats,
          g.team_comparison?.away_emblem,
        )}
        ${renderPitcherCard(
          `${g.home_team || "홈"} 선발`,
          g.home_starter,
          g.home_starter_image,
          g.home_starter_stats,
          g.team_comparison?.home_emblem,
        )}
        </div>
      </div>
    </div>
    ${renderWeatherSection(g)}
    ${renderTeamComparison(g.team_comparison, g.away_team, g.home_team, g.head_to_head_summary, g)}
    ${renderLeagueProbableSection(g)}
    ${renderLeagueResultsSection(g)}
    ${renderLineupSection(g)}
    ${renderRegisterMoveSection(g)}
    ${renderPlayoffRaceSection(g)}
    ${renderSeriesSection(g)}
    ${renderEaglesTvSection(g)}
    ${renderLatestNewsSection(g)}
    ${renderTeamRankings(g.team_rankings, g.team_rank_date)}
  `;
  bindScheduleCalendarEvents();
  bindSunShadowEvents();
  bindWeatherChartEvents();
};

const shouldStartPolling = (g) => {
  if (!g) return false;
  if (g?.live_status?.is_live) return true;
  if (g?.live_status?.is_cancelled) return true;

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
