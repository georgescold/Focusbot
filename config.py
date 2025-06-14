import os
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()

# Configuration Discord
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))

# Configuration Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
SUPABASE_SECRET = os.getenv('SUPABASE_SECRET')

# Configuration des canaux
VOICE_CHANNEL_PAUSE_ID = int(os.getenv('VOICE_CHANNEL_PAUSE_ID'))
STATISTIQUES_CHANNEL_ID = int(os.getenv('STATISTIQUES_CHANNEL_ID'))
GENERAL_CHANNEL_ID = int(os.getenv('GENERAL_CHANNEL_ID'))
CLASSEMENT_LIVE_CHANNEL_ID = int(os.getenv('CLASSEMENT_LIVE_CHANNEL_ID'))

# Configuration des rôles
ROLES = {
    'Starter': 5,  # 5 heures
    'Ambitieux': 10,
    'Prometteur': 50,
    'Emergent': 100,
    'Ascendant': 500,
    'Visionnaire': 1000,
    'Potentiel infini': 5000,
    'Divin': 10000
}

# Configuration des streaks
MINIMUM_DAILY_MINUTES = int(os.getenv('MINIMUM_DAILY_MINUTES', 30))  # Minutes minimum par jour pour valider le streak, par défaut 30 minutes

# Configuration des rapports
REPORT_CONFIG = {
    'daily': {
        'channels': [CLASSEMENT_LIVE_CHANNEL_ID],
        'time': '23:59',
        'mention_everyone': False
    },
    'weekly': {
        'channels': [CLASSEMENT_LIVE_CHANNEL_ID, GENERAL_CHANNEL_ID],
        'day': 'sunday',
        'time': '23:59',
        'mention_everyone': True
    },
    'monthly': {
        'channels': [CLASSEMENT_LIVE_CHANNEL_ID, GENERAL_CHANNEL_ID],
        'day': 1,
        'time': '00:00',
        'mention_everyone': True
    },
    'yearly': {
        'channels': [CLASSEMENT_LIVE_CHANNEL_ID, GENERAL_CHANNEL_ID],
        'month': 1,
        'day': 1,
        'time': '00:00',
        'mention_everyone': True
    }
} 