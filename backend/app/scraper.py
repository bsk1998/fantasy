"""
scraper.py — Moteur de scraping asynchrone avec Playwright + analyse Groq IA pour Fantasy Boulzazen WC 2026

Sources officielles ciblées :
  1. Scores & Calendrier  : https://www.fifa.com/fr/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures?country=DZ&wtw-filter=ALL
  2. Classements groupes  : https://www.fifa.com/fr/tournaments/mens/worldcup/canadamexicousa2026/standings
  3. Effectifs officiels  : https://www.olympics.com/fr/infos/coupe-du-monde-2026-composition-equipes-selections-liste-joueurs

Architecture :
  - Playwright en mode headless pour charger le JavaScript et récupérer le contenu rendu
  - Fallback sur httpx en cas d'erreur (pour légèreté)
  - BeautifulSoup4 pour l'extraction du HTML propre
  - Groq API (llama3-8b-8192) pour structurer les données en JSON propre
  - Cache intégré avec TTL pour éviter les requêtes excessives
  - Fallback sur les données statiques si le scraping échoue complètement
"""

import asyncio
import logging
import json
import os
import time
import re
from typing import Optional, List, Dict, Any

logger = logging.getLogger("fantasy_scraper")

# ── Tentative d'import des dépendances optionnelles ─────────────────────────
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    logger.warning("playwright non installé — pip install playwright")
    PLAYWRIGHT_AVAILABLE = False

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    logger.warning("httpx non installé — pip install httpx")
    HTTPX_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    logger.warning("beautifulsoup4 non installé — pip install beautifulsoup4")
    BS4_AVAILABLE = False

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    logger.warning("groq non installé — pip install groq")
    GROQ_AVAILABLE = False

# ── Configuration ─────────────────────────��───────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = "llama3-8b-8192"

# URLs sources officielles
URL_FIFA_FIXTURES = "https://www.fifa.com/fr/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures?country=DZ&wtw-filter=ALL"
URL_FIFA_STANDINGS = "https://www.fifa.com/fr/tournaments/mens/worldcup/canadamexicousa2026/standings"
URL_OLYMPICS_SQUADS = "https://www.olympics.com/fr/infos/coupe-du-monde-2026-composition-equipes-selections-liste-joueurs"

# Headers HTTP pour simuler un navigateur réel
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Cache simple en mémoire {clé: (timestamp, données)}
_cache: Dict[str, tuple] = {}
CACHE_TTL_SECONDS = 3600  # 1 heure

# Singleton pour le navigateur Playwright
_playwright_browser: Optional[Browser] = None


# ────────────────────────────────────────────────────────────────────────────
#  GESTION DU NAVIGATEUR PLAYWRIGHT
# ────────────────────────────────────────────────────────────────────────────

async def _get_playwright_browser() -> Optional[Browser]:
    """Initialise ou retourne le navigateur Playwright singleton."""
    global _playwright_browser
    if not PLAYWRIGHT_AVAILABLE:
        return None
    
    if _playwright_browser is None:
        try:
            playwright = await async_playwright().start()
            _playwright_browser = await playwright.chromium.launch(headless=True)
            logger.info("✅ Navigateur Playwright initialisé (headless mode)")
        except Exception as e:
            logger.error(f"❌ Impossible d'initialiser Playwright : {e}")
            return None
    
    return _playwright_browser


async def _close_playwright_browser() -> None:
    """Ferme le navigateur Playwright singleton."""
    global _playwright_browser
    if _playwright_browser:
        try:
            await _playwright_browser.close()
            _playwright_browser = None
            logger.info("✅ Navigateur Playwright fermé")
        except Exception as e:
            logger.error(f"⚠️ Erreur lors de la fermeture du navigateur : {e}")


# ────────────────────────────────────────────────────────────────────────────
#  UTILITAIRES CACHE
# ────────────────────────────────────────────────────────────────────────────

