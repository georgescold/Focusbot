import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
from config import MINIMUM_DAILY_MINUTES
from database.supabase_client import supabase
import logging
import os

logger = logging.getLogger('Focusbot')

class Discipline(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_discipline.start()

    async def cog_load(self):
        """Vérifie les mises à jour manquées lors du chargement du cog"""
        await self.check_missed_updates()

    async def check_missed_updates(self):
        """Vérifie et effectue les mises à jour manquées depuis la dernière exécution"""
        try:
            # Récupérer tous les utilisateurs
            response = supabase.client.table('user_discipline').select('*').execute()
            users = response.data

            for user in users:
                user_id = user['user_id']
                last_check = datetime.fromisoformat(user['last_check'])
                now = datetime.now()

                # Si la dernière vérification date de plus d'un jour
                if (now - last_check).days >= 1:
                    # Calculer le nombre de jours à vérifier
                    days_to_check = min((now - last_check).days, 7)  # Maximum 7 jours
                    
                    # Vérifier les jours manqués
                    for day in range(days_to_check):
                        check_date = last_check + timedelta(days=day+1)
                        # Vérifier le temps passé en vocal pour ce jour
                        day_stats = await supabase.get_day_stats(user_id, check_date)
                        if day_stats and day_stats['total_seconds'] >= MINIMUM_DAILY_MINUTES * 60:  # MINIMUM_DAILY_MINUTES en secondes
                            await self.update_discipline(user_id, user['discipline_level'] + 1)
                        else:
                            await self.update_discipline(user_id, 0)
                            break  # Arrêter si un jour n'est pas validé

            logger.info("Vérification des mises à jour manquées terminée")
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des mises à jour manquées: {e}")

    def cog_unload(self):
        """Arrête les tâches planifiées lors du déchargement du cog"""
        self.check_discipline.cancel()

    @tasks.loop(hours=24)
    async def check_discipline(self):
        """Vérifie la discipline de tous les utilisateurs chaque jour à minuit"""
        try:
            # Récupérer tous les utilisateurs
            response = supabase.client.table('user_discipline').select('*').execute()
            users = response.data

            for user in users:
                user_id = user['user_id']
                # Vérifier les 7 derniers jours
                last_7_days_stats = await supabase.get_period_stats(user_id, 'weekly')
                if not last_7_days_stats:
                    logger.warning(f"Impossible de récupérer les stats pour l'utilisateur {user_id} pour la discipline.")
                    continue

                # Calculer le nombre de jours validés (MINIMUM_DAILY_MINUTES minimum)
                validated_days = 0
                for day_stats in last_7_days_stats:
                    if day_stats['total_seconds'] >= MINIMUM_DAILY_MINUTES * 60:  # MINIMUM_DAILY_MINUTES en secondes
                        validated_days += 1

                # Mettre à jour le niveau de discipline
                if validated_days >= 5:  # Au moins 5 jours sur 7
                    await self.update_discipline(user_id, user['discipline_level'] + 1)
                else:
                    await self.update_discipline(user_id, 0)

        except Exception as e:
            logger.error(f"Erreur lors de la vérification de la discipline: {e}")

    async def update_discipline(self, user_id: int, discipline_level: int) -> None:
        """Met à jour le niveau de discipline d'un utilisateur"""
        try:
            # Limiter le niveau de discipline à 10
            discipline_level = min(discipline_level, 10)
            
            # Récupérer les données actuelles
            current_data = await supabase.get_user_discipline(user_id)
            if current_data:
                # Mettre à jour le meilleur niveau si nécessaire
                best_level = max(current_data['best_discipline_level'], discipline_level)
            else:
                best_level = discipline_level

            # Mettre à jour la discipline avec la date actuelle
            await supabase.update_discipline(user_id, discipline_level, best_level, datetime.now())
            
            # Mettre à jour le rôle Discord
            await self.update_discord_role(user_id, discipline_level)
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de la discipline: {e}")

    async def update_discord_role(self, user_id: int, discipline_level: int) -> None:
        """Met à jour le rôle Discord en fonction du niveau de discipline"""
        try:
            # Récupérer le serveur et l'utilisateur
            guild = self.bot.guilds[0]  # Premier serveur
            member = guild.get_member(user_id)
            if not member:
                return

            # Supprimer tous les rôles de discipline existants
            discipline_roles = [role for role in guild.roles if role.name.startswith("Discipline")]
            for role in discipline_roles:
                if role in member.roles:
                    await member.remove_roles(role)

            # Ajouter le nouveau rôle si le niveau est > 0
            if discipline_level > 0:
                role_name = f"Discipline {discipline_level}"
                role = discord.utils.get(guild.roles, name=role_name)
                if role:
                    await member.add_roles(role)

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du rôle: {e}")

    @app_commands.command(name="discipline", description="Affiche votre niveau de discipline")
    async def discipline(self, interaction: discord.Interaction):
        """Affiche le niveau de discipline de l'utilisateur"""
        try:
            data = await supabase.get_user_discipline(interaction.user.id)
            if not data:
                await interaction.response.send_message("Vous n'avez pas encore de niveau de discipline.", ephemeral=True)
                return

            embed = discord.Embed(
                title="Niveau de Discipline",
                color=discord.Color.blue()
            )
            
            # Afficher le niveau actuel
            embed.add_field(
                name="Niveau Actuel",
                value=f"{data['discipline_level']}",
                inline=True
            )
            
            # Afficher le meilleur niveau
            embed.add_field(
                name="Meilleur Niveau",
                value=f"{data['best_discipline_level']}",
                inline=True
            )
            
            # Afficher la dernière vérification
            last_check = datetime.fromisoformat(data['last_check'])
            embed.add_field(
                name="Dernière Vérification",
                value=last_check.strftime("%d/%m/%Y %H:%M"),
                inline=False
            )

            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            logger.error(f"Erreur lors de l'affichage de la discipline: {e}")
            await interaction.response.send_message("Une erreur est survenue lors de la récupération de votre niveau de discipline.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Discipline(bot)) 