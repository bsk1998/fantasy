"""
scraper_olympics.py
Scraper pour https://www.olympics.com/fr/infos/coupe-du-monde-2026-...
Stratégie 1 : HTTP direct + BeautifulSoup
Stratégie 2 : Fallback IA (Groq/Gemini) sur le texte brut fourni
Stratégie 3 : Import JSON manuel structuré
"""

import re
import json
import logging
import httpx
from bs4 import BeautifulSoup
from typing import Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

OLYMPICS_URL = (
    "https://www.olympics.com/fr/infos/"
    "coupe-du-monde-2026-composition-equipes-selections-liste-joueurs"
)

SCRAPER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Cache-Control": "max-age=0",
}

# Postes reconnus en français et anglais
POSITION_MAP = {
    "gardien": "GK", "goalkeeper": "GK", "portero": "GK",
    "défenseur": "DEF", "defenseur": "DEF", "defender": "DEF", "defensor": "DEF",
    "milieu": "MID", "midfielder": "MID", "centrocampista": "MID",
    "attaquant": "ATT", "forward": "ATT", "delantero": "ATT",
    "ailier": "ATT", "buteur": "ATT",
}

# Prix par défaut selon le poste (modifiable en admin)
DEFAULT_PRICES = {"GK": 5.0, "DEF": 6.0, "MID": 7.5, "ATT": 9.0, "COACH": 8.0}


@dataclass
class Player:
    name: str
    position: str = "MID"
    number: Optional[int] = None
    club: Optional[str] = None
    age: Optional[int] = None
    caps: Optional[int] = None
    price: float = 7.5
    source: str = "olympics"


@dataclass
class Coach:
    name: str
    nationality: Optional[str] = None
    price: float = 8.0
    source: str = "olympics"


@dataclass
class TeamSquad:
    nation: str
    nation_code: Optional[str] = None
    group: Optional[str] = None
    coach: Optional[Coach] = None
    players: list = field(default_factory=list)

    def to_dict(self):
        d = asdict(self)
        d["players"] = [asdict(p) for p in self.players]
        d["coach"] = asdict(self.coach) if self.coach else None
        return d


# ─────────────────────────────────────────────
# STRATÉGIE 1 : Scraping HTTP direct
# ─────────────────────────────────────────────

