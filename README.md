# 📚 Révisions #AlmaUteam4ever

Plateforme de révision pour le midterm : 4 matières (Global Marketing, Marketing with AI, Customer Development, Lodging & Accommodation), fiches FR/EN, QCM adaptatifs avec explications, coach IA, connexion par prénom, scores et niveaux, classement.

## Déployer (≈ 10 min, gratuit)
1. **GitHub** : pousse ce dossier dans un nouveau repo (le fichier `accounts_PRIVE.txt` n'est pas dans le zip, ne le commit jamais).
2. **Supabase** (base persistante, Render gratuit efface le disque) : Project Settings → Database → *Connection string* (URI). Les tables sont préfixées `rev_` : tu peux réutiliser le projet de ton app de dépenses.
3. **Render** : New → Web Service → ton repo (le `render.yaml` est détecté). Variables d'environnement :
   - `DATABASE_URL` = l'URI Supabase
   - `SEED_USERS` = la dernière ligne de `accounts_PRIVE.txt` (crée les 9 comptes au 1er démarrage)
   - `ANTHROPIC_API_KEY` = ta clé (console.anthropic.com) → active le coach IA
   - optionnels : `COACH_MODEL` (défaut `claude-sonnet-5-5`, `claude-haiku-4-5-20251001` = moins cher), `COACH_DAILY_LIMIT` (40 msg/jour/personne)
4. Ouvre l'URL Render, connecte-toi avec `sixte` : le menu **Admin** permet d'ajouter un ami ou de changer un mot de passe.

> Render gratuit s'endort après 15 min d'inactivité : le 1er chargement prend ~30 s. Ouvre le site quelques minutes avant de réviser.

## Tester en local
```bash
pip install -r requirements.txt
SEED_USERS="Sixte:test123" python app.py     # http://localhost:5000  (SQLite local)
python scripts/check_content.py              # valide les fiches/QCM
```

## Ajouter / corriger du contenu
Un fichier JSON par matière dans `content/` (fiches bilingues + QCM `correct` / `wrong` ×3 / `why`). Les réponses sont mélangées à chaque quiz. Pour une nouvelle matière : copie un fichier, ajoute son id dans `SUBJECT_ORDER` (`app.py`) et une couleur dans `static/app.js`. Lance `check_content.py` avant de déployer.

## Comment ça marche
- **Maîtrise** d'une matière = % de questions dont la *dernière* réponse était juste. Niveaux : Débutant < 20 % < Apprenti < 40 % < Avancé < 60 % < Confirmé < 80 % < Expert < 95 % ≤ Maître.
- **Quiz** : tirage pondéré (questions ratées > jamais vues > déjà réussies). Mode « points faibles » = uniquement les ratées.
- **Coach** : Claude reçoit les fiches de la matière + tes points faibles ; il répond en français (termes en anglais), donne des exemples, t'interroge.


## 📂 Brancher le Drive (cours) — v2

L'onglet **Cours (Drive)** de chaque matière affiche les fichiers du dossier Drive correspondant, permet de les ouvrir/télécharger
(sans que les amis aient besoin d'accès au Drive) et d'**ajouter** un fichier directement depuis la plateforme (il est envoyé dans le bon dossier).
Correspondance par défaut : *Globa Marketing* → Global Marketing, *AI in marketing* → Marketing with AI, *Customer development* → Customer Development,
*Lodging and acommodation management* → Lodging (surchargeable via `DRIVE_FOLDER_MAP`).

À faire **une seule fois**, avec le compte propriétaire du Drive (sixte.fabry@gmail.com) :
1. https://console.cloud.google.com → nouveau projet → **APIs & Services → Library → Google Drive API → Enable**.
2. **OAuth consent screen** : type *External*, ajoute ton mail en utilisateur test, puis clique **Publish app** (sinon le jeton expire au bout de 7 jours).
3. **Credentials → Create credentials → OAuth client ID → Desktop app** → télécharge le JSON (`client_secret.json`).
4. Sur ton ordinateur : `pip install google-auth-oauthlib` puis `python scripts/drive_auth.py client_secret.json` → connecte-toi, accepte
   (écran « application non vérifiée » : *Avancé → Continuer*). Le script affiche les 3 valeurs à copier.
5. Dans Render → Environment : `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REFRESH_TOKEN` → redéploie.

Alternative lecture seule : un *compte de service* (`GOOGLE_SERVICE_ACCOUNT_JSON`) avec le dossier « ALMA U » partagé à son adresse ; Google refuse souvent
l'ajout de fichiers dans ce mode (pas de quota), donc préfère le mode OAuth ci-dessus.

Sécurité : seuls les fichiers situés dans les 4 dossiers de matières sont accessibles ; il faut être connecté ; formats limités (PDF, PPTX, DOCX, images…), 25 Mo max.

## 📅 Agenda partagé — v2
Menu **Agenda** : calendrier mensuel + liste « à venir ». « Ajouter un événement » : titre, date/heure, **matière(s)** cochées, **personnes concernées**
(ou « tout le groupe »), détails. Filtre « ce qui me concerne » ; les prochains événements qui te concernent apparaissent sur l'accueil.
Seul l'auteur (ou l'admin) peut modifier/supprimer un événement. Heures affichées telles que saisies (pas de conversion de fuseau).
