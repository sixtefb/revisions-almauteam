# 🚀 Déployer la plateforme (gratuit) — ~15 min

Trois services : **GitHub** (code) → **Supabase** (base de données) → **Render** (site). Tout est gratuit ; seul le coach IA (clé Anthropic) est payant à l'usage.

## 1. GitHub (code)
1. Crée un compte sur github.com → **New repository** → nom `revisions-almauteam`, **Private** → Create.
2. Dézippe `revisions-almauteam.zip`, ouvre le dossier `revision-platform`.
3. Sur la page du repo : **uploading an existing file** → glisse **tout le contenu** du dossier (pas le dossier lui-même ; ne mets PAS `accounts_PRIVE.txt`) → **Commit changes**.

## 2. Supabase (base de données, gratuit)
1. supabase.com → **New project** (nom `revisions`, mot de passe de base **à noter**, région proche : Frankfurt).
2. Une fois créé : bouton **Connect** (en haut) → onglet **Session pooler** → copie l'URI (`postgresql://postgres.xxxx:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:5432/postgres`) et remplace `[YOUR-PASSWORD]` par ton mot de passe.
   ⚠️ Prends bien le *Session pooler* : la connexion « directe » ne marche pas depuis Render gratuit (IPv6). Si tu réutilises ta base « dépenses », c'est OK, les tables sont préfixées `rev_`.
3. Gratuit = projet mis en pause après 7 jours sans activité (tu le réveilles en 1 clic) : utilise-le au moins une fois par semaine.

## 3. Render (site web, gratuit)
1. render.com → connexion avec GitHub → **New + → Blueprint** → choisis le repo (il lit `render.yaml`) → Apply. (Ou **Web Service**, runtime Python, plan **Free**, build `pip install -r requirements.txt`, start `gunicorn app:app --workers 2 --timeout 90`.)
2. Onglet **Environment**, renseigne :
| Variable | Valeur |
|---|---|
| `DATABASE_URL` | l'URI Session pooler de Supabase |
| `SEED_USERS` | `Sixte:AlmaU123,Ulysse:AlmaU123,Alexandre:AlmaU123,Auguste:AlmaU123,Brune:AlmaU123,Victoria:AlmaU123,Jade:AlmaU123,Ginevra:AlmaU123,Capucine:AlmaU123` |
| `ADMIN_USERS` | `sixte` |
| `ANTHROPIC_API_KEY` | (optionnel) clé sur console.anthropic.com → active le coach |
| `COACH_MODEL` | `claude-haiku-4-5-20251001` (≈ 3× moins cher) |
| `COACH_DAILY_LIMIT` | `25` (messages/jour/personne) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REFRESH_TOKEN` | voir README, section « Brancher le Drive » (optionnel, à faire après) |
   `SECRET_KEY` est généré automatiquement.
3. **Manual Deploy → Deploy latest commit**. Au bout de ~3 min tu as une URL `https://revisions-almauteam.onrender.com`. Test : `/healthz` doit répondre `ok`.
4. Envoie l'URL au groupe. Identifiant = prénom, mot de passe = `AlmaU123`.

## À savoir
- Render gratuit **s'endort après 15 min** sans visite : le 1er chargement prend ~30 s. Astuce : un ping toutes les 10 min via uptimerobot.com (gratuit) sur `/healthz`.
- Les comptes sont créés au premier démarrage ; si tu changes `SEED_USERS` ensuite, seuls les prénoms *nouveaux* sont ajoutés (les mots de passe existants ne sont pas écrasés — utilise l'onglet Admin pour les réinitialiser).
- Coût réel : 0 € hors coach IA (quelques centimes par jour avec Haiku ; plafonné par `COACH_DAILY_LIMIT`). Sans clé API, tout marche sauf le coach.
- Mot de passe identique pour tous = pratique mais faible : demande à chacun de le changer dans son profil (surtout toi, admin).
