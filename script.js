let game = window.__NEXT_GAME__;
let updatedAt = window.__UPDATED_AT__ || "";
const container = document.getElementById("game-content");
let pollTimer = null;

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
    const rows = rankings.map((row) => `
      <tr>
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
    `).join("");

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

const formatUpdatedAt = (value) => {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ko-KR", { hour12: false });
};

const renderGame = (g, refreshedAt) => {
  if (!g) {
    container.innerHTML = "<p>가까운 일정에서 한화 이글스 경기 정보를 찾지 못했습니다.</p>";
    return;
  }

  container.innerHTML = `
    <div class="updated-at">마지막 갱신: ${formatUpdatedAt(refreshedAt)}</div>
    ${renderLiveHeader(g)}
    <div class="row"><span class="label">경기일:</span>${g.game_date}</div>
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
    ${renderTeamComparison(g.team_comparison, g.away_team, g.home_team, g.head_to_head_summary)}
    ${renderTeamRankings(g.team_rankings, g.team_rank_date)}
  `;
};

const shouldStartPolling = (g) => {
  if (!g || g?.live_status?.is_final) return false;
  if (g?.live_status?.is_live) return true;
  if (!g.game_date_ymd) return false;

  const now = new Date();
  const today = now.toISOString().slice(0, 10);
  if (g.game_date_ymd !== today) return false;

  const start = new Date(`${today}T18:30:00`);
  return now >= start;
};

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
};

const refreshGameInfo = async () => {
  try {
    const response = await fetch("/api/game-info", { cache: "no-store" });
    if (!response.ok) return;
    const payload = await response.json();
    if (!payload?.ok) return;
    game = payload.game_info;
    updatedAt = payload.updated_at || new Date().toISOString();
    renderGame(game, updatedAt);
    if (game?.live_status?.is_final) stopPolling();
  } catch (err) {
    // Keep last rendered data when a transient refresh failure happens.
    console.debug("live refresh failed", err);
  }
};

const startPolling = () => {
  if (pollTimer) return;
  pollTimer = setInterval(refreshGameInfo, 60 * 1000);
};

renderGame(game, updatedAt);
if (shouldStartPolling(game)) {
  startPolling();
}
