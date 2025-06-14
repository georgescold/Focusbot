import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
from config import REPORT_CONFIG, STATISTIQUES_CHANNEL_ID, GENERAL_CHANNEL_ID
from database.supabase_client import supabase
import logging
from typing import List, Tuple
from datetime import timedelta

logger = logging.getLogger('Focusbot')

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_report.start()
        self.weekly_report.start()
        self.monthly_report.start()
        self.yearly_report.start()

    def format_duration(self, total_seconds: int) -> str:
        """Formate une durée en secondes en format h/min/s"""
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    def cog_unload(self):
        """Arrête les tâches planifiées lors du déchargement du cog"""
        self.daily_report.cancel()
        self.weekly_report.cancel()
        self.monthly_report.cancel()
        self.yearly_report.cancel()

    @tasks.loop(time=datetime.time(23, 59))
    async def daily_report(self):
        """Rapport journalier"""
        await self.send_report('daily')

    @tasks.loop(time=datetime.time(23, 59))
    async def weekly_report(self):
        """Rapport hebdomadaire"""
        if datetime.datetime.now().strftime('%A').lower() == 'sunday':
            await self.send_report('weekly')

    @tasks.loop(time=datetime.time(0, 0))
    async def monthly_report(self):
        """Rapport mensuel"""
        if datetime.datetime.now().day == 1:
            await self.send_report('monthly')

    @tasks.loop(time=datetime.time(0, 0))
    async def yearly_report(self):
        """Rapport annuel"""
        now = datetime.datetime.now()
        if now.month == 1 and now.day == 1:
            await self.send_report('yearly')

    async def send_report(self, report_type: str):
        """Envoie un rapport de classement dans les canaux configurés"""
        try:
            # Récupérer la configuration du rapport
            config = REPORT_CONFIG[report_type]
            
            # Récupérer les données du classement
            leaderboard_data = await self.get_leaderboard_data(report_type)
            
            if not leaderboard_data:
                return
            
            # Créer l'embed du classement
            embed = discord.Embed(
                title=f"🏆 Classement {report_type.capitalize()}",
                color=discord.Color.gold()
            )
            
            # Ajouter les utilisateurs au classement
            for i, (user_id, total_seconds) in enumerate(leaderboard_data[:10], 1):
                user = self.bot.get_user(user_id)
                if user:
                    hours, minutes, seconds = self.format_duration(total_seconds)
                    embed.add_field(
                        name=f"{i}. {user.name}",
                        value=f"`{hours}h {minutes}m {seconds}s`",
                        inline=False
                    )
            
            # Envoyer le rapport dans chaque canal configuré
            for channel_id in config['channels']:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    content = "@everyone" if config.get('mention_everyone', False) else None
                    await channel.send(content=content, embed=embed)
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du rapport {report_type}: {e}")

    async def send_leaderboard(self, interaction: discord.Interaction, period: str, title: str):
        """Envoie un classement pour une période donnée"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Récupérer les statistiques de tous les utilisateurs
            response = await supabase.get_leaderboard(period)
            if not response:
                await interaction.followup.send("Aucune donnée disponible pour le classement.", ephemeral=True)
                return

            # Créer l'embed pour le classement
            embed = discord.Embed(
                title=f"🏆 {title}",
                description="Voici le classement des membres les plus actifs :",
                color=discord.Color.gold()
            )

            # Ajouter les 10 premiers au classement
            for i, user in enumerate(response[:10], 1):
                member = interaction.guild.get_member(user['user_id'])
                if member:
                    username = member.display_name
                    duration = self.format_duration(user['total_seconds'])
                    embed.add_field(
                        name=f"{i}. {username}",
                        value=f"⏱️ {duration}",
                        inline=False
                    )

            # Ajouter le footer
            embed.set_footer(text="Le classement est mis à jour en temps réel")

            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du classement: {e}")
            await interaction.followup.send("Une erreur est survenue lors de la récupération du classement.", ephemeral=True)

    @app_commands.command(name="classement", description="Affiche le classement journalier")
    async def daily_leaderboard(self, interaction: discord.Interaction):
        """Commande /classement pour afficher le classement journalier"""
        await self.send_leaderboard(interaction, 'daily', "Classement Journalier")

    @app_commands.command(name="classement-semaine", description="Affiche le classement hebdomadaire")
    async def weekly_leaderboard(self, interaction: discord.Interaction):
        """Commande /classement-semaine pour afficher le classement hebdomadaire"""
        await self.send_leaderboard(interaction, 'weekly', "Classement Hebdomadaire")

    @app_commands.command(name="classement-mois", description="Affiche le classement mensuel")
    async def monthly_leaderboard(self, interaction: discord.Interaction):
        """Commande /classement-mois pour afficher le classement mensuel"""
        await self.send_leaderboard(interaction, 'monthly', "Classement Mensuel")

    @app_commands.command(name="classement-annee", description="Affiche le classement annuel")
    async def yearly_leaderboard(self, interaction: discord.Interaction):
        """Commande /classement-annee pour afficher le classement annuel"""
        await self.send_leaderboard(interaction, 'yearly', "Classement Annuel")

    async def get_leaderboard_data(self, period: str) -> List[Tuple[int, int]]:
        """Récupère les données du classement pour une période donnée"""
        try:
            # Définir la date de début en fonction de la période
            now = datetime.now()
            if period == 'daily':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == 'weekly':
                start_date = now - timedelta(days=now.weekday())
                start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == 'monthly':
                start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            elif period == 'yearly':
                start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                return []

            # Récupérer les données depuis la base de données
            response = supabase.client.table('sessions').select('user_id, duration_seconds').gte('start_time', start_date.isoformat()).execute()
            
            if not response.data:
                return []

            # Calculer le temps total par utilisateur
            user_times = {}
            for session in response.data:
                user_id = session['user_id']
                duration = session['duration_seconds']
                user_times[user_id] = user_times.get(user_id, 0) + duration

            # Trier les utilisateurs par temps total
            sorted_users = sorted(user_times.items(), key=lambda x: x[1], reverse=True)
            return sorted_users

        except Exception as e:
            logger.error(f"Erreur lors de la récupération des données du classement: {e}")
            return []

async def setup(bot):
    await bot.add_cog(Leaderboard(bot)) 