def _cache_get(key: str) -> Optional[Any]:
    """Retourne les données en cache si elles ne sont pas expirées."""
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_TTL_SECONDS:
            return data
        del _cache[key]
    return None


def _cache_set(key: str, data: Any) -> None:
    """Stocke des données dans le cache avec un timestamp."""
    _cache[key] = (time.time(), data)


# ────────────────────────────────────────────────────────────────────────────
#  REQUÊTES AVEC PLAYWRIGHT + FALLBACK HTTPX
# ────────────────────────────────────────────────────────────────────────────

async def _fetch_url_playwright(url: str, timeout: int = 30000) -> Optional[str]:
    """
    Récupère le contenu HTML d'une URL avec Playwright (JS rendu).
    Retourne le texte HTML ou None en cas d'échec.
    timeout en millisecondes.
    """
    browser = await _get_playwright_browser()
    if not browser:
        logger.warning(f"Playwright non disponible pour : {url}")
        return None

    page = None
    try:
        page = await browser.new_page()
        await page.set_extra_http_headers(HTTP_HEADERS)
        
        # Naviguer vers l'URL avec attente du chargement complet
        await page.goto(url, wait_until="networkidle", timeout=timeout)
        
        # Attendre un peu supplémentaire pour les scripts asynchrones
        await asyncio.sleep(2)
        
        # Extraire le contenu HTML rendu
        html = await page.content()
        logger.info(f"✅ Scraping Playwright réussi : {url[:60]}...")
        return html

    except Exception as e:
        logger.warning(f"⚠️ Erreur Playwright pour {url[:60]}... : {e}")
        return None
    finally:
        if page:
            try:
                await page.close()
            except:
                pass


async def _fetch_url_httpx(url: str, timeout: int = 20) -> Optional[str]:
    """
    Fallback : Récupère le contenu HTML d'une URL avec httpx (sans JS).
    Retourne le texte HTML ou None en cas d'échec.
    """
    if not HTTPX_AVAILABLE:
        logger.warning(f"httpx non disponible, impossible de fallback : {url}")
        return None

    try:
        async with httpx.AsyncClient(
            headers=HTTP_HEADERS,
            timeout=timeout,
            follow_redirects=True,
            verify=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            logger.info(f"✅ Scraping httpx réussi (fallback) : {url[:60]}...")
            return response.text

    except httpx.TimeoutException:
        logger.warning(f"⏰ Timeout httpx lors du scraping de : {url}")
    except httpx.HTTPStatusError as e:
        logger.warning(f"⚠️ Erreur HTTP {e.response.status_code} pour : {url}")
    except Exception as e:
        logger.error(f"❌ Erreur httpx inattendue pour {url} : {e}")

    return None


async def _fetch_url(url: str, timeout: int = 30) -> Optional[str]:
    """
    Récupère le contenu HTML d'une URL en priorité avec Playwright, 
    fallback sur httpx en cas d'erreur.
    """
    # Essayer Playwright en premier
    html = await _fetch_url_playwright(url, timeout=timeout * 1000)
    if html:
        return html

    # Fallback sur httpx
    logger.info(f"🔄 Fallback sur httpx pour : {url[:60]}...")
    return await _fetch_url_httpx(url, timeout=timeout)


# ────────────────────────────────────────────────────────────────────────────
#  NETTOYAGE ET EXTRACTION HTML
# ────────────────────────────────────────────────────────────────────────────

def _nettoyer_html(html: str, selecteur_principal: Optional[str] = None) -> str:
    """
    Nettoie le HTML brut pour n'extraire que le texte utile.
    Optionnellement cible un sélecteur CSS spécifique.
    """
    if not BS4_AVAILABLE:
        return html[:3000]  # Fallback : retourne les 3000 premiers chars

    soup = BeautifulSoup(html, "html.parser")

    # Supprimer les éléments inutiles
    for tag in soup(["script", "style", "nav", "footer", "head",
                     "iframe", "noscript", "svg", "img", "meta", "link"]):
        tag.decompose()

    # Cibler une section spécifique si demandé
    if selecteur_principal:
        cible = soup.select_one(selecteur_principal)
        if cible:
            texte = cible.get_text(separator="\n", strip=True)
        else:
            texte = soup.get_text(separator="\n", strip=True)
    else:
        texte = soup.get_text(separator="\n", strip=True)

    # Compresser les lignes vides multiples
    lignes = [l for l in texte.splitlines() if l.strip()]
    return "\n".join(lignes)[:4000]  # Limiter à 4000 chars pour Groq


# ────────────────────────────────────────────────────────────────────────────
#  ANALYSE PAR GROQ IA
# ────────────────────────────────────────────────────────────────────────────

def _appeler_groq(
    prompt_systeme: str, 
    contenu: str, 
    max_tokens: int = 2000
) -> Optional[Dict[str, Any]]:
    """
    Envoie du texte brut à l'IA Groq pour extraction et structuration JSON.
    Retourne un dict Python ou None si l'appel échoue.
    """
    if not GROQ_AVAILABLE or not GROQ_API_KEY:
        logger.warning("Groq non disponible ou clé API absente")
        return None

    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": prompt_systeme},
                {"role": "user", "content": contenu},
            ],
            max_tokens=max_tokens,
            temperature=0.1,  # Très déterministe pour l'extraction de données
        )
        texte_reponse = completion.choices[0].message.content

        # Extraire le JSON de la réponse (il peut être entouré de texte)
        match = re.search(r'\{[\s\S]*\}|\[[\s\S]*\]', texte_reponse)
        if match:
            return json.loads(match.group(0))
        else:
            logger.warning("Groq n'a pas retourné de JSON valide")
            return None

    except json.JSONDecodeError as e:
        logger.error(f"Erreur de parsing JSON Groq : {e}")
    except Exception as e:
        logger.error(f"Erreur appel Groq : {e}")

    return None


