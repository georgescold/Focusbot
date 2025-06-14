# Focusbot

Un bot Discord pour suivre et encourager le temps passé en vocal, avec des statistiques et des classements.

## Fonctionnalités

- Suivi du temps passé en vocal
- Statistiques détaillées (quotidiennes, hebdomadaires, mensuelles)
- Système de rôles basé sur le temps passé
- Classement en direct
- Système de pause

## Installation

1. Clonez le repository :
```bash
git clone https://github.com/georgescold/Focusbot.git
cd Focusbot
```

2. Installez les dépendances :
```bash
pip install -r requirements.txt
```

3. Créez un fichier `.env` avec les variables suivantes :
```env
DISCORD_TOKEN=votre_token_discord
GUILD_ID=votre_id_serveur
SUPABASE_URL=votre_url_supabase
SUPABASE_KEY=votre_clé_supabase
SUPABASE_SECRET=votre_secret_supabase
VOICE_CHANNEL_PAUSE_ID=id_du_canal_vocal_pause
STATISTIQUES_CHANNEL_ID=id_du_canal_statistiques
GENERAL_CHANNEL_ID=id_du_canal_general
CLASSEMENT_LIVE_CHANNEL_ID=id_du_canal_classement
MINIMUM_DAILY_MINUTES=30
```

4. Lancez le bot :
```bash
python main.py
```

## Commandes

- `/stats` - Affiche vos statistiques de temps en vocal
- `/next-rank` - Affiche le prochain rôle à atteindre

## Contribution

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request.

## Licence

Ce projet est sous licence MIT. 