# Используем официальный образ Python 3.11
FROM python:3.11-slim

# Устанавливаем системные зависимости
# - imagemagick: для обработки изображений
# - ffmpeg: для обработки видео
# - libmagickwand-dev: для работы с ImageMagick через Python
RUN apt-get update && apt-get install -y \
    imagemagick \
    ffmpeg \
    libmagickwand-dev \
    libmagickcore-dev \
    ghostscript \
    fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем файл requirements.txt
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем все файлы проекта
COPY bot.py .
COPY telegram-logo.png .
COPY telegram-logo.svg .
COPY Roboto-Regular.ttf .
COPY Roboto-Italic-VariableFont_wdth,wght.ttf .
COPY Roboto-VariableFont_wdth,wght.ttf .
COPY back_music ./back_music/

# Создаем директорию для временных файлов
RUN mkdir -p /app/temp

# Устанавливаем переменные окружения
ENV PYTHONUNBUFFERED=1

# Команда запуска бота
CMD ["python", "bot.py"]
