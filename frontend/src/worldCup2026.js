// frontend/src/worldCup2026.js
// ⚽ Équipes officielles CDM 2026 — groupes mis à jour

export const WC2026_GROUPS = {
  "Groupe A": ["Mexique", "Afrique du Sud", "République de Corée", "Tchéquie"],
  "Groupe B": ["Canada", "Bosnie-Herzégovine", "Qatar", "Suisse"],
  "Groupe C": ["Brésil", "Maroc", "Haïti", "Écosse"],
  "Groupe D": ["États-Unis d'Amérique", "Paraguay", "Australie", "Türkiye"],
  "Groupe E": ["Allemagne", "Curaçao", "Côte d'Ivoire", "Équateur"],
  "Groupe F": ["Pays-Bas", "Japon", "Suède", "Tunisie"],
  "Groupe G": ["Belgique", "Égypte", "République islamique d'Iran", "Nouvelle-Zélande"],
  "Groupe H": ["Espagne", "Cabo Verde", "Arabie saoudite", "Uruguay"],
  "Groupe I": ["France", "Sénégal", "Iraq", "Norvège"],
  "Groupe J": ["Argentine", "Algérie", "Autriche", "Jordanie"],
  "Groupe K": ["Portugal", "République démocratique du Congo", "Ouzbékistan", "Colombie"],
  "Groupe L": ["Angleterre", "Croatie", "Ghana", "Panama"],
};

export const KNOCKOUT_ROUNDS = [
  ["round32", "16es de finale", 16],
  ["round16", "8es de finale", 8],
  ["quarter", "Quarts de finale", 4],
  ["semi", "Demi-finales", 2],
  ["third", "3e place", 1],
  ["final", "Finale", 1],
];

export const ANNEXES = [
  ["top_scorers",   "Top buteurs"],
  ["top_assists",   "Top passeurs"],
  ["best_players",  "Meilleurs joueurs"],
  ["best_goalkeepers", "Meilleurs gardiens"],
  ["surprise_teams","Équipes surprises"],
];

const GROUP_MATCH_DAYS = [
  "2026-06-11", "2026-06-15", "2026-06-19",
  "2026-06-23", "2026-06-26", "2026-06-27",
];

export function buildFallbackMatches() {
  const pairings = [[0,1],[2,3],[0,2],[1,3],[0,3],[1,2]];
  let order = 1;
  return Object.entries(WC2026_GROUPS).flatMap(([group, teams], groupIndex) =>
    pairings.map(([homeIndex, awayIndex], matchIndex) => ({
      id:            `SIM-${String(order).padStart(3, "0")}`,
      home:          teams[homeIndex],
      away:          teams[awayIndex],
      group,
      date:          GROUP_MATCH_DAYS[matchIndex],
      home_score:    null,
      away_score:    null,
      is_finished:   false,
      is_locked:     false,
      status:        "scheduled",
      display_order: order++,
      round:         "group",
      stadium_slot:  groupIndex + 1,
    }))
  );
}

export const FALLBACK_PLAYERS = Object.values(WC2026_GROUPS).flatMap((teams, groupIndex) =>
  teams.flatMap((team, teamIndex) => {
    const seed = groupIndex * 4 + teamIndex + 1;
    const base = 4.5 + ((seed % 6) * 0.6);
    return [
      { id: seed*10+1, name:`${team} Gardien`,    position:"G", nationality:team, price:+(base-0.8).toFixed(1), points_total:0, is_confirmed:true },
      { id: seed*10+2, name:`${team} Défenseur`,  position:"D", nationality:team, price:+(base-0.3).toFixed(1), points_total:0, is_confirmed:true },
      { id: seed*10+3, name:`${team} Milieu`,     position:"M", nationality:team, price:+(base+0.2).toFixed(1), points_total:0, is_confirmed:true },
      { id: seed*10+4, name:`${team} Attaquant`,  position:"A", nationality:team, price:+(base+0.7).toFixed(1), points_total:0, is_confirmed:true },
    ];
  })
);

export const FALLBACK_COACHES = Object.values(WC2026_GROUPS).flatMap((teams, groupIndex) =>
  teams.map((team, teamIndex) => ({
    id:           groupIndex * 4 + teamIndex + 1,
    name:         `Sélectionneur ${team}`,
    nationality:  team,
    team_name:    team,
    price:        +(4 + (((groupIndex + teamIndex) % 5) * 0.5)).toFixed(1),
    points_total: 0,
    status:       "present",
    is_confirmed: true,
  }))
);