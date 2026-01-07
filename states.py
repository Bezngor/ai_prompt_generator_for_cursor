"""FSM состояния для управления диалогом"""
from aiogram.fsm.state import State, StatesGroup


class PromptGenerationStates(StatesGroup):
    """Состояния процесса генерации промпта"""
    
    # Фаза 1: Сбор информации о задаче
    waiting_for_task_description = State()  # Ожидание описания задачи
    waiting_for_clarification_answers = State()  # Ожидание ответов на уточняющие вопросы
    
    # Фаза 2: Анализ ответов
    showing_recommendations = State()  # Показ рекомендаций
    
    # Фаза 3: Принятие рекомендаций
    waiting_for_recommendation_decision = State()  # Ожидание решения по рекомендациям
    
    # Фаза 4: Генерация промпта
    prompt_generated = State()  # Промпт сгенерирован
    
    # Фаза 5: Итеративное улучшение
    editing_section = State()  # Редактирование секции
    adding_requirement = State()  # Добавление требования
    removing_requirement = State()  # Удаление требования