async def fetch_page_html(url: str = OLYMPICS_URL) -> Optional[str]:
    """Télécharge le HTML de la page olympics.com."""
    try:
        async with httpx.AsyncClient(
            headers=SCRAPER_HEADERS,
            timeout=30,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            logger.info(f"[olympics] Page récupérée : {resp.status_code} ({len(resp.text)} chars)")
            return resp.text
    except httpx.HTTPStatusError as e:
        logger.warning(f"[olympics] HTTP {e.response.status_code} — site bloqué ou URL incorrecte")
        return None
    except Exception as e:
        logger.error(f"[olympics] Erreur réseau : {e}")
        return None


def parse_html_to_squads(html: str) -> list[TeamSquad]:
    """
    Parse le HTML d'olympics.com.
    La page est un article avec des sections par équipe :
      - Titre de section = nom de l'équipe (h2/h3 ou strong)
      - Listes ul/ol ou paragraphes = joueurs
      - Entraîneur = ligne contenant 'entraîneur' ou 'sélectionneur'
    """
    soup = BeautifulSoup(html, "html.parser")
    squads: list[TeamSquad] = []

    # Cherche le conteneur principal de l'article
    article = (
        soup.find("article")
        or soup.find("main")
        or soup.find("div", class_=re.compile(r"article|content|body", re.I))
        or soup
    )

    current_squad: Optional[TeamSquad] = None

    # Parcourt tous les éléments du contenu
    for tag in article.find_all(["h1", "h2", "h3", "h4", "ul", "ol", "p", "table"]):
        text = tag.get_text(separator=" ", strip=True)
        if not text:
            continue

        # ── Nouveau bloc équipe (heading avec un nom de pays) ──
        if tag.name in ("h2", "h3", "h4") and _looks_like_nation(text):
            if current_squad and current_squad.players:
                squads.append(current_squad)
            nation, code = _extract_nation(text)
            current_squad = TeamSquad(nation=nation, nation_code=code)
            continue

        if current_squad is None:
            continue

        # ── Table (parfois utilisée sur le site) ──
        if tag.name == "table":
            _parse_table(tag, current_squad)
            continue

        # ── Liste de joueurs ──
        if tag.name in ("ul", "ol"):
            for li in tag.find_all("li"):
                li_text = li.get_text(separator=" ", strip=True)
                player = _parse_player_line(li_text)
                if player:
                    current_squad.players.append(player)
            continue

        # ── Paragraphe : peut contenir l'entraîneur ou des joueurs séparés par virgule ──
        if tag.name == "p":
            low = text.lower()
            if any(kw in low for kw in ("entraîneur", "sélectionneur", "coach", "manager")):
                coach_name = _extract_coach_name(text)
                if coach_name:
                    current_squad.coach = Coach(
                        name=coach_name,
                        nationality=current_squad.nation,
                        price=DEFAULT_PRICES["COACH"],
                    )
            elif "," in text and len(text) > 30:
                # Peut être une liste de joueurs séparés par virgule
                for part in text.split(","):
                    player = _parse_player_line(part.strip())
                    if player:
                        current_squad.players.append(player)

    # N'oublie pas la dernière équipe
    if current_squad and current_squad.players:
        squads.append(current_squad)

    logger.info(f"[olympics] {len(squads)} équipes parsées depuis le HTML")
    return squads


def _parse_table(table_tag, squad: TeamSquad):
    """Parse une balise <table> pour en extraire les joueurs."""
    headers = [th.get_text(strip=True).lower() for th in table_tag.find_all("th")]
    for row in table_tag.find_all("tr")[1:]:  # skip header row
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if not cells:
            continue
        player = Player(name="")
        for i, val in enumerate(cells):
            if i < len(headers):
                h = headers[i]
                if any(k in h for k in ("nom", "name", "joueur", "player")):
                    player.name = val
                elif any(k in h for k in ("poste", "pos", "position")):
                    player.position = _normalize_position(val)
                elif any(k in h for k in ("num", "n°", "#")):
                    try:
                        player.number = int(re.sub(r"\D", "", val))
                    except ValueError:
                        pass
                elif any(k in h for k in ("club", "équipe")):
                    player.club = val
                elif any(k in h for k in ("âge", "age")):
                    try:
                        player.age = int(re.sub(r"\D", "", val))
                    except ValueError:
                        pass
            elif i == 0 and not player.name:
                player.name = val
        if player.name and len(player.name) > 2:
            player.price = DEFAULT_PRICES.get(player.position, 7.5)
            squad.players.append(player)


def _parse_player_line(line: str) -> Optional[Player]:
    """
    Parse une ligne de texte pour en extraire un joueur.
    Formats supportés :
      '10. Lionel Messi (Attaquant)'
      'Kylian Mbappé – Attaquant – Paris SG'
      'Kylian Mbappé (ATT, PSG)'
    """
    line = line.strip()
    if len(line) < 3 or _looks_like_section_title(line):
        return None

    player = Player(name="")

    # Numéro en début de ligne
    num_match = re.match(r"^(\d{1,2})[.\s-]+(.+)", line)
    if num_match:
        player.number = int(num_match.group(1))
        line = num_match.group(2).strip()

    # Parenthèses ou tirets contenant poste/club
    paren_match = re.search(r"\(([^)]+)\)", line)
    if paren_match:
        inside = paren_match.group(1)
        line = line.replace(paren_match.group(0), "").strip()
        parts = [p.strip() for p in re.split(r"[,/]", inside)]
        for part in parts:
            pos = _normalize_position(part)
            if pos != "MID" or part.upper() in ("MID", "MF"):
                player.position = pos
            elif len(part) > 2:
                player.club = part

    # Séparateurs tiret/barre
    if " – " in line or " - " in line or " | " in line:
        parts = re.split(r"\s[–\-|]\s", line)
        player.name = parts[0].strip()
        for p in parts[1:]:
            pos = _normalize_position(p)
            if pos != "MID" or p.upper() == "MID":
                player.position = pos
            elif len(p) > 2:
                player.club = p
    else:
        player.name = line.strip(" .-,;")

    # Validation minimale du nom (au moins 2 mots ou 4 chars)
    name = player.name.strip()
    if len(name) < 3 or name.isdigit() or _looks_like_section_title(name):
        return None

    player.name = name
    player.price = DEFAULT_PRICES.get(player.position, 7.5)
    return player


def _normalize_position(text: str) -> str:
    """Normalise un texte de poste vers GK/DEF/MID/ATT."""
    t = text.lower().strip()
    for key, val in POSITION_MAP.items():
        if key in t:
            return val
    t_upper = text.upper().strip()
    if t_upper in ("GK", "GKP", "POR"):
        return "GK"
    if t_upper in ("DEF", "CB", "LB", "RB", "WB"):
        return "DEF"
    if t_upper in ("MID", "MF", "CM", "DM", "AM", "CDM", "CAM"):
        return "MID"
    if t_upper in ("ATT", "FW", "ST", "LW", "RW", "CF", "SS"):
        return "ATT"
    return "MID"


def _looks_like_nation(text: str) -> bool:
    """Détermine si un heading ressemble à un nom d'équipe nationale."""
    words = text.strip().split()
    # Entre 1 et 5 mots, pas de ponctuation excessive, pas de chiffres seuls
    return (
        1 <= len(words) <= 5
        and not text[0].isdigit()
        and len(text) < 60
        and not any(c in text for c in ["?", ":", "www", "@"])
    )


def _extract_nation(text: str) -> tuple[str, Optional[str]]:
    """Extrait le nom de la nation et son code depuis un heading."""
    # Ex: "France 🇫🇷" ou "France (FRA)" ou "FRANCE"
    code_match = re.search(r"\(([A-Z]{2,3})\)", text)
    code = code_match.group(1) if code_match else None
    name = re.sub(r"\([^)]*\)", "", text)
    name = re.sub(r"[^\w\s\-'éèêëàâùûôîïç]", "", name, flags=re.UNICODE)
    return name.strip().title(), code


def _extract_coach_name(text: str) -> Optional[str]:
    """Extrait le nom de l'entraîneur d'une ligne."""
    # Ex: "Entraîneur : Didier Deschamps" ou "Sélectionneur : Luis Enrique"
    patterns = [
        r"(?:entraîneur|sélectionneur|coach|manager)\s*[:\–\-]\s*(.+)",
        r"(.+?)\s*(?:\(entraîneur\)|\(coach\))",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            name = m.group(1).strip(" .,;")
            if 3 < len(name) < 60:
                return name
    return None


def _looks_like_section_title(text: str) -> bool:
    """Filtre les textes qui ne sont pas des noms de joueurs."""
    low = text.lower()
    keywords = [
        "groupe", "groupe", "poule", "phase", "tour", "finale",
        "joueurs", "entraîneur", "sélection", "effectif",
        "gardiens", "défenseurs", "milieux", "attaquants",
        "liste", "composition", "sélectionné",
    ]
    return any(kw in low for kw in keywords) or text.isupper()


# ─────────────────────────────────────────────
# STRATÉGIE 2 : Parsing IA sur texte brut
# ─────────────────────────────────────────────

AI_PARSE_PROMPT = """
Tu es un assistant qui extrait des données structurées de listes de joueurs de football.

Voici du texte brut contenant des effectifs de la Coupe du Monde 2026.
Extrais TOUTES les équipes avec leurs joueurs et entraîneurs.

Réponds UNIQUEMENT avec un JSON valide, sans markdown ni explication :
{
  "squads": [
    {
      "nation": "France",
      "nation_code": "FRA",
      "group": "A",
      "coach": {"name": "Didier Deschamps", "price": 8.0},
      "players": [
        {"name": "Mike Maignan", "position": "GK", "number": 1, "club": "AC Milan", "price": 5.0},
        {"name": "Kylian Mbappé", "position": "ATT", "number": 10, "club": "Real Madrid", "price": 9.0}
      ]
    }
  ]
}

Postes valides : GK (gardien), DEF (défenseur), MID (milieu), ATT (attaquant)
Prix par défaut : GK=5.0, DEF=6.0, MID=7.5, ATT=9.0, COACH=8.0

Texte à analyser :
"""


async def parse_with_ai(raw_text: str, ai_service) -> tuple[list[TeamSquad], str]:
    """
    Utilise le service IA (Groq/Gemini) pour parser un texte brut
    contenant les effectifs et retourne une liste de TeamSquad.
    """
    if not ai_service:
        return [], "Service IA non disponible"

    prompt = AI_PARSE_PROMPT + raw_text[:15000]  # limite de tokens

    try:
        result_text = await ai_service.complete(prompt)
        # Nettoie le JSON (parfois l'IA ajoute des backticks)
        clean = re.sub(r"```(?:json)?", "", result_text).strip().strip("`")
        data = json.loads(clean)
        squads = _json_to_squads(data.get("squads", []))
        return squads, f"{len(squads)} équipes parsées par IA"
    except json.JSONDecodeError as e:
        logger.error(f"[olympics/ai] JSON invalide : {e}")
        return [], f"Erreur parsing JSON IA : {e}"
    except Exception as e:
        logger.error(f"[olympics/ai] Erreur IA : {e}")
        return [], f"Erreur IA : {e}"


def _json_to_squads(raw_squads: list) -> list[TeamSquad]:
    """Convertit une liste de dicts JSON en objets TeamSquad."""
    squads = []
    for s in raw_squads:
        squad = TeamSquad(
            nation=s.get("nation", "Inconnu"),
            nation_code=s.get("nation_code"),
            group=s.get("group"),
        )
        if s.get("coach"):
            c = s["coach"]
            squad.coach = Coach(
                name=c.get("name", ""),
                nationality=squad.nation,
                price=float(c.get("price", DEFAULT_PRICES["COACH"])),
            )
        for p in s.get("players", []):
            pos = _normalize_position(p.get("position", "MID"))
            squad.players.append(Player(
                name=p.get("name", ""),
                position=pos,
                number=p.get("number"),
                club=p.get("club"),
                age=p.get("age"),
                price=float(p.get("price", DEFAULT_PRICES.get(pos, 7.5))),
            ))
        if squad.nation and squad.players:
            squads.append(squad)
    return squads


# ─────────────────────────────────────────────
# STRATÉGIE 3 : Import JSON direct (manuel)
# ─────────────────────────────────────────────

def parse_from_json(json_data: dict) -> list[TeamSquad]:
    """
    Import direct depuis un JSON fourni manuellement.
    Même format que la réponse IA.
    """
    return _json_to_squads(json_data.get("squads", []))


# ─────────────────────────────────────────────
# FONCTION PRINCIPALE — orchestre les stratégies
# ─────────────────────────────────────────────

async def import_squads_from_olympics(
    ai_service=None,
    raw_text: Optional[str] = None,
    json_data: Optional[dict] = None,
    url: str = OLYMPICS_URL,
) -> tuple[list[TeamSquad], str, str]:
    """
    Point d'entrée principal.
    Retourne (squads, message, strategy_used).

    Ordre de priorité :
    1. json_data fourni explicitement  → import direct
    2. raw_text fourni                 → parsing IA
    3. Sinon                           → scraping HTTP
    """

    # Stratégie 3 : JSON manuel
    if json_data:
        squads = parse_from_json(json_data)
        if squads:
            return squads, f"{len(squads)} équipes importées (JSON manuel)", "json"

    # Stratégie 2 : texte brut via IA
    if raw_text and raw_text.strip():
        squads, msg = await parse_with_ai(raw_text, ai_service)
        if squads:
            return squads, msg, "ai_text"
        return [], f"Parsing IA échoué : {msg}", "ai_text"

    # Stratégie 1 : scraping HTTP
    html = await fetch_page_html(url)
    if html:
        squads = parse_html_to_squads(html)
        if squads:
            return squads, f"{len(squads)} équipes importées depuis olympics.com", "http"
        # HTML récupéré mais non parsé → essai IA dessus
        if ai_service:
            soup = BeautifulSoup(html, "html.parser")
            text_content = soup.get_text(separator="\n", strip=True)
            squads, msg = await parse_with_ai(text_content, ai_service)
            if squads:
                return squads, f"{msg} (HTML→IA)", "http_ai"

    return [], (
        "Impossible de récupérer les données. "
        "Copiez le contenu de la page olympics.com dans le champ 'Texte brut' "
        "et relancez l'import."
    ), "failed"