# ────────────────────────────────────────────────────────────────────────────
#  SCRAPING : SCORES & CALENDRIER FIFA
# ────────────────────────────────────────────────────────────────────────────

PROMPT_SYSTEME_SCORES = """Tu es un extracteur de données sportives spécialisé en football.
Analyse le texte d'une page web FIFA et extrais les matchs de la Coupe du Monde 2026.
Retourne UNIQUEMENT un JSON valide (pas de texte autour) avec cette structure :
{
  "matchs": [
    {
      "id": 1,
      "home": "Nom équipe domicile",
      "away": "Nom équipe extérieure",
      "group": "Groupe X ou Phase",
      "date": "YYYY-MM-DD",
      "home_score": null,
      "away_score": null,
      "is_finished": false,
      "is_locked": false
    }
  ]
}
Pour les matchs terminés, remplis home_score, away_score et mets is_finished=true.
Si le score n'est pas disponible, mets null.
Extrais TOUS les matchs visibles. Maximum 100 matchs."""


async def scraper_scores_fifa() -> List[Dict[str, Any]]:
    """
    Scrape le calendrier et les scores depuis la page FIFA officielle.
    Retourne une liste de matchs structurés.
    """
    cache_key = "fifa_scores"
    cached = _cache_get(cache_key)
    if cached:
        logger.info("✅ Scores FIFA récupérés depuis le cache")
        return cached

    logger.info("🌐 Scraping des scores FIFA en cours...")
    html = await _fetch_url(URL_FIFA_FIXTURES, timeout=35)

    if not html:
        logger.warning("⚠️ Impossible de scraper FIFA, retour aux données statiques")
        return _get_matchs_statiques()

    texte_propre = _nettoyer_html(html, selecteur_principal="main")
    resultat = _appeler_groq(PROMPT_SYSTEME_SCORES, texte_propre, max_tokens=3000)

    if resultat and isinstance(resultat.get("matchs"), list):
        matchs = resultat["matchs"]
        _cache_set(cache_key, matchs)
        logger.info(f"✅ {len(matchs)} matchs extraits via Groq IA")
        return matchs
    else:
        logger.warning("⚠️ Groq n'a pas pu extraire les matchs, retour statique")
        return _get_matchs_statiques()


