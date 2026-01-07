"""Основной файл бота с handlers и командами"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from states import PromptGenerationStates
from llm_client import LLMClient
from session_manager import session_manager
from templates import (
    WELCOME_MESSAGE, HELP_MESSAGE, TASK_DESCRIPTION_RECEIVED,
    ANSWERS_RECEIVED, RECOMMENDATIONS_READY, PROMPT_GENERATED,
    ERROR_MESSAGE
)
from utils import (
    format_recommendations, parse_sections, get_section_list,
    update_section, add_requirement_to_prompt,
    remove_requirement_from_prompt, create_export_file
)

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Инициализация LLM клиента
llm_client = LLMClient()


def create_recommendation_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для работы с рекомендациями"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="✅ Принять", callback_data="accept_recommendations"))
    builder.add(InlineKeyboardButton(text="🔄 Пересчитать", callback_data="rethink_recommendations"))
    builder.add(InlineKeyboardButton(text="📝 Редактировать описание", callback_data="edit_task_description"))
    builder.adjust(1)
    return builder.as_markup()


def create_prompt_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру для работы с промптом"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="📌 Сохранить", callback_data="save_prompt"))
    builder.add(InlineKeyboardButton(text="📤 Экспортировать", callback_data="export_prompt"))
    builder.add(InlineKeyboardButton(text="🔧 Редактировать секцию", callback_data="edit_section"))
    builder.add(InlineKeyboardButton(text="➕ Добавить требование", callback_data="add_requirement"))
    builder.add(InlineKeyboardButton(text="➖ Удалить требование", callback_data="remove_requirement"))
    builder.add(InlineKeyboardButton(text="🔄 Начать заново", callback_data="restart"))
    builder.adjust(2)
    return builder.as_markup()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    logger.info(f"Пользователь {message.from_user.id} запустил бота")
    
    # Очищаем предыдущую сессию
    session_manager.clear_session(message.from_user.id)
    await state.clear()
    
    # Устанавливаем начальное состояние
    await state.set_state(PromptGenerationStates.waiting_for_task_description)
    
    await message.answer(WELCOME_MESSAGE)


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    await message.answer(HELP_MESSAGE, parse_mode="Markdown")


@router.message(Command("restart"))
async def cmd_restart(message: Message, state: FSMContext):
    """Обработчик команды /restart"""
    logger.info(f"Пользователь {message.from_user.id} перезапустил бота")
    
    session_manager.clear_session(message.from_user.id)
    await state.clear()
    await state.set_state(PromptGenerationStates.waiting_for_task_description)
    
    await message.answer("🔄 Начинаем заново!\n\n" + WELCOME_MESSAGE)


@router.message(Command("accept"))
async def cmd_accept(message: Message, state: FSMContext):
    """Обработчик команды /accept - принять рекомендации"""
    current_state = await state.get_state()
    
    if current_state != PromptGenerationStates.showing_recommendations:
        await message.answer("❌ Сейчас нет активных рекомендаций для принятия.")
        return
    
    await process_accept_recommendations(message, state)


@router.message(Command("rethink"))
async def cmd_rethink(message: Message, state: FSMContext):
    """Обработчик команды /rethink - пересчитать рекомендации"""
    current_state = await state.get_state()
    
    if current_state != PromptGenerationStates.showing_recommendations:
        await message.answer("❌ Сейчас нет активных рекомендаций для пересчета.")
        return
    
    await process_rethink_recommendations(message, state)


@router.message(Command("edit"))
async def cmd_edit(message: Message, state: FSMContext):
    """Обработчик команды /edit - редактировать описание задачи"""
    await state.set_state(PromptGenerationStates.waiting_for_task_description)
    await message.answer("📝 Введите новое описание задачи:")


@router.message(Command("save"))
async def cmd_save(message: Message, state: FSMContext):
    """Обработчик команды /save - сохранить промпт"""
    session = session_manager.get_session(message.from_user.id)
    prompt = session.get("current_prompt", "")
    
    if not prompt:
        await message.answer("❌ Нет промпта для сохранения.")
        return
    
    # Сохраняем в сессию (в реальном приложении можно сохранить в БД)
    session["saved_at"] = datetime.now().isoformat()
    await message.answer("✅ Промпт сохранен в сессии!")


@router.message(Command("export"))
async def cmd_export(message: Message, state: FSMContext):
    """Обработчик команды /export - экспортировать промпт"""
    session = session_manager.get_session(message.from_user.id)
    prompt = session.get("current_prompt", "")
    
    if not prompt:
        await message.answer("❌ Нет промпта для экспорта.")
        return
    
    try:
        file_path = create_export_file(prompt, message.from_user.id)
        file = FSInputFile(file_path)
        await message.answer_document(file, caption="📤 Ваш промпт экспортирован!")
        logger.info(f"Промпт экспортирован пользователем {message.from_user.id}")
    except Exception as e:
        logger.error(f"Ошибка при экспорте: {e}")
        await message.answer("❌ Ошибка при экспорте промпта.")


@router.message(Command("edit_section"))
async def cmd_edit_section(message: Message, state: FSMContext):
    """Обработчик команды /edit_section"""
    session = session_manager.get_session(message.from_user.id)
    prompt = session.get("current_prompt", "")
    
    if not prompt:
        await message.answer("❌ Нет промпта для редактирования.")
        return
    
    sections = get_section_list(prompt)
    if not sections:
        await message.answer("❌ Не удалось найти секции в промпте.")
        return
    
    sections_text = "\n".join([f"{i+1}. {section}" for i, section in enumerate(sections)])
    await message.answer(
        f"📝 Выберите секцию для редактирования:\n\n{sections_text}\n\n"
        f"Отправьте номер секции и новый текст в формате:\n"
        f"`номер: новый текст`",
        parse_mode="Markdown"
    )
    await state.set_state(PromptGenerationStates.editing_section)


@router.message(Command("add_requirement"))
async def cmd_add_requirement(message: Message, state: FSMContext):
    """Обработчик команды /add_requirement"""
    await state.set_state(PromptGenerationStates.adding_requirement)
    await message.answer("➕ Введите новое требование:")


@router.message(Command("remove_requirement"))
async def cmd_remove_requirement(message: Message, state: FSMContext):
    """Обработчик команды /remove_requirement"""
    await state.set_state(PromptGenerationStates.removing_requirement)
    await message.answer("➖ Введите текст требования, которое нужно удалить:")


# Callback handlers
@router.callback_query(lambda c: c.data == "accept_recommendations")
async def process_accept_recommendations(callback: CallbackQuery, state: FSMContext):
    """Обработка принятия рекомендаций"""
    await callback.answer()
    
    session = session_manager.get_session(callback.from_user.id)
    task_description = session.get("task_description", "")
    recommendations = session.get("recommendations", {})
    
    if not task_description or not recommendations:
        await callback.message.answer("❌ Недостаточно данных для генерации промпта.")
        return
    
    await callback.message.answer("🔄 Генерирую финальный промпт...")
    
    try:
        prompt = await llm_client.generate_final_prompt(task_description, recommendations)
        session_manager.set_current_prompt(callback.from_user.id, prompt)
        
        await state.set_state(PromptGenerationStates.prompt_generated)
        
        await callback.message.answer(
            f"{PROMPT_GENERATED}\n\n" + "="*50 + "\n\n" + prompt,
            reply_markup=create_prompt_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Ошибка при генерации промпта: {e}")
        await callback.message.answer(ERROR_MESSAGE)


@router.callback_query(lambda c: c.data == "rethink_recommendations")
async def process_rethink_recommendations(callback: CallbackQuery, state: FSMContext):
    """Обработка пересчета рекомендаций"""
    await callback.answer("🔄 Пересчитываю рекомендации...")
    
    session = session_manager.get_session(callback.from_user.id)
    task_description = session.get("task_description", "")
    answers = session.get("answers", {})
    
    if not task_description or not answers:
        await callback.message.answer("❌ Недостаточно данных для пересчета рекомендаций.")
        return
    
    try:
        recommendations = await llm_client.generate_recommendations(task_description, answers)
        session_manager.set_recommendations(callback.from_user.id, recommendations)
        
        formatted_recommendations = format_recommendations(recommendations)
        await callback.message.answer(
            f"{RECOMMENDATIONS_READY}\n\n{formatted_recommendations}",
            reply_markup=create_recommendation_keyboard(),
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Ошибка при пересчете рекомендаций: {e}")
        await callback.message.answer(ERROR_MESSAGE)


@router.callback_query(lambda c: c.data == "edit_task_description")
async def process_edit_task_description(callback: CallbackQuery, state: FSMContext):
    """Обработка редактирования описания задачи"""
    await callback.answer()
    await state.set_state(PromptGenerationStates.waiting_for_task_description)
    await callback.message.answer("📝 Введите новое описание задачи:")


@router.callback_query(lambda c: c.data == "save_prompt")
async def process_save_prompt(callback: CallbackQuery):
    """Обработка сохранения промпта"""
    await callback.answer("✅ Сохранено!")
    
    session = session_manager.get_session(callback.from_user.id)
    prompt = session.get("current_prompt", "")
    
    if prompt:
        session["saved_at"] = datetime.now().isoformat()
        await callback.message.answer("✅ Промпт сохранен в сессии!")
    else:
        await callback.message.answer("❌ Нет промпта для сохранения.")


@router.callback_query(lambda c: c.data == "export_prompt")
async def process_export_prompt(callback: CallbackQuery):
    """Обработка экспорта промпта"""
    await callback.answer()
    
    session = session_manager.get_session(callback.from_user.id)
    prompt = session.get("current_prompt", "")
    
    if not prompt:
        await callback.message.answer("❌ Нет промпта для экспорта.")
        return
    
    try:
        file_path = create_export_file(prompt, callback.from_user.id)
        file = FSInputFile(file_path)
        await callback.message.answer_document(file, caption="📤 Ваш промпт экспортирован!")
    except Exception as e:
        logger.error(f"Ошибка при экспорте: {e}")
        await callback.message.answer("❌ Ошибка при экспорте промпта.")


@router.callback_query(lambda c: c.data == "edit_section")
async def process_edit_section_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка редактирования секции через callback"""
    await callback.answer()
    
    session = session_manager.get_session(callback.from_user.id)
    prompt = session.get("current_prompt", "")
    
    if not prompt:
        await callback.message.answer("❌ Нет промпта для редактирования.")
        return
    
    sections = get_section_list(prompt)
    if not sections:
        await callback.message.answer("❌ Не удалось найти секции в промпте.")
        return
    
    sections_text = "\n".join([f"{i+1}. {section}" for i, section in enumerate(sections)])
    await callback.message.answer(
        f"📝 Выберите секцию для редактирования:\n\n{sections_text}\n\n"
        f"Отправьте номер секции и новый текст в формате:\n"
        f"`номер: новый текст`",
        parse_mode="Markdown"
    )
    await state.set_state(PromptGenerationStates.editing_section)


