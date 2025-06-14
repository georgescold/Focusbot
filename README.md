# Focusbot - Bot Discord Deep Work Tracker

Bot Discord pour suivre et encourager le Deep Work dans votre communauté.

## Prérequis

- Python 3.8 ou supérieur
- Compte Discord Developer
- Compte Supabase
- Serveur Discord

## Installation

1. Clonez ce dépôt :
```bash
git clone [URL_DU_REPO]
cd Focusbot
```

2. Installez les dépendances :
```bash
pip install -r requirements.txt
```

3. Configurez les variables d'environnement :
   - Copiez le fichier `.env.example` en `.env`
   - Remplissez les variables avec vos informations :
     - `DISCORD_TOKEN` : Token de votre bot Discord
     - `GUILD_ID` : ID de votre serveur Discord
     - `SUPABASE_URL` : URL de votre projet Supabase
     - `SUPABASE_KEY` : Clé API anonyme Supabase
     - `SUPABASE_SECRET` : Clé secrète Supabase
     - `VOICE_CHANNEL_CATEGORY_ID` : ID de la catégorie des salons vocaux
     - `LEADERBOARD_CHANNEL_ID` : ID du canal pour les classements

4. Configurez la base de données Supabase :
   - Créez les tables nécessaires via l'interface Supabase
   - Les schémas SQL seront fournis dans le dossier `database/`

5. Lancez le bot :
```bash
python main.py
```

## Commandes disponibles

- `/stats` : Affiche vos statistiques personnelles
- `/classement` : Affiche les classements (jour/semaine/mois)
- `/streak` : Affiche votre streak actuel
- `/next-rank` : Indique le prochain rôle à atteindre

## Structure du projet

```
Focusbot/
├── main.py              # Point d'entrée du bot
├── cogs/               # Modules de commandes Discord
├── database/           # Scripts et schémas de base de données
├── utils/             # Fonctions utilitaires
├── config.py          # Configuration du bot
├── requirements.txt   # Dépendances Python
└── .env              # Variables d'environnement (à créer)
```

## Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request.

## Licence

MIT 