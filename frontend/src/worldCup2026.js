export const WC2026_GROUPS = {
  "Groupe A": ["Mexico", "South Africa", "South Korea", "UEFA Play-Off D"],
  "Groupe B": ["Canada", "UEFA Play-Off A", "Qatar", "Switzerland"],
  "Groupe C": ["Brazil", "Morocco", "Haiti", "Scotland"],
  "Groupe D": ["United States", "Paraguay", "Australia", "UEFA Play-Off C"],
  "Groupe E": ["Germany", "Curacao", "Ivory Coast", "Ecuador"],
  "Groupe F": ["Netherlands", "Japan", "UEFA Play-Off B", "Tunisia"],
  "Groupe G": ["Belgium", "Egypt", "Iran", "New Zealand"],
  "Groupe H": ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
  "Groupe I": ["France", "Senegal", "Intercontinental Play-Off 2", "Norway"],
  "Groupe J": ["Argentina", "Algeria", "Austria", "Jordan"],
  "Groupe K": ["Portugal", "Intercontinental Play-Off 1", "Uzbekistan", "Colombia"],
  "Groupe L": ["England", "Croatia", "Ghana", "Panama"],
};

export const KNOCKOUT_ROUNDS = [
  ["round32", "16es de finale", 16],
  ["round16", "8es de finale", 8],
  ["quarter", "Quarts", 4],
  ["semi", "Demi-finales", 2],
  ["third", "3e place", 1],
  ["final", "Finale", 1],
];

export const ANNEXES = [
  ["top_scorers", "Top buteurs"],
  ["top_assists", "Top passeurs"],
  ["best_players", "Meilleurs joueurs"],
  ["best_goalkeepers", "Meilleurs gardiens"],
  ["surprise_teams", "Equipes surprises"],
];

const GROUP_MATCH_DAYS = ["2026-06-11", "2026-06-15", "2026-06-19", "2026-06-23", "2026-06-26", "2026-06-27"];

export function buildFallbackMatches() {
  const pairings = [[0, 1], [2, 3], [0, 2], [1, 3], [0, 3], [1, 2]];
  let order = 1;

  return Object.entries(WC2026_GROUPS).flatMap(([group, teams], groupIndex) =>
    pairings.map(([homeIndex, awayIndex], matchIndex) => ({
      id: `SIM-${String(order).padStart(3, "0")}`,
      home: teams[homeIndex],
      away: teams[awayIndex],
      group,
      date: GROUP_MATCH_DAYS[matchIndex],
      home_score: null,
      away_score: null,
      is_finished: false,
      is_locked: false,
      status: "scheduled",
      display_order: order++,
      round: "group",
      stadium_slot: groupIndex + 1,
    }))
  );
}

export const FALLBACK_PLAYERS = Object.values(WC2026_GROUPS).flatMap((teams, groupIndex) =>
  teams.flatMap((team, teamIndex) => {
    const seed = groupIndex * 4 + teamIndex + 1;
    const basePrice = 4.5 + ((seed % 6) * 0.6);
    return [
      { id: seed * 10 + 1, name: `${team} Gardien`, position: "G", nationality: team, price: +(basePrice - 0.8).toFixed(1), points_total: 0, is_confirmed: true },
      { id: seed * 10 + 2, name: `${team} Defenseur`, position: "D", nationality: team, price: +(basePrice - 0.3).toFixed(1), points_total: 0, is_confirmed: true },
      { id: seed * 10 + 3, name: `${team} Milieu`, position: "M", nationality: team, price: +(basePrice + 0.2).toFixed(1), points_total: 0, is_confirmed: true },
      { id: seed * 10 + 4, name: `${team} Attaquant`, position: "A", nationality: team, price: +(basePrice + 0.7).toFixed(1), points_total: 0, is_confirmed: true },
    ];
  })
);

export const FALLBACK_COACHES = Object.values(WC2026_GROUPS).flatMap((teams, groupIndex) =>
  teams.map((team, teamIndex) => ({
    id: groupIndex * 4 + teamIndex + 1,
    name: `Selectionneur ${team}`,
    nationality: team,
    team_name: team,
    price: +(4 + (((groupIndex + teamIndex) % 5) * 0.5)).toFixed(1),
    points_total: 0,
    status: "present",
    is_confirmed: true,
  }))
);
