"""Утилиты для форматирования и парсинга"""
import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


def format_recommendations(recommendations: Dict[str, any]) -> str:
    """Форматирует рекомендации для отображения пользователю"""
    text = "📋 **Рекомендации:**\n\n"
    
    if recommendations.get("tech_stack"):
        text += f"🔧 **Технологический стек:**\n{recommendations['tech_stack']}\n\n"
    
    if recommendations.get("architecture"):
        text += f"🏗️ **Архитектура:**\n{recommendations['architecture']}\n\n"
    
    if recommendations.get("key_features"):
        features = recommendations["key_features"]
        if isinstance(features, list) and features:
            text += f"✨ **Ключевые особенности:**\n"
            for feature in features:
                text += f"• {feature}\n"
            text += "\n"
    
    if recommendations.get("scalability"):
        text += f"📈 **Масштабируемость:**\n{recommendations['scalability']}\n\n"
    
    if recommendations.get("compliance"):
        text += f"🔒 **Compliance и безопасность:**\n{recommendations['compliance']}\n\n"
    
    if recommendations.get("risks"):
        risks = recommendations["risks"]
        if isinstance(risks, list) and risks:
            text += f"⚠️ **Риски:**\n"
            for risk in risks:
                text += f"• {risk}\n"
            text += "\n"
    
    if recommendations.get("recommendation_summary"):
        text += f"📝 **Резюме:**\n{recommendations['recommendation_summary']}\n"
    
    return text


def parse_sections(prompt: str) -> Dict[str, str]:
    """Парсит промпт на секции"""
    sections = {}
    current_section = None
    current_content = []
    
    lines = prompt.split('\n')
    
    for line in lines:
        # Проверяем, является ли строка заголовком секции
        if line.strip().startswith('#') and any(
            keyword in line.upper() 
            for keyword in ['ЗАДАЧА', 'GOAL', 'ТРЕБОВАНИЯ', 'REQUIREMENTS', 
                          'TECH STACK', 'АРХИТЕКТУРА', 'ARCHITECTURE',
                          'ДОПОЛНИТЕЛЬНЫЕ', 'ADDITIONAL', 'OUTPUT', 'ФОРМАТ']
        ):
            # Сохраняем предыдущую секцию
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            
            # Начинаем новую секцию
            current_section = line.strip()
            current_content = []
        else:
            if current_section:
                current_content.append(line)
    
    # Сохраняем последнюю секцию
    if current_section:
        sections[current_section] = '\n'.join(current_content).strip()
    
    # Если секции не найдены, возвращаем весь промпт как одну секцию
    if not sections:
        sections["Полный промпт"] = prompt
    
    return sections


def get_section_list(prompt: str) -> List[str]:
    """Получает список секций промпта"""
    sections = parse_sections(prompt)
    return list(sections.keys())


def update_section(prompt: str, section_name: str, new_content: str) -> str:
    """Обновляет секцию в промпте"""
    sections = parse_sections(prompt)
    
    # Находим точное совпадение или частичное
    matched_section = None
    for section_key in sections.keys():
        if section_name.lower() in section_key.lower() or section_key.lower() in section_name.lower():
            matched_section = section_key
            break
    
    if matched_section:
        sections[matched_section] = new_content
    else:
        # Если секция не найдена, добавляем новую
        sections[f"# {section_name.upper()}"] = new_content
    
    # Собираем промпт обратно
    result = []
    for section_name_key, section_content in sections.items():
        result.append(section_name_key)
        result.append(section_content)
        result.append("")  # Пустая строка между секциями
    
    return '\n'.join(result).strip()


def add_requirement_to_prompt(prompt: str, requirement: str) -> str:
    """Добавляет требование в секцию REQUIREMENTS"""
    sections = parse_sections(prompt)
    
    # Ищем секцию с требованиями
    requirements_section = None
    for section_key in sections.keys():
        if any(keyword in section_key.upper() for keyword in ['ТРЕБОВАНИЯ', 'REQUIREMENTS']):
            requirements_section = section_key
            break
    
    if requirements_section:
        # Добавляем требование в существующую секцию
        current_content = sections[requirements_section]
        sections[requirements_section] = f"{current_content}\n- {requirement}"
    else:
        # Создаем новую секцию требований
        sections["# ТРЕБОВАНИЯ / # REQUIREMENTS"] = f"- {requirement}"
    
    # Собираем промпт обратно
    result = []
    for section_name_key, section_content in sections.items():
        result.append(section_name_key)
        result.append(section_content)
        result.append("")
    
    return '\n'.join(result).strip()


def remove_requirement_from_prompt(prompt: str, requirement_text: str) -> str:
    """Удаляет требование из промпта"""
    sections = parse_sections(prompt)
    
    # Ищем секцию с требованиями
    requirements_section = None
    for section_key in sections.keys():
        if any(keyword in section_key.upper() for keyword in ['ТРЕБОВАНИЯ', 'REQUIREMENTS']):
            requirements_section = section_key
            break
    
    if requirements_section:
        # Удаляем строки, содержащие требование
        lines = sections[requirements_section].split('\n')
        filtered_lines = [
            line for line in lines 
            if requirement_text.lower() not in line.lower()
        ]
        sections[requirements_section] = '\n'.join(filtered_lines).strip()
    
    # Собираем промпт обратно
    result = []
    for section_name_key, section_content in sections.items():
        result.append(section_name_key)
        result.append(section_content)
        result.append("")
    
    return '\n'.join(result).strip()


def create_export_file(prompt: str, user_id: int) -> str:
    """Создает файл для экспорта промпта"""
    from datetime import datetime
    from pathlib import Path
    
    # Создаем директорию exports если её нет (Windows-совместимо)
    from pathlib import Path
    exports_dir = Path("exports")
    exports_dir.mkdir(exist_ok=True)
    
    # Генерируем имя файла
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = exports_dir / f"prompt_{user_id}_{timestamp}.txt"
    
    # Записываем промпт в файл
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(prompt)
    
    logger.info(f"Создан файл экспорта: {filename}")
    return str(filename)

