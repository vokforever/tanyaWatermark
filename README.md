# Telegram Watermark Bot

Бот для добавления водяных знаков на изображения в Telegram.

## Установка

### Способ 1: Docker (рекомендуется для Linux)

**Требования:**
- Docker Engine 20.10+
- Docker Compose 2.0+

**Инструкция:**

1. **Клонируйте репозиторий:**
```bash
git clone <репозиторий>
cd tanyaWatermark
```

2. **Создайте файл `.env` на основе `env_template.txt`:**
```bash
cp env_template.txt .env
```

3. **Отредактируйте файл `.env` и вставьте ваш токен от @BotFather:**
```
TELEGRAM_BOT_TOKEN=ваш_токен_здесь
```

4. **Запустите бота с помощью Docker Compose:**
```bash
docker-compose up -d
```

5. **Для просмотра логов:**
```bash
docker-compose logs -f
```

6. **Для остановки бота:**
```bash
docker-compose down
```

### Способ 2: Локальный запуск (с виртуальным окружением)

1. **Создайте виртуальное окружение:**
```bash
python -m venv venv
```

2. **Активируйте виртуальное окружение:**
```bash
# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Windows (Command Prompt)
venv\Scripts\activate.bat

# Linux/Mac
source venv/bin/activate
```

3. **Установите зависимости:**
```bash
pip install -r requirements.txt
```

4. **Создайте файл `.env` на основе `env_template.txt`:**
```bash
# Windows
copy env_template.txt .env

# Linux/Mac
cp env_template.txt .env
```

5. **Отредактируйте файл `.env` и вставьте ваш токен от @BotFather:**
```
TELEGRAM_BOT_TOKEN=ваш_токен_здесь
```

6. **Убедитесь, что у вас есть файлы:**
   - `telegram-logo.png` - логотип для водяного знака
   - `Roboto-VariableFont_wdth,wght.ttf` - шрифт для текста

## Запуск

### Способ 1: Docker (рекомендуется для Linux)

**Требования:**
- Установленный Docker и Docker Compose

**Инструкция:**

1. **Создайте файл `.env` на основе `env_template.txt`:**
```bash
# Linux/Mac
cp env_template.txt .env
```

2. **Отредактируйте файл `.env` и вставьте ваш токен от @BotFather:**
```
TELEGRAM_BOT_TOKEN=ваш_токен_здесь
```

3. **Запустите бота с помощью Docker Compose:**
```bash
docker-compose up -d
```

4. **Для просмотра логов:**
```bash
docker-compose logs -f
```

5. **Для остановки бота:**
```bash
docker-compose down
```

### Способ 2: Локальный запуск (без Docker)

**Убедитесь, что виртуальное окружение активировано!**

```bash
# Активируйте виртуальное окружение (если еще не активировано)
.\venv\Scripts\Activate.ps1

# Запустите бота
python bot.py
```

## Использование

1. Запустите бота командой `/start`
2. Отправьте изображение боту
3. Получите изображение с водяным знаком

## Настройки

Вы можете изменить параметры водяного знака в файле `bot.py`:
- `WATERMARK_TEXT` - текст водяного знака
- `FONT_SIZE` - размер шрифта
- `TEXT_COLOR` - цвет текста
- `STROKE_COLOR` - цвет обводки
- `STROKE_WIDTH` - толщина обводки
- `PADDING` - отступ от краев
