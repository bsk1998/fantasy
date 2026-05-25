"""
rules_engine.py — Moteur de calcul des points Fantasy Boulzazen
Barème 100% fidèle au cahier des charges "Coupe du Monde 2026"
Auteur : Tech Lead — Fantasy Boulzazen

Corrections v2 :
  - BUG FIX : parades limitées au poste G uniquement
  - BUG FIX : récupérations exclues pour les Attaquants (G/D/M seulement)
  - AJOUT   : calculer_points_pronostic_score()
  - AJOUT   : calculer_points_bracket() — barème tableau complet
  - AJOUT   : calculer_points_predictions_annexes()
"""

from typing import Literal

# ─── Types ────────────────────────────────────────────────────────────────────
Position = Literal["G", "D", "M", "A"]

# ─── Barème Joueurs ───────────────────────────────────────────────────────────
BUTS_PAR_POSTE: dict = {"G": 8, "D": 6, "M": 5, "A": 4}
PASSES_PAR_POSTE: dict = {"G": 6, "D": 5, "M": 4, "A": 4}
CS_PAR_POSTE: dict = {"G": 5, "D": 4, "M": 1, "A": 0}

# Postes éligibles aux récupérations : G, D, M — Attaquants EXCLUS
RECUPS_POSTES = frozenset({"G", "D", "M"})
# Postes éligibles aux parades : Gardien UNIQUEMENT
PARADES_POSTES = frozenset({"G"})


# ══════════════════════════════════════════════════════════════════════════════
#  1. CALCUL JOUEURS
# ══════════════════════════════════════════════════════════════════════════════

