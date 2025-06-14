import discord
from discord.ext import commands
import asyncio
from config import DISCORD_TOKEN, GUILD_ID
import logging
from cogs.voice_tracking import VoiceTracking
import sys
import traceback
import signal
from typing import Optional
import platform

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('Focusbot')

# Configuration des intents
intents = discord.Intents.default()
intents.members = True  # Nécessaire pour le tracking des membres
intents.message_content = True  # Nécessaire pour les commandes

# Création du bot
bot = commands.Bot(command_prefix='/', intents=intents)

# Variables globales pour la gestion des reconnexions
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5  # secondes
INITIAL_RECONNECT_DELAY = 1  # seconde

async def load_extensions():
    """Charge les extensions du bot"""
    try:
        await bot.load_extension('cogs.voice_tracking')
        await bot.load_extension('cogs.stats')
        await bot.load_extension('cogs.leaderboard')
        await bot.load_extension('cogs.discipline')
        await bot.load_extension('cogs.podium')
    except Exception as e:
        logger.error(f"Erreur lors du chargement des extensions: {e}")
        raise

@bot.event
async def on_ready():
    """Événement déclenché quand le bot est prêt"""
    logger.info(f'Bot connecté en tant que {bot.user.name}')
    logger.info(f'ID du bot: {bot.user.id}')

    # Attribuer GUILD_ID à l'objet bot pour une accessibilité globale
    bot.guild_id = GUILD_ID
    
    # Synchronisation des commandes slash
    try:
        synced = await bot.tree.sync()
        logger.info(f'Synchronisé {len(synced)} commande(s)')
    except Exception as e:
        logger.error(f'Erreur lors de la synchronisation des commandes: {e}')

    # Vérification du serveur
    guild = bot.get_guild(GUILD_ID)
    if guild:
        logger.info(f'Serveur Discord trouvé: {guild.name} ({guild.id})')
        logger.info('Démarrage de la vérification des rôles pour tous les membres')
        voice_tracking_cog = bot.get_cog('VoiceTracking')
        if voice_tracking_cog:
            await voice_tracking_cog.check_all_roles()
        else:
            logger.error("Le cog VoiceTracking n'a pas été trouvé.")
    else:
        logger.error(f"Le serveur avec l'ID {GUILD_ID} n'a pas été trouvé.")

@bot.event
async def on_error(event, *args, **kwargs):
    """Gestionnaire d'erreurs global"""
    logger.error(f'Erreur dans {event}:', exc_info=True)

async def handle_shutdown(signal_name: Optional[str] = None):
    """Gère l'arrêt propre du bot"""
    if signal_name:
        logger.info(f"Signal {signal_name} reçu, arrêt du bot...")
    else:
        logger.info("Arrêt du bot...")
    
    try:
        # Nettoyer les ressources
        for cog in bot.cogs.values():
            if hasattr(cog, 'cog_unload'):
                await cog.cog_unload()
        
        # Fermer la connexion Discord
        await bot.close()
    except Exception as e:
        logger.error(f"Erreur lors de l'arrêt du bot: {e}")
    finally:
        logger.info("Bot arrêté")
        sys.exit(0)

def setup_signal_handlers():
    """Configure les gestionnaires de signaux"""
    if platform.system() == 'Windows':
        # Sous Windows, on utilise les gestionnaires de signaux standards
        signal.signal(signal.SIGINT, lambda s, f: asyncio.create_task(handle_shutdown('SIGINT')))
        signal.signal(signal.SIGTERM, lambda s, f: asyncio.create_task(handle_shutdown('SIGTERM')))
    else:
        # Sous Unix, on utilise add_signal_handler
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda s=sig: asyncio.create_task(handle_shutdown(s.name))
            )

async def start_bot():
    """Démarre le bot avec gestion des reconnexions"""
    attempt = 0
    delay = INITIAL_RECONNECT_DELAY
    
    while attempt < MAX_RECONNECT_ATTEMPTS:
        try:
            async with bot:
                await load_extensions()
                await bot.start(DISCORD_TOKEN)
        except discord.LoginFailure:
            logger.error("Échec de la connexion : Token invalide")
            sys.exit(1)
        except KeyboardInterrupt:
            await handle_shutdown()
        except Exception as e:
            attempt += 1
            logger.error(f"Erreur de connexion (tentative {attempt}/{MAX_RECONNECT_ATTEMPTS}): {e}")
            if attempt < MAX_RECONNECT_ATTEMPTS:
                logger.info(f"Tentative de reconnexion dans {delay} secondes...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, RECONNECT_DELAY)  # Exponential backoff avec limite
            else:
                logger.error("Nombre maximum de tentatives de reconnexion atteint")
                sys.exit(1)

async def main():
    """Fonction principale"""
    setup_signal_handlers()
    await start_bot()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        asyncio.run(handle_shutdown())
    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        logger.error("Traceback complet:", exc_info=True)
        sys.exit(1) 