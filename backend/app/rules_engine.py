"""
rules_engine.py — Moteur de calcul des points Fantasy Boulzazen
"""

from typing import Literal

Position = Literal["G", "D", "M", "A"]

BUTS_PAR_POSTE: dict = {"G": 8, "D": 6, "M": 5, "A": 4}
PASSES_PAR_POSTE: dict = {"G": 6, "D": 5, "M": 4, "A": 4}
CS_PAR_POSTE: dict = {"G": 5, "D": 4, "M": 1, "A": 0}
RECUPS_POSTES = frozenset({"G", "D", "M"})
PARADES_POSTES = frozenset({"G"})


def calculer_points_joueur(stats: dict, position: Position) -> dict:
    if position not in ("G", "D", "M", "A"):
        raise ValueError(f"Position invalide : {position!r}")

    detail = {"temps_de_jeu": 0, "buts": 0, "passes": 0, "clean_sheet": 0,
              "parades": 0, "recups": 0, "cartons": 0, "total": 0}

    if stats["minutes"] >= 90:
        detail["temps_de_jeu"] = 2
    elif stats["minutes"] > 0:
        detail["temps_de_jeu"] = 1

    detail["buts"] = stats["buts"] * BUTS_PAR_POSTE[position]
    detail["passes"] = stats["passes"] * PASSES_PAR_POSTE[position]

    if stats.get("clean_sheet", False):
        detail["clean_sheet"] = CS_PAR_POSTE[position]

    if position in PARADES_POSTES:
        detail["parades"] = (stats.get("parades", 0) // 3) * 3

    if position in RECUPS_POSTES:
        detail["recups"] = (stats.get("recups", 0) // 5) * 3

    detail["cartons"] = -(stats.get("jaune", 0) * 1) - (stats.get("rouge", 0) * 2)
    detail["total"] = sum(v for k, v in detail.items() if k != "total")
    return detail


def calculer_points_entraineur(stats: dict) -> dict:
    if stats["status"] == "suspended":
        return {"presence": 0, "resultat": 0, "ecart_bonus": 0,
                "coaching": 0, "cartons": 0, "total": 0}

    detail = {"presence": 1, "resultat": 0, "ecart_bonus": 0,
              "coaching": 0, "cartons": 0, "total": 0}

    ecart = stats["buts_marques"] - stats["buts_encaisses"]

    if stats.get("is_win", False):
        detail["resultat"] = 2
        if ecart >= 2:
            detail["ecart_bonus"] = (ecart // 2) * 3
    elif stats.get("is_loss", False):
        detail["resultat"] = -2
        ecart_abs = abs(ecart)
        if ecart_abs >= 2:
            detail["ecart_bonus"] = -((ecart_abs // 2) * 3)

    detail["coaching"] = (stats.get("buts_banc", 0) * 3 + stats.get("passes_banc", 0) * 2)
    detail["cartons"] = -(stats.get("jaune", 0) * 1) - (stats.get("rouge", 0) * 2)
    detail["total"] = sum(v for k, v in detail.items() if k != "total")
    return detail


def calculer_points_pronostic_score(prono_dom, prono_ext, reel_dom, reel_ext) -> int:
    if prono_dom == reel_dom and prono_ext == reel_ext:
        return 5

    def vainqueur(dom, ext):
        if dom > ext: return "dom"
        elif ext > dom: return "ext"
        return "nul"

    if vainqueur(prono_dom, prono_ext) == vainqueur(reel_dom, reel_ext):
        return 2
    return 0


def calculer_score_global_utilisateur(points_fantasy, points_pronos_scores,
                                       points_bracket, points_annexes) -> dict:
    total = points_fantasy + points_pronos_scores + points_bracket + points_annexes
    return {"fantasy": points_fantasy, "pronos_scores": points_pronos_scores,
            "bracket": points_bracket, "annexes": points_annexes, "total": total}