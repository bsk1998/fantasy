MATCHS_GROUPES = [
    {"id": 1, "domicile": "USA", "exterieur": "Canada", "groupe": "Groupe A", "date": "2026-06-11", "is_locked": False, "score_dom": None, "score_ext": None, "is_finished": False},
    {"id": 2, "domicile": "Mexique", "exterieur": "Jamaïque", "groupe": "Groupe A", "date": "2026-06-11", "is_locked": False, "score_dom": None, "score_ext": None, "is_finished": False},
    {"id": 3, "domicile": "France", "exterieur": "Belgique", "groupe": "Groupe B", "date": "2026-06-12", "is_locked": False, "score_dom": None, "score_ext": None, "is_finished": False},
    {"id": 4, "domicile": "Maroc", "exterieur": "Tunisie", "groupe": "Groupe B", "date": "2026-06-12", "is_locked": False, "score_dom": None, "score_ext": None, "is_finished": False},
    {"id": 5, "domicile": "Brésil", "exterieur": "Argentine", "groupe": "Groupe C", "date": "2026-06-13", "is_locked": False, "score_dom": None, "score_ext": None, "is_finished": False},
    {"id": 6, "domicile": "Uruguay", "exterieur": "Colombie", "groupe": "Groupe C", "date": "2026-06-13", "is_locked": False, "score_dom": None, "score_ext": None, "is_finished": False},
    {"id": 7, "domicile": "Angleterre", "exterieur": "Allemagne", "groupe": "Groupe D", "date": "2026-06-14", "is_locked": False, "score_dom": None, "score_ext": None, "is_finished": False},
    {"id": 8, "domicile": "Pays-Bas", "exterieur": "Croatie", "groupe": "Groupe D", "date": "2026-06-14", "is_locked": False, "score_dom": None, "score_ext": None, "is_finished": False},
    {"id": 9, "domicile": "Espagne", "exterieur": "Portugal", "groupe": "Groupe E", "date": "2026-06-15", "is_locked": False, "score_dom": None, "score_ext": None, "is_finished": False},
    {"id": 10, "domicile": "Italie", "exterieur": "Suisse", "groupe": "Groupe E", "date": "2026-06-15", "is_locked": False, "score_dom": None, "score_ext": None, "is_finished": False},
    {"id": 11, "domicile": "Japon", "exterieur": "Corée du Sud", "groupe": "Groupe F", "date": "2026-06-16", "is_locked": False, "score_dom": None, "score_ext": None, "is_finished": False},
    {"id": 12, "domicile": "Australie", "exterieur": "Iran", "groupe": "Groupe F", "date": "2026-06-16", "is_locked": False, "score_dom": None, "score_ext": None, "is_finished": False},
    {"id": 13, "domicile": "Sénégal", "exterieur": "Algérie", "groupe": "Groupe G", "date": "2026-06-17", "is_locked": False, "score_dom": None, "score_ext": None, "is_finished": False},
    {"id": 14, "domicile": "Nigeria", "exterieur": "Ghana", "groupe": "Groupe G", "date": "2026-06-17", "is_locked": False, "score_dom": None, "score_ext": None, "is_finished": False},
    {"id": 15, "domicile": "Côte d'Ivoire", "exterieur": "Égypte", "groupe": "Groupe H", "date": "2026-06-18", "is_locked": False, "score_dom": None, "score_ext": None, "is_finished": False},
    {"id": 16, "domicile": "Cameroun", "exterieur": "Mali", "groupe": "Groupe H", "date": "2026-06-18", "is_locked": False, "score_dom": None, "score_ext": None, "is_finished": False},
]

ENTRAINEURS = {
    "France": {"nom": "Didier Deschamps", "nationalite": "France", "prix": 5.0},
    "Belgique": {"nom": "Domenico Tedesco", "nationalite": "Belgique", "prix": 4.5},
    "Maroc": {"nom": "Walid Regragui", "nationalite": "Maroc", "prix": 4.5},
    "Argentine": {"nom": "Lionel Scaloni", "nationalite": "Argentine", "prix": 5.0},
    "Brésil": {"nom": "Dorival Júnior", "nationalite": "Brésil", "prix": 5.0},
    "Angleterre": {"nom": "Thomas Tuchel", "nationalite": "Allemagne", "prix": 5.0},
    "Espagne": {"nom": "Luis de la Fuente", "nationalite": "Espagne", "prix": 5.0},
    "Portugal": {"nom": "Roberto Martínez", "nationalite": "Espagne", "prix": 4.5},
    "Sénégal": {"nom": "Pape Thiaw", "nationalite": "Sénégal", "prix": 4.0},
    "Algérie": {"nom": "Vladimir Petković", "nationalite": "Suisse", "prix": 4.0},
}


def get_tous_les_matchs():
    return MATCHS_GROUPES
