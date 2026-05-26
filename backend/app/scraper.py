"""
scraper.py — Données statiques + fallback pour Fantasy Boulzazen WC 2026
"""

import logging

logger = logging.getLogger("fantasy_scraper")

_STATIC_SQUADS = {
    "France": [
        {"id": 101, "name": "M. Maignan",      "position": "G", "nationality": "Française",  "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 102, "name": "A. Areola",        "position": "G", "nationality": "Française",  "price": 4.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 103, "name": "W. Saliba",        "position": "D", "nationality": "Française",  "price": 9.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 104, "name": "T. Hernandez",     "position": "D", "nationality": "Française",  "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 105, "name": "D. Upamecano",     "position": "D", "nationality": "Française",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 106, "name": "J. Koundé",        "position": "D", "nationality": "Française",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 107, "name": "N. Tchouaméni",    "position": "M", "nationality": "Française",  "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 108, "name": "A. Rabiot",        "position": "M", "nationality": "Française",  "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 109, "name": "A. Griezmann",     "position": "M", "nationality": "Française",  "price": 11.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 110, "name": "K. Mbappé",        "position": "A", "nationality": "Française",  "price": 18.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 111, "name": "O. Dembélé",       "position": "A", "nationality": "Française",  "price": 10.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 112, "name": "M. Thuram",        "position": "A", "nationality": "Française",  "price": 9.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 113, "name": "B. Camavinga",     "position": "M", "nationality": "Française",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 114, "name": "Y. Fofana",        "position": "D", "nationality": "Française",  "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Argentine": [
        {"id": 201, "name": "E. Martínez",      "position": "G", "nationality": "Argentine",  "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 202, "name": "G. Montiel",       "position": "D", "nationality": "Argentine",  "price": 6.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 203, "name": "C. Romero",        "position": "D", "nationality": "Argentine",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 204, "name": "L. Martínez",      "position": "D", "nationality": "Argentine",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 205, "name": "N. Tagliafico",    "position": "D", "nationality": "Argentine",  "price": 6.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 206, "name": "E. Fernández",     "position": "M", "nationality": "Argentine",  "price": 9.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 207, "name": "R. De Paul",       "position": "M", "nationality": "Argentine",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 208, "name": "A. Mac Allister",  "position": "M", "nationality": "Argentine",  "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 209, "name": "L. Messi",         "position": "A", "nationality": "Argentine",  "price": 16.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 210, "name": "J. Álvarez",       "position": "A", "nationality": "Argentine",  "price": 11.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 211, "name": "A. Di María",      "position": "A", "nationality": "Argentine",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Brésil": [
        {"id": 301, "name": "Alisson",          "position": "G", "nationality": "Brésilienne","price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 302, "name": "Danilo",           "position": "D", "nationality": "Brésilienne","price": 6.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 303, "name": "Marquinhos",       "position": "D", "nationality": "Brésilienne","price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 304, "name": "Gabriel Magalhães","position": "D", "nationality": "Brésilienne","price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 305, "name": "Casemiro",         "position": "M", "nationality": "Brésilienne","price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 306, "name": "Lucas Paquetá",    "position": "M", "nationality": "Brésilienne","price": 9.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 307, "name": "B. Guimarães",     "position": "M", "nationality": "Brésilienne","price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 308, "name": "Vini Jr.",         "position": "A", "nationality": "Brésilienne","price": 16.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 309, "name": "Rodrygo",          "position": "A", "nationality": "Brésilienne","price": 11.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 310, "name": "Raphinha",         "position": "A", "nationality": "Brésilienne","price": 10.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 311, "name": "Endrick",          "position": "A", "nationality": "Brésilienne","price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Angleterre": [
        {"id": 401, "name": "J. Pickford",      "position": "G", "nationality": "Anglaise",  "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 402, "name": "K. Walker",        "position": "D", "nationality": "Anglaise",  "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 403, "name": "H. Maguire",       "position": "D", "nationality": "Anglaise",  "price": 6.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 404, "name": "J. Gomez",         "position": "D", "nationality": "Anglaise",  "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 405, "name": "L. Shaw",          "position": "D", "nationality": "Anglaise",  "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 406, "name": "D. Rice",          "position": "M", "nationality": "Anglaise",  "price": 10.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 407, "name": "J. Bellingham",    "position": "M", "nationality": "Anglaise",  "price": 14.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 408, "name": "P. Foden",         "position": "M", "nationality": "Anglaise",  "price": 12.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 409, "name": "H. Kane",          "position": "A", "nationality": "Anglaise",  "price": 13.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 410, "name": "B. Saka",          "position": "A", "nationality": "Anglaise",  "price": 11.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 411, "name": "C. Palmer",        "position": "A", "nationality": "Anglaise",  "price": 10.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Espagne": [
        {"id": 501, "name": "U. Simón",         "position": "G", "nationality": "Espagnole",  "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 502, "name": "D. Carvajal",      "position": "D", "nationality": "Espagnole",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 503, "name": "A. Laporte",       "position": "D", "nationality": "Espagnole",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 504, "name": "R. Le Normand",    "position": "D", "nationality": "Espagnole",  "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 505, "name": "M. Cucurella",     "position": "D", "nationality": "Espagnole",  "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 506, "name": "R. Merino",        "position": "M", "nationality": "Espagnole",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 507, "name": "P. Gavi",          "position": "M", "nationality": "Espagnole",  "price": 10.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 508, "name": "P. Barrios",       "position": "M", "nationality": "Espagnole",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 509, "name": "L. Yamal",         "position": "A", "nationality": "Espagnole",  "price": 13.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 510, "name": "A. Morata",        "position": "A", "nationality": "Espagnole",  "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 511, "name": "N. Williams",      "position": "A", "nationality": "Espagnole",  "price": 11.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Allemagne": [
        {"id": 601, "name": "M. ter Stegen",    "position": "G", "nationality": "Allemande",  "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 602, "name": "J. Kimmich",       "position": "D", "nationality": "Allemande",  "price": 10.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 603, "name": "A. Rüdiger",       "position": "D", "nationality": "Allemande",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 604, "name": "J. Tah",           "position": "D", "nationality": "Allemande",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 605, "name": "M. Mittelstädt",   "position": "D", "nationality": "Allemande",  "price": 6.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 606, "name": "T. Müller",        "position": "M", "nationality": "Allemande",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 607, "name": "J. Musiala",       "position": "M", "nationality": "Allemande",  "price": 13.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 608, "name": "F. Wirtz",         "position": "M", "nationality": "Allemande",  "price": 13.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 609, "name": "K. Havertz",       "position": "A", "nationality": "Allemande",  "price": 10.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 610, "name": "N. Füllkrug",      "position": "A", "nationality": "Allemande",  "price": 9.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 611, "name": "L. Gnonto",        "position": "A", "nationality": "Allemande",  "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": False},
    ],
    "Portugal": [
        {"id": 701, "name": "D. Costa",         "position": "G", "nationality": "Portugaise", "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 702, "name": "D. Dalot",         "position": "D", "nationality": "Portugaise", "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 703, "name": "R. Dias",          "position": "D", "nationality": "Portugaise", "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 704, "name": "N. Mendes",        "position": "D", "nationality": "Portugaise", "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 705, "name": "V. Fernandes",     "position": "M", "nationality": "Portugaise", "price": 11.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 706, "name": "R. Neves",         "position": "M", "nationality": "Portugaise", "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 707, "name": "J. Palhinha",      "position": "M", "nationality": "Portugaise", "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 708, "name": "C. Ronaldo",       "position": "A", "nationality": "Portugaise", "price": 14.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 709, "name": "R. Leão",          "position": "A", "nationality": "Portugaise", "price": 12.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 710, "name": "G. Ramos",         "position": "A", "nationality": "Portugaise", "price": 11.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Maroc": [
        {"id": 801, "name": "Y. Bounou",        "position": "G", "nationality": "Marocaine",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 802, "name": "A. Hakimi",        "position": "D", "nationality": "Marocaine",  "price": 11.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 803, "name": "R. Aguerd",        "position": "D", "nationality": "Marocaine",  "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 804, "name": "N. Mazraoui",      "position": "D", "nationality": "Marocaine",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 805, "name": "S. Amrabat",       "position": "M", "nationality": "Marocaine",  "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 806, "name": "I. Ziyech",        "position": "M", "nationality": "Marocaine",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 807, "name": "A. Ounahi",        "position": "M", "nationality": "Marocaine",  "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 808, "name": "Y. En-Nesyri",     "position": "A", "nationality": "Marocaine",  "price": 10.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 809, "name": "S. Benrahma",      "position": "A", "nationality": "Marocaine",  "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Algérie": [
        {"id": 901, "name": "R. M'Bolhi",       "position": "G", "nationality": "Algérienne", "price": 5.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 902, "name": "A. Mandi",         "position": "D", "nationality": "Algérienne", "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 903, "name": "D. Benlamri",      "position": "D", "nationality": "Algérienne", "price": 5.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 904, "name": "Y. Atal",          "position": "D", "nationality": "Algérienne", "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 905, "name": "H. Bennacer",      "position": "M", "nationality": "Algérienne", "price": 10.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 906, "name": "S. Feghouli",      "position": "M", "nationality": "Algérienne", "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 907, "name": "A. Mahrez",        "position": "A", "nationality": "Algérienne", "price": 11.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 908, "name": "B. Bounedjah",     "position": "A", "nationality": "Algérienne", "price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 909, "name": "A. Slimani",       "position": "A", "nationality": "Algérienne", "price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Sénégal": [
        {"id": 1001, "name": "E. Mendy",        "position": "G", "nationality": "Sénégalaise","price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1002, "name": "K. Koulibaly",    "position": "D", "nationality": "Sénégalaise","price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1003, "name": "A. Gaye",         "position": "D", "nationality": "Sénégalaise","price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1004, "name": "P. Gueye",        "position": "M", "nationality": "Sénégalaise","price": 8.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1005, "name": "S. Mané",         "position": "A", "nationality": "Sénégalaise","price": 12.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1006, "name": "B. Diallo",       "position": "M", "nationality": "Sénégalaise","price": 7.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1007, "name": "N. Jackson",      "position": "A", "nationality": "Sénégalaise","price": 10.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1008, "name": "L. Balde",        "position": "D", "nationality": "Sénégalaise","price": 6.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Japon": [
        {"id": 1101, "name": "S. Gonda",        "position": "G", "nationality": "Japonaise",  "price": 6.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1102, "name": "H. Sakai",        "position": "D", "nationality": "Japonaise",  "price": 6.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1103, "name": "K. Itakura",      "position": "D", "nationality": "Japonaise",  "price": 7.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1104, "name": "W. Endo",         "position": "M", "nationality": "Japonaise",  "price": 9.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1105, "name": "D. Mitoma",       "position": "A", "nationality": "Japonaise",  "price": 10.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1106, "name": "A. Ueda",         "position": "A", "nationality": "Japonaise",  "price": 9.0,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1107, "name": "K. Kamada",       "position": "M", "nationality": "Japonaise",  "price": 8.5,  "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
}


def get_all_players_market() -> list:
    all_players = []
    seen_names = set()
    for team_name, squad in _STATIC_SQUADS.items():
        for player in squad:
            name_key = player["name"].lower().strip()
            if name_key not in seen_names:
                seen_names.add(name_key)
                all_players.append({**player, "team": team_name})
    logger.info(f"Marché Fantasy : {len(all_players)} joueurs")
    return all_players


def recuperer_effectif_web(team_name: str):
    return _STATIC_SQUADS.get(team_name, None)