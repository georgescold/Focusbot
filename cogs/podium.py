import discord
from discord.ext import commands, tasks
import datetime
from typing import Dict, List, Optional, Tuple
import random
import logging
from database.supabase_client import supabase
from config import CLASSEMENT_LIVE_CHANNEL_ID, GUILD_ID

logger = logging.getLogger('Focusbot')

# Configuration des rôles et salons
ROLE_TOP_1_NAME = "🥇N°1 de la semaine"
ROLE_TOP_2_NAME = "🥈N°2 de la semaine"
ROLE_TOP_3_NAME = "🥉N°3 de la semaine"

# Messages pour les changements de position
PODIUM_MESSAGES = {
    "TOP_1": [
        "🥇 {user} prend la tête. Travail acharné, constance, maîtrise.",
        "⚔️ {user} dépasse {previous_user}. La première place se mérite.",
        "🏁 {user} s'installe en tête. L'effort finit toujours par payer.",
        "🔥 {user} devient numéro 1. Le travail silencieux parle fort.",
        "🧠 {user} s'impose. Qui viendra le défier ?"
    ],
    "TOP_2": [
        "🥈 {user} progresse vers le sommet. {previous_user}, tu es dans le viseur.",
        "💼 {user} atteint la 2ᵉ marche. La tension monte.",
        "⚙️ {user} maintient un rythme solide. Objectif : décrocher la première place.",
        "🔁 {user} passe devant {previous_user}. L'effort constant fait la différence.",
        "📈 {user} poursuit son ascension. Chaque heure compte."
    ],
    "TOP_3": [
        "🥉 {user} entre dans le top 3. Détermination visible.",
        "🧗 {user} grimpe les échelons. Rien n'arrête celui qui agit.",
        "🪜 {user} rejoint l'élite. À confirmer dans les prochains jours.",
        "📊 {user} passe devant {previous_user}. Le podium se resserre.",
        "🧱 {user} s'installe dans le classement. La rigueur porte ses fruits."
    ],
    "DROPPED": [
        "⚠️ {user} quitte le podium. Moins de régularité, moins de résultats.",
        "⌛ {user} est dépassé. La discipline quotidienne est la clé.",
        "🔄 {user} perd sa place. Le travail se mesure dans la durée.",
        "💭 {user} cède du terrain. Reste-t-il du temps pour revenir ?"
    ]
}

