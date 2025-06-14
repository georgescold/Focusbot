import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
from config import ROLES
from database.supabase_client import supabase
import logging
from discord.ext import tasks

logger = logging.getLogger('Focusbot')

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.aggregate_stats.start()

    def cog_unload(self):
        """Arrête les tâches planifiées lors du déchargement du cog"""
        self.aggregate_stats.cancel()

    @tasks.loop(hours=24)
    async def aggregate_stats(self):
        """Agrège les anciennes sessions une fois par mois"""
        try:
            # Vérifier si c'est le premier jour du mois
            now = datetime.now()
            if now.day == 1 and now.hour == 0:
                await supabase.aggregate_old_sessions()
                logger.info("Agrégation mensuelle des statistiques effectuée")
        except Exception as e:
            logger.error(f"Erreur lors de l'agrégation mensuelle: {e}")

    @aggregate_stats.before_loop
    async def before_aggregate_stats(self):
        """Attend que le bot soit prêt avant de démarrer la tâche"""
        await self.bot.wait_until_ready()

    def format_duration(self, seconds: int) -> str:
        """Formate une durée en secondes en heures, minutes et secondes"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    async def get_period_stats(self, user_id: int, period: str) -> dict:
        """Récupère les statistiques pour une période donnée"""
        try:
            now = datetime.now()
            if period == 'day':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == 'week':
                start_date = now - timedelta(days=now.weekday())
                start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == 'month':
                start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            else:  # all
                start_date = datetime.min

            response = supabase.client.table('sessions').select('duration_seconds').eq('user_id', user_id).gte('start_time', start_date.isoformat()).execute()
            
            total_seconds = sum(session['duration_seconds'] for session in response.data)
            return {'total_seconds': total_seconds}
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des stats: {e}")
            return {'total_seconds': 0}

    @commands.hybrid_command(name="stats", description="Affiche vos statistiques de temps en vocal")
    async def stats(self, ctx):
        """Affiche les statistiques de temps en vocal de l'utilisateur"""
        try:
            # Récupérer les statistiques pour différentes périodes
            today_stats = await self.get_period_stats(ctx.author.id, 'day')
            week_stats = await self.get_period_stats(ctx.author.id, 'week')
            month_stats = await self.get_period_stats(ctx.author.id, 'month')
            total_stats = await self.get_period_stats(ctx.author.id, 'all')

            embed = discord.Embed(
                title=f"📊 Statistiques de {ctx.author.display_name}",
                color=discord.Color.blue()
            )

            # Ajouter les statistiques pour chaque période
            embed.add_field(
                name="Aujourd'hui",
                value=f"⏱️ {self.format_duration(today_stats['total_seconds'])}",
                inline=True
            )
            embed.add_field(
                name="Cette semaine",
                value=f"📅 {self.format_duration(week_stats['total_seconds'])}",
                inline=True
            )
            embed.add_field(
                name="Ce mois",
                value=f"📆 {self.format_duration(month_stats['total_seconds'])}",
                inline=True
            )
            embed.add_field(
                name="Total",
                value=f"🎯 {self.format_duration(total_stats['total_seconds'])}",
                inline=False
            )

            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Erreur lors de l'affichage des statistiques: {e}")
            await ctx.send("Une erreur est survenue lors de la récupération de vos statistiques.")

    @app_commands.command(name="next-rank", description="Affiche le prochain rôle à atteindre")
    async def next_rank(self, interaction: discord.Interaction):
        """Commande /next-rank pour afficher le prochain rôle à atteindre"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            stats = await supabase.get_user_stats(interaction.user.id)
            if not stats:
                await interaction.followup.send("Aucune statistique trouvée.", ephemeral=True)
                return

            current_hours = stats['total_hours']
            next_role, hours_needed = self.get_next_role(current_hours)
            
            if next_role:
                embed = discord.Embed(
                    title="🎯 Prochain Rôle",
                    description=f"Vous êtes à {self.format_duration(int(hours_needed * 3600))} du rôle **{next_role}**",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="⏱️ Temps Actuel",
                    value=self.format_duration(stats['total_seconds']),
                    inline=True
                )
                embed.add_field(
                    name="🎯 Temps Requis",
                    value=self.format_duration(ROLES[next_role] * 3600),
                    inline=True
                )
            else:
                embed = discord.Embed(
                    title="🏆 Rôle Maximum",
                    description="Vous avez atteint le niveau maximum !",
                    color=discord.Color.gold()
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du prochain rôle: {e}")
            await interaction.followup.send("Une erreur est survenue lors de la récupération de vos informations.", ephemeral=True)

    def get_next_role(self, current_hours):
        """Détermine le prochain rôle à atteindre"""
        for role, hours in sorted(ROLES.items(), key=lambda x: x[1]):
            if hours > current_hours:
                return role, hours - current_hours
        return None, 0

async def setup(bot):
    await bot.add_cog(Stats(bot)) 