"""Клиент для взаимодействия с LLM через ProxyAPI"""
import asyncio
import logging
from typing import Optional, List, Dict, Any
from openai import AsyncOpenAI
from openai import OpenAIError

import config

logger = logging.getLogger(__name__)


class LLMClient:
    """Клиент для работы с LLM через ProxyAPI"""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
            timeout=config.LLM_TIMEOUT
        )
        self.model = config.LLM_MODEL
        self.max_tokens = config.LLM_MAX_TOKENS
        self.temperature = config.LLM_TEMPERATURE
    
    async def _call_with_retry(
        self,
        system_prompt: str,
        user_message: str,
        max_retries: int = config.MAX_RETRIES
    ) -> Optional[str]:
        """Вызов LLM с retry логикой"""
        delay = config.RETRY_DELAY
        
        for attempt in range(max_retries):
            try:
                logger.info(f"LLM запрос (попытка {attempt + 1}/{max_retries})")
                
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    max_tokens=self.max_tokens,
                    temperature=self.temperature
                )
                
                result = response.choices[0].message.content
                logger.info("LLM запрос успешно выполнен")
                return result
                
            except OpenAIError as e:
                logger.warning(f"Ошибка LLM (попытка {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= 2  # Экспоненциальная задержка
                else:
                    logger.error(f"Все попытки исчерпаны: {e}")
                    raise
            
            except Exception as e:
                logger.error(f"Неожиданная ошибка при вызове LLM: {e}")
                raise
        
        return None
    
    async def generate_clarification_questions(self, task_description: str) -> List[str]:
        """Генерирует уточняющие вопросы на основе описания задачи"""
        from templates import PHASE1_SYSTEM_PROMPT
        
        logger.info("Генерация уточняющих вопросов")
        
        response = await self._call_with_retry(
            system_prompt=PHASE1_SYSTEM_PROMPT,
            user_message=f"Описание задачи:\n{task_description}"
        )
        
        if not response:
            raise ValueError("Не удалось сгенерировать вопросы")
        
        # Парсим вопросы из ответа
        questions = []
        for line in response.strip().split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith('-')):
                # Убираем нумерацию и маркеры
                question = line.split('.', 1)[-1].strip()
                question = question.lstrip('- ').strip()
                if question and question.endswith('?'):
                    questions.append(question)
        
        if not questions:
            # Если парсинг не удался, возвращаем весь ответ как один вопрос
            questions = [response.strip()]
        
        logger.info(f"Сгенерировано {len(questions)} вопросов")
        return questions
    
    async def generate_recommendations(
        self,
        task_description: str,
        answers: Dict[str, str]
    ) -> Dict[str, Any]:
        """Генерирует рекомендации на основе задачи и ответов"""
        from templates import PHASE2_SYSTEM_PROMPT
        import json
        
        logger.info("Генерация рекомендаций")
        
        # Формируем текст с ответами
        answers_text = "\n".join([
            f"Вопрос: {q}\nОтвет: {a}\n"
            for q, a in answers.items()
        ])
        
        user_message = f"""Исходная задача:
{task_description}

Ответы на вопросы:
{answers_text}"""
        
        response = await self._call_with_retry(
            system_prompt=PHASE2_SYSTEM_PROMPT,
            user_message=user_message
        )
        
        if not response:
            raise ValueError("Не удалось сгенерировать рекомендации")
        
        # Парсим JSON из ответа
        try:
            # Пытаемся найти JSON в ответе
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                recommendations = json.loads(json_str)
            else:
                # Если JSON не найден, создаем структуру из текста
                recommendations = {
                    "tech_stack": response[:200] if len(response) > 200 else response,
                    "architecture": "Требуется уточнение",
                    "key_features": [],
                    "scalability": "Требуется уточнение",
                    "compliance": "Требуется уточнение",
                    "risks": [],
                    "recommendation_summary": response
                }
        except json.JSONDecodeError as e:
            logger.warning(f"Ошибка парсинга JSON: {e}. Используем текст как есть.")
            recommendations = {
                "tech_stack": "Требуется уточнение",
                "architecture": "Требуется уточнение",
                "key_features": [],
                "scalability": "Требуется уточнение",
                "compliance": "Требуется уточнение",
                "risks": [],
                "recommendation_summary": response
            }
        
        logger.info("Рекомендации успешно сгенерированы")
        return recommendations
    
    async def generate_final_prompt(
        self,
        task_description: str,
        recommendations: Dict[str, Any]
    ) -> str:
        """Генерирует финальный промпт для Cursor"""
        from templates import PHASE3_SYSTEM_PROMPT
        
        logger.info("Генерация финального промпта")
        
        # Форматируем рекомендации в текст
        recommendations_text = f"""Технологический стек: {recommendations.get('tech_stack', 'Не указан')}
Архитектура: {recommendations.get('architecture', 'Не указана')}
Ключевые особенности: {', '.join(recommendations.get('key_features', []))}
Масштабируемость: {recommendations.get('scalability', 'Не указана')}
Compliance: {recommendations.get('compliance', 'Не указан')}
Риски: {', '.join(recommendations.get('risks', []))}
Резюме: {recommendations.get('recommendation_summary', 'Не указано')}"""
        
        user_message = f"""Исходная задача:
{task_description}

Принятые рекомендации:
{recommendations_text}"""
        
        response = await self._call_with_retry(
            system_prompt=PHASE3_SYSTEM_PROMPT,
            user_message=user_message
        )
        
        if not response:
            raise ValueError("Не удалось сгенерировать промпт")
        
        logger.info("Промпт успешно сгенерирован")
        return response.strip()