# ────────────────────────────────────────────────────────────────────────────
#  SCRAPING : CLASSEMENTS FIFA
# ────────────────────────────────────────────────────────────────────────────

PROMPT_SYSTEME_STANDINGS = """Tu es un extracteur de données sportives.
Analyse le texte d'une page web FIFA et extrais les classements des groupes.
Retourne UNIQUEMENT un JSON valide avec cette structure :
{
  "groupes": {
    "Groupe A": [
      {"equipe": "Nom", "points": 9, "joues": 3, "gagnes": 3, "nuls": 0, "perdus": 0, "buts_pour": 8, "buts_contre": 2, "diff": 6}
    ]
  }
}
Extrais tous les groupes visibles."""


async def scraper_classements_fifa() -> Dict[str, List[Dict[str, Any]]]:
    """
    Scrape les classements de groupes depuis la page FIFA.
    Retourne un dict {groupe: [équipes triées]}.
    """
    cache_key = "fifa_standings"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    logger.info("🌐 Scraping des classements FIFA en cours...")
    html = await _fetch_url(URL_FIFA_STANDINGS, timeout=35)

    if not html:
        return {}

    texte_propre = _nettoyer_html(html)
    resultat = _appeler_groq(PROMPT_SYSTEME_STANDINGS, texte_propre)

    if resultat and "groupes" in resultat:
        groupes = resultat["groupes"]
        _cache_set(cache_key, groupes)
        logger.info(f"✅ Classements extraits pour {len(groupes)} groupes")
        return groupes

    return {}


# ────────────────────────────────────────────────────────────────────────────
#  SCRAPING : EFFECTIFS OLYMPICS
# ────────────────────────────────────────────────────────────────────────────

PROMPT_SYSTEME_SQUADS = """Tu es un extracteur de données footballistiques expert.
Analyse le texte d'une page web Olympics sur les effectifs de la Coupe du Monde 2026.
RÈGLE CRITIQUE : N'extrais QUE les équipes qui ont officiellement publié leur liste définitive COMPLÈTE.
Pour chaque équipe listée, vérifie que la liste complète est disponible avant de l'inclure.
Retourne UNIQUEMENT un JSON valide avec cette structure :
{
  "equipes_publiees": [
    {
      "nation": "Nom du pays en français",
      "entraineur": "Nom Prénom",
      "joueurs": [
        {
          "nom": "Prénom Nom",
          "poste": "G" ou "D" ou "M" ou "A",
          "club": "Nom du club",
          "numero": 1
        }
      ]
    }
  ]
}
Si une équipe n'a pas encore publié sa liste définitive, NE PAS l'inclure du tout.
Maximum 15 équipes pour rester dans les limites du contexte."""


async def scraper_effectifs_olympics() -> List[Dict[str, Any]]:
    """
    Scrape les effectifs officiels depuis la page Olympics.
    RÈGLE : Ne retourne que les équipes avec liste définitive publiée.
    """
    cache_key = "olympics_squads"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    logger.info("🌐 Scraping des effectifs Olympics en cours...")
    html = await _fetch_url(URL_OLYMPICS_SQUADS, timeout=40)

    if not html:
        logger.warning("⚠️ Page Olympics inaccessible")
        return []

    texte_propre = _nettoyer_html(html)
    resultat = _appeler_groq(PROMPT_SYSTEME_SQUADS, texte_propre, max_tokens=3000)

    if resultat and isinstance(resultat.get("equipes_publiees"), list):
        equipes = resultat["equipes_publiees"]
        _cache_set(cache_key, equipes)
        logger.info(f"✅ {len(equipes)} effectifs officiels extraits via Groq IA")
        return equipes

    return []


# ────────────────────────────────────────────────────────────────────────────
#  DÉTECTION DES NOUVELLES LISTES PUBLIÉES
# ────────────────────────────────────────────────────────────────────────────

