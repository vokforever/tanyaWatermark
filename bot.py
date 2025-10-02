import logging
import os
import json
import asyncio
import subprocess
import concurrent.futures

print("Импортирую библиотеки...")
try:
    from dotenv import load_dotenv
    print("dotenv импортирован")
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
    print("telegram импортирован")
    from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
    print("telegram.ext импортирован")
    from PIL import Image, ImageDraw, ImageFont
    print("PIL импортирован")

    # --- Библиотеки для работы с видео ---
    from moviepy.editor import VideoFileClip, TextClip, ImageClip, CompositeVideoClip, AudioClip
    print("moviepy импортирован")

    # --- НАСТРОЙКА ImageMagick (ОБЯЗАТЕЛЬНО ДЛЯ ВИДЕО) ---
    # Указываем прямой путь к magick.exe для корректной работы с видео
    print("Настраиваю ImageMagick...")
    from moviepy.config import change_settings
    change_settings({"IMAGEMAGICK_BINARY": r"C:\Program Files\ImageMagick-7.1.2-Q16-HDRI\magick.exe"})
    print("ImageMagick настроен")
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("Убедитесь, что все необходимые библиотеки установлены:")
    print("pip install python-telegram-bot python-dotenv pillow moviepy")
    exit(1)

# Загружаем переменные окружения из .env файла
print("Загружаю переменные окружения...")
load_dotenv()
print("Переменные окружения загружены")

# --- НАСТРОЙКИ ---
# Получаем токен из переменных окружения
print("Получаю токен из переменных окружения...")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
print(f"Токен получен: {'Да' if TOKEN else 'Нет'}")

# Глобальные переменные для управления состоянием
print("Инициализирую пути к файлам...")
script_dir = os.path.dirname(os.path.abspath(__file__))
print(f"Директория скрипта: {script_dir}")
STATE_FILE = os.path.join(script_dir, "user_states.json")
user_states = {}

# Путь к файлам
LOGO_FILE = os.path.join(script_dir, "telegram-logo.png")
FONT_FILE = os.path.join(script_dir, "Roboto-Regular.ttf")
print(f"Путь к логотипу: {LOGO_FILE}")
print(f"Путь к шрифту: {FONT_FILE}")

# Включаем логирование, чтобы видеть ошибки
print("Настраиваю логирование...")
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)
logger.info("Логирование настроено")

# Параметры водяного знака
logger.info("Настраиваю параметры водяного знака...")
WATERMARK_TEXT = "@mprelest"
BASE_FONT_SIZE = 16
LOGO_SCALE_FACTOR = 1.9
LOGO_TO_TEXT_RATIO = 1.2 # Лого будет на 20% выше текста
TEXT_COLOR = "white"
STROKE_COLOR = "black"
STROKE_WIDTH = 2
PADDING = 10
logger.info(f"Параметры водяного знака: текст='{WATERMARK_TEXT}', размер={BASE_FONT_SIZE}, масштаб={LOGO_SCALE_FACTOR}, множитель лого={LOGO_TO_TEXT_RATIO}")

def load_states():
    """Загружает состояния пользователей из файла, очищая устаревшие."""
    global user_states
    logger.info(f"Загружаю состояния из файла: {STATE_FILE}")
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            loaded_states = json.load(f)
        logger.info(f"Загружено состояний: {len(loaded_states)}")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.info(f"Файл состояний не найден или поврежден: {e}")
        loaded_states = {}

    users_to_remove = []
    for user_id, state in loaded_states.items():
        input_path = state.get('input_path')
        if not input_path or not os.path.exists(input_path):
            users_to_remove.append(user_id)
    
    if users_to_remove:
        logger.info(f"Удаляю устаревшие состояния: {len(users_to_remove)}")
        for user_id in users_to_remove:
            del loaded_states[user_id]

    user_states = loaded_states
    if users_to_remove:
        save_states()
    logger.info(f"Итоговое количество состояний: {len(user_states)}")

def save_states():
    """Сохраняет состояния пользователей в файл."""
    logger.info(f"Сохраняю состояния в файл: {STATE_FILE}")
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(user_states, f)
        logger.info(f"Состояния сохранены: {len(user_states)}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении состояний: {e}")

