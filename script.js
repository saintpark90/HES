const game = window.__NEXT_GAME__;
const container = document.getElementById("game-content");

if (!container) {
  throw new Error("game-content container not found");
}

if (!game) {
  container.innerHTML = "<p>가까운 일정에서 한화 이글스 경기 정보를 찾지 못했습니다.</p>";
} else {
  container.innerHTML = `
    <div class="row"><span class="label">경기일:</span>${game.game_date}</div>
    <div class="row"><span class="label">경기시간:</span>${game.game_time}</div>
    <div class="row"><span class="label">대진:</span>${game.matchup}</div>
    <div class="row"><span class="label">구장:</span>${game.stadium}</div>
    <div class="row"><span class="label">한화 홈/원정:</span>${game.hanwha_home_away}</div>
    <div class="row"><span class="label">상대팀:</span>${game.opponent}</div>
    <div class="row"><span class="label">한화 선발투수:</span>${game.hanwha_starter}</div>
    <div class="sub">
      <div class="row"><span class="label">원정팀 선발:</span>${game.away_starter}</div>
      <div class="row"><span class="label">홈팀 선발:</span>${game.home_starter}</div>
    </div>
  `;
}