class Podium(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.current_top3: Dict[int, int] = {}  # {position: user_id}
        self.previous_top3: Dict[int, int] = {}  # {position: user_id}
        self.stable_since: Optional[datetime.datetime] = None
        self.last_message_time: Optional[datetime.datetime] = None
        self.check_podium.start()
        self.weekly_summary.start()

    def cog_unload(self):
        """Arrête les tâches périodiques lors du déchargement du cog"""
        self.check_podium.cancel()
        self.weekly_summary.cancel()

    async def get_weekly_ranking(self) -> List[Tuple[int, float]]:
        """Récupère le classement hebdomadaire des temps vocaux"""
        try:
            # Calculer la date de début (7 jours avant)
            start_date = datetime.datetime.now() - datetime.timedelta(days=7)
            
            # Récupérer les sessions des 7 derniers jours
            response = supabase.client.table('sessions')\
                .select('user_id, duration_seconds')\
                .gte('start_time', start_date.isoformat())\
                .execute()
            
            # Calculer le total par utilisateur
            user_totals = {}
            for session in response.data:
                user_id = session['user_id']
                if user_id not in user_totals:
                    user_totals[user_id] = 0
                user_totals[user_id] += session['duration_seconds']
            
            # Convertir en liste et trier
            ranking = [(user_id, total/3600) for user_id, total in user_totals.items()]
            ranking.sort(key=lambda x: x[1], reverse=True)
            
            return ranking
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du classement hebdomadaire: {e}")
            return []

    async def update_roles(self, guild: discord.Guild, new_top3: Dict[int, int]):
        """Met à jour les rôles du podium"""
        try:
            # Récupérer les rôles
            role_top1 = discord.utils.get(guild.roles, name=ROLE_TOP_1_NAME)
            role_top2 = discord.utils.get(guild.roles, name=ROLE_TOP_2_NAME)
            role_top3 = discord.utils.get(guild.roles, name=ROLE_TOP_3_NAME)
            
            if not all([role_top1, role_top2, role_top3]):
                logger.error("Un ou plusieurs rôles du podium sont manquants")
                return
            
            # Retirer les anciens rôles
            for position, user_id in self.current_top3.items():
                member = guild.get_member(user_id)
                if member:
                    if position == 1:
                        await member.remove_roles(role_top1)
                    elif position == 2:
                        await member.remove_roles(role_top2)
                    elif position == 3:
                        await member.remove_roles(role_top3)
            
            # Attribuer les nouveaux rôles
            for position, user_id in new_top3.items():
                member = guild.get_member(user_id)
                if member:
                    if position == 1:
                        await member.add_roles(role_top1)
                    elif position == 2:
                        await member.add_roles(role_top2)
                    elif position == 3:
                        await member.add_roles(role_top3)
            
            self.current_top3 = new_top3.copy()
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des rôles: {e}")

    async def send_podium_message(self, channel: discord.TextChannel, change_type: str, user: discord.Member, previous_user: Optional[discord.Member] = None):
        """Envoie un message de changement de position"""
        if self.last_message_time and (datetime.datetime.now() - self.last_message_time).total_seconds() < 1800:
            return  # Ne pas envoyer plus d'un message toutes les 30 minutes
        
        try:
            message = random.choice(PODIUM_MESSAGES[change_type])
            if previous_user:
                message = message.format(user=user.mention, previous_user=previous_user.mention)
            else:
                message = message.format(user=user.mention)
            
            await channel.send(message)
            self.last_message_time = datetime.datetime.now()
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du message de podium: {e}")

    @tasks.loop(minutes=5)
    async def check_podium(self):
        """Vérifie et met à jour le podium toutes les 5 minutes"""
        try:
            guild = self.bot.get_guild(GUILD_ID)
            if not guild:
                return
            
            channel = guild.get_channel(CLASSEMENT_LIVE_CHANNEL_ID)
            if not channel:
                logger.error(f"Canal de classement non trouvé (ID: {CLASSEMENT_LIVE_CHANNEL_ID})")
                return
            
            # Récupérer le classement actuel
            ranking = await self.get_weekly_ranking()
            if not ranking:
                return
            
            # Extraire le top 3
            new_top3 = {i+1: user_id for i, (user_id, _) in enumerate(ranking[:3])}
            
            # Vérifier les changements
            if new_top3 != self.current_top3:
                if not self.stable_since:
                    self.stable_since = datetime.datetime.now()
                elif (datetime.datetime.now() - self.stable_since).total_seconds() >= 900:  # 15 minutes
                    # Mettre à jour les rôles
                    await self.update_roles(guild, new_top3)
                    
                    # Envoyer les messages de changement
                    for position, user_id in new_top3.items():
                        if user_id not in self.current_top3.values():
                            member = guild.get_member(user_id)
                            if member:
                                if position == 1:
                                    await self.send_podium_message(channel, "TOP_1", member)
                                elif position == 2:
                                    await self.send_podium_message(channel, "TOP_2", member)
                                elif position == 3:
                                    await self.send_podium_message(channel, "TOP_3", member)
                    
                    # Vérifier les sorties du podium
                    for position, user_id in self.current_top3.items():
                        if user_id not in new_top3.values():
                            member = guild.get_member(user_id)
                            if member:
                                await self.send_podium_message(channel, "DROPPED", member)
                    
                    self.stable_since = None
            else:
                self.stable_since = None
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du podium: {e}")

    @tasks.loop(time=datetime.time(23, 59))
    async def weekly_summary(self):
        """Envoie le résumé hebdomadaire chaque dimanche à 23h59"""
        try:
            if datetime.datetime.now().weekday() != 6:  # 6 = dimanche
                return
            
            guild = self.bot.get_guild(GUILD_ID)
            if not guild:
                return
            
            channel = guild.get_channel(CLASSEMENT_LIVE_CHANNEL_ID)
            if not channel:
                logger.error(f"Canal de classement non trouvé (ID: {CLASSEMENT_LIVE_CHANNEL_ID})")
                return
            
            # Récupérer le classement final
            ranking = await self.get_weekly_ranking()
            if not ranking:
                return
            
            # Construire le message
            message = "📆 **Classement de la semaine – Temps passé en vocal**\n"
            
            for i, (user_id, hours) in enumerate(ranking[:10], 1):
                member = guild.get_member(user_id)
                if member:
                    if i <= 3:
                        medals = ["🥇", "🥈", "🥉"]
                        message += f"{medals[i-1]} {member.mention} — {hours:.1f}h\n"
                    else:
                        message += f"{i}. {member.mention} — {hours:.1f}h\n"
            
            message += "\nFélicitations aux plus disciplinés. Nouvelle semaine, nouveau départ.\n"
            message += "Chacun repart de zéro. À qui l'effort donnera-t-il raison cette fois ?"
            
            await channel.send(message)
            
            # Réinitialiser le podium
            self.current_top3 = {}
            self.previous_top3 = {}
            self.stable_since = None
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du résumé hebdomadaire: {e}")

    @check_podium.before_loop
    async def before_check_podium(self):
        """Attend que le bot soit prêt avant de démarrer la vérification"""
        await self.bot.wait_until_ready()

    @weekly_summary.before_loop
    async def before_weekly_summary(self):
        """Attend que le bot soit prêt avant de démarrer le résumé hebdomadaire"""
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(Podium(bot)) 