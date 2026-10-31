# Mairy Project — Commune Urbaine de Mahajanga

Plateforme de délivrance et de vérification de documents administratifs (QR code, empreinte SHA-256, signature numérique) avec un espace personnel pour déposer des demandes de dossiers et recevoir les réponses de la Commune.

- `frontend/` : React 19 + TypeScript + Vite + Tailwind CSS v4 + Clerk (authentification), interface en français / anglais / malagasy.
- `backend/` : Python + Django (API JSON, administration, vérification des documents, demandes de dossiers, contact).

Frontend et backend sont reliés : le frontend envoie le jeton de session Clerk au backend, qui le vérifie avec les clés publiques de Clerk avant d'accepter ou de lister les demandes d'un usager.

## Lancement rapide (après la première installation)

```bash
cd frontend
npm run dev                      # frontend http://localhost:5173 + backend Django http://localhost:8000
```

`npm run dev` démarre aussi le backend avec le Python de `backend/.venv` (pas besoin de `source .venv/bin/activate`) ; `Ctrl+C` arrête les deux. Si Django tourne déjà, il n'est pas relancé ; `MAIRY_NO_BACKEND=1 npm run dev` lance le frontend seul. Depuis la racine du projet, `./start.sh` fait la même chose.

Raccourci vers l'administration : sur le site, appuyez **20 fois de suite** (moins de 1,5 s entre deux appuis) sur l'icône de profil à côté de « Se connecter » : la page d'accueil du backend s'ouvre (la connexion à l'admin reste exigée).

## Lancer le backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # puis adapter les valeurs (voir ci-dessous)
python manage.py makemigrations  # première fois uniquement (aucune migration n'est livrée)
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo       # (optionnel) documents de démonstration
python3 manage.py runserver       # http://localhost:8000 : page d'accueil, puis « Se connecter » vers /admin/
```

Dans `backend/.env`, ajoutez la **même clé publique Clerk** que celle du frontend, sinon l'espace personnel répondra « 503 auth_not_configured » :

```
CLERK_PUBLISHABLE_KEY=pk_test_...
```

Tests : `python manage.py test`

## Lancer le frontend

```bash
cd frontend
npm install
cp .env.example .env.local       # renseigner VITE_CLERK_PUBLISHABLE_KEY (et VITE_API_URL si besoin)
npm run dev                      # http://localhost:5173
```

Vérification des types / build de production : `npm run build`

## Répondre aux demandes des usagers

Dans l'administration Django (`http://localhost:8000/admin/`), ouvrez **Demandes de dossiers** : changez le statut et écrivez la « réponse de la mairie ». La réponse apparaît aussitôt dans la page **Notifications** de l'usager (cloche de son espace) ; le compteur de la cloche passe à « non lu ».

Les messages du formulaire de la page Contact arrivent dans **Messages de contact**.

## Agents municipaux (guichets)

Chaque agent est rattaché à **un seul guichet** et ne traite que les demandes de ce guichet :

| Guichet | Demandes traitées |
|---|---|
| 1 | Actes de naissance |
| 2 | Actes de mariage |
| 3 | Actes de décès |
| 4 | Législation |
| 5 | Recette, transport, marché, urbanisme, cadastre, impôt foncier, actes divers |

1. Sur la page de connexion (`http://localhost:8000/connexion/`), le bouton **« Demander un accès »** ouvre `/agent/inscription/` : nom, prénom, e-mail et mot de passe (choisi par l'agent, enregistré haché). L'agent ne choisit pas son guichet.
2. Dans l'administration, **Demandes d'accès agent** : attribuez le guichet (colonne « Guichet », puis « Enregistrer »), puis action **« Approuver et créer les comptes agents »**. Le compte est créé avec l'e-mail comme identifiant et le mot de passe choisi par l'agent.
3. L'agent se connecte sur `/connexion/` avec son e-mail et son mot de passe : il arrive directement sur **son** guichet (`/agent/guichet-N/`), traite les demandes (statut + réponse à l'usager) et peut changer son mot de passe. Un autre guichet lui est refusé. Tant que sa demande n'est pas validée, la connexion lui indique qu'elle est en attente.

Les demandes envoyées depuis le site public (`/demande-agent`, sans mot de passe) restent possibles : à l'approbation, un mot de passe provisoire est affiché une seule fois à l'administrateur.

Chaque demande d'usager est **aiguillée automatiquement** vers le guichet de son type (champ `guichet` de la demande) ; l'agent concerné est averti (cloche, page **Notifications**, alerte qui apparaît sans recharger la page).

Dans le menu de l'agent, **Documents officiels** : chaque guichet établit son propre document, scellé par une empreinte SHA-256 + signature, avec un QR code unique vérifiable sur `/verifier/<id>` du site, téléchargeable en PDF et envoyable à l'usager (bouton « Télécharger » dans ses notifications) :

| Guichet | Document | Numéro |
|---|---|---|
| 1 | Extrait d'acte de naissance | `2026-NAI-00001` |
| 2 | Extrait d'acte de mariage | `2026-MAR-00001` |
| 3 | Extrait d'acte de décès | `2026-DEC-00001` |
| 4 | Extrait certifié conforme d'un texte (arrêté, délibération…) | `2026-LEG-00001` |
| 5 | Attestation de service (recette, transport, marché, urbanisme, cadastre, impôt foncier, actes divers) | `2026-ATT-00001` |

Établi depuis la demande d'un usager, le document est pré-rempli avec les informations de cette demande. Le menu contient aussi **Mail** (e-mails des usagers du guichet) et **Messages** (réponses envoyées et leur lecture). Un agent ne supprime pas un document lui-même : il **demande** la suppression avec un motif, et l'administrateur l'accepte ou la refuse (rubrique **Documents officiels** de l'administration ; un document n'y est jamais effacé définitivement). Le PDF utilise ReportLab (`pip install -r requirements.txt`).

Les rôles se modifient dans **Agents municipaux** (administration). Les administrateurs utilisent la même page de connexion et arrivent dans l'administration.

## Routes du frontend

| URL | Page |
|---|---|
| `/` | Accueil (recherche dans la plateforme, icône de scan) |
| `/services` | Liste des services (menu « Services » de l'en-tête) |
| `/services/<service>` | Recette, transport, urbanisme, marché, cadastre, impôt foncier |
| `/services/etat-civil` et `/services/etat-civil/<acte>` | Naissance, mariage, décès, législation, actes divers |
| `/contact` | Page Contact (formulaire relié au backend) |
| `/scanner` | Scanner un QR code (caméra ou saisie manuelle) |
| `/verifier/:uuid` | Résultat de la vérification d'un document |
| `/demande-agent` | Demande d'accès agent municipal |
| `/espace` | Espace personnel (connexion requise) : demandes et état civil en rangées défilantes |
| `/espace/demande/<type>` | Page dédiée d'une demande (formulaire, envoi seulement si tous les champs sont remplis) |
| `/espace/notifications` | Réponses de la Commune aux demandes |

## Routes de l'API (backend)

- Public : `GET /api/health/` · `GET /api/verify/<uuid>/` · `POST /api/agent-requests/` · `POST /api/contact/` · `GET /api/documents/<uuid>/qr.png`
- Connecté (jeton Clerk) : `GET` et `POST /api/dossiers/` · `POST /api/dossiers/<id>/read/` · `POST /api/dossiers/read-all/`
- Personnel Django : `GET /api/admin/stats/` · `POST /api/admin/fraud-scan/`

Ne commitez jamais `.env` ni `.env.local`.
