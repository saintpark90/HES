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
  `;
}