@router.callback_query(lambda c: c.data == "add_requirement")
async def process_add_requirement_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка добавления требования через callback"""
    await callback.answer()
    await state.set_state(PromptGenerationStates.adding_requirement)
    await callback.message.answer("➕ Введите новое требование:")


@router.callback_query(lambda c: c.data == "remove_requirement")
async def process_remove_requirement_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка удаления требования через callback"""
    await callback.answer()
    await state.set_state(PromptGenerationStates.removing_requirement)
    await callback.message.answer("➖ Введите текст требования, которое нужно удалить:")


@router.callback_query(lambda c: c.data == "restart")
async def process_restart_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка перезапуска через callback"""
    await callback.answer()
    session_manager.clear_session(callback.from_user.id)
    await state.clear()
    await state.set_state(PromptGenerationStates.waiting_for_task_description)
    await callback.message.answer("🔄 Начинаем заново!\n\n" + WELCOME_MESSAGE)


# Message handlers для состояний FSM
@router.message(PromptGenerationStates.waiting_for_task_description)
async def process_task_description(message: Message, state: FSMContext):
    """Обработка описания задачи"""
    task_description = message.text
    
    if not task_description or len(task_description.strip()) < 10:
        await message.answer("❌ Описание задачи слишком короткое. Пожалуйста, опишите задачу подробнее.")
        return
    
    logger.info(f"Получено описание задачи от пользователя {message.from_user.id}")
    
    session_manager.update_task_description(message.from_user.id, task_description)
    await message.answer(TASK_DESCRIPTION_RECEIVED)
    
    try:
        # Генерируем уточняющие вопросы
        questions = await llm_client.generate_clarification_questions(task_description)
        session_manager.set_clarification_questions(message.from_user.id, questions)
        
        # Формируем сообщение с вопросами
        questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
        await message.answer(
            f"❓ Пожалуйста, ответьте на следующие вопросы:\n\n{questions_text}\n\n"
            f"Отправляйте ответы по одному, каждый ответ на отдельное сообщение."
        )
        
        await state.set_state(PromptGenerationStates.waiting_for_clarification_answers)
        
    except Exception as e:
        logger.error(f"Ошибка при генерации вопросов: {e}")
        await message.answer(ERROR_MESSAGE)


@router.message(PromptGenerationStates.waiting_for_clarification_answers)
async def process_clarification_answer(message: Message, state: FSMContext):
    """Обработка ответов на уточняющие вопросы"""
    session = session_manager.get_session(message.from_user.id)
    questions = session.get("clarification_questions", [])
    answers = session.get("answers", {})
    
    if not questions:
        await message.answer("❌ Ошибка: вопросы не найдены. Используйте /restart для начала заново.")
        return
    
    # Определяем, на какой вопрос отвечает пользователь
    answered_count = len(answers)
    
    if answered_count >= len(questions):
        # Все вопросы уже отвечены, переходим к генерации рекомендаций
        await message.answer(ANSWERS_RECEIVED)
        
        try:
            task_description = session.get("task_description", "")
            recommendations = await llm_client.generate_recommendations(task_description, answers)
            session_manager.set_recommendations(message.from_user.id, recommendations)
            
            formatted_recommendations = format_recommendations(recommendations)
            await message.answer(
                f"{RECOMMENDATIONS_READY}\n\n{formatted_recommendations}",
                reply_markup=create_recommendation_keyboard(),
                parse_mode="Markdown"
            )
            
            await state.set_state(PromptGenerationStates.showing_recommendations)
            
        except Exception as e:
            logger.error(f"Ошибка при генерации рекомендаций: {e}")
            await message.answer(ERROR_MESSAGE)
        
        return
    
    # Добавляем ответ на текущий вопрос
    current_question = questions[answered_count]
    answer_text = message.text
    
    session_manager.add_answer(message.from_user.id, current_question, answer_text)
    
    answered_count += 1
    
    if answered_count < len(questions):
        # Есть еще вопросы
        remaining_questions = len(questions) - answered_count
        await message.answer(
            f"✅ Ответ принят! ({answered_count}/{len(questions)})\n\n"
            f"Следующий вопрос:\n{questions[answered_count]}\n\n"
            f"Осталось вопросов: {remaining_questions}"
        )
    else:
        # Все вопросы отвечены, переходим к генерации рекомендаций
        await message.answer(ANSWERS_RECEIVED)
        
        try:
            task_description = session.get("task_description", "")
            recommendations = await llm_client.generate_recommendations(task_description, answers)
            session_manager.set_recommendations(message.from_user.id, recommendations)
            
            formatted_recommendations = format_recommendations(recommendations)
            await message.answer(
                f"{RECOMMENDATIONS_READY}\n\n{formatted_recommendations}",
                reply_markup=create_recommendation_keyboard(),
                parse_mode="Markdown"
            )
            
            await state.set_state(PromptGenerationStates.showing_recommendations)
            
        except Exception as e:
            logger.error(f"Ошибка при генерации рекомендаций: {e}")
            await message.answer(ERROR_MESSAGE)


@router.message(PromptGenerationStates.editing_section)
async def process_edit_section(message: Message, state: FSMContext):
    """Обработка редактирования секции"""
    session = session_manager.get_session(message.from_user.id)
    prompt = session.get("current_prompt", "")
    
    if not prompt:
        await message.answer("❌ Нет промпта для редактирования.")
        await state.set_state(PromptGenerationStates.prompt_generated)
        return
    
    # Парсим ввод пользователя: "номер: новый текст"
    text = message.text.strip()
    
    if ':' not in text:
        await message.answer("❌ Неверный формат. Используйте: `номер: новый текст`", parse_mode="Markdown")
        return
    
    try:
        section_num_str, new_content = text.split(':', 1)
        section_num = int(section_num_str.strip()) - 1
        
        sections = get_section_list(prompt)
        if section_num < 0 or section_num >= len(sections):
            await message.answer(f"❌ Неверный номер секции. Доступны номера от 1 до {len(sections)}")
            return
        
        section_name = sections[section_num]
        updated_prompt = update_section(prompt, section_name, new_content.strip())
        
        session_manager.update_prompt(message.from_user.id, updated_prompt)
        
        await message.answer(
            "✅ Секция обновлена!\n\n" + "="*50 + "\n\n" + updated_prompt,
            reply_markup=create_prompt_keyboard()
        )
        
        await state.set_state(PromptGenerationStates.prompt_generated)
        
    except ValueError:
        await message.answer("❌ Неверный формат номера секции.")
    except Exception as e:
        logger.error(f"Ошибка при редактировании секции: {e}")
        await message.answer("❌ Ошибка при редактировании секции.")


@router.message(PromptGenerationStates.adding_requirement)
async def process_add_requirement(message: Message, state: FSMContext):
    """Обработка добавления требования"""
    session = session_manager.get_session(message.from_user.id)
    prompt = session.get("current_prompt", "")
    
    if not prompt:
        await message.answer("❌ Нет промпта для редактирования.")
        await state.set_state(PromptGenerationStates.prompt_generated)
        return
    
    requirement = message.text.strip()
    updated_prompt = add_requirement_to_prompt(prompt, requirement)
    
    session_manager.update_prompt(message.from_user.id, updated_prompt)
    
    await message.answer(
        "✅ Требование добавлено!\n\n" + "="*50 + "\n\n" + updated_prompt,
        reply_markup=create_prompt_keyboard()
    )
    
    await state.set_state(PromptGenerationStates.prompt_generated)


@router.message(PromptGenerationStates.removing_requirement)
async def process_remove_requirement(message: Message, state: FSMContext):
    """Обработка удаления требования"""
    session = session_manager.get_session(message.from_user.id)
    prompt = session.get("current_prompt", "")
    
    if not prompt:
        await message.answer("❌ Нет промпта для редактирования.")
        await state.set_state(PromptGenerationStates.prompt_generated)
        return
    
    requirement_text = message.text.strip()
    updated_prompt = remove_requirement_from_prompt(prompt, requirement_text)
    
    session_manager.update_prompt(message.from_user.id, updated_prompt)
    
    await message.answer(
        "✅ Требование удалено!\n\n" + "="*50 + "\n\n" + updated_prompt,
        reply_markup=create_prompt_keyboard()
    )
    
    await state.set_state(PromptGenerationStates.prompt_generated)


# Обработчик всех остальных сообщений
@router.message()
async def process_other_messages(message: Message):
    """Обработка прочих сообщений"""
    await message.answer(
        "❓ Не понимаю команду. Используйте /help для справки или /start для начала работы."
    )


async def main():
    """Главная функция запуска бота"""
    logger.info("Запуск бота...")
    
    # Регистрируем router
    dp.include_router(router)
    
    # Создаем директорию для экспорта
    Path("exports").mkdir(exist_ok=True)
    
    # Запускаем бота
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")

