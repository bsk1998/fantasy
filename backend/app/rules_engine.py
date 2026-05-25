def calculer_points_joueur(stats: dict, position: str) -> int:
    """
    Calcule les points d'un joueur pour un match selon les règles exactes.

    Paramètres attendus dans 'stats' :
        - minutes    (int)  : minutes jouées
        - buts       (int)  : buts marqués
        - passes     (int)  : passes décisives
        - clean_sheet(bool) : clean sheet ou non
        - parades    (int)  : parades réalisées (Gardien)
        - recups     (int)  : récupérations de balle
        - jaune      (int)  : cartons jaunes reçus
        - rouge      (int)  : cartons rouges reçus

    Positions valides : 'G' (Gardien), 'D' (Défenseur), 'M' (Milieu), 'A' (Attaquant)
    """
    pts = 0

    # ── 1. Temps de jeu ────────────────────────────────────────────────────────
    if stats['minutes'] >= 90:
        pts += 2   # Match complet
    elif stats['minutes'] > 0:
        pts += 1   # Entré ou sorti avant la 90e

    # ── 2. Buts selon le poste ─────────────────────────────────────────────────
    if position == 'A':
        pts += stats['buts'] * 4
    elif position == 'M':
        pts += stats['buts'] * 5
    elif position == 'D':
        pts += stats['buts'] * 6
    elif position == 'G':
        pts += stats['buts'] * 8

    # ── 3. Passes décisives selon le poste ─────────────────────────────────────
    if position in ['A', 'M']:
        pts += stats['passes'] * 4
    elif position == 'D':
        pts += stats['passes'] * 5
    elif position == 'G':
        pts += stats['passes'] * 6

    # ── 4. Clean Sheet ─────────────────────────────────────────────────────────
    if stats['clean_sheet']:
        if position == 'G':
            pts += 5
        elif position == 'D':
            pts += 4
        elif position == 'M':
            pts += 1

    # ── 5. Événements par paliers ──────────────────────────────────────────────
    pts += (stats['parades'] // 3) * 3    # +3 pts par tranche de 3 parades
    pts += (stats['recups'] // 5) * 3     # +3 pts par tranche de 5 récupérations

    # ── 6. Malus Cartons ───────────────────────────────────────────────────────
    pts -= stats['jaune'] * 1
    pts -= stats['rouge'] * 2

    return pts


def calculer_points_entraineur(stats: dict) -> int:
    """
    Calcule les points de l'entraîneur selon les règles.

    Paramètres attendus dans 'stats' :
        - status      (str)  : 'present' ou 'suspended'
        - is_win      (bool) : victoire de l'équipe
        - is_loss     (bool) : défaite de l'équipe
        - buts_marques(int)  : buts marqués par l'équipe
        - buts_encaisses(int): buts encaissés par l'équipe
        - jaune       (int)  : cartons jaunes de l'entraîneur
        - rouge       (int)  : cartons rouges de l'entraîneur
        - buts_banc   (int)  : buts marqués par des remplaçants entrés en jeu
        - passes_banc (int)  : passes déc. réalisées par des remplaçants entrés en jeu
    """
    if stats['status'] == 'suspended':
        return 0

    pts = 0

    # ── 1. Présence sur le banc ────────────────────────────────────────────────
    if stats['status'] == 'present':
        pts += 1

    écart = stats['buts_marques'] - stats['buts_encaisses']

    # ── 2. Victoire + bonus écart de buts ──────────────────────────────────────
    if stats['is_win']:
        pts += 2
        if écart >= 2:
            paliers_ecart = écart // 2
            pts += paliers_ecart * 3   # +3 pts par tranche de 2 buts d'écart

    # ── 3. Défaite + malus écart de buts (effet miroir) ────────────────────────
    elif stats['is_loss']:
        pts -= 2
        ecart_negatif = abs(écart)
        if ecart_negatif >= 2:
            paliers_perte = ecart_negatif // 2
            pts -= paliers_perte * 3   # -3 pts par tranche de 2 buts d'écart

    # ── 4. Bonus joueurs sortis du banc ───────────────────────────────────────
    pts += stats['buts_banc'] * 3
    pts += stats['passes_banc'] * 2

    # ── 5. Malus cartons de l'entraîneur ──────────────────────────────────────
    pts -= stats['jaune'] * 1
    pts -= stats['rouge'] * 2

    return pts
