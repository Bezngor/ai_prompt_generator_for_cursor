FROM python:3.11-slim

# Рабочая директория внутри контейнера
WORKDIR /app

# Обновляем пакеты (при необходимости можно добавить системные зависимости)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем зависимости Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект в контейнер
COPY . .

# Отключаем буферизацию вывода Python (удобнее для логов)
ENV PYTHONUNBUFFERED=1

# Команда запуска бота
CMD ["python", "main.py"]


