Voici un **prompt de travail propre, structuré et directement utilisable dans une autre IA** (type Groq / Gemini / ChatGPT dev / agent code). Il est conçu pour corriger ton problème d’“effectif admin IA” dans ton projet Fantasy.

---

# 🧠 PROMPT DE TRAVAIL (À DONNER À UNE IA)

Tu peux copier-coller tel quel :

---

## 🎯 CONTEXTE DU PROJET

Tu travailles sur une application web/mobile appelée **Fantasy**, un jeu de football privé (type FIFA/UEFA Gaming) avec :

* Frontend React (AdminPanel)
* Backend FastAPI (Python)
* Base de données (Supabase ou PostgreSQL)
* Système d’administration pour gérer les équipes nationales et leurs effectifs

---

## ❌ PROBLÈME ACTUEL

Dans le mode admin :

* L’utilisateur peut envoyer un **prompt texte** ou une **capture d’écran**
* Le but est de **modifier automatiquement l’effectif d’une équipe nationale**
* MAIS actuellement :

  * le prompt n’est pas interprété correctement
  * les images ne sont pas exploitées
  * l’effectif n’est pas injecté correctement en base
  * le système n’a pas de vraie intelligence IA centralisée

---

## 🎯 OBJECTIF ATTENDU

Créer un système IA complet capable de :

### 1. INPUTS ACCEPTÉS

* Texte libre (prompt utilisateur)
* Image (capture d’écran d’effectif FIFA / tableau / liste joueurs)

---

### 2. TRAITEMENT IA OBLIGATOIRE

Utiliser les APIs disponibles :

* Groq API (LLM rapide)
* Gemini API (vision + compréhension avancée image)

L’IA doit :

* Comprendre le contenu
* Extraire une liste structurée de joueurs
* Identifier :

  * nom joueur
  * poste (GK, DEF, MID, ATT)
  * équipe nationale
  * éventuellement note / rating si présent

---

### 3. SORTIE OBLIGATOIRE (FORMAT STRICT JSON)

Le résultat doit toujours être :

```json
{
  "team": "France",
  "players": [
    {
      "name": "Kylian Mbappé",
      "position": "ATT",
      "rating": 91
    }
  ]
}
```

---

## ⚙️ FONCTIONNALITÉS À IMPLÉMENTER

### A. OCR / IMAGE → TEXTE

* Si input est une image :

  * utiliser Gemini Vision
  * extraire texte propre de l’image
  * nettoyer les données

---

### B. TEXTE → STRUCTURE

* utiliser Groq (LLM)
* transformer texte brut en JSON structuré effectif

---

### C. ROUTEUR IA

Créer une fonction centrale :

```python
def process_effectif(input_type, data):
```

Logique :

* si image → OCR (Gemini)
* si texte → parsing direct (Groq)
* retour JSON standardisé

---

## 🧠 RÈGLES IMPORTANTES

* Toujours retourner un JSON valide
* Ne jamais renvoyer du texte non structuré
* Gérer erreurs / données incomplètes
* Normaliser les positions :

  * goalkeeper → GK
  * defender → DEF
  * midfielder → MID
  * attacker → ATT

---

## 💾 INJECTION BASE DE DONNÉES

Ajouter fonction :

```python
def inject_team_effectif(team_name, players)
```

Elle doit :

* supprimer anciens joueurs de l’équipe
* insérer les nouveaux joueurs
* maintenir relation Team → Players

---

## 🔌 ENDPOINT BACKEND ATTENDU

Créer endpoint :

```
POST /ai/effectif
```

Input :

* image (optional)
* prompt (optional)

Output :

```json
{
  "status": "success",
  "data": { ...structured team... }
}
```

---

## 🚨 IMPORTANT

Le système doit être :

* robuste
* reproductible
* sans dépendance au format utilisateur
* capable de comprendre des screenshots FIFA ou listes texte désordonnées

---

## 🎯 OBJECTIF FINAL

Permettre à un admin de :

* envoyer une image ou un texte brut
* obtenir automatiquement un effectif propre
* injecter directement en base de données sans manipulation manuelle
