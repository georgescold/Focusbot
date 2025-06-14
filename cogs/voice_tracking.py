import discord
from discord.ext import commands
from discord import app_commands
import datetime
from config import VOICE_CHANNEL_PAUSE_ID, MINIMUM_DAILY_MINUTES, ROLES, GUILD_ID
from database.supabase_client import supabase
import logging
import asyncio
from typing import Optional, Dict

logger = logging.getLogger('Focusbot')

class VoiceTracking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions: Dict[int, Dict] = {}  # {user_id: {'start_time': datetime, 'last_save': datetime}}
        self.session_tasks: Dict[int, asyncio.Task] = {}  # {user_id: task}
        self.role_check_task: Optional[asyncio.Task] = None
        self.role_check_interval = 300  # 5 minutes
        self.session_save_interval = 60  # 1 minute
        
    async def cog_load(self):
        """Démarre la vérification périodique des rôles"""
        self.role_check_task = self.bot.loop.create_task(self.periodic_role_check())
        
    async def cog_unload(self):
        """Arrête la vérification périodique des rôles et nettoie les sessions actives"""
        if self.role_check_task:
            self.role_check_task.cancel()
            try:
                await self.role_check_task
            except asyncio.CancelledError:
                pass

        # Nettoyer toutes les sessions actives
        for user_id, task in list(self.session_tasks.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            await self.save_session(user_id)
        
    async def periodic_role_check(self):
        """Vérifie périodiquement les rôles de tous les membres"""
        while True:
            try:
                guild = self.bot.get_guild(GUILD_ID)
                if guild:
                    for member in guild.members:
                        if not member.bot:
                            try:
                                stats = await supabase.get_user_stats(member.id)
                                if stats:
                                    await self.update_user_role(member, stats['total_hours'])
                            except Exception as e:
                                logger.error(f"Erreur lors de la vérification du rôle pour {member.name}: {e}")
                                continue
                await asyncio.sleep(self.role_check_interval)
            except asyncio.CancelledError:
                logger.info("Vérification périodique des rôles annulée")
                break
            except Exception as e:
                logger.error(f"Erreur lors de la vérification périodique des rôles: {e}")
                await asyncio.sleep(60)  # Attendre 1 minute en cas d'erreur

    async def save_session(self, user_id: int) -> bool:
        """Sauvegarde une session vocale"""
        if user_id not in self.active_sessions:
            return False

        session_data = self.active_sessions[user_id]
        try:
            end_time = datetime.datetime.now()
            duration = end_time - session_data['last_save']
            duration_seconds = int(duration.total_seconds())
            
            if duration_seconds >= 1:
                await supabase.add_session(
                    user_id=user_id,
                    start_time=session_data['last_save'],
                    end_time=end_time,
                    duration_seconds=duration_seconds
                )
                session_data['last_save'] = end_time
                return True
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde de la session pour l'utilisateur {user_id}: {e}")
        return False

    async def track_session(self, member: discord.Member, start_time: datetime.datetime):
        """Suivi d'une session vocale"""
        if member.id in self.session_tasks:
            self.session_tasks[member.id].cancel()
            try:
                await self.session_tasks[member.id]
            except asyncio.CancelledError:
                pass

        self.active_sessions[member.id] = {
            'start_time': start_time,
            'last_save': start_time
        }

        async def session_tracker():
            try:
                while True:
                    await asyncio.sleep(self.session_save_interval)
                    if member.id not in self.active_sessions:
                        break
                    await self.save_session(member.id)
            except asyncio.CancelledError:
                logger.info(f"Suivi de session annulé pour {member.name}")
                raise
            except Exception as e:
                logger.error(f"Erreur inattendue dans le suivi de session pour {member.name}: {e}")
                raise
            finally:
                if member.id in self.active_sessions:
                    await self.save_session(member.id)
                    del self.active_sessions[member.id]
                if member.id in self.session_tasks:
                    del self.session_tasks[member.id]

        self.session_tasks[member.id] = self.bot.loop.create_task(session_tracker())

    async def check_all_roles(self):
        """Vérifie les rôles de tous les membres"""
        try:
            guild = self.bot.get_guild(GUILD_ID)
            if guild:
                logger.info(f"Serveur Discord trouvé: {guild.name} ({guild.id})")
                logger.info("Démarrage de la vérification des rôles pour tous les membres")
                for member in guild.members:
                    if not member.bot:
                        stats = await supabase.get_user_stats(member.id)
                        if stats:
                            logger.info(f"Vérification du rôle pour {member.name}")
                            await self.update_user_role(member, stats['total_hours'])
                logger.info("Vérification des rôles terminée")
            else:
                logger.warning(f"Serveur Discord (ID: {GUILD_ID}) non trouvé.")
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des rôles: {e}")

    async def update_user_role(self, member: discord.Member, total_hours: float):
        """Met à jour le rôle d'un utilisateur en fonction de son temps total"""
        try:
            logger.info(f"Vérification du rôle pour {member.name} avec {total_hours} heures")
            
            # Déterminer le rôle approprié en fonction des heures totales
            new_role_name = None
            for role_name, hours_required in sorted(ROLES.items(), key=lambda x: x[1], reverse=True):
                if total_hours >= hours_required:
                    new_role_name = role_name
                    break

            logger.info(f"Rôle éligible trouvé pour {member.name}: {new_role_name if new_role_name else 'Aucun'}")

            # Vérifier si l'utilisateur a déjà le bon rôle
            current_role = None
            for role in member.roles:
                if role.name in ROLES:
                    current_role = role.name
                    break

            # Ne faire les modifications que si le rôle a changé
            if current_role != new_role_name:
                # Retirer l'ancien rôle si nécessaire
                if current_role:
                    discord_role = discord.utils.get(member.guild.roles, name=current_role)
                    if discord_role:
                        await member.remove_roles(discord_role)
                        logger.info(f"Ancien rôle '{current_role}' retiré de {member.name} sur Discord.")

                # Attribuer le nouveau rôle si nécessaire
                if new_role_name:
                    discord_new_role = discord.utils.get(member.guild.roles, name=new_role_name)
                    if discord_new_role:
                        await member.add_roles(discord_new_role)
                        logger.info(f"Rôle '{new_role_name}' attribué à {member.name} sur Discord.")
                        await supabase.update_user_role(member.id, new_role_name, ROLES[new_role_name])
                        logger.info(f"Rôle '{new_role_name}' mis à jour dans la base de données pour {member.name}.")
                else:
                    await supabase.delete_user_role(member.id)
                    logger.info(f"Aucun rôle de progression attribué à {member.name}. Rôle effacé de la base de données.")

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour du rôle: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Gère les changements d'état vocal des membres"""
        # Ignorer les bots
        if member.bot:
            return
            
        # Gestion de l'entrée dans un salon vocal
        if before.channel is None and after.channel is not None:
            # Ignorer le salon "Pause"
            if after.channel.id == VOICE_CHANNEL_PAUSE_ID:
                return
                
            start_time = datetime.datetime.now()
            self.active_sessions[member.id] = start_time
            
            # Démarrer le suivi de la session
            task = asyncio.create_task(self.track_session(member, start_time))
            self.session_tasks[member.id] = task
            
            logger.info(f"{member.name} est entré dans {after.channel.name}")
            
        # Gestion de la sortie d'un salon vocal
        elif before.channel is not None and after.channel is None:
            if member.id in self.active_sessions:
                # Annuler la tâche de suivi
                if member.id in self.session_tasks:
                    self.session_tasks[member.id].cancel()
                    del self.session_tasks[member.id]
                    
                start_time = self.active_sessions.pop(member.id)
                end_time = datetime.datetime.now()
                duration = end_time - start_time
                duration_seconds = int(duration.total_seconds())
                
                # Ignorer les sessions de moins d'une seconde
                if duration_seconds < 1:
                    return
                    
                # Enregistrer la session dans la base de données
                await supabase.add_session(
                    user_id=member.id,
                    start_time=start_time,
                    end_time=end_time,
                    duration_seconds=duration_seconds
                )
                logger.info(f"Session de {member.name} enregistrée: {duration_seconds} secondes")

async def setup(bot):
    await bot.add_cog(VoiceTracking(bot))