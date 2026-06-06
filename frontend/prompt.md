apres une analyse de claude, voilà pourquoi je n'arrive pas à ajouter des joueurs dans le module effictif dans le mode admin :

**Problème principal : Le endpoint `/api/admin/squad/parse` n'existe pas dans `admin_routes.py`**

Dans `AdminPanel.jsx`, la section Effectifs appelle :
```
POST /api/admin/squad/parse
```

Mais dans `admin_routes.py`, ce endpoint n'existe **pas**. Il y a seulement `/squad/inject` et `/ai/effectif`. Le frontend appelle une route fantôme.

**Problème secondaire : `/squad/inject` attend les joueurs en body JSON, mais le frontend envoie du texte brut**

Dans `AdminPanel.jsx`, `parseWithGroq` envoie `{ nation, raw_squad_text: rawText }` à `/squad/parse` (inexistant), puis `injectSquad` envoie correctement les joueurs via `/squad/inject` — mais seulement si le parsing a fonctionné, ce qui n'est jamais le cas.

**Problème tertiaire : La clé Groq**

La section "Paramètres" sauvegarde la clé en `localStorage` (`admin_groq_key`), mais le backend lit `GROQ_API_KEY` depuis `backend/.env`. Ces deux choses ne sont jamais synchronisées.

**Solution en 2 étapes :**

**Étape 1** — Ajouter la route manquante dans `backend/app/admin_routes.py`. Cherche la route `/squad/inject` et ajoute juste avant :

```python
class SquadParseRequest(BaseModel):
    nation: Optional[str] = None
    raw_squad_text: str

@router.post("/squad/parse")
async def parse_squad(req: SquadParseRequest, admin: dict = Depends(verify_admin)):
    """Parse un effectif via IA et retourne les données structurées."""
    if not ai_service:
        raise HTTPException(503, "Moteur IA non disponible.")
    if not (ai_service.groq_configured or ai_service.gemini_configured):
        raise HTTPException(503, "Aucune clé IA configurée (GROQ_API_KEY dans backend/.env).")

    raw = req.raw_squad_text.strip()
    if len(raw) < 10:
        raise HTTPException(400, "Texte trop court.")

    parsed_data, msg = await ai_service.parse_squad_list(raw)
    if not parsed_data:
        return {"status": "error", "message": msg, "parsed_data": None}

    if req.nation and not parsed_data.get("nation"):
        parsed_data["nation"] = req.nation

    _log_action("squad_parse_success", "ai_squad",
                target_id=parsed_data.get("nation", "N/A"), details=msg)
    return {"status": "success", "message": msg, "parsed_data": parsed_data}
```