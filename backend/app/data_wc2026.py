"""
data_wc2026.py — Données de la Coupe du Monde 2026
===================================================

⚠️ CE FICHIER EST MAINTENANT VIDE

Toutes les données (matchs, effectifs, entraîneurs, classements) sont désormais:
- Scrappées en temps réel depuis Sofascore et Olympics via Groq IA
- Stockées dans la base de données (tables MatchResult, Player, Coach, TeamNation, GroupStanding)
- Mises à jour automatiquement via le scheduler

Les fonctions précédentes ont été supprimées :
- MATCHS_GROUPES ❌ → MatchResult table
- ENTRAINEURS ❌ → Coach table
- get_tous_les_matchs() ❌ → get_matchs_actuels() dans updater.py

Voir backend/app/scraper.py pour le pipeline de scraping.
Voir backend/app/updater.py pour le scheduler intelligent.
"""

# Ce fichier est conservé pour la compatibilité des imports existants
# mais ne contient AUCUNE donnée codée en dur.