def add_watermark(image_path: str, scale_factor: float) -> str:
    """
    Добавляет водяной знак на изображение, используя ImageMagick через subprocess.
    Версия с исправлением артефактов прозрачности.
    """
    logger.info(f"Начинаю обработку (метод с фиксом артефактов): {image_path}, масштаб: {scale_factor}")
    
    # --- Шаг 0: Подготовка ---
    logo_resized_path = os.path.join(script_dir, "temp_logo_resized.png")
    text_path = os.path.join(script_dir, "temp_text.png")
    watermark_temp_path = os.path.join(script_dir, "temp_watermark_combined.png")
    output_path = os.path.join(script_dir, "watermarked_image.png")

    try:
        # --- Получаем размеры и рассчитываем параметры ---
        with Image.open(image_path) as img:
            img_width, img_height = img.size
        logger.info(f"Размеры изображения: {img_width}x{img_height}")

        font_size = int((img_height * 0.035) * scale_factor)
        logo_height = int(font_size * LOGO_TO_TEXT_RATIO) 
        spacing = int(font_size * 0.25)

        # --- ШАГ 1: Создаём отмасштабированный логотип ---
        cmd_create_logo = [
            "magick", "-background", "none", LOGO_FILE,
            "-resize", f"x{logo_height}",
            logo_resized_path
        ]
        logger.info(f"Шаг 1 (Лого): {' '.join(cmd_create_logo)}")
        subprocess.run(cmd_create_logo, check=True, capture_output=True, text=True)
        
        # --- ШАГ 2: Создаём изображение с текстом ---
        cmd_create_text = [
            "magick", "-background", "none", "-font", FONT_FILE,
            "-pointsize", str(font_size), "-fill", TEXT_COLOR,
            "-stroke", STROKE_COLOR, "-strokewidth", str(STROKE_WIDTH),
            f"label:{WATERMARK_TEXT}",
            text_path
        ]
        logger.info(f"Шаг 2 (Текст): {' '.join(cmd_create_text)}")
        subprocess.run(cmd_create_text, check=True, capture_output=True, text=True)

        # --- ШАГ 3: Соединяем логотип и текст ---
        cmd_combine = [
            "magick",
            "-background", "none",  # ИСПРАВЛЕНО: Заставляет холст быть идеально прозрачным
            logo_resized_path,
            "-size", f"{spacing}x0", "xc:none",
            text_path,
            "-gravity", "Center",
            "+append",
            watermark_temp_path
        ]
        logger.info(f"Шаг 3 (Соединение): {' '.join(cmd_combine)}")
        subprocess.run(cmd_combine, check=True, capture_output=True, text=True)

        # --- ШАГ 4: Накладываем готовый водяной знак ---
        cmd_apply_watermark = [
            "magick", "composite", "-gravity", "Center",
            watermark_temp_path, image_path, output_path
        ]
        logger.info(f"Шаг 4 (Наложение): {' '.join(cmd_apply_watermark)}")
        subprocess.run(cmd_apply_watermark, check=True, capture_output=True, text=True)
        
        logger.info(f"Изображение с водяным знаком успешно сохранено: {output_path}")
        return output_path

    except subprocess.CalledProcessError as e:
        logger.critical(f"Ошибка выполнения команды ImageMagick!", exc_info=True)
        logger.error(f"STDERR: {e.stderr.strip()}")
        return None
    except Exception as e:
        logger.critical(f"Неизвестная ошибка при обработке изображения: {e}", exc_info=True)
        return None
    finally:
        # --- ШАГ 5: Очистка ---
        for f_path in [logo_resized_path, text_path, watermark_temp_path]:
            if os.path.exists(f_path):
                os.remove(f_path)
        logger.info("Временные файлы очищены.")

