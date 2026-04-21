const game = window.__NEXT_GAME__;
const container = document.getElementById("game-content");

if (!container) {
  throw new Error("game-content container not found");
}

if (!game) {
  container.innerHTML = "<p>가까운 일정에서 한화 이글스 경기 정보를 찾지 못했습니다.</p>";
} else {
  const renderPitcherCard = (teamLabel, name, image, stats) => `
    <article class="pitcher-card">
      <img src="${image || "./thumbnail.jpg"}" alt="${name} 선수 사진" loading="lazy" />
      <div class="pitcher-body">
        <h3>${teamLabel}: ${name}</h3>
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

  const renderTeamComparison = (tc, awayName, homeName) => {
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

  container.innerHTML = `
    <div class="row"><span class="label">경기일:</span>${game.game_date}</div>
    <div class="row"><span class="label">경기시간:</span>${game.game_time}</div>
    <div class="row"><span class="label">대진:</span>${game.matchup}</div>
    <div class="row"><span class="label">구장:</span>${game.stadium}</div>
    <div class="row"><span class="label">한화 홈/원정:</span>${game.hanwha_home_away}</div>
    <div class="row"><span class="label">상대팀:</span>${game.opponent}</div>
    <div class="row"><span class="label">한화 선발투수:</span>${game.hanwha_starter}</div>
    <div class="sub">
      <div class="pitcher-grid">
        ${renderPitcherCard("원정팀 선발", game.away_starter, game.away_starter_image, game.away_starter_stats)}
        ${renderPitcherCard("홈팀 선발", game.home_starter, game.home_starter_image, game.home_starter_stats)}
      </div>
    </div>
    ${renderTeamComparison(game.team_comparison, game.away_team, game.home_team)}
  `;
}