PROMPT_SYSTEME_DETECTION = """Tu es un détecteur de nouvelles publications d'effectifs footballistiques.
Analyse ce texte et identifie UNIQUEMENT les nations pour lesquelles une liste définitive
complète de joueurs pour la Coupe du Monde 2026 a été officiellement publiée sur Olympics.
Retourne UNIQUEMENT un JSON valide :
{
  "nations_avec_liste_definitive": ["France", "Espagne", "Brésil"]
}
Si aucune liste n'est clairement identifiée, retourne une liste vide.
Les noms de pays doivent être en français."""


async def detecter_nouvelles_listes() -> List[str]:
    """
    Détecte dynamiquement quelles équipes ont publié leur liste définitive.
    Utilisé par updater.py pour savoir quoi mettre à jour.
    """
    logger.info("🔍 Détection des nouvelles listes définitives...")
    html = await _fetch_url(URL_OLYMPICS_SQUADS, timeout=40)

    if not html:
        return []

    texte_propre = _nettoyer_html(html)
    resultat = _appeler_groq(PROMPT_SYSTEME_DETECTION, texte_propre, max_tokens=500)

    if resultat and isinstance(resultat.get("nations_avec_liste_definitive"), list):
        nations = resultat["nations_avec_liste_definitive"]
        logger.info(f"✅ Nations avec liste publiée : {nations}")
        return nations

    return []


# ────────────────────────────────────────────────────────────────────────────
#  CONVERSION EFFECTIF OLYMPICS → FORMAT BASE DE DONNÉES
# ────────────────────────────────────────────────────────────────────────────

# Table de conversion des postes (depuis différentes notations)
_POSTE_MAP = {
    "gardien": "G",
    "goalkeeper": "G",
    "gk": "G",
    "g": "G",
    "défenseur": "D",
    "defender": "D",
    "def": "D",
    "d": "D",
    "milieu": "M",
    "midfielder": "M",
    "mid": "M",
    "m": "M",
    "attaquant": "A",
    "forward": "A",
    "att": "A",
    "a": "A",
    "ailier": "A",
    "striker": "A",
    "winger": "A",
}


def _normaliser_poste(poste_brut: str) -> str:
    """Normalise un poste dans le format G/D/M/A."""
    if not poste_brut:
        return "M"  # Défaut
    p = poste_brut.lower().strip()
    return _POSTE_MAP.get(p, p.upper()[:1] if p else "M")


# Compteur global d'ID pour les joueurs scrappés
_JOUEUR_ID_COUNTER = 9000


