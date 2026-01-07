"""Менеджер сессий для хранения данных пользователей"""
import logging
from datetime import datetime
from typing import Dict, Optional, Any
from collections import defaultdict

logger = logging.getLogger(__name__)


class SessionManager:
    """Управление сессиями пользователей"""
    
    def __init__(self):
        self.sessions: Dict[int, Dict[str, Any]] = defaultdict(dict)
    
    def get_session(self, user_id: int) -> Dict[str, Any]:
        """Получить сессию пользователя"""
        if user_id not in self.sessions:
            self.sessions[user_id] = {
                "task_description": "",
                "clarification_questions": [],
                "answers": {},
                "recommendations": {},
                "current_prompt": "",
                "created_at": datetime.now(),
                "edited_count": 0
            }
        return self.sessions[user_id]
    
    def update_task_description(self, user_id: int, description: str):
        """Обновить описание задачи"""
        session = self.get_session(user_id)
        session["task_description"] = description
        logger.info(f"Обновлено описание задачи для пользователя {user_id}")
    
    def set_clarification_questions(self, user_id: int, questions: list):
        """Установить уточняющие вопросы"""
        session = self.get_session(user_id)
        session["clarification_questions"] = questions
        logger.info(f"Установлено {len(questions)} вопросов для пользователя {user_id}")
    
    def add_answer(self, user_id: int, question: str, answer: str):
        """Добавить ответ на вопрос"""
        session = self.get_session(user_id)
        session["answers"][question] = answer
        logger.info(f"Добавлен ответ для пользователя {user_id}")
    
    def set_recommendations(self, user_id: int, recommendations: Dict[str, Any]):
        """Установить рекомендации"""
        session = self.get_session(user_id)
        session["recommendations"] = recommendations
        logger.info(f"Установлены рекомендации для пользователя {user_id}")
    
    def set_current_prompt(self, user_id: int, prompt: str):
        """Установить текущий промпт"""
        session = self.get_session(user_id)
        session["current_prompt"] = prompt
        logger.info(f"Установлен промпт для пользователя {user_id}")
    
    def update_prompt(self, user_id: int, new_prompt: str):
        """Обновить промпт"""
        session = self.get_session(user_id)
        session["current_prompt"] = new_prompt
        session["edited_count"] += 1
        logger.info(f"Обновлен промпт для пользователя {user_id} (редакций: {session['edited_count']})")
    
    def get_current_prompt(self, user_id: int) -> Optional[str]:
        """Получить текущий промпт"""
        session = self.get_session(user_id)
        return session.get("current_prompt", "")
    
    def clear_session(self, user_id: int):
        """Очистить сессию пользователя"""
        if user_id in self.sessions:
            del self.sessions[user_id]
            logger.info(f"Сессия пользователя {user_id} очищена")
    
    def get_all_data(self, user_id: int) -> Dict[str, Any]:
        """Получить все данные сессии"""
        return self.get_session(user_id).copy()


# Глобальный экземпляр менеджера сессий
session_manager = SessionManager()