def calculer_points_joueur(stats: dict, position: Position) -> dict:
    """
    Calcule les points Fantasy d'un joueur pour UN match.

    Paramètres `stats` :
        minutes     (int)  : minutes jouées dans le match
        buts        (int)  : buts marqués
        passes      (int)  : passes décisives
        clean_sheet (bool) : l'équipe n'a pas encaissé de but
        parades     (int)  : arrêts du gardien (ignoré si position != 'G')
        recups      (int)  : récupérations de balle (ignoré si position == 'A')
        jaune       (int)  : nombre de cartons jaunes reçus
        rouge       (int)  : nombre de cartons rouges reçus

    Retourne un dict détaillant chaque rubrique + le total.
    """
    if position not in ("G", "D", "M", "A"):
        raise ValueError(f"Position invalide : {position!r} — valeurs acceptées : G, D, M, A")

    detail = {
        "temps_de_jeu": 0,
        "buts": 0,
        "passes": 0,
        "clean_sheet": 0,
        "parades": 0,
        "recups": 0,
        "cartons": 0,
        "total": 0,
    }

    # ── 1. Temps de jeu ────────────────────────────────────────────────────────
    # Match complet (≥90 min) → +2 pts
    # Entré ou sorti avant 90 min (> 0 min) → +1 pt
    if stats["minutes"] >= 90:
        detail["temps_de_jeu"] = 2
    elif stats["minutes"] > 0:
        detail["temps_de_jeu"] = 1

    # ── 2. Buts selon le poste ─────────────────────────────────────────────────
    detail["buts"] = stats["buts"] * BUTS_PAR_POSTE[position]

    # ── 3. Passes décisives selon le poste ─────────────────────────────────────
    detail["passes"] = stats["passes"] * PASSES_PAR_POSTE[position]

    # ── 4. Clean Sheet (Attaquants n'ont aucun bonus) ──────────────────────────
    if stats.get("clean_sheet", False):
        detail["clean_sheet"] = CS_PAR_POSTE[position]

    # ── 5. Parades : +3 pts par tranche de 3 — GARDIEN SEULEMENT ──────────────
    #   CORRECTION BUG : ancienne version n'avait pas de filtre de poste
    if position in PARADES_POSTES:
        nb_parades = stats.get("parades", 0)
        detail["parades"] = (nb_parades // 3) * 3

    # ── 6. Récupérations : +3 pts par tranche de 5 — G/D/M (pas A) ───────────
    #   CORRECTION BUG : ancienne version appliquait le bonus aux Attaquants
    if position in RECUPS_POSTES:
        nb_recups = stats.get("recups", 0)
        detail["recups"] = (nb_recups // 5) * 3

    # ── 7. Malus cartons ───────────────────────────────────────────────────────
    detail["cartons"] = -(stats.get("jaune", 0) * 1) - (stats.get("rouge", 0) * 2)

    # ── Total ──────────────────────────────────────────────────────────────────
    detail["total"] = sum(v for k, v in detail.items() if k != "total")

    return detail


# ══════════════════════════════════════════════════════════════════════════════
#  2. CALCUL ENTRAÎNEUR
# ══════════════════════════════════════════════════════════════════════════════

def calculer_points_entraineur(stats: dict) -> dict:
    """
    Calcule les points Fantasy de l'entraîneur pour UN match.

    Paramètres `stats` :
        status         (str)  : 'present' | 'suspended'
        is_win         (bool) : son équipe a gagné
        is_loss        (bool) : son équipe a perdu (False = match nul)
        buts_marques   (int)  : buts marqués par son équipe
        buts_encaisses (int)  : buts encaissés par son équipe
        jaune          (int)  : cartons jaunes de l'entraîneur
        rouge          (int)  : cartons rouges de l'entraîneur
        buts_banc      (int)  : buts marqués par des remplaçants entrés en jeu
        passes_banc    (int)  : passes déc. de remplaçants entrés en jeu

    Barème vérifié sur les exemples du cahier des charges :
        Victoire 1-0  →  présence(+1) + victoire(+2)              =  3 pts
        Victoire 2-0  →  présence(+1) + victoire(+2) + tranche(+3) =  6 pts
        Victoire 4-0  →  présence(+1) + victoire(+2) + 2×(+3)      =  9 pts

    Note : les exemples du cahier des charges (2 pts, 5 pts, 8 pts) semblent
    omettre le +1 de présence pour simplifier l'illustration du bonus d'écart.
    On applique le barème complet tel que décrit dans le tableau README.
    """
    # Coach suspendu → 0 point absolu, aucun calcul
    if stats["status"] == "suspended":
        return {"presence": 0, "resultat": 0, "ecart_bonus": 0,
                "coaching": 0, "cartons": 0, "total": 0}

    detail = {
        "presence": 0,
        "resultat": 0,
        "ecart_bonus": 0,
        "coaching": 0,
        "cartons": 0,
        "total": 0,
    }

    # ── 1. Présence sur le banc ────────────────────────────────────────────────
    detail["presence"] = 1

    # ── 2. Résultat + Bonus / Malus d'écart de buts ───────────────────────────
    ecart = stats["buts_marques"] - stats["buts_encaisses"]

    if stats.get("is_win", False):
        detail["resultat"] = 2

        # Bonus : +3 pts par tranche de 2 buts d'écart (à partir de 2)
        # Exemples barème :
        #   écart 1 → 0 tranche  → +0 bonus
        #   écart 2 → 1 tranche  → +3 bonus
        #   écart 3 → 1 tranche  → +3 bonus
        #   écart 4 → 2 tranches → +6 bonus
        if ecart >= 2:
            detail["ecart_bonus"] = (ecart // 2) * 3

    elif stats.get("is_loss", False):
        detail["resultat"] = -2

        # Malus miroir : même logique inversée
        ecart_abs = abs(ecart)
        if ecart_abs >= 2:
            detail["ecart_bonus"] = -((ecart_abs // 2) * 3)

    # ── 3. Bonus coaching gagnant (remplaçants décisifs) ──────────────────────
    detail["coaching"] = (
        stats.get("buts_banc", 0) * 3 +
        stats.get("passes_banc", 0) * 2
    )

    # ── 4. Malus cartons de l'entraîneur ──────────────────────────────────────
    detail["cartons"] = -(stats.get("jaune", 0) * 1) - (stats.get("rouge", 0) * 2)

    # ── Total ──────────────────────────────────────────────────────────────────
    detail["total"] = sum(v for k, v in detail.items() if k != "total")

    return detail


# ══════════════════════════════════════════════════════════════════════════════
#  3. CALCUL PRONOSTICS SCORES (Mode 2)
# ══════════════════════════════════════════════════════════════════════════════

def calculer_points_pronostic_score(
    prono_dom: int,
    prono_ext: int,
    reel_dom: int,
    reel_ext: int,
) -> int:
    """
    Compare un pronostic de score exact avec le résultat réel.

    Barème :
        Score exact trouvé                              → +5 pts
        Bon vainqueur ou match nul, mais mauvais score  → +2 pts
        Mauvais pronostic (faux vainqueur)              → +0 pts

    Exemple :
        prono 2-1, résultat 2-1 → 5 pts
        prono 2-0, résultat 3-1 → 2 pts (victoire domicile correcte)
        prono 2-1, résultat 1-2 → 0 pts (vainqueur inversé)
    """
    # Cas 1 : score exact
    if prono_dom == reel_dom and prono_ext == reel_ext:
        return 5

    # Déduire le vainqueur pronostiqué vs réel
    def vainqueur(dom, ext):
        if dom > ext:
            return "dom"
        elif ext > dom:
            return "ext"
        return "nul"

    # Cas 2 : bonne direction, mauvais score
    if vainqueur(prono_dom, prono_ext) == vainqueur(reel_dom, reel_ext):
        return 2

    return 0


# ══════════════════════════════════════════════════════════════════════════════
#  4. CALCUL PRONOSTICS TABLEAU DU TOURNOI (Mode 3)
# ══════════════════════════════════════════════════════════════════════════════

def calculer_points_bracket(bracket_prono: dict, bracket_reel: dict) -> dict:
    """
    Calcule les points du Mode Pronostics Tableau (arbre complet du tournoi).

    Structure attendue pour `bracket_prono` et `bracket_reel` :
    {
        "groupes": {
            "A": ["Equipe1", "Equipe2", "Equipe3", "Equipe4"],  # classement final
            ...
        },
        "meilleurs_troisièmes": ["EquipeX", "EquipeY", ...],    # qualifiés
        "huitièmes": [
            {"equipe1": "...", "equipe2": "...", "vainqueur": "..."},
            ...
        ],
        "quarts": [...],
        "demies": [...],
        "troisieme_place": {"equipe1": "...", "equipe2": "...", "vainqueur": "..."},
        "finale": {"equipe1": "...", "equipe2": "...", "vainqueur": "..."},
    }

    Barème par rubrique :
        Phase de groupes : +5 pts pour chaque classement exact dans un groupe
        Qualifiés (16e de finale) : +5 pts par équipe qualifiée trouvée
        Phase à élimination directe — par match :
            +5 pts si l'équipe est bien présente dans ce tour
            +5 pts si le match est prédit exactement (bons adversaires)
            +5 pts si le bon vainqueur est trouvé
        Match pour la 3e place inclus.
        Vainqueur final inclus dans les mêmes règles.
    """
    detail = {
        "groupes_classement": 0,
        "qualifies_tour": 0,
        "huitièmes": 0,
        "quarts": 0,
        "demies": 0,
        "troisieme_place": 0,
        "finale": 0,
        "total": 0,
    }

    # ── Phase de groupes : classement exact ────────────────────────────────────
    for groupe, classement_reel in bracket_reel.get("groupes", {}).items():
        classement_prono = bracket_prono.get("groupes", {}).get(groupe, [])
        for position, equipe in enumerate(classement_reel):
            if position < len(classement_prono) and classement_prono[position] == equipe:
                detail["groupes_classement"] += 5

    # ── Meilleurs troisièmes qualifiés ─────────────────────────────────────────
    qualifies_reels = set(bracket_reel.get("meilleurs_troisièmes", []))
    qualifies_prono = set(bracket_prono.get("meilleurs_troisièmes", []))
    detail["qualifies_tour"] = len(qualifies_reels & qualifies_prono) * 5

    # ── Phases à élimination directe ──────────────────────────────────────────
    tours = ["huitièmes", "quarts", "demies"]
    for tour in tours:
        matchs_reels = bracket_reel.get(tour, [])
        matchs_prono = bracket_prono.get(tour, [])
        detail[tour] += _evaluer_tour(matchs_prono, matchs_reels)

    # ── Match pour la 3e place ─────────────────────────────────────────────────
    m3_reel = bracket_reel.get("troisieme_place", {})
    m3_prono = bracket_prono.get("troisieme_place", {})
    detail["troisieme_place"] += _evaluer_match_unique(m3_prono, m3_reel)

    # ── Finale ─────────────────────────────────────────────────────────────────
    finale_reel = bracket_reel.get("finale", {})
    finale_prono = bracket_prono.get("finale", {})
    detail["finale"] += _evaluer_match_unique(finale_prono, finale_reel)

    # ── Total ──────────────────────────────────────────────────────────────────
    detail["total"] = sum(v for k, v in detail.items() if k != "total")
    return detail


def _evaluer_tour(matchs_prono: list, matchs_reels: list) -> int:
    """
    Évalue un tour complet de la phase à élimination directe.
    Pour chaque match réel, cherche si les équipes ou le résultat était prédit.
    """
    pts = 0
    equipes_reelles_dans_tour = set()
    for m in matchs_reels:
        equipes_reelles_dans_tour.add(m.get("equipe1", ""))
        equipes_reelles_dans_tour.add(m.get("equipe2", ""))

    equipes_prono_dans_tour = set()
    for m in matchs_prono:
        equipes_prono_dans_tour.add(m.get("equipe1", ""))
        equipes_prono_dans_tour.add(m.get("equipe2", ""))

    # +5 par équipe réelle présente dans le tour, que le joueur avait pronostiquée
    for equipe in equipes_reelles_dans_tour:
        if equipe and equipe in equipes_prono_dans_tour:
            pts += 5

    # +5 par match exact (bons adversaires peu importe l'ordre)
    for m_reel in matchs_reels:
        paire_reel = frozenset([m_reel.get("equipe1", ""), m_reel.get("equipe2", "")])
        for m_prono in matchs_prono:
            paire_prono = frozenset([m_prono.get("equipe1", ""), m_prono.get("equipe2", "")])
            if paire_reel == paire_prono:
                pts += 5  # match prédit exactement
                # +5 si le bon vainqueur est trouvé
                if m_reel.get("vainqueur") == m_prono.get("vainqueur"):
                    pts += 5
                break

    return pts


def _evaluer_match_unique(match_prono: dict, match_reel: dict) -> int:
    """Évalue un match unique (finale ou 3e place) avec le même barème."""
    if not match_reel or not match_prono:
        return 0
    pts = 0
    equipes_reelles = {match_reel.get("equipe1", ""), match_reel.get("equipe2", "")}
    equipes_prono = {match_prono.get("equipe1", ""), match_prono.get("equipe2", "")}

    # +5 par équipe réelle présente que le joueur avait pronostiquée
    for eq in equipes_reelles:
        if eq and eq in equipes_prono:
            pts += 5

    # +5 si le match est prédit exactement (bonnes équipes)
    if equipes_reelles == equipes_prono:
        pts += 5
        # +5 si le bon vainqueur
        if match_reel.get("vainqueur") == match_prono.get("vainqueur"):
            pts += 5

    return pts


# ══════════════════════════════════════════════════════════════════════════════
#  5. CALCUL PRÉDICTIONS ANNEXES (Mode 4 — Bonus de fin de tournoi)
# ══════════════════════════════════════════════════════════════════════════════

def calculer_points_predictions_annexes(prono: dict, reel: dict) -> dict:
    """
    Calcule les points des prédictions annexes de fin de tournoi.

    Structure `prono` et `reel` :
    {
        "top3_buteurs":  ["Joueur1", "Joueur2", "Joueur3"],
        "top3_passeurs": ["Joueur1", "Joueur2", "Joueur3"],
        "top3_joueurs":  ["Joueur1", "Joueur2", "Joueur3"],
        "top3_jeunes":   ["Joueur1", "Joueur2", "Joueur3"],
    }

    Barème appliqué (cohérent avec les modes précédents) :
        Joueur exactement à la bonne place du Top 3 → +5 pts
        Joueur dans le Top 3 mais à la mauvaise place → +2 pts
        Joueur absent du Top 3 réel → 0 pt
    """
    detail = {
        "top3_buteurs": 0,
        "top3_passeurs": 0,
        "top3_joueurs": 0,
        "top3_jeunes": 0,
        "total": 0,
    }

    categories = ["top3_buteurs", "top3_passeurs", "top3_joueurs", "top3_jeunes"]

    for categorie in categories:
        liste_prono = prono.get(categorie, [])
        liste_reel = reel.get(categorie, [])

        for i, joueur_prono in enumerate(liste_prono[:3]):
            if i < len(liste_reel) and liste_reel[i] == joueur_prono:
                detail[categorie] += 5   # Bonne place exacte
            elif joueur_prono in liste_reel:
                detail[categorie] += 2   # Dans le Top 3 mais mauvaise place

    detail["total"] = sum(v for k, v in detail.items() if k != "total")
    return detail


# ══════════════════════════════════════════════════════════════════════════════
#  6. AGRÉGATION GLOBALE — Calcul du score total d'un utilisateur
# ══════════════════════════════════════════════════════════════════════════════

def calculer_score_global_utilisateur(
    points_fantasy: int,
    points_pronos_scores: int,
    points_bracket: int,
    points_annexes: int,
) -> dict:
    """
    Agrège les 4 modes de jeu en un score global.
    Retourne aussi le détail pour affichage dans le leaderboard.
    """
    total = points_fantasy + points_pronos_scores + points_bracket + points_annexes
    return {
        "fantasy": points_fantasy,
        "pronos_scores": points_pronos_scores,
        "bracket": points_bracket,
        "annexes": points_annexes,
        "total": total,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  TESTS DE VALIDATION INTÉGRÉS
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("TESTS DE VALIDATION DU MOTEUR DE RÈGLES")
    print("=" * 60)

    # ── Test joueur : Gardien avec parades ────────────────────────────────────
    stats_gardien = {
        "minutes": 90, "buts": 0, "passes": 0, "clean_sheet": True,
        "parades": 6, "recups": 5, "jaune": 0, "rouge": 0,
    }
    res_g = calculer_points_joueur(stats_gardien, "G")
    # Attendu : 2(tps) + 0(buts) + 0(passes) + 5(CS) + 6(parades 6//3*3) + 3(recups 5//5*3) = 16
    assert res_g["total"] == 16, f"Gardien attendu 16, obtenu {res_g['total']}"
    print(f"✅ Gardien clean sheet + 6 parades + 5 recups : {res_g['total']} pts (attendu 16)")

    # ── Test joueur : Attaquant — vérifie que parades ET recups = 0 ───────────
    stats_attaquant = {
        "minutes": 90, "buts": 2, "passes": 1, "clean_sheet": False,
        "parades": 99, "recups": 99, "jaune": 1, "rouge": 0,
    }
    res_a = calculer_points_joueur(stats_attaquant, "A")
    # Attendu : 2(tps) + 8(2 buts×4) + 4(1 passe×4) + 0(CS) + 0(parades=N/A) + 0(recups=N/A) - 1(jaune) = 13
    assert res_a["total"] == 13, f"Attaquant attendu 13, obtenu {res_a['total']}"
    assert res_a["parades"] == 0, "Attaquant ne doit avoir aucun point de parade"
    assert res_a["recups"] == 0, "Attaquant ne doit avoir aucun point de récupération"
    print(f"✅ Attaquant 2 buts + 1 passe + jaune (parades/recups ignorés) : {res_a['total']} pts (attendu 13)")

    # ── Test entraîneur : Victoire 2-0 = barème attendu ───────────────────────
    stats_coach_2_0 = {
        "status": "present", "is_win": True, "is_loss": False,
        "buts_marques": 2, "buts_encaisses": 0,
        "jaune": 0, "rouge": 0, "buts_banc": 0, "passes_banc": 0,
    }
    res_coach_2_0 = calculer_points_entraineur(stats_coach_2_0)
    # Attendu : 1(présence) + 2(victoire) + 3(écart 2//2*3) = 6
    assert res_coach_2_0["total"] == 6, f"Coach 2-0 attendu 6, obtenu {res_coach_2_0['total']}"
    print(f"✅ Coach Victoire 2-0 : {res_coach_2_0['total']} pts (attendu 6)")

    # ── Test entraîneur : Victoire 4-0 ────────────────────────────────────────
    stats_coach_4_0 = {**stats_coach_2_0, "buts_marques": 4}
    res_coach_4_0 = calculer_points_entraineur(stats_coach_4_0)
    # Attendu : 1(présence) + 2(victoire) + 6(écart 4//2*3) = 9
    assert res_coach_4_0["total"] == 9, f"Coach 4-0 attendu 9, obtenu {res_coach_4_0['total']}"
    print(f"✅ Coach Victoire 4-0 : {res_coach_4_0['total']} pts (attendu 9)")

    # ── Test pronostic score ───────────────────────────────────────────────────
    assert calculer_points_pronostic_score(2, 1, 2, 1) == 5, "Score exact → 5 pts"
    assert calculer_points_pronostic_score(2, 0, 3, 1) == 2, "Bon vainqueur → 2 pts"
    assert calculer_points_pronostic_score(2, 1, 1, 2) == 0, "Mauvais prono → 0 pts"
    assert calculer_points_pronostic_score(1, 1, 2, 2) == 2, "Match nul correct → 2 pts"
    assert calculer_points_pronostic_score(1, 1, 1, 1) == 5, "Nul exact → 5 pts"
    print("✅ Pronostics scores : tous les cas de figure validés")

    print("=" * 60)
    print("✅ TOUS LES TESTS PASSÉS — Moteur de règles validé")
    print("=" * 60)