Agis en tant qu'expert Full-Stack Software Developer, architecte logiciel et designer UX/UI spécialisé en Python (FastAPI), React (Vite, Tailwind CSS) et intégration d'IA (Groq). Je développe une application de Fantasy League et de Pronostics pour la Coupe du Monde 2026 nommée "Fantasy Boulzazen".

Je veux que tu réarchitectures et conçoives l'intégralité du système (modèles de base de données, routes API FastAPI et composants UI React) en te basant sur les spécifications exactes détaillées ci-dessous. Supprime toutes les anciennes logiques statiques.

---

### 🏗️ ARCHITECTURE GÉNÉRALE & AUTOMATISATION (LAZY LOADING)

1. Système Privé : Il s'agit d'une ligue fermée entre amis. L'application gère l'inscription, la création de compte et l'accès sécurisé au classement général de la ligue.
2. Mise à jour "Lazy Loading" en temps réel : Je ne veux pas d'un serveur backend lourd avec des tâches de fond (Background Tasks) constantes ou des Cron Jobs gourmands. À chaque fois qu'un utilisateur se connecte ou actualise sa session, l'application déclenche automatiquement et de manière transparente un script de scraping et de décompte. S'il s'avère qu'aucun match n'a été joué depuis la dernière connexion globale, le système maintient les scores actuels pour garantir une connexion instantanée (Fast-cache).
3. Scraping Dynamique : Le backend intègre un script gratuit (Playwright asynchrone + BeautifulSoup) capable de lire et scraper en temps réel les résultats réels, les scores en direct, et les statistiques individuelles avancées des joueurs sur deux sites sources :
   - Sofascore (Matchs, classements et stats individuelles) : https://www.sofascore.com/fr/football/tournament/world/world-championship/16#id:58210,tab:knockout
   - Olympics (Compositions d'équipes officielles) : https://www.olympics.com/fr/infos/coupe-du-monde-2026-composition-equipes-selections-liste-joueurs
Le calcul et la mise à jour des points de ma base de données s'alimentent dynamiquement lors de ce processus.

---

### 🛠️ 1. LE MODE ADMIN (Gestion Totale & Intégration IA Groq)
Je veux un panneau d'administration sécurisé offrant une flexibilité absolue pour peupler le jeu :
- Remplissage flexible : Possibilité de remplir les listes de sélections (équipes), les joueurs, les entraîneurs, les groupes et le tableau final de deux manières :
  1. Manuellement via des formulaires classiques.
  2. Semi-automatiquement en envoyant un prompt textuel ou une photo (OCR + Analyse) directement à l'IA Groq intégrée pour qu'elle extraie, structure et injecte automatiquement les informations en base de données.
- Configuration des Règles du Jeu : Un écran permettant à l'administrateur de modifier dynamiquement les barèmes et règles de calcul des points pour chaque mode de jeu. Les barèmes définis ci-dessous doivent être stockés en BDD sous forme de variables lues par le moteur de calcul.

---

### 👥 2. SYSTÈME DE LIGUES AMICALES
- Ligues Privées : Chaque utilisateur peut créer ou rejoindre une ligue avec ses amis. Chaque joueur possède son propre compte autonome avec son propre total de points.
- Confidentialité & Compétitivité : Pour préserver le suspense, il est strictement IMPOSSIBLE de voir les compositions ou les pronostics détaillés des autres membres de la ligue au sein des écrans de jeu. Le seul endroit où l'on peut voir et comparer les scores des autres est l'écran dédié au "Mode Classement".

---

### 🛡️ 3. MODE FANTASY LEAGUE (Règles strictes de composition & Visual UX)
Les informations de ce mode sont tirées directement des données validées dans le Mode Admin ou le Scraping :
- Contraintes de l'effectif : Budget maximum de 100M pour concevoir une équipe complète de 15 joueurs + 1 Entraîneur. Limite stricte de 3 joueurs maximum par nation.
- Règle d'or de l'Entraîneur : L'entraîneur choisi ne doit avoir AUCUN joueur de sa propre nationalité au sein de l'effectif complet des 15 joueurs.
- Outils de gestion : L'utilisateur peut choisir ses formations tactiques et dispose d'une option de "Remplissage Automatique" (Auto-Fill) intelligent qui génère une équipe valide respectant scrupuleusement le budget, la limite par nation et la règle de l'entraîneur.
- Filtres de Recherche Avancés : Recherche par Nom, Sélection (Pays), Prix, et Disponibilité (affiche si la limite des 3 joueurs par équipe est atteinte). La recherche ou la suggestion s'adapte et se filtre automatiquement selon le poste sélectionné sur le terrain (Gardiens, Défenseurs, Milieux, Attaquants).
- Identité Visuelle (UX/UI Premium) : Sur le terrain, chaque joueur est graphiquement représenté par le maillot officiel de sa sélection nationale. L'emplacement ou le bouton du "Coach" est visuellement matérialisé sur le banc de touche de l'interface.

#### 🧮 Barème du Compteur de points personnalisé (Mode Fantasy) :
- Temps de jeu : Match joué EN ENTIER (+2 pts) | Joue jusqu'à 55 min ou rentre en cours de jeu (+1 pt).
- Buts marqués : Attaquant (+4 pts) | Milieu (+5 pts) | Défenseur (+6 pts) | Gardien (+8 pts).
- Passes décisives : Attaquant ou Milieu (+4 pts) | Défenseur (+5 pts) | Gardien (+6 pts).
- Solidité (Clean Sheet) : Gardien (+5 pts) | Défenseur (+4 pts) | Milieu (+1 pt).
- Gardien (Parades) : +3 pts toutes les 3 parades/arrêts.
- Défense (Récupérations) : +3 pts toutes les 5 récupérations de balle.
- Discipline : Carton jaune (-1 pt) | Carton rouge (-2 pts).
- Entraîneur (Règles uniques) :
  * Victoire de son équipe : +2 pts de base.
  * Bonus écart de buts : Si son équipe gagne par plus de 2 buts d'écart, l'entraîneur reçoit +3 points supplémentaires par tranche de 2 buts d'écart. (Exemples : Victoire 1-0 = 2 pts | Victoire 2-0 = 5 pts (2+3) | Victoire 4-0 = 8 pts (2+6)).
  * Défaite de son équipe : Logique inverse, il perd ses points selon le même barème d'écart de buts.
  * Présence : +1 pt si présent sur le banc | 0 pt si suspendu | Malus cartons identique aux joueurs.
  * Coaching gagnant : +3 pts si un joueur entré depuis son banc marque un but | +2 pts si le remplaçant fait une passe décisive.

---

### 🔮 4. MODE PRONOSTICS MATCHS (Indépendant)
Les joueurs prédisent indépendamment le score exact de chaque rencontre de la Coupe du Monde :
- Score exact trouvé (Ex: Prono 2-1, Fin du match 2-1) = 5 points.
- Bon vainqueur ou match nul trouvé, mais mauvais score (Ex: Prono 2-0, Fin du match 3-1) = 2 points.
- Mauvais pronostic (Mauvais résultat) = 0 point.

---

### 🗺️ 5. MODE PRONOSTICS TABLEAU DU TOURNOI (Bracket)
L'utilisateur doit remplir l'arbre complet du tournoi (Bracket complet) du début à la fin avant le coup d'envoi du tout premier match de la compétition.
- Phase de groupes : L'utilisateur prédit l'issue des poules. Les classements se calculent automatiquement en temps réel côté front. Le système calcule automatiquement le repêchage des meilleurs troisièmes pour afficher le tableau final. +5 pts sont accordés pour chaque bon classement exact trouvé dans un groupe.
- Équipes qualifiées : +5 pts pour chaque équipe qualifiée trouvée (incluant les meilleurs troisièmes).
- Phase à élimination directe (Cumul par tour jusqu'à la finale et le match de la 3ème place) :
  * +5 pts pour chaque équipe présente dans ce tour (même si elle n'est pas arrivée par le chemin exact prédit dans l'arbre).
  * +5 pts pour un match prédit exactement.
  * +5 pts pour chaque équipe qualifiée au tour suivant.
- Verrouillage strict : Dès le coup d'envoi du premier match officiel de la Coupe du Monde, le tableau de prédiction est COMPLÈTEMENT BLOQUÉ. Plus aucun changement n'est possible, sauf réclamation acceptée.

---

### 🎯 6. MODE PRÉDICTIONS ANNEXES (Bonus de fin de tournoi)
Avant le début de la compétition, le joueur doit obligatoirement pronostiquer ses quatre "Top 3" :
- Le Top 3 des meilleurs buteurs du tournoi.
- Le Top 3 des meilleurs passeurs du tournoi.
- Le Top 3 des meilleurs joueurs du tournoi (MVP).
- Le Top 3 des meilleurs jeunes joueurs.
Des points spécifiques (configurables par l'admin) seront accordés à la fin du tournoi si l'utilisateur a vu juste.

---

### 📊 7. MODE CLASSEMENT & 📢 MODE PLAINTE / RÉCLAMATION
- Mode Classement : Conserve sa logique actuelle de centralisation et d'affichage des scores globaux et par ligue amicale.
- Mode Plainte : Ajoute une fonctionnalité de "Réclamation". Un utilisateur peut soumettre un ticket concernant le calcul des points d'un match spécifique (ex: s'il conteste une statistique de passe décisive ou de temps de jeu). L'administrateur reçoit cette réclamation sur son panneau pour la valider (ce qui recalcule les points) ou la rejeter.