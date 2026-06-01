"""
data_wc2026.py — INTENTIONNELLEMENT VIDE
=========================================

⚠️  Ce fichier ne contient AUCUNE donnée codée en dur.

Toutes les données (matchs, effectifs, entraîneurs, classements) sont :
  ✅ Scrappées en temps réel depuis Sofascore + Olympics via Groq IA
  ✅ Stockées dans la base de données (MatchResult, Player, Coach, TeamNation, etc.)
  ✅ Mises à jour automatiquement par le scheduler APScheduler

Voir : backend/app/scraper.py → scraping_complet()
Voir : backend/app/updater.py → tache_mise_a_jour_quotidienne()

Ne pas importer de données sportives depuis ce fichier.
"""