def convertir_effectif_pour_db(equipe_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convertit un effectif extrait par Groq IA en format compatible
    avec le modèle Player de notre base de données.
    """
    global _JOUEUR_ID_COUNTER

    nation = equipe_data.get("nation", "Inconnu")
    entraineur = equipe_data.get("entraineur", "")
    joueurs_bruts = equipe_data.get("joueurs", [])

    joueurs_formatés = []
    for j in joueurs_bruts:
        _JOUEUR_ID_COUNTER += 1
        joueurs_formatés.append({
            "id": _JOUEUR_ID_COUNTER,
            "name": j.get("nom", "Joueur inconnu"),
            "position": _normaliser_poste(j.get("poste", "M")),
            "nationality": nation,
            "price": _estimer_prix(j.get("poste", "M")),
            "goals": 0,
            "assists": 0,
            "points_total": 0,
            "is_confirmed": True,  # Car liste officielle publiée
            "team": nation,
            "club": j.get("club", ""),
            "numero": j.get("numero", 0),
        })

    return {
        "nation": nation,
        "entraineur": entraineur,
        "joueurs": joueurs_formatés,
        "is_definitive": True,
    }


def _estimer_prix(poste: str) -> float:
    """Attribue un prix Fantasy par défaut selon le poste."""
    poste_norm = _normaliser_poste(poste)
    prix_defaut = {"G": 5.5, "D": 6.0, "M": 7.0, "A": 7.5}
    return prix_defaut.get(poste_norm, 6.0)


# ────────────────────────────────────────────────────────────────────────────
#  DONNÉES STATIQUES DE FALLBACK
# ────────────────────────────────────────────────────────────────────────────

_STATIC_SQUADS = {
    "France": [
        {"id": 101, "name": "M. Maignan", "position": "G", "nationality": "Française", "price": 7.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 102, "name": "W. Saliba", "position": "D", "nationality": "Française", "price": 9.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 103, "name": "T. Hernandez", "position": "D", "nationality": "Française", "price": 9.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 104, "name": "N. Tchouaméni", "position": "M", "nationality": "Française", "price": 9.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 105, "name": "A. Griezmann", "position": "M", "nationality": "Française", "price": 11.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 106, "name": "K. Mbappé", "position": "A", "nationality": "Française", "price": 18.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 107, "name": "O. Dembélé", "position": "A", "nationality": "Française", "price": 10.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Argentine": [
        {"id": 201, "name": "E. Martínez", "position": "G", "nationality": "Argentine", "price": 9.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 202, "name": "C. Romero", "position": "D", "nationality": "Argentine", "price": 8.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 203, "name": "E. Fernández", "position": "M", "nationality": "Argentine", "price": 9.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 204, "name": "L. Messi", "position": "A", "nationality": "Argentine", "price": 16.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 205, "name": "J. Álvarez", "position": "A", "nationality": "Argentine", "price": 11.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Brésil": [
        {"id": 301, "name": "Alisson", "position": "G", "nationality": "Brésilienne", "price": 8.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 302, "name": "Marquinhos", "position": "D", "nationality": "Brésilienne", "price": 8.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 303, "name": "Vini Jr.", "position": "A", "nationality": "Brésilienne", "price": 16.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 304, "name": "Rodrygo", "position": "A", "nationality": "Brésilienne", "price": 11.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Angleterre": [
        {"id": 401, "name": "J. Pickford", "position": "G", "nationality": "Anglaise", "price": 7.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 402, "name": "J. Bellingham", "position": "M", "nationality": "Anglaise", "price": 14.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 403, "name": "H. Kane", "position": "A", "nationality": "Anglaise", "price": 13.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 404, "name": "B. Saka", "position": "A", "nationality": "Anglaise", "price": 11.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Espagne": [
        {"id": 501, "name": "U. Simón", "position": "G", "nationality": "Espagnole", "price": 7.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 502, "name": "L. Yamal", "position": "A", "nationality": "Espagnole", "price": 13.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 503, "name": "P. Gavi", "position": "M", "nationality": "Espagnole", "price": 10.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Algérie": [
        {"id": 901, "name": "R. M'Bolhi", "position": "G", "nationality": "Algérienne", "price": 5.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 902, "name": "A. Mandi", "position": "D", "nationality": "Algérienne", "price": 7.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 903, "name": "H. Bennacer", "position": "M", "nationality": "Algérienne", "price": 10.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 904, "name": "A. Mahrez", "position": "A", "nationality": "Algérienne", "price": 11.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Maroc": [
        {"id": 801, "name": "Y. Bounou", "position": "G", "nationality": "Marocaine", "price": 8.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 802, "name": "A. Hakimi", "position": "D", "nationality": "Marocaine", "price": 11.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 803, "name": "Y. En-Nesyri", "position": "A", "nationality": "Marocaine", "price": 10.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
    "Sénégal": [
        {"id": 1001, "name": "E. Mendy", "position": "G", "nationality": "Sénégalaise", "price": 8.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1002, "name": "K. Koulibaly", "position": "D", "nationality": "Sénégalaise", "price": 8.5, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
        {"id": 1003, "name": "S. Mané", "position": "A", "nationality": "Sénégalaise", "price": 12.0, "goals": 0, "assists": 0, "points_total": 0, "is_confirmed": True},
    ],
}


def _get_matchs_statiques() -> List[Dict[str, Any]]:
    """Retourne les matchs de la phase de groupes codés en dur (fallback)."""
    return [
        {"id": 1, "home": "USA", "away": "Canada", "group": "Groupe A", "date": "2026-06-11", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
        {"id": 2, "home": "Mexique", "away": "Jamaïque", "group": "Groupe A", "date": "2026-06-11", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
        {"id": 3, "home": "France", "away": "Belgique", "group": "Groupe B", "date": "2026-06-12", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
        {"id": 4, "home": "Maroc", "away": "Tunisie", "group": "Groupe B", "date": "2026-06-12", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
        {"id": 5, "home": "Brésil", "away": "Argentine", "group": "Groupe C", "date": "2026-06-13", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
        {"id": 6, "home": "Angleterre", "away": "Allemagne", "group": "Groupe D", "date": "2026-06-13", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
        {"id": 7, "home": "Espagne", "away": "Portugal", "group": "Groupe E", "date": "2026-06-14", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
        {"id": 8, "home": "Sénégal", "away": "Algérie", "group": "Groupe G", "date": "2026-06-15", "is_locked": False, "home_score": None, "away_score": None, "is_finished": False},
    ]


def get_all_players_market() -> List[Dict[str, Any]]:
    """
    Retourne tous les joueurs du marché Fantasy.
    Utilise les données statiques intégrées (fallback immédiat).
    """
    all_players = []
    seen_names = set()
    for team_name, squad in _STATIC_SQUADS.items():
        for player in squad:
            name_key = player["name"].lower().strip()
            if name_key not in seen_names:
                seen_names.add(name_key)
                all_players.append({**player, "team": team_name})
    logger.info(f"📊 Marché Fantasy : {len(all_players)} joueurs disponibles")
    return all_players


def recuperer_effectif_web(team_name: str) -> Optional[List[Dict[str, Any]]]:
    """Retourne l'effectif statique d'une équipe ou None si inconnu."""
    return _STATIC_SQUADS.get(team_name, None)


# ────────────────────────────────────────────────────────────────────────────
#  ORCHESTRATEUR : SCRAPING COMPLET EN UNE PASSE
# ────────────────────────────────────────────────────────────────────────────

async def scraping_complet() -> Dict[str, Any]:
    """
    Lance le scraping de toutes les sources en parallèle.
    Retourne un résumé de ce qui a été récupéré.
    """
    logger.info("🚀 Lancement du scraping complet (FIFA + Olympics)...")

    # Lancement en parallèle pour optimiser le temps de traitement
    resultats = await asyncio.gather(
        scraper_scores_fifa(),
        scraper_classements_fifa(),
        detecter_nouvelles_listes(),
        return_exceptions=True,  # Ne pas planter si l'un échoue
    )

    matchs = resultats[0] if not isinstance(resultats[0], Exception) else []
    classements = resultats[1] if not isinstance(resultats[1], Exception) else {}
    nouvelles_nations = resultats[2] if not isinstance(resultats[2], Exception) else []

    # Si de nouvelles listes sont détectées, les scraper aussi
    effectifs_nouveaux = []
    if nouvelles_nations:
        logger.info(f"📋 {len(nouvelles_nations)} nouvelles listes détectées, scraping des effectifs...")
        effectifs_bruts = await scraper_effectifs_olympics()
        effectifs_nouveaux = [
            convertir_effectif_pour_db(e)
            for e in effectifs_bruts
            if e.get("nation") in nouvelles_nations
        ]

    resume = {
        "matchs_scraped": len(matchs),
        "groupes_scraped": len(classements),
        "nouvelles_nations": nouvelles_nations,
        "effectifs_nouveaux": len(effectifs_nouveaux),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    logger.info(
        f"✅ Scraping complet terminé : {resume['matchs_scraped']} matchs, "
        f"{resume['groupes_scraped']} groupes, "
        f"{resume['effectifs_nouveaux']} effectifs mis à jour"
    )

    return {
        "matchs": matchs,
        "classements": classements,
        "effectifs": effectifs_nouveaux,
        "resume": resume,
    }