def add_watermark_to_video(video_path: str) -> tuple:
    """Добавляет водяной знак на видео и возвращает путь и метаданные."""
    output_path = os.path.join(script_dir, "watermarked_video.mp4")
    try:
        logger.info(f"Начало обработки видео: {video_path}")
        video = VideoFileClip(video_path)
        
        width, height = video.size
        duration = video.duration
        logger.info(f"Видео загружено. Размеры: {width}x{height}, длительность: {duration}с.")
        
        video_font_size = int(video.h * 0.05)
        txt_clip = TextClip(WATERMARK_TEXT, 
                           fontsize=video_font_size, color=TEXT_COLOR, font=FONT_FILE,
                           stroke_color=STROKE_COLOR, stroke_width=2)
        
        logo = ImageClip(LOGO_FILE)
        logo_height = int(txt_clip.h * LOGO_TO_TEXT_RATIO)
        logo = logo.resize(height=logo_height)
        
        # Центрируем текст относительно логотипа
        y_logo = (video.h - logo.h) // 2
        y_text = (video.h - txt_clip.h) // 2
        
        total_width = logo.w + 10 + txt_clip.w
        x_start = (video.w - total_width) // 2
        
        logo = logo.set_position((x_start, y_logo)).set_duration(video.duration)
        txt_clip = txt_clip.set_position((x_start + logo.w + 10, y_text)).set_duration(video.duration)
        
        final = CompositeVideoClip([video, logo, txt_clip])
        
        # --- ИЗМЕНЕНО: ГАРАНТИРУЕМ НАЛИЧИЕ АУДИОДОРОЖКИ ---
        # Если в исходном видео нет звука, создаем тихую дорожку
        if final.audio is None:
            logger.info("Аудиодорожка не найдена. Создаю тишину...")
            # Создаем аудиоклип с нулевой громкостью (тишиной)
            silent_audio = AudioClip(make_frame=lambda t: [0, 0], duration=duration, fps=44100)
            final.audio = silent_audio
            logger.info("Тихая аудиодорожка успешно добавлена.")

        logger.info(f"Начало сохранения видео в {output_path}...")
        final.write_videofile(
            output_path, 
            codec='libx264', 
            audio_codec='aac', # Указываем аудиокодек
            preset='medium', 
            threads=4
        )
        logger.info("Видео успешно сохранено.")
        
        video.close()
        final.close()
        
        return output_path, width, height, duration
    except Exception as e:
        logger.error(f"Ошибка при обработке видео: {e}", exc_info=True)
        return None, None, None, None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение."""
    user_id = str(update.effective_user.id)
    logger.info(f"Пользователь {user_id} запустил бота")
    await update.message.reply_text(
        "Привет! Просто отправь мне фото, видео или файл с картинкой/видео, и я добавлю водяной знак."
    )
    logger.info(f"Приветственное сообщение отправлено пользователю {user_id}")

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает фото и видео."""
    user_id = str(update.effective_user.id)

    # --- ДОБАВЛЕНО: УМНАЯ ОЧИСТКА ---
    # Перед обработкой нового файла, удаляем старый результат для этого пользователя
    if user_id in user_states and 'output_path' in user_states[user_id]:
        previous_output = user_states[user_id]['output_path']
        if previous_output and os.path.exists(previous_output):
            logger.info(f"Очистка: удаляю предыдущий файл {previous_output} для пользователя {user_id}")
            os.remove(previous_output)
    # --- КОНЕЦ БЛОКА ОЧИСТКИ ---

    logger.info(f"Получено медиа от пользователя {user_id}")
    file_obj = None
    media_type = None
    file_extension = None
    
    if update.message.photo:
        logger.info(f"Обнаружено фото от пользователя {user_id}")
        file_obj = await update.message.photo[-1].get_file()
        media_type = "photo"
        file_extension = ".png"
    elif update.message.video:
        logger.info(f"Обнаружено видео от пользователя {user_id}")
        file_obj = await update.message.video.get_file()
        media_type = "video"
        file_extension = ".mp4"
    elif update.message.document and update.message.document.mime_type:
        logger.info(f"Обнаружен документ от пользователя {user_id}, MIME: {update.message.document.mime_type}")
        if 'image' in update.message.document.mime_type:
            file_obj = await update.message.document.get_file()
            media_type = "photo"
            file_extension = ".png"
        elif 'video' in update.message.document.mime_type:
            file_obj = await update.message.document.get_file()
            media_type = "video"
            file_extension = ".mp4"

    if not file_obj:
        logger.warning(f"Пользователь {user_id} отправил неподдерживаемый тип файла")
        await update.message.reply_text("Ошибка: это не изображение или видео.")
        return

    input_path = os.path.join(script_dir, f"temp_{user_id}{file_extension}")
    logger.info(f"Путь для сохранения файла: {input_path}")
    
    if os.path.exists(input_path):
        logger.info(f"Удаляю существующий файл: {input_path}")
        os.remove(input_path)
    
    try:
        logger.info(f"Скачиваю файл для пользователя {user_id}...")
        await file_obj.download_to_drive(input_path)
        logger.info(f"Файл успешно скачан: {input_path}")
    except Exception as e:
        logger.error(f"User {user_id}: Download failed with error: {e}")
        await update.message.reply_text("Ошибка: не удалось скачать файл.")
        return

    if not os.path.exists(input_path):
        logger.error(f"User {user_id}: File not found at path: {input_path} after download.")
        await update.message.reply_text("Ошибка: файл не найден после скачивания.")
        return

    # --- Синхронная обработка фото ---
    if media_type == "photo":
        logger.info(f"Начинаю обработку фото для пользователя {user_id}")
        processing_message = await update.message.reply_text("Обрабатываю фото...")
        output_path = None
        
        try:
            current_scale = user_states.get(user_id, {}).get('scale', LOGO_SCALE_FACTOR)
            logger.info(f"Текущий масштаб для пользователя {user_id}: {current_scale}")
            
            logger.info(f"Вызываю add_watermark для пользователя {user_id}")
            
            loop = asyncio.get_event_loop()
            try:
                output_path = await asyncio.wait_for(
                    loop.run_in_executor(None, add_watermark, input_path, current_scale),
                    timeout=30.0
                )
                logger.info(f"add_watermark вернул: {output_path}")
            except asyncio.TimeoutError:
                logger.error(f"Обработка изображения превысила таймаут для пользователя {user_id}")
                await processing_message.edit_text("Обработка изображения занимает слишком много времени. Попробуйте изображение меньшего размера.")
                return

            if output_path and os.path.exists(output_path):
                logger.info(f"Файл с водяным знаком создан: {output_path}")
                keyboard = [
                    [InlineKeyboardButton("➖ Уменьшить", callback_data='decrease'),
                     InlineKeyboardButton("➕ Увеличить", callback_data='increase')],
                    [InlineKeyboardButton("✅ Скачать файлом", callback_data='download')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                logger.info(f"Отправляю фото пользователю {user_id}")
                with open(output_path, 'rb') as photo_file:
                    await update.message.reply_photo(photo=photo_file, reply_markup=reply_markup)
                logger.info(f"Фото отправлено пользователю {user_id}")
                
                user_states[user_id] = {'input_path': input_path, 'scale': current_scale, 'media_type': 'photo'}
                save_states()
            else:
                logger.error(f"add_watermark вернул None или файл не существует для пользователя {user_id}")
                await processing_message.edit_text("Не удалось создать изображение с водяным знаком. Проверьте логи.")

        except Exception as e:
            logger.error(f"Критическая ошибка при обработке фото для пользователя {user_id}: {e}", exc_info=True)
            await processing_message.edit_text("Произошла непредвиденная ошибка при обработке фото.")
        
        finally:
            if output_path and os.path.exists(output_path):
                logger.info(f"Удаляю временный файл: {output_path}")
                os.remove(output_path)
            await processing_message.delete()
            logger.info(f"Обработка фото завершена для пользователя {user_id}")

    # --- Обработка видео ---
    else: # video
        logger.info(f"Начинаю обработку видео для пользователя {user_id}")
        processing_message = await update.message.reply_text("Файл принят в обработку. Это может занять время, я сообщу, когда буду готов.")
        logger.info(f"Создаю задачу для обработки видео пользователя {user_id}")
        context.application.create_task(process_video_task(update, context, processing_message, input_path))

async def process_video_task(update: Update, context: ContextTypes.DEFAULT_TYPE, processing_message, input_path: str) -> None:
    """Фоновая задача для обработки видео. Отправляет превью с кнопкой "Скачать"."""
    user_id = str(update.effective_user.id)
    logger.info(f"Начинаю фоновую обработку видео для пользователя {user_id}")
    output_path = None
    try:
        await processing_message.edit_text("Добавляю водяной знак на видео...")
        output_path, width, height, duration = add_watermark_to_video(input_path)

        if output_path:
            logger.info(f"Видео успешно обработано: {output_path}")
            await processing_message.edit_text("Отправляю видео-превью...")
            
            # Создаем клавиатуру с кнопкой "Скачать файлом"
            keyboard = [[InlineKeyboardButton("✅ Скачать файлом", callback_data='download_video')]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            with open(output_path, 'rb') as video_file:
                await update.message.reply_video(
                    video=video_file,
                    filename="watermarked_video.mp4",
                    width=width, height=height, duration=int(duration),
                    supports_streaming=True,
                    reply_markup=reply_markup # Прикрепляем кнопку
                )
            
            # Сохраняем путь к готовому файлу, чтобы его можно было скачать по кнопке
            user_states[user_id] = {'output_path': output_path, 'media_type': 'video'}
            save_states()
            logger.info(f"Видео-превью отправлено, путь сохранен для пользователя {user_id}")
            
        else:
            await processing_message.edit_text("Не удалось обработать видео.")

    except Exception as e:
        logger.error(f"Критическая ошибка в process_video_task: {e}", exc_info=True)
        await processing_message.edit_text("Произошла ошибка при обработке видео.")
    finally:
        # ВАЖНО: Удаляем только ИСХОДНЫЙ файл. Обработанный (output) оставляем для скачивания.
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        await processing_message.delete()
        logger.info(f"Обработка видео завершена. Исходный файл удален.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает нажатия кнопок (только для фото)."""
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    logger.info(f"Получен callback от пользователя {user_id}: {query.data}")

    if user_id not in user_states or user_states[user_id].get('media_type') != 'photo':
        await query.edit_message_text(text="Эта сессия устарела. Пожалуйста, отправьте фото заново.")
        return

    state = user_states[user_id]
    input_path = state.get('input_path')

    if not input_path or not os.path.exists(input_path):
        logger.warning(f"Файл {input_path} не найден для user {user_id}.")
        await query.edit_message_text(text="Оригинальное изображение утеряно. Пожалуйста, отправьте его снова.")
        if user_id in user_states:
            del user_states[user_id]
            save_states()
        return

    current_scale = state.get('scale', LOGO_SCALE_FACTOR)
    new_scale = current_scale

    if query.data == 'increase':
        new_scale = round(current_scale + 0.2, 1) # Увеличим шаг для заметности
    elif query.data == 'decrease':
        new_scale = round(current_scale - 0.2, 1)

    user_states[user_id]['scale'] = new_scale
    save_states()
    logger.info(f"User {user_id}: Нажата кнопка. Новый масштаб: {new_scale}.")

    output_path = None
    try:
        # Генерируем новое изображение с новым масштабом
        output_path = add_watermark(input_path, new_scale)

        if output_path and os.path.exists(output_path):
            keyboard = [
                [InlineKeyboardButton("➖ Уменьшить", callback_data='decrease'),
                 InlineKeyboardButton("➕ Увеличить", callback_data='increase')],
                [InlineKeyboardButton("✅ Скачать файлом", callback_data='download')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # ИСПРАВЛЕНИЕ: Редактируем сообщение, заменяя в нём медиафайл
            with open(output_path, 'rb') as photo_file:
                media = InputMediaPhoto(media=photo_file)
                await query.edit_message_media(media=media, reply_markup=reply_markup)
            logger.info(f"Сообщение для пользователя {user_id} обновлено с новым фото.")
        else:
            await query.edit_message_text(text="Не удалось обработать изображение с новым масштабом.")
            logger.error(f"add_watermark вернул None для user {user_id}")

    except Exception as e:
        logger.error(f"Ошибка в handle_callback для user {user_id}: {e}", exc_info=True)
        # Не отправляем текст, так как это может вызвать ошибку, если сообщение уже с медиа
    finally:
        if output_path and os.path.exists(output_path):
            os.remove(output_path)

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет файл фото для скачивания (только для фото)."""
    query = update.callback_query
    await query.answer("Готовлю файл...")
    user_id = str(query.from_user.id)
    logger.info(f"Запрос на скачивание от пользователя {user_id}")

    if user_id not in user_states or user_states[user_id].get('media_type') != 'photo':
        await query.message.reply_text("Сессия устарела. Пожалуйста, отправьте фото заново.")
        return

    state = user_states[user_id]
    input_path = state.get('input_path')
    scale = state.get('scale', LOGO_SCALE_FACTOR)

    if not input_path or not os.path.exists(input_path):
        await query.message.reply_text("Оригинальное изображение утеряно. Пожалуйста, отправьте его снова.")
        if user_id in user_states: del user_states[user_id]
        save_states()
        return
    
    output_path = None
    try:
        logger.info(f"Создаю файл для скачивания пользователем {user_id} с масштабом {scale}")
        output_path = add_watermark(input_path, scale)
        if output_path:
            logger.info(f"Файл создан, отправляю пользователю {user_id}")
            with open(output_path, 'rb') as doc_file:
                await query.message.reply_document(document=doc_file, filename="watermarked_image.png")
            logger.info(f"Файл отправлен пользователю {user_id}")
        else:
            logger.error(f"Не удалось создать файл для скачивания для user {user_id}")
            await query.message.reply_text("Не удалось создать файл для скачивания.")
    except Exception as e:
        logger.error(f"Ошибка в handle_download для user {user_id}: {e}", exc_info=True)
        await query.message.reply_text("Произошла ошибка при подготовке файла.")
    finally:
        if output_path and os.path.exists(output_path):
            os.remove(output_path)

async def handle_video_download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет файл видео для скачивания."""
    query = update.callback_query
    await query.answer("Готовлю файл...")
    user_id = str(query.from_user.id)
    logger.info(f"Запрос на скачивание видео от пользователя {user_id}")

    if user_id not in user_states or user_states[user_id].get('media_type') != 'video':
        await query.message.reply_text("Сессия устарела. Пожалуйста, отправьте видео заново.")
        return

    # Получаем путь к уже обработанному файлу из состояния
    output_path = user_states[user_id].get('output_path')

    if not output_path or not os.path.exists(output_path):
        await query.message.reply_text("Файл утерян (возможно, была начата новая обработка). Пожалуйста, отправьте видео снова.")
        return
    
    logger.info(f"Отправляю видео-файл {output_path} пользователю {user_id}")
    try:
        with open(output_path, 'rb') as doc_file:
            await query.message.reply_document(document=doc_file, filename="watermarked_video.mp4")
        logger.info(f"Видео-файл успешно отправлен.")
    except Exception as e:
        logger.error(f"Ошибка при отправке видео-файла: {e}", exc_info=True)
        await query.message.reply_text("Произошла ошибка при отправке файла.")

def main() -> None:
    """Запускает бота."""
    try:
        logger.info("Начинаю запуск бота...")
        
        if not TOKEN or TOKEN == "СЮДА_ВСТАВИТЬ_ВАШ_ТОКЕН":
            logger.error("Токен не установлен")
            print("Ошибка: Пожалуйста, установите переменную окружения TELEGRAM_BOT_TOKEN в файле .env")
            return

        logger.info(f"Токен получен: {TOKEN[:10]}...")

        if not os.path.exists(LOGO_FILE):
            logger.error(f"Файл логотипа не найден: {LOGO_FILE}")
            print(f"Ошибка: Файл логотипа '{LOGO_FILE}' не найден.")
            return
        logger.info(f"Файл логотипа найден: {LOGO_FILE}")
        
        if not os.path.exists(FONT_FILE):
            logger.error(f"Файл шрифта не найден: {FONT_FILE}")
            print(f"Ошибка: Файл шрифта '{FONT_FILE}' не найден.")
            return
        logger.info(f"Файл шрифта найден: {FONT_FILE}")

        logger.info("Загружаю состояния пользователей...")
        load_states()
        logger.info("Состояния загружены")

        logger.info("Создаю приложение...")
        application = Application.builder().token(TOKEN).build()
        logger.info("Приложение создано")

        logger.info("Добавляю обработчики...")
        application.add_handler(CommandHandler("start", start))
        # Обработчик для фото, видео и документов
        application.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_media))
        # Обработчики кнопок
        application.add_handler(CallbackQueryHandler(handle_callback, pattern='^(increase|decrease)$'))
        application.add_handler(CallbackQueryHandler(handle_download, pattern='^download$'))
        application.add_handler(CallbackQueryHandler(handle_video_download, pattern='^download_video$'))
        logger.info("Обработчики добавлены")

        print("Бот запущен...")
        logger.info("Запускаю polling...")
        application.run_polling()
    except Exception as e:
        print(f"Критическая ошибка при запуске бота: {e}")
        logger.error(f"Критическая ошибка при запуске бота: {e}", exc_info=True)

if __name__ == "__main__":
    print("Запускаю бота...")
    print("Инициализация...")
    logger.info("Точка входа в программу")
    logger.info("Начинаю инициализацию...")
    main()
    print("Бот завершил работу")
    logger.info("Программа завершена")