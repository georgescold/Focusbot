import os
from supabase import create_client, Client
from config import SUPABASE_URL, SUPABASE_KEY
import logging
import datetime
from typing import Optional, Dict, List
import asyncio
from functools import wraps

logger = logging.getLogger('Focusbot')

def with_retry(max_retries=3, delay=1):
    """Décorateur pour ajouter des retries aux opérations de base de données"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(f"Tentative {attempt + 1}/{max_retries} échouée pour {func.__name__}. Nouvelle tentative dans {wait_time}s. Erreur: {e}")
                        await asyncio.sleep(wait_time)
            logger.error(f"Toutes les tentatives ont échoué pour {func.__name__}. Dernière erreur: {last_error}")
            raise last_error
        return wrapper
    return decorator

class SupabaseClient:
    def __init__(self):
        try:
            if not SUPABASE_URL or not SUPABASE_KEY:
                raise ValueError("Les variables d'environnement SUPABASE_URL et SUPABASE_KEY sont requises")
            
            self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
            # Configuration du timeout
            self.client.postgrest.timeout = 10  # 10 secondes de timeout
            logger.info("Connexion à Supabase établie avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de Supabase: {e}")
            raise

    @with_retry(max_retries=3, delay=1)
    async def add_session(self, user_id: int, start_time: datetime.datetime, end_time: datetime.datetime, duration_seconds: int):
        """Ajoute une session vocale à la base de données"""
        data = {
            'user_id': user_id,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration_seconds': duration_seconds
        }
        response = self.client.table('sessions').insert(data).execute()
        return response.data

    @with_retry(max_retries=3, delay=1)
    async def get_user_stats(self, user_id: int):
        """Récupère les statistiques d'un utilisateur"""
        # Récupérer le temps total en secondes des 6 derniers mois
        response = self.client.table('sessions')\
            .select('duration_seconds')\
            .eq('user_id', user_id)\
            .gte('start_time', (datetime.datetime.now() - datetime.timedelta(days=180)).isoformat())\
            .execute()
        
        recent_seconds = sum(session['duration_seconds'] for session in response.data)

        # Récupérer les statistiques agrégées des mois plus anciens
        old_stats = self.client.table('monthly_stats')\
            .select('total_seconds')\
            .eq('user_id', user_id)\
            .execute()
        
        old_seconds = sum(stat['total_seconds'] for stat in old_stats.data)
        
        # Calculer le total
        total_seconds = recent_seconds + old_seconds
        total_hours = total_seconds / 3600  # Conversion en heures
        
        return {
            'total_hours': total_hours,
            'total_seconds': total_seconds
        }

    @with_retry(max_retries=3, delay=1)
    async def get_user_streak(self, user_id: int) -> dict:
        """Récupère les données de streak d'un utilisateur"""
        response = await self.client.table('user_stats').select('*').eq('user_id', user_id).execute()
        if response.data:
            return response.data[0]
        return None

    @with_retry(max_retries=3, delay=1)
    async def update_streak(self, user_id: int, current_streak: int, longest_streak: int) -> None:
        """Met à jour le streak d'un utilisateur"""
        today = datetime.datetime.now().date()
        data = {
            'user_id': user_id,
            'current_streak': current_streak,
            'longest_streak': longest_streak,
            'last_active_date': today.isoformat()
        }
        
        # Vérifier si l'utilisateur existe déjà
        existing = await self.get_user_streak(user_id)
        if existing:
            await self.client.table('user_stats').update(data).eq('user_id', user_id).execute()
        else:
            await self.client.table('user_stats').insert(data).execute()

    @with_retry(max_retries=3, delay=1)
    async def get_all_users_with_sessions(self) -> list:
        """Récupère la liste de tous les utilisateurs qui ont des sessions"""
        response = await self.client.table('sessions').select('user_id').execute()
        if response.data:
            # Retourner une liste unique d'user_ids
            return list(set(session['user_id'] for session in response.data))
        return []

    @with_retry(max_retries=3, delay=1)
    async def get_user_role(self, user_id: int):
        """Récupère le rôle actuel d'un utilisateur"""
        response = self.client.table('user_roles')\
            .select('role_name')\
            .eq('user_id', user_id)\
            .execute()
        return response.data[0] if response.data else None

    @with_retry(max_retries=3, delay=1)
    async def check_user_role_exists(self, user_id: int) -> bool:
        """Vérifie si un utilisateur existe dans la table user_roles"""
        response = self.client.table('user_roles')\
            .select('user_id')\
            .eq('user_id', user_id)\
            .execute()
        return len(response.data) > 0

    @with_retry(max_retries=3, delay=1)
    async def update_user_role(self, user_id: int, role_name: str, total_hours: float):
        """Met à jour le rôle d'un utilisateur"""
        data = {
            'user_id': user_id,
            'role_name': role_name,
            'total_hours': total_hours
        }
        
        # Vérifier si l'utilisateur existe déjà
        exists = await self.check_user_role_exists(user_id)
        if exists:
            response = self.client.table('user_roles')\
                .update(data)\
                .eq('user_id', user_id)\
                .execute()
        else:
            response = self.client.table('user_roles')\
                .insert(data)\
                .execute()
        return response.data

    @with_retry(max_retries=3, delay=1)
    async def delete_user_role(self, user_id: int) -> bool:
        """Supprime le rôle d'un utilisateur de la base de données"""
        response = self.client.table('user_roles')\
            .delete()\
            .eq('user_id', user_id)\
            .execute()
        return True if response.data else False

    @with_retry(max_retries=3, delay=1)
    async def get_leaderboard(self, period: str) -> Optional[List[Dict]]:
        """Récupère le classement pour une période donnée"""
        now = datetime.datetime.now()
        
        # Définir la date de début selon la période
        if period == 'daily':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'weekly':
            start_date = now - datetime.timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'monthly':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == 'yearly':
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:  # 'all'
            start_date = None

        # Construire la requête
        query = self.client.table('sessions').select('user_id, duration_seconds')
        if start_date:
            query = query.gte('start_time', start_date.isoformat())
        
        response = query.execute()
        
        # Grouper par utilisateur et calculer le total
        user_totals = {}
        for session in response.data:
            user_id = session['user_id']
            if user_id not in user_totals:
                user_totals[user_id] = 0
            user_totals[user_id] += session['duration_seconds']
        
        # Convertir en liste et trier
        leaderboard = [
            {'user_id': user_id, 'total_seconds': total}
            for user_id, total in user_totals.items()
        ]
        leaderboard.sort(key=lambda x: x['total_seconds'], reverse=True)
        
        return leaderboard

    @with_retry(max_retries=3, delay=1)
    async def get_user_discipline(self, user_id: int) -> Optional[Dict]:
        """Récupère les données de discipline d'un utilisateur"""
        response = self.client.table('user_discipline').select('*').eq('user_id', user_id).execute()
        if response.data:
            return response.data[0]
        return None

    @with_retry(max_retries=3, delay=1)
    async def update_discipline(self, user_id: int, discipline_level: int, best_discipline_level: int, last_check: datetime.datetime) -> bool:
        """Met à jour les données de discipline d'un utilisateur"""
        data = {
            'discipline_level': discipline_level,
            'best_discipline_level': best_discipline_level,
            'last_check': last_check.isoformat()
        }
        response = self.client.table('user_discipline').update(data).eq('user_id', user_id).execute()
        return True if response.data else False

    @with_retry(max_retries=3, delay=1)
    async def get_period_stats(self, user_id: int, period: str) -> Optional[Dict]:
        """Récupère les statistiques d'un utilisateur pour une période donnée (daily, weekly, monthly, yearly)"""
        now = datetime.datetime.now()
        start_date = None

        if period == 'daily':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'weekly':
            start_date = now - datetime.timedelta(days=now.weekday())
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'monthly':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == 'yearly':
            start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

        if not start_date:
            return None

        response = self.client.table('sessions')\
            .select('start_time, duration_seconds')\
            .eq('user_id', user_id)\
            .gte('start_time', start_date.isoformat())\
            .order('start_time', desc=False)\
            .execute()

        if not response.data:
            return None

        # Grouper les sessions par jour
        daily_stats = {}
        for session in response.data:
            session_date = datetime.datetime.fromisoformat(session['start_time']).date()
            if session_date not in daily_stats:
                daily_stats[session_date] = 0
            daily_stats[session_date] += session['duration_seconds']

        # Retourner une liste de dictionnaires pour chaque jour
        return [{
            'date': date.isoformat(),
            'total_seconds': total_seconds
        } for date, total_seconds in daily_stats.items()]

    @with_retry(max_retries=3, delay=1)
    async def get_day_stats(self, user_id: int, date: datetime.datetime) -> Optional[Dict]:
        """Récupère les statistiques d'un utilisateur pour un jour spécifique"""
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = date.replace(hour=23, minute=59, second=59, microsecond=999999)

        response = self.client.table('sessions')\
            .select('duration_seconds')\
            .eq('user_id', user_id)\
            .gte('start_time', start_of_day.isoformat())\
            .lte('start_time', end_of_day.isoformat())\
            .execute()

        if not response.data:
            return None

        total_seconds = sum(session['duration_seconds'] for session in response.data)
        return {'total_seconds': total_seconds}

    @with_retry(max_retries=3, delay=1)
    async def aggregate_old_sessions(self) -> bool:
        """Agrège les sessions vocales de plus de 6 mois dans une table mensuelle"""
        six_months_ago = datetime.datetime.now() - datetime.timedelta(days=180)
        
        # Récupérer les sessions à agréger
        response = self.client.table('sessions')\
            .select('id, user_id, duration_seconds, start_time')\
            .lt('start_time', six_months_ago.isoformat())\
            .execute()
        
        if not response.data:
            logger.info("Aucune ancienne session à agréger.")
            return False

        # Agrégation par mois et par utilisateur
        monthly_aggregates = {}
        for session in response.data:
            user_id = session['user_id']
            month_year = datetime.datetime.fromisoformat(session['start_time']).strftime('%Y-%m')
            
            if (user_id, month_year) not in monthly_aggregates:
                monthly_aggregates[(user_id, month_year)] = 0
            monthly_aggregates[(user_id, month_year)] += session['duration_seconds']
        
        # Insérer ou mettre à jour les statistiques mensuelles
        for (user_id, month_year), total_seconds in monthly_aggregates.items():
            # Vérifier si l'entrée existe déjà
            existing_stat = self.client.table('monthly_stats')\
                .select('total_seconds')\
                .eq('user_id', user_id)\
                .eq('month', month_year)\
                .execute()

            if existing_stat.data:
                # Mettre à jour
                new_total = existing_stat.data[0]['total_seconds'] + total_seconds
                self.client.table('monthly_stats')\
                    .update({'total_seconds': new_total})\
                    .eq('user_id', user_id)\
                    .eq('month', month_year)\
                    .execute()
            else:
                # Insérer
                self.client.table('monthly_stats')\
                    .insert({'user_id': user_id, 'month': month_year, 'total_seconds': total_seconds})\
                    .execute()
        
        # Supprimer les sessions agrégées
        session_ids_to_delete = [session['id'] for session in response.data]
        if session_ids_to_delete:
            self.client.table('sessions')\
                .delete()\
                .in_('id', session_ids_to_delete)\
                .execute()
        
        logger.info(f"Agrégation de {len(response.data)} anciennes sessions terminée. {len(monthly_aggregates)} entrées mensuelles mises à jour.")
        return True

# Création et exportation de l'instance
try:
    supabase = SupabaseClient()
except Exception as e:
    logger.error(f"Erreur fatale lors de l'initialisation de Supabase: {e}")
    raise 