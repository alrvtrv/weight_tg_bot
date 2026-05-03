import asyncio
import logging
import json
from datetime import datetime, date
from pathlib import Path
from dotenv import load_dotenv
import os
import httpx

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


BASE_URL = "http://127.0.0.1:8000"
SAVE_WEIGHT_URL = f"{BASE_URL}/save-weight"
HISTORY_URL = f"{BASE_URL}/weight"

# Загружаем переменные окружения
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в .env файле!")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Определение состояний для FSM
class UserStates(StatesGroup):
    waiting_for_bio = State()
    waiting_for_weight = State()

# Файл для сохранения био
BIOS_FILE = "user_bios.json"

def load_bios():
    """Загружает существующие био из файла"""
    if Path(BIOS_FILE).exists():
        with open(BIOS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_bio(user_id: int, username: str, bio: str):
    """Сохраняет био в файл"""
    bios = load_bios()
    bios[str(user_id)] = {
        "username": username,
        "bio": bio,
        "saved_at": datetime.now().isoformat()
    }
    with open(BIOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(bios, f, ensure_ascii=False, indent=4)


####################################################################################
# Клавиатура
####################################################################################

def get_main_keyboard() -> InlineKeyboardMarkup:
    'Функция вызывает кнопки для выбора пользователем'
    keyboard = [
        [
            InlineKeyboardButton(text="Weight", callback_data="weight"),
            InlineKeyboardButton(text="History", callback_data="history"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

####################################################################################
# Хендлеры команд
####################################################################################

@dp.message(Command("start"))
async def start_handler(message: Message):
    """Обработчик команды /start"""
    logger.info(f"Новый пользователь: {message.from_user.username} (ID: {message.from_user.id})")
    
    await message.answer(
        f"Hi, {message.from_user.first_name}! 👋\n\n"
        f"I'm Weight Bot.\n"
        f"I can help you track your weight. Tell me what to do for you",
        reply_markup=get_main_keyboard()
    )

####################################################################################
# Хендлеры кнопок
####################################################################################

@dp.callback_query(F.data == "weight")
async def handle_weight_button(callback: CallbackQuery, state: FSMContext):
    '''Функция обрабатывает нажатие на кнопку "Weight"'''
    await state.set_state(UserStates.waiting_for_weight)
    
    await callback.message.edit_text(
        "Please enter your current weight (e.g. 75.5 or 80):"
    )
    await callback.answer()


@dp.message(UserStates.waiting_for_weight)
async def process_weight(message: Message, state: FSMContext):
    '''Функция обработчик сообщений от юзера'''
    try:
        # Обрабатываем значения
        weight_text = message.text.strip().replace(",", ".")
        weight = float(weight_text)

        # Проверяем значения
        if weight <= 0 or weight > 300:
            raise ValueError

        # Получаем текущую дату
        current_date = datetime.now().date().isoformat()

        # Отправка в FastAPI
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SAVE_WEIGHT_URL,
                json={
                    "user_id": message.from_user.id,
                    "weight": weight,
                    "date": current_date,
                    "username": message.from_user.username
                },
                timeout=10.0
            )

        # Возвращаем ответ в зависимости от успеха отправки в FastAPI
        if response.status_code in (200, 201):
            await message.answer(
                f"Your weight ({weight} kg) has been saved successfully!",
                reply_markup=get_main_keyboard()
            )
        else:
            await message.answer("Failed to save weight. Please try again later.")

        await state.clear()  # Обновляем статус

    except ValueError:
        await message.answer("Please enter a valid number.\nExample: 72.3 or 80")
    except Exception as e:
        logger.error(f"Error processing weight: {e}")
        await message.answer("Something went wrong. Please try again.")
        await state.clear()

@dp.callback_query(F.data == "history")
async def handle_history_button(callback: CallbackQuery):
    """Хендлер нажатия на кнопку History"""
    user_id = callback.from_user.id
    
    async with httpx.AsyncClient() as client:
        try:
            # Делаем GET запрос к FastAPI: /weight/{user_id}
            response = await client.get(f"{HISTORY_URL}/{user_id}", params={"limit": 10})
            
            if response.status_code == 200:
                data = response.json()
                weights = data.get("weights", [])
                
                if not weights:
                    text = "You haven't recorded any weights yet! 🕸️"
                else:
                    text = "📋 **Your Last 10 Records:**\n\n"
                    for entry in weights:
                        # Форматируем дату для красоты
                        entry_date = entry['date']
                        text += f"• {entry_date}: **{entry['weight']} kg**\n"
                
                await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=get_main_keyboard())
            else:
                await callback.answer("Error fetching data from server.")
        
        except Exception as e:
            logger.error(f"History error: {e}")
            await callback.answer("Server connection error.")
    
    await callback.answer()

async def main():
    """Главная функция"""
    logger.info("Бот запущен!")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())