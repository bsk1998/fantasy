# backend/app/simulation_data.py
# Équipes CDM 2026 — groupes mis à jour

WC2026_GROUPS = {
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
}

GROUP_MATCH_DAYS = [
    "2026-06-11", "2026-06-15", "2026-06-19",
    "2026-06-23", "2026-06-26", "2026-06-27",
]


def build_fallback_matches():
    pairings = [(0, 1), (2, 3), (0, 2), (1, 3), (0, 3), (1, 2)]
    matches = []
    order = 1
    for group, teams in WC2026_GROUPS.items():
        for index, (home_idx, away_idx) in enumerate(pairings):
            matches.append({
                "id":            f"SIM-{order:03d}",
                "home":          teams[home_idx],
                "away":          teams[away_idx],
                "group":         group,
                "date":          GROUP_MATCH_DAYS[index],
                "home_score":    None,
                "away_score":    None,
                "is_finished":   False,
                "is_locked":     False,
                "status":        "scheduled",
                "display_order": order,
            })
            order += 1
    return matches


def build_fallback_players():
    players = []
    for group_index, teams in enumerate(WC2026_GROUPS.values()):
        for team_index, team in enumerate(teams):
            seed = group_index * 4 + team_index + 1
            base_price = 4.5 + ((seed % 6) * 0.6)
            players.extend([
                _player(seed * 10 + 1, f"{team} Gardien",   "G", team, base_price - 0.8),
                _player(seed * 10 + 2, f"{team} Défenseur", "D", team, base_price - 0.3),
                _player(seed * 10 + 3, f"{team} Milieu",    "M", team, base_price + 0.2),
                _player(seed * 10 + 4, f"{team} Attaquant", "A", team, base_price + 0.7),
            ])
    return players


def build_fallback_coaches():
    coaches = []
    for group_index, teams in enumerate(WC2026_GROUPS.values()):
        for team_index, team in enumerate(teams):
            coaches.append({
                "id":           group_index * 4 + team_index + 1,
                "name":         f"Sélectionneur {team}",
                "nationality":  team,
                "price":        round(4 + (((group_index + team_index) % 5) * 0.5), 1),
                "wins":         0,
                "losses":       0,
                "points_total": 0,
                "status":       "present",
            })
    return coaches


def build_fallback_teams():
    return [
        {"id": index + 1, "name": team, "is_confirmed": True, "is_locked": False, "flag": ""}
        for index, team in enumerate(
            team for teams in WC2026_GROUPS.values() for team in teams
        )
    ]


def _player(player_id, name, position, nationality, price):
    return {
        "id":           player_id,
        "name":         name,
        "position":     position,
        "nationality":  nationality,
        "price":        round(price, 1),
        "club":         None,
        "goals":        0,
        "assists":      0,
        "points_total": 0,
        "is_confirmed": True,
    }