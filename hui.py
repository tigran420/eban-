
import asyncio
import json
import logging
import threading
import time
from enum import Enum
from typing import Dict, Any, Optional, List


# VK imports
import vk_api  # type: ignore

# Telegram imports
from telegram import (  # type: ignore
    Bot,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InputMediaPhoto,
)
from telegram.error import TelegramError  # type: ignore
from telegram.ext import (  # type: ignore
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)  # type: ignore

from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType  # type: ignore
import requests  # type: ignore

TELEGRAM_TOKEN = "8036375043:AAEpcpOfpQans5BaMpLMtrb0oPBYUtd6JaE"
TELEGRAM_CHAT_ID = "-1003166604153"  # Замените на корректный ID вашей группы/канала Telegram. Для групп ID обычно начинается с -100.
VK_TOKEN = "vk1.a.Do3IzROgiVPPGSjBVw3nFEg2eIAsy7673mBTpwakOxj_qNTtCxEXx8Pa9NS_q7FbDZqVlfecQgofYCYotRguILuXWAYu7DL2gkQocsu7zcRvk3M9R_0jCzzjErAJRLcy_Zx4jEZR87zCFUJvKIvkU_hLmJbfozuPkamZbBaElI1yZ8U3RpRNqMdjkdwm5SdFFS1HqCp7xxLu0EnF4JyVqA"
VK_GROUP_ID = "233089872"

# URL изображений
WELCOME_PHOTOS = [
    "https://raw.githubusercontent.com/tigran420/dermo/5be79081c7a6fa620a49671bf22703d98c6d9020/photo_2025-10-05_16-08-58%20(2).jpg",
    "https://raw.githubusercontent.com/tigran420/dermo/5be79081c7a6fa620a49671bf22703d98c6d9020/photo_2025-10-05_16-08-58%20(3).jpg",
    "https://raw.githubusercontent.com/tigran420/dermo/5be79081c7a6fa620a49671bf22703d98c6d9020/photo_2025-10-05_16-08-58%20(4).jpg",
    "https://raw.githubusercontent.com/tigran420/dermo/5be79081c7a6fa620a49671bf22703d98c6d9020/photo_2025-10-05_16-08-58%20(5).jpg",
    "https://raw.githubusercontent.com/tigran420/dermo/5be79081c7a6fa620a49671bf22703d98c6d9020/photo_2025-10-05_16-08-58%20(6).jpg",
    "https://raw.githubusercontent.com/tigran420/dermo/5be79081c7a6fa620a49671bf22703d98c6d9020/photo_2025-10-05_16-08-58%20(7).jpg",
    "https://raw.githubusercontent.com/tigran420/dermo/5be79081c7a6fa620a49671bf22703d98c6d9020/photo_2025-10-05_16-08-58.jpg",
    "https://raw.githubusercontent.com/tigran420/dermo/5be79081c7a6fa620a49671bf22703d98c6d9020/photo_2025-10-05_16-08-59.jpg",
]

MATERIAL_PHOTOS = {
    "Материалы": "https://raw.githubusercontent.com/Egorinho77/eban-/refs/heads/main/photo_2025-10-11_00-34-48.jpg",
}


def send_telegram_application(application_data):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram bot token or chat ID not configured. Skipping sending application to Telegram group.")
        return

    # Начало текста заявки
    message_text = "📩 Новая заявка:\n\n"

    # Исключаем служебные поля
    exclude_keys = {"current_step", "waiting_for"}

    # Добавляем только полезные данные
    for key, value in application_data.items():
        if key not in exclude_keys and value not in [None, "", "Не указано"]:
            message_text += f"{key}: {value}\n"

    # URL для запроса Telegram API
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    # Формируем тело запроса
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message_text,
        "parse_mode": "HTML",
    }

    # Отправляем заявку
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logging.info(f"✅ Заявка успешно отправлена в Telegram-группу: {response.json()}")
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Ошибка отправки заявки в Telegram-группу: {e}")


from vk_api.utils import get_random_id  # type: ignore

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class Platform(Enum):
    TELEGRAM = "telegram"
    VK = "vk"


# Приветственное сообщение
WELCOME_MESSAGE = (
    "Приветствуем!🤝\n"
    "На связи 2М ФАБРИКА МЕБЕЛИ!\n\n"

    "Мы изготавливаем корпусную и встроенную мебель с 1993 года, по индивидуальным размерам:\n"
    "кухни, шкафы-купе, гардеробные, мебель для ванной и многое другое.\n\n"

    "Собственное производство, работаем без посредников, делаем все сами от замера до установки.\n"
    "Широкий выбор материалов более 1000 расцветок, от ЛДСП до Эмали и фурнитуры (Blum, Hettich, Boyard и др.).\n"
    "Бесплатный замер, доставка и установка по городу.\n\n"

    "Гарантия 24 месяца на всю продукцию!\n"
    "Цены приятно удивят!\n"
    "Рассрочка!!!"
)

# Хранилище данных пользователя
user_data: Dict[int, Dict[str, Any]] = {}


class KeyboardManager:
    @staticmethod
    def get_initial_keyboard(platform: Platform):
        if platform == Platform.TELEGRAM:
            keyboard = [
                [InlineKeyboardButton("Кухня", callback_data="кухня")],
                [InlineKeyboardButton("Шкаф", callback_data="шкаф")],
                [InlineKeyboardButton("Гардеробная", callback_data="гардеробная")],
                [InlineKeyboardButton("Прихожая", callback_data="прихожая")],
                [InlineKeyboardButton("Мебель для ванной", callback_data="ванная")],
                [InlineKeyboardButton("Другая мебель", callback_data="другое")],
                [InlineKeyboardButton("Свяжитесь со мной", callback_data="связаться_со_мной")],
            ]
            return InlineKeyboardMarkup(keyboard)
        else:  # VK
            keyboard = {
                "inline": True,
                "buttons": [
                    [
                        {"action": {"type": "callback", "label": "🍳 Кухня", "payload": "{\"command\": \"кухня\"}"},
                         "color": "primary"},
                        {"action": {"type": "callback", "label": "🚪 Шкаф", "payload": "{\"command\": \"шкаф\"}"},
                         "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "👔 Гардеробная",
                                    "payload": "{\"command\": \"гардеробная\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "🛋 Прихожая",
                                    "payload": "{\"command\": \"прихожая\"}"}, "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "🛁 Мебель для ванной",
                                    "payload": "{\"command\": \"ванная\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "🛋 Другая мебель",
                                    "payload": "{\"command\": \"другое\"}"}, "color": "secondary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "📞 Свяжитесь со мной",
                                    "payload": "{\"command\": \"связаться_со_мной\"}"}, "color": "positive"}
                    ],
                ],
            }
            return json.dumps(keyboard, ensure_ascii=False)

    @staticmethod
    def get_service_keyboard(platform: Platform):
        if platform == Platform.TELEGRAM:
            return None
        else:  # VK
            keyboard = {
                "inline": True,
                "buttons": [
                    [
                        {"action": {"type": "callback", "label": "📏 Замеры",
                                    "payload": "{\"command\": \"услуга_замеры\"}"}, "color": "positive"},
                        {"action": {"type": "callback", "label": "💰 Рассчитать стоимость",
                                    "payload": "{\"command\": \"услуга_стоимость\"}"}, "color": "primary"}
                    ],
                    [
                        {"action": {"type": "callback", "label": "🔙 Назад",
                                    "payload": "{\"command\": \"назад_сроки\"}"}, "color": "negative"}
                    ]
                ],
            }
            return json.dumps(keyboard, ensure_ascii=False)

    @staticmethod
    def get_contact_final_keyboard(platform: Platform):
        if platform == Platform.TELEGRAM:
            keyboard = [[KeyboardButton("🔄 Начать заново")]]
            return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, input_field_placeholder="Выберите действие...")
        else:  # VK
            keyboard = {
                "inline": True,
                "buttons": [
                    [
                        {"action": {"type": "callback", "label": "📞 По телефону",
                                    "payload": "{\"command\": \"по_телефону\"}"}, "color": "positive"},
                        {"action": {"type": "callback", "label": "💬 Сообщение в Telegram",
                                    "payload": "{\"command\": \"сообщение_тг\"}"}, "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "🔄 Начать заново",
                                    "payload": "{\"command\": \"начать_заново\"}"}, "color": "secondary"},
                    ],
                ],
            }
            return json.dumps(keyboard, ensure_ascii=False)

    @staticmethod
    def get_phone_keyboard(platform: Platform):
        if platform == Platform.TELEGRAM:
            keyboard = [[KeyboardButton("📱 Отправить номер", request_contact=True)], [KeyboardButton("Ввести вручную")]]
            return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        else:  # VK
            return None

    @staticmethod
    def get_kitchen_type_keyboard(platform: Platform):
        if platform == Platform.TELEGRAM:
            keyboard = [
                [InlineKeyboardButton("Угловая", callback_data="кухня_угловая")],
                [InlineKeyboardButton("Прямая", callback_data="кухня_прямая")],
                [InlineKeyboardButton("П-образная", callback_data="кухня_п_образная")],
                [InlineKeyboardButton("С островом", callback_data="кухня_остров")],
                [InlineKeyboardButton("↩️ Назад", callback_data="назад_категории")],
            ]
            return InlineKeyboardMarkup(keyboard)
        else:  # VK
            keyboard = {
                "inline": True,
                "buttons": [
                    [
                        {"action": {"type": "callback", "label": "📐 Угловая",
                                    "payload": "{\"command\": \"кухня_угловая\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "📏 Прямая",
                                    "payload": "{\"command\": \"кухня_прямая\"}"}, "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "🔄 П-образная",
                                    "payload": "{\"command\": \"кухня_п_образная\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "🏝 С островом",
                                    "payload": "{\"command\": \"кухня_остров\"}"}, "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "🔙 Назад",
                                    "payload": "{\"command\": \"назад_категории\"}"}, "color": "negative"},
                    ],
                ],
            }
            return json.dumps(keyboard, ensure_ascii=False)

    @staticmethod
    def get_cabinet_type_keyboard(platform: Platform):
        if platform == Platform.TELEGRAM:
            keyboard = [
                [InlineKeyboardButton("Распашной", callback_data="шкаф_распашной")],
                [InlineKeyboardButton("Купе", callback_data="шкаф_купе")],
                [InlineKeyboardButton("↩️ Назад", callback_data="назад_категории")],
            ]
            return InlineKeyboardMarkup(keyboard)
        else:  # VK
            keyboard = {
                "inline": True,
                "buttons": [
                    [
                        {"action": {"type": "callback", "label": "🚪 Распашной",
                                    "payload": "{\"command\": \"шкаф_распашной\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "🚶 Купе", "payload": "{\"command\": \"шкаф_купе\"}"},
                         "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "🔙 Назад",
                                    "payload": "{\"command\": \"назад_категории\"}"}, "color": "negative"},
                    ],
                ],
            }
            return json.dumps(keyboard, ensure_ascii=False)

    @staticmethod
    def get_hallway_type_keyboard(platform: Platform):
        if platform == Platform.TELEGRAM:
            keyboard = [
                [InlineKeyboardButton("Прямая", callback_data="прихожая_прямая")],
                [InlineKeyboardButton("Угловая", callback_data="прихожая_угловая")],
                [InlineKeyboardButton("↩️ Назад", callback_data="назад_категории")],
            ]
            return InlineKeyboardMarkup(keyboard)
        else:  # VK
            keyboard = {
                "inline": True,
                "buttons": [
                    [
                        {"action": {"type": "callback", "label": "📏 Прямая",
                                    "payload": "{\"command\": \"прихожая_прямая\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "📐 Угловая",
                                    "payload": "{\"command\": \"прихожая_угловая\"}"}, "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "🔙 Назад",
                                    "payload": "{\"command\": \"назад_категории\"}"}, "color": "negative"},
                    ],
                ],
            }
            return json.dumps(keyboard, ensure_ascii=False)

    @staticmethod
    def get_bathroom_type_keyboard(platform: Platform):
        if platform == Platform.TELEGRAM:
            keyboard = [
                [InlineKeyboardButton("Тумба под раковину", callback_data="ванная_тумба")],
                [InlineKeyboardButton("Шкаф-пенал", callback_data="ванная_пенал")],
                [InlineKeyboardButton("Зеркало с подсветкой", callback_data="ванная_зеркало")],
                [InlineKeyboardButton("↩️ Назад", callback_data="назад_категории")],
            ]
            return InlineKeyboardMarkup(keyboard)
        else:  # VK
            keyboard = {
                "inline": True,
                "buttons": [
                    [
                        {"action": {"type": "callback", "label": "🚰 Тумба под раковину",
                                    "payload": "{\"command\": \"ванная_тумба\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "🧺 Шкаф-пенал",
                                    "payload": "{\"command\": \"ванная_пенал\"}"}, "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "💡 Зеркало с подсветкой",
                                    "payload": "{\"command\": \"ванная_зеркало\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "🔙 Назад",
                                    "payload": "{\"command\": \"назад_категории\"}"}, "color": "negative"},
                    ],
                ],
            }
            return json.dumps(keyboard, ensure_ascii=False)

    @staticmethod
    def get_size_keyboard(platform: Platform, back_callback: str = "назад_тип"):
        if platform == Platform.TELEGRAM:
            keyboard = [
                [InlineKeyboardButton("Точные", callback_data="размер_точные")],
                [InlineKeyboardButton("Приблизительные", callback_data="размер_приблизительные")],
                [InlineKeyboardButton("Не знаю", callback_data="размер_не_знаю")],
                [InlineKeyboardButton("↩️ Назад", callback_data=back_callback)],
            ]
            return InlineKeyboardMarkup(keyboard)
        else:  # VK
            keyboard = {
                "inline": True,
                "buttons": [
                    [
                        {"action": {"type": "callback", "label": "📏 Точные размеры",
                                    "payload": "{\"command\": \"размер_точные\"}"}, "color": "positive"},
                        {"action": {"type": "callback", "label": "📐 Приблизительные",
                                    "payload": "{\"command\": \"размер_приблизительные\"}"}, "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "❓ Не знаю",
                                    "payload": "{\"command\": \"размер_не_знаю\"}"}, "color": "secondary"},
                        {"action": {"type": "callback", "label": "🔙 Назад",
                                    "payload": f"{{\"command\": \"{back_callback}\"}}"}, "color": "negative"},
                    ],
                ],
            }
            return json.dumps(keyboard, ensure_ascii=False)

    @staticmethod
    def get_approximate_size_keyboard(platform: Platform, back_callback: str = "назад_размер"):
        if platform == Platform.TELEGRAM:
            keyboard = [
                [InlineKeyboardButton("1,5 - 2 м", callback_data="размер_1.5_2")],
                [InlineKeyboardButton("2 - 2,5 м", callback_data="размер_2_2.5")],
                [InlineKeyboardButton("2,5 - 3 м", callback_data="размер_2.5_3")],
                [InlineKeyboardButton("3 - 3,5 м", callback_data="размер_3_3.5")],
                [InlineKeyboardButton("3,5 - 4 м", callback_data="размер_3.5_4")],
                [InlineKeyboardButton("4 - 4,5 м", callback_data="размер_4_4.5")],
                [InlineKeyboardButton("4,5 - 5 м", callback_data="размер_4.5_5")],
                [InlineKeyboardButton("Более 5 м", callback_data="размер_более_5")],
                [InlineKeyboardButton("↩️ Назад", callback_data=back_callback)],
            ]
            return InlineKeyboardMarkup(keyboard)
        else:  # VK
            keyboard = {
                "inline": True,
                "buttons": [
                    [
                        {"action": {"type": "callback", "label": "1,5 - 2 м",
                                    "payload": "{\"command\": \"размер_1.5_2\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "2 - 2,5 м",
                                    "payload": "{\"command\": \"размер_2_2.5\"}"}, "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "2,5 - 3 м",
                                    "payload": "{\"command\": \"размер_2.5_3\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "3 - 3,5 м",
                                    "payload": "{\"command\": \"размер_3_3.5\"}"}, "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "3,5 - 4 м",
                                    "payload": "{\"command\": \"размер_3.5_4\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "4 - 4,5 м",
                                    "payload": "{\"command\": \"размер_4_4.5\"}"}, "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "4,5 - 5 м",
                                    "payload": "{\"command\": \"размер_4.5_5\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "Более 5 м",
                                    "payload": "{\"command\": \"размер_более_5\"}"}, "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "🔙 Назад",
                                    "payload": f"{{\"command\": \"{back_callback}\"}}"}, "color": "negative"},
                    ],
                ],
            }
            return json.dumps(keyboard, ensure_ascii=False)

    @staticmethod
    def get_material_keyboard(platform: Platform):
        if platform == Platform.TELEGRAM:
            keyboard = [
                [InlineKeyboardButton("ЛДСП", callback_data="материал_лдсп")],
                [InlineKeyboardButton("АГТ", callback_data="материал_агт")],
                [InlineKeyboardButton("Эмаль", callback_data="материал_эмаль")],
                [InlineKeyboardButton("Пластик", callback_data="материал_пластик")],
                [InlineKeyboardButton("Акрил", callback_data="материал_акрил")],
                [InlineKeyboardButton("↩️ Назад", callback_data="назад_размер")],
            ]
            return InlineKeyboardMarkup(keyboard)
        else:  # VK
            keyboard = {
                "inline": True,
                "buttons": [
                    [
                        {"action": {"type": "callback", "label": "🌳 ЛДСП",
                                    "payload": "{\"command\": \"материал_лдсп\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "✨ АГТ", "payload": "{\"command\": \"материал_агт\"}"},
                         "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "🎨 Эмаль",
                                    "payload": "{\"command\": \"материал_эмаль\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "🔲 Пластик",
                                    "payload": "{\"command\": \"материал_пластик\"}"}, "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "💎 Акрил",
                                    "payload": "{\"command\": \"материал_акрил\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "🔙 Назад",
                                    "payload": "{\"command\": \"назад_размер\"}"}, "color": "negative"},
                    ],
                ],
            }
            return json.dumps(keyboard, ensure_ascii=False)

    @staticmethod
    def get_hardware_keyboard(platform: Platform):
        if platform == Platform.TELEGRAM:
            keyboard = [
                [InlineKeyboardButton("Эконом", callback_data="фурнитура_эконом")],
                [InlineKeyboardButton("Стандарт", callback_data="фурнитура_стандарт")],
                [InlineKeyboardButton("Премиум", callback_data="фурнитура_премиум")],
                [InlineKeyboardButton("↩️ Назад", callback_data="назад_материал")],
            ]
            return InlineKeyboardMarkup(keyboard)
        else:  # VK
            keyboard = {
                "inline": True,
                "buttons": [
                    [
                        {"action": {"type": "callback", "label": "💰 Эконом",
                                    "payload": "{\"command\": \"фурнитура_эконом\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "💎 Стандарт",
                                    "payload": "{\"command\": \"фурнитура_стандарт\"}"}, "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "👑 Премиум",
                                    "payload": "{\"command\": \"фурнитура_премиум\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "🔙 Назад",
                                    "payload": "{\"command\": \"назад_материал\"}"}, "color": "negative"},
                    ],
                ],
            }
            return json.dumps(keyboard, ensure_ascii=False)

    @staticmethod
    def get_budget_keyboard(platform: Platform, back_callback: str = "назад_предыдущий"):
        if platform == Platform.TELEGRAM:
            keyboard = [
                [InlineKeyboardButton("Эконом - (до 150 тыс руб)", callback_data="бюджет_эконом")],
                [InlineKeyboardButton("Стандарт - (150-300 тыс руб)", callback_data="бюджет_стандарт")],
                [InlineKeyboardButton("Премиум - (от 300 тыс руб)", callback_data="бюджет_премиум")],
                [InlineKeyboardButton("↩️ Назад", callback_data=back_callback)],
            ]
            return InlineKeyboardMarkup(keyboard)
        else:  # VK
            keyboard = {
                "inline": True,
                "buttons": [
                    [
                        {"action": {"type": "callback", "label": "💰 Эконом",
                                    "payload": "{\"command\": \"бюджет_эконом\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "💎 Стандарт",
                                    "payload": "{\"command\": \"бюджет_стандарт\"}"}, "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "👑 Премиум",
                                    "payload": "{\"command\": \"бюджет_премиум\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "🔙 Назад",
                                    "payload": f"{{\"command\": \"{back_callback}\"}}"}, "color": "negative"},
                    ],
                ],
            }
            return json.dumps(keyboard, ensure_ascii=False)

    @staticmethod
    def get_deadline_keyboard(platform: Platform, back_callback: str = "назад_бюджет"):
        if platform == Platform.TELEGRAM:
            keyboard = [
                [InlineKeyboardButton("Этот месяц", callback_data="срок_месяц")],
                [InlineKeyboardButton("1-2 месяца", callback_data="срок_1_2")],
                [InlineKeyboardButton("3 месяца", callback_data="срок_3")],
                [InlineKeyboardButton("Присматриваюсь", callback_data="срок_присмотр")],
                [InlineKeyboardButton("↩️ Назад", callback_data=back_callback)],
            ]
            return InlineKeyboardMarkup(keyboard)
        else:  # VK
            keyboard = {
                "inline": True,
                "buttons": [
                    [
                        {"action": {"type": "callback", "label": "🗓 Этот месяц",
                                    "payload": "{\"command\": \"срок_месяц\"}"}, "color": "primary"},
                        {"action": {"type": "callback", "label": "⏳ 1-2 месяца",
                                    "payload": "{\"command\": \"срок_1_2\"}"}, "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "📅 3 месяца", "payload": "{\"command\": \"срок_3\"}"},
                         "color": "primary"},
                        {"action": {"type": "callback", "label": "👀 Присматриваюсь",
                                    "payload": "{\"command\": \"срок_присмотр\"}"}, "color": "primary"},
                    ],
                    [
                        {"action": {"type": "callback", "label": "🔙 Назад",
                                    "payload": f"{{\"command\": \"{back_callback}\"}}"}, "color": "negative"},
                    ],
                ],
            }
            return json.dumps(keyboard, ensure_ascii=False)


class FurnitureBotCore:
    def __init__(self):
        self.adapters: Dict[Platform, Any] = {}

    def register_adapter(self, platform: Platform, adapter):
        self.adapters[platform] = adapter

    async def send_message(self, platform: Platform, user_id: int, text: str, keyboard=None):
        if platform in self.adapters:
            await self.adapters[platform].send_message(user_id, text, keyboard)

    async def edit_message(self, platform: Platform, user_id: int, message_id: int, text: str, keyboard=None):
        if platform in self.adapters:
            await self.adapters[platform].edit_message(user_id, message_id, text, keyboard)

    def get_user_data(self, user_id: int) -> Dict[str, Any]:
        if user_id not in user_data:
            user_data[user_id] = {}
        return user_data[user_id]

    def clear_user_data(self, user_id: int):
        if user_id in user_data:
            del user_data[user_id]

    async def handle_start(self, platform: Platform, user_id: int):
        self.clear_user_data(user_id)
        await self.send_photo_album(
            platform, user_id, WELCOME_PHOTOS, WELCOME_MESSAGE, KeyboardManager.get_initial_keyboard(platform)
        )

    async def request_service_type(self, platform: Platform, user_id: int, message_id: int = None):
        if platform != Platform.VK:
            return

        text = "📋 **Выберите услугу:**\n\n• 📏 Замеры - наш специалист приедет для точных замеров\n• 💰 Рассчитать стоимость - предварительный расчет стоимости мебели"

        if message_id:
            await self.edit_message(platform, user_id, message_id, text, KeyboardManager.get_service_keyboard(platform))
        else:
            await self.send_message(platform, user_id, text, KeyboardManager.get_service_keyboard(platform))
        self.get_user_data(user_id)["current_step"] = "service_type"

    async def request_name(self, platform: Platform, user_id: int, message_id: int = None):
        text = "👤 **Контактные данные**\n\nПожалуйста, напишите ваше имя:"
        if message_id and platform == Platform.TELEGRAM:
            await self.edit_message(platform, user_id, message_id, text)
        else:
            await self.send_message(platform, user_id, text)
        self.get_user_data(user_id)["waiting_for"] = "name"

    async def request_phone(self, platform: Platform, user_id: int):
        text = (
            f"👤 **Имя принято!**\n\n"
            f"📱 **Телефон**\n\n"
            f"Пожалуйста, отправьте ваш номер телефона:"
        )

        keyboard = KeyboardManager.get_phone_keyboard(platform) if platform == Platform.TELEGRAM else None

        await self.send_message(
            platform,
            user_id,
            text,
            keyboard
        )
        self.get_user_data(user_id)["waiting_for"] = "phone"

    async def handle_callback(self, platform: Platform, user_id: int, data: str, message_id: int = None):
        user_data_local = self.get_user_data(user_id)

        # Обработка кнопки "Назад"
        if data.startswith("назад_"):
            await self.handle_back_button(platform, user_id, data, message_id)
            return

        # Обработка выбора услуги (только для VK)
        if data.startswith("услуга_"):
            if data == "услуга_замеры":
                user_data_local["service_type"] = "Замеры"
                await self.request_name(platform, user_id, message_id)
                return
            elif data == "услуга_стоимость":
                user_data_local["service_type"] = "Рассчитать стоимость"
                user_data_local["note"] = "❗️СМОТРИ VK - нужна стоимость"
                send_telegram_application(user_data_local)

                cost_message = (
                    "💰 **Расчет стоимости**\n\n"
                    "Спасибо за интерес к нашим услугам! "
                    "Наш администратор уже уведомлен и скоро свяжется с вами "
                    "для предварительного расчета стоимости.\n\n"
                    "Мы учтем все ваши пожелания и предоставим "
                    "подробную информацию о стоимости выбранной мебели."
                )
                await self.send_or_edit_message(platform, user_id, message_id, cost_message)

                await asyncio.sleep(2)
                await self.send_message(
                    platform, user_id,
                    "Хотите оформить ещё одну заявку на замеры или выбрать другую мебель?",
                    KeyboardManager.get_initial_keyboard(platform)
                )
                self.clear_user_data(user_id)
                return

        # Обработка кнопки "Свяжитесь со мной"
        if data == "связаться_со_мной":
            user_data_local["category"] = "связаться_со_мной"
            if platform == Platform.VK:
                await self.request_service_type(platform, user_id, message_id)
            else:
                await self.request_name(platform, user_id, message_id)
            return

        # Обработка выбора категории
        if data in ["кухня", "шкаф", "гардеробная", "прихожая", "ванная", "другое"]:
            user_data_local["category"] = data

            if data == "кухня":
                user_data_local["current_step"] = "kitchen_type"
                await self.send_or_edit_message(
                    platform, user_id, message_id, "🏠 **Кухня**\n\nВыберите тип кухни:",
                    KeyboardManager.get_kitchen_type_keyboard(platform)
                )
            elif data == "шкаф":
                user_data_local["current_step"] = "cabinet_type"
                await self.send_or_edit_message(
                    platform, user_id, message_id, "🚪 **Шкаф**\n\nВыберите тип шкафа:",
                    KeyboardManager.get_cabinet_type_keyboard(platform)
                )
            elif data == "гардеробная":
                user_data_local["current_step"] = "size"
                await self.send_or_edit_message(
                    platform, user_id, message_id, "👔 **Гардеробная**\n\nКакие у вас размеры?",
                    KeyboardManager.get_size_keyboard(platform, back_callback="назад_категории")
                )
            elif data == "прихожая":
                user_data_local["current_step"] = "hallway_type"
                await self.send_or_edit_message(
                    platform, user_id, message_id, "🛋 **Прихожая**\n\nВыберите тип прихожей:",
                    KeyboardManager.get_hallway_type_keyboard(platform)
                )
            elif data == "ванная":
                user_data_local["current_step"] = "bathroom_type"
                await self.send_or_edit_message(
                    platform, user_id, message_id, "🛁 **Мебель для ванной**\n\nВыберите тип мебели для ванной:",
                    KeyboardManager.get_bathroom_type_keyboard(platform)
                )
            elif data == "другое":
                user_data_local["current_step"] = "other_furniture_text"
                await self.send_or_edit_message(platform, user_id, message_id,
                                                "🛋 **Другая мебель**\n\nПожалуйста, опишите, какая мебель вас интересует:")
                user_data_local["waiting_for"] = "other_furniture_description"

        # Обработка сценария КУХНЯ
        elif data.startswith("кухня_"):
            if data == "кухня_угловая":
                user_data_local["kitchen_type"] = "Угловая"
            elif data == "кухня_прямая":
                user_data_local["kitchen_type"] = "Прямая"
            elif data == "кухня_п_образная":
                user_data_local["kitchen_type"] = "П-образная"
            elif data == "кухня_остров":
                user_data_local["kitchen_type"] = "С островом"
            user_data_local["current_step"] = "size"
            await self.send_or_edit_message(
                platform, user_id, message_id, "📏 **Размеры**\n\nКакие у вас размеры?",
                KeyboardManager.get_size_keyboard(platform, back_callback="назад_тип")
            )

        # Обработка сценария ПРИХОЖАЯ
        elif data.startswith("прихожая_"):
            if data == "прихожая_прямая":
                user_data_local["hallway_type"] = "Прямая"
            elif data == "прихожая_угловая":
                user_data_local["hallway_type"] = "Угловая"
            user_data_local["current_step"] = "size"
            await self.send_or_edit_message(
                platform, user_id, message_id, "📏 **Размеры**\n\nКакие у вас размеры?",
                KeyboardManager.get_size_keyboard(platform, back_callback="назад_тип")
            )

        # Обработка сценария ВАННАЯ
        elif data.startswith("ванная_"):
            if data == "ванная_тумба":
                user_data_local["bathroom_type"] = "Тумба под раковину"
            elif data == "ванная_пенал":
                user_data_local["bathroom_type"] = "Шкаф-пенал"
            elif data == "ванная_зеркало":
                user_data_local["bathroom_type"] = "Зеркало с подсветкой"
            user_data_local["current_step"] = "size"
            await self.send_or_edit_message(
                platform, user_id, message_id, "📏 **Размеры**\n\nКакие у вас размеры?",
                KeyboardManager.get_size_keyboard(platform, back_callback="назад_тип")
            )

        # Обработка сценария ШКАФ
        elif data.startswith("шкаф_"):
            if data == "шкаф_распашной":
                user_data_local["cabinet_type"] = "Распашной"
            elif data == "шкаф_купе":
                user_data_local["cabinet_type"] = "Купе"
            user_data_local["current_step"] = "size"
            await self.send_or_edit_message(
                platform, user_id, message_id, "📏 **Размеры**\n\nКакие у вас размеры?",
                KeyboardManager.get_size_keyboard(platform, back_callback="назад_тип")
            )

        # Обработка размеров (общее для всех категорий)
        elif data.startswith("размер_"):
            if data == "размер_точные":
                user_data_local["size"] = "Точные"
                user_data_local["waiting_for"] = "exact_size"
                await self.send_or_edit_message(
                    platform, user_id, message_id,
                    "📏 **Точные размеры**\n\nПожалуйста, напишите точные размеры (например: 2.5м х 1.8м):"
                )
                return
            elif data == "размер_приблизительные":
                user_data_local["size"] = "Приблизительные"
                await self.send_or_edit_message(
                    platform, user_id, message_id,
                    "📐 **Приблизительные размеры**\n\nВыберите диапазон размеров:",
                    KeyboardManager.get_approximate_size_keyboard(platform, back_callback="назад_размер")
                )
                return
            elif data == "размер_не_знаю":
                user_data_local["size"] = "Не знаю"
            elif data in ["размер_1.5_2", "размер_2_2.5", "размер_2.5_3", "размер_3_3.5",
                          "размер_3.5_4", "размер_4_4.5", "размер_4.5_5", "размер_более_5"]:
                size_map = {
                    "размер_1.5_2": "1,5 - 2 м",
                    "размер_2_2.5": "2 - 2,5 м",
                    "размер_2.5_3": "2,5 - 3 м",
                    "размер_3_3.5": "3 - 3,5 м",
                    "размер_3.5_4": "3,5 - 4 м",
                    "размер_4_4.5": "4 - 4,5 м",
                    "размер_4.5_5": "4,5 - 5 м",
                    "размер_более_5": "Более 5 м"
                }
                user_data_local["approximate_size"] = size_map[data]

            # Определяем следующий шаг в зависимости от категории
            category = user_data_local.get("category", "")
            if category == "кухня":
                user_data_local["current_step"] = "material"
                await self.send_material_options(platform, user_id, message_id)
            elif category in ["шкаф", "гардеробная", "прихожая", "ванная", "другое"]:
                user_data_local["current_step"] = "budget"
                await self.send_or_edit_message(
                    platform, user_id, message_id, "💰 **Бюджет**\n\nВыберите бюджет:",
                    KeyboardManager.get_budget_keyboard(platform, back_callback="назад_размер")
                )

        elif data.startswith("материал_"):
            if data == "материал_лдсп":
                user_data_local["material"] = "ЛДСП"
            elif data == "материал_агт":
                user_data_local["material"] = "АГТ"
            elif data == "материал_эмаль":
                user_data_local["material"] = "Эмаль"
            elif data == "материал_пластик":
                user_data_local["material"] = "Пластик"
            elif data == "материал_акрил":
                user_data_local["material"] = "Акрил"

            material_key = data.replace("материал_", "")
            photo_url = MATERIAL_PHOTOS.get(material_key)
            if photo_url:
                await self.send_photo_album(platform, user_id, [photo_url],
                                            f"Подробнее о материалах: {user_data_local['material']}")

            user_data_local["current_step"] = "hardware"
            await self.send_message(platform, user_id, "🔧 **Фурнитура**\n\nВыберите класс фурнитуры:",
                                    KeyboardManager.get_hardware_keyboard(platform))

        elif data.startswith("фурнитура_"):
            if data == "фурнитура_эконом":
                user_data_local["hardware"] = "Эконом"
            elif data == "фурнитура_стандарт":
                user_data_local["hardware"] = "Стандарт"
            elif data == "фурнитура_премиум":
                user_data_local["hardware"] = "Премиум"
            user_data_local["current_step"] = "budget"
            await self.send_or_edit_message(
                platform, user_id, message_id, "💰 **Бюджет**\n\nВыберите бюджет:",
                KeyboardManager.get_budget_keyboard(platform, back_callback="назад_фурнитура")
            )

        elif data.startswith("бюджет_"):
            if data == "бюджет_эконом":
                user_data_local["budget"] = "Эконом"
            elif data == "бюджет_стандарт":
                user_data_local["budget"] = "Стандарт"
            elif data == "бюджет_премиум":
                user_data_local["budget"] = "Премиум"
            user_data_local["current_step"] = "deadline"
            await self.send_or_edit_message(
                platform, user_id, message_id, "📅 **Сроки заказа**\n\nВыберите сроки:",
                KeyboardManager.get_deadline_keyboard(platform, back_callback="назад_бюджет")
            )

        # Обработка сроков заказа
        elif data.startswith("срок_"):
            if data == "срок_месяц":
                user_data_local["deadline"] = "Этот месяц"
            elif data == "срок_1_2":
                user_data_local["deadline"] = "1-2 месяца"
            elif data == "срок_3":
                user_data_local["deadline"] = "3 месяца"
            elif data == "срок_присмотр":
                user_data_local["deadline"] = "Присматриваюсь"

            if platform == Platform.VK:
                await self.request_service_type(platform, user_id, message_id)
            else:
                await self.request_name(platform, user_id, message_id)

        # Обработка дополнительных кнопок для VK
        elif data == "ввести_телефон":
            await self.send_or_edit_message(platform, user_id, message_id,
                                            "📱 **Введите номер телефона:**\n\nФормат: +7XXXXXXXXXX или 8XXXXXXXXXX")
            user_data_local["waiting_for"] = "phone"
        elif data == "консультация":
            await self.send_or_edit_message(
                platform, user_id, message_id,
                "📞 **Консультация**\n\nДля консультации свяжитесь с нами:\n\n💬 Телеграм: @max_lap555\n📱 WhatsApp: +79063405556",
                KeyboardManager.get_contact_final_keyboard(platform),
            )
        elif data == "написать_тг":
            await self.send_or_edit_message(
                platform, user_id, message_id,
                "💬 **Написать в Telegram**\n\nПерейдите в Telegram: @max_lap555\nИли напишите на номер: +79063405556",
                KeyboardManager.get_contact_final_keyboard(platform),
            )
        elif data == "по_телефону":
            await self.send_or_edit_message(
                platform, user_id, message_id,
                "📞 **Связь по телефону**\n\nПозвоните нам по номеру:\n📱 +79063405556\n\nМы доступны:\n• Пн-Пт: 9:00-18:00\n• Сб: 10:00-16:00",
                KeyboardManager.get_contact_final_keyboard(platform),
            )
        elif data == "сообщение_тг":
            await self.send_or_edit_message(
                platform, user_id, message_id,
                "💬 **Сообщение в Telegram**\n\nНапишите нам в Telegram:\n👤 @max_lap555\n\nИли перейдите по ссылке:\nhttps://t.me/max_lap555",
                KeyboardManager.get_contact_final_keyboard(platform),
            )
        elif data == "начать_заново":
            self.clear_user_data(user_id)
            await self.handle_start(platform, user_id)

    async def send_material_options(self, platform: Platform, user_id: int, message_id: int = None):
        await self.send_or_edit_message(platform, user_id, message_id, "🎨 **Материал фасадов**\n\nВыберите материал:",
                                        KeyboardManager.get_material_keyboard(platform))
        for material_name, photo_url in MATERIAL_PHOTOS.items():
            material_display_name = material_name.upper()
            await self.send_photo_album(platform, user_id, [photo_url], f"{material_display_name}")

    async def send_or_edit_message(self, platform: Platform, user_id: int, message_id: int, text: str, keyboard=None):
        if message_id and platform == Platform.TELEGRAM:
            await self.edit_message(platform, user_id, message_id, text, keyboard)
        else:
            await self.send_message(platform, user_id, text, keyboard)

    async def send_photo_album(self, platform: Platform, user_id: int, photo_urls: list, text: str, keyboard=None):
        if platform in self.adapters:
            await self.adapters[platform].send_photo_album(user_id, photo_urls, text, keyboard)

    async def handle_back_button(self, platform: Platform, user_id: int, data: str, message_id: int = None):
        back_step = data.replace("назад_", "")
        user_data_local = self.get_user_data(user_id)

        if back_step == "услуга":
            await self.send_or_edit_message(
                platform, user_id, message_id, "📅 **Сроки заказа**\n\nВыберите сроки:",
                KeyboardManager.get_deadline_keyboard(platform, back_callback="назад_бюджет")
            )
        elif back_step == "категории":
            self.clear_user_data(user_id)
            await self.send_or_edit_message(platform, user_id, message_id, WELCOME_MESSAGE,
                                            KeyboardManager.get_initial_keyboard(platform))
        elif back_step == "тип":
            category = user_data_local.get("category", "")
            if category == "кухня":
                await self.send_or_edit_message(platform, user_id, message_id, "🏠 **Кухня**\n\nВыберите тип кухни:",
                                                KeyboardManager.get_kitchen_type_keyboard(platform))
            elif category == "шкаф":
                await self.send_or_edit_message(platform, user_id, message_id, "🚪 **Шкаф**\n\nВыберите тип шкафа:",
                                                KeyboardManager.get_cabinet_type_keyboard(platform))
            elif category == "прихожая":
                await self.send_or_edit_message(platform, user_id, message_id,
                                                "🛋 **Прихожая**\n\nВыберите тип прихожей:",
                                                KeyboardManager.get_hallway_type_keyboard(platform))
            elif category == "ванная":
                await self.send_or_edit_message(platform, user_id, message_id,
                                                "🛁 **Мебель для ванной**\n\nВыберите тип мебели для ванной:",
                                                KeyboardManager.get_bathroom_type_keyboard(platform))
        elif back_step == "размер":
            category = user_data_local.get("category", "")
            if category == "кухня":
                user_data_local["current_step"] = "kitchen_type"
                await self.send_or_edit_message(platform, user_id, message_id, "🏠 **Кухня**\n\nВыберите тип кухни:",
                                                KeyboardManager.get_kitchen_type_keyboard(platform))
            elif category == "гардеробная":
                user_data_local["current_step"] = "size"
                await self.send_or_edit_message(platform, user_id, message_id,
                                                "👔 **Гардеробная**\n\nКакие у вас размеры?",
                                                KeyboardManager.get_size_keyboard(platform,
                                                                                  back_callback="назад_категории"))
            elif category == "прихожая":
                user_data_local["current_step"] = "hallway_type"
                await self.send_or_edit_message(platform, user_id, message_id,
                                                "🛋 **Прихожая**\n\nВыберите тип прихожей:",
                                                KeyboardManager.get_hallway_type_keyboard(platform))
            elif category == "ванная":
                user_data_local["current_step"] = "bathroom_type"
                await self.send_or_edit_message(platform, user_id, message_id,
                                                "🛁 **Мебель для ванной**\n\nВыберите тип мебели для ванной:",
                                                KeyboardManager.get_bathroom_type_keyboard(platform))
            elif category == "шкаф":
                user_data_local["current_step"] = "cabinet_type"
                await self.send_or_edit_message(platform, user_id, message_id, "🚪 **Шкаф**\n\nВыберите тип шкафа:",
                                                KeyboardManager.get_cabinet_type_keyboard(platform))
            elif category == "другое":
                user_data_local["current_step"] = "other_furniture_text"
                await self.send_or_edit_message(platform, user_id, message_id,
                                                "🛋 **Другая мебель**\n\nПожалуйста, опишите, какая мебель вас интересует:")
                user_data_local["waiting_for"] = "other_furniture_description"
        elif back_step == "материал":
            await self.send_material_options(platform, user_id, message_id)
        elif back_step == "фурнитура":
            await self.send_or_edit_message(platform, user_id, message_id,
                                            "🔧 **Фурнитура**\n\nВыберите класс фурнитуры:",
                                            KeyboardManager.get_hardware_keyboard(platform))
        elif back_step == "бюджет":
            category = user_data_local.get("category", "")
            if category == "кухня":
                await self.send_or_edit_message(platform, user_id, message_id,
                                                "🔧 **Фурнитура**\n\nВыберите класс фурнитуры:",
                                                KeyboardManager.get_hardware_keyboard(platform))
            elif category in ["шкаф", "гардеробная", "прихожая", "ванная", "другое"]:
                user_data_local["current_step"] = "size"
                await self.send_or_edit_message(platform, user_id, message_id, "📏 **Размеры**\n\nКакие у вас размеры?",
                                                KeyboardManager.get_size_keyboard(platform, back_callback="назад_тип"))
        elif back_step == "сроки":
            user_data_local["current_step"] = "deadline"
            await self.send_or_edit_message(platform, user_id, message_id, "📅 **Сроки заказа**\n\nВыберите сроки:",
                                            KeyboardManager.get_deadline_keyboard(platform,
                                                                                  back_callback="назад_бюджет"))
        elif back_step == "другое":
            await self.send_or_edit_message(platform, user_id, message_id, WELCOME_MESSAGE,
                                            KeyboardManager.get_initial_keyboard(platform))

    async def handle_text_message(self, platform: Platform, user_id: int, text: str):
        user_data_local = self.get_user_data(user_id)

        normalized_text = text.lower().strip()
        start_commands = ["/start", "start", "начать", "старт", "go", "меню"]

        if normalized_text in start_commands:
            await self.handle_start(platform, user_id)
            return

        # Если ожидаем точные размеры
        if user_data_local.get("waiting_for") == "exact_size":
            user_data_local["exact_size"] = text
            user_data_local["waiting_for"] = None

            category = user_data_local.get("category", "")
            if category == "кухня":
                user_data_local["current_step"] = "material"
                await self.send_material_options(platform, user_id)
            elif category in ["шкаф", "гардеробная", "прихожая", "ванная", "другое"]:
                user_data_local["current_step"] = "budget"
                await self.send_or_edit_message(
                    platform, user_id, None, "💰 **Бюджет**\n\nВыберите бюджет:",
                    KeyboardManager.get_budget_keyboard(platform, back_callback="назад_размер")
                )
            return

        # Если ожидаем имя
        if user_data_local.get("waiting_for") == "name":
            user_data_local["name"] = text
            user_data_local["waiting_for"] = None
            await self.request_phone(platform, user_id)
            return

        # Если ожидаем телефон
        if user_data_local.get("waiting_for") == "phone":
            if len(text) >= 10 and all(char.isdigit() or char in ["+", "(", ")", "-", " "] for char in text):
                user_data_local["phone"] = text
                user_data_local["waiting_for"] = None
                await self.send_final_summary(platform, user_id)
            else:
                await self.send_message(
                    platform, user_id,
                    "❌ Некорректный формат номера. Пожалуйста, введите номер телефона в формате +7XXXXXXXXXX или 8XXXXXXXXXX:",
                )
            return

        # Если ожидаем описание другой мебели
        if user_data_local.get("waiting_for") == "other_furniture_description":
            user_data_local["other_furniture_description"] = text
            user_data_local["waiting_for"] = None
            user_data_local["current_step"] = "size"
            await self.send_or_edit_message(platform, user_id, None, "📏 **Размеры**\n\nКакие у вас размеры?",
                                            KeyboardManager.get_size_keyboard(platform, back_callback="назад_другое"))
            return

        # Если сообщение не является командой и не ожидается ввод
        await self.send_message(
            platform, user_id,
            "Извините, я не понял ваше сообщение. Пожалуйста, используйте кнопки или начните заново /start.",
            KeyboardManager.get_initial_keyboard(platform)
        )

    async def send_final_summary(self, platform: Platform, user_id: int):
        user_data_local = self.get_user_data(user_id)

        summary = "✅ **Ваша заявка принята!**\n\n"

        category = user_data_local.get("category", "Не указано")
        if category == "связаться_со_мной":
            summary += "Мы свяжемся с вами в ближайшее время.\n\n"
        else:
            summary += f"**Детали заказа {category.capitalize()}:**\n"

        if category == "кухня":
            summary += f"• Тип кухни: {user_data_local.get('kitchen_type', 'Не указано')}\n"
            summary += f"• Размеры: {user_data_local.get('size', 'Не указано')}\n"
            if user_data_local.get('size') == "Точные" and user_data_local.get('exact_size'):
                summary += f"• Точные размеры: {user_data_local.get('exact_size', 'Не указано')}\n"
            elif user_data_local.get('size') == "Приблизительные" and user_data_local.get('approximate_size'):
                summary += f"• Приблизительные размеры: {user_data_local.get('approximate_size', 'Не указано')}\n"
            summary += f"• Материал: {user_data_local.get('material', 'Не указано')}\n"
            summary += f"• Фурнитура: {user_data_local.get('hardware', 'Не указано')}\n"
        elif category == "шкаф":
            summary += f"• Тип шкафа: {user_data_local.get('cabinet_type', 'Не указано')}\n"
            summary += f"• Размеры: {user_data_local.get('size', 'Не указано')}\n"
            if user_data_local.get('size') == "Точные" and user_data_local.get('exact_size'):
                summary += f"• Точные размеры: {user_data_local.get('exact_size', 'Не указано')}\n"
            elif user_data_local.get('size') == "Приблизительные" and user_data_local.get('approximate_size'):
                summary += f"• Приблизительные размеры: {user_data_local.get('approximate_size', 'Не указано')}\n"
        elif category == "гардеробная":
            summary += f"• Размеры: {user_data_local.get('size', 'Не указано')}\n"
            if user_data_local.get('size') == "Точные" and user_data_local.get('exact_size'):
                summary += f"• Точные размеры: {user_data_local.get('exact_size', 'Не указано')}\n"
            elif user_data_local.get('size') == "Приблизительные" and user_data_local.get('approximate_size'):
                summary += f"• Приблизительные размеры: {user_data_local.get('approximate_size', 'Не указано')}\n"
        elif category == "прихожая":
            summary += f"• Тип прихожей: {user_data_local.get('hallway_type', 'Не указано')}\n"
            summary += f"• Размеры: {user_data_local.get('size', 'Не указано')}\n"
            if user_data_local.get('size') == "Точные" and user_data_local.get('exact_size'):
                summary += f"• Точные размеры: {user_data_local.get('exact_size', 'Не указано')}\n"
            elif user_data_local.get('size') == "Приблизительные" and user_data_local.get('approximate_size'):
                summary += f"• Приблизительные размеры: {user_data_local.get('approximate_size', 'Не указано')}\n"
        elif category == "ванная":
            summary += f"• Тип мебели для ванной: {user_data_local.get('bathroom_type', 'Не указано')}\n"
            summary += f"• Размеры: {user_data_local.get('size', 'Не указано')}\n"
            if user_data_local.get('size') == "Точные" and user_data_local.get('exact_size'):
                summary += f"• Точные размеры: {user_data_local.get('exact_size', 'Не указано')}\n"
            elif user_data_local.get('size') == "Приблизительные" and user_data_local.get('approximate_size'):
                summary += f"• Приблизительные размеры: {user_data_local.get('approximate_size', 'Не указано')}\n"
        elif category == "другое":
            summary += f"• Описание мебели: {user_data_local.get('other_furniture_description', 'Не указано')}\n"
            summary += f"• Размеры: {user_data_local.get('size', 'Не указано')}\n"
            if user_data_local.get('size') == "Точные" and user_data_local.get('exact_size'):
                summary += f"• Точные размеры: {user_data_local.get('exact_size', 'Не указано')}\n"
            elif user_data_local.get('size') == "Приблизительные" and user_data_local.get('approximate_size'):
                summary += f"• Приблизительные размеры: {user_data_local.get('approximate_size', 'Не указано')}\n"

        if category != "связаться_со_мной":
            summary += f"• Бюджет: {user_data_local.get('budget', 'Не указано')}\n"
            summary += f"• Сроки: {user_data_local.get('deadline', 'Не указано')}\n"

        summary += f"• Имя: {user_data_local.get('name', 'Не указано')}\n"
        summary += f"• Телефон: {user_data_local.get('phone', 'Не указано')}\n"
        summary += f"• Услуга: {user_data_local.get('service_type', 'Не указано')}\n\n"

        summary += "📞 Свяжитесь с нами:\n"
        summary += "💬 Телеграм: @max_lap555\n"
        summary += "📱 WhatsApp: +79063405556\n\n"
        summary += "Спасибо за вашу заявку! Мы свяжемся с вами в ближайшее время."

        await self.send_message(platform, user_id, summary, KeyboardManager.get_contact_final_keyboard(platform))

        send_telegram_application(user_data_local)
        self.clear_user_data(user_id)


# Остальной код остается без изменений (TelegramAdapter, VKAdapter, main функция)
# [TelegramAdapter и VKAdapter классы остаются такими же как в предыдущем коде]
# [main функция также остается без изменений]

# Адаптер для Telegram
class TelegramAdapter:
    def __init__(self, token: str, bot_core: FurnitureBotCore):
        self.bot_core = bot_core
        self.bot = Bot(token=token)
        self.application = ApplicationBuilder().token(token).build()
        self.setup_handlers()

    def setup_handlers(self):
        self.application.add_handler(CommandHandler("start", self.handle_start))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        self.application.add_handler(MessageHandler(filters.CONTACT, self.handle_contact))

    async def handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id if update.effective_user else update.effective_chat.id
        await self.bot_core.handle_start(Platform.TELEGRAM, user_id)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        if query:
            await query.answer()
            user_id = update.effective_user.id if update.effective_user else update.effective_chat.id
            await self.bot_core.handle_callback(Platform.TELEGRAM, user_id, query.data, query.message.message_id)

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id if update.effective_user else update.effective_chat.id
        text = update.message.text if update.message else ""
        await self.bot_core.handle_text_message(Platform.TELEGRAM, user_id, text)

    async def handle_contact(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id if update.effective_user else update.effective_chat.id
        user_data_local = self.bot_core.get_user_data(user_id)
        if user_data_local.get("waiting_for") == "phone":
            contact = update.message.contact
            if contact:
                phone_number = contact.phone_number
                user_data_local["phone"] = phone_number
                user_data_local["waiting_for"] = None
                await self.bot_core.send_final_summary(Platform.TELEGRAM, user_id)

    async def send_photo_album(self, user_id: int, photo_urls: list, text: str, keyboard=None):
        try:
            if not photo_urls:
                await self.send_message(user_id, text, keyboard)
                return

            if len(photo_urls) == 1:
                await self.bot.send_photo(chat_id=user_id, photo=photo_urls[0], caption=text)
            else:
                media_group = []
                for i, photo_url in enumerate(photo_urls[:10]):
                    if i == 0:
                        media_group.append(InputMediaPhoto(media=photo_url, caption=text))
                    else:
                        media_group.append(InputMediaPhoto(media=photo_url))
                await self.bot.send_media_group(chat_id=user_id, media=media_group)

            if keyboard:
                await self.send_message(user_id, "Выберите категорию:", keyboard)

        except TelegramError as e:
            logger.error(f"Ошибка отправки фото(альбома) в Telegram: {e}")
            await self.send_message(user_id, text, keyboard)
        except Exception as e:
            logger.error(f"Unexpected error in send_photo_album: {e}")
            await self.send_message(user_id, text, keyboard)

    async def send_message(self, user_id: int, text: str, keyboard=None):
        try:
            await self.bot.send_message(chat_id=user_id, text=text, reply_markup=keyboard)
        except TelegramError as e:
            logger.error(f"Telegram send_message error: {e}. Text: {text}")
        except Exception as e:
            logger.error(f"Unexpected error in send_message: {e}. Text: {text}")

    async def edit_message(self, user_id: int, message_id: Optional[int], text: str, keyboard=None):
        if message_id is None:
            await self.send_message(user_id, text, keyboard)
            return

        try:
            await self.bot.edit_message_text(chat_id=user_id, message_id=message_id, text=text, reply_markup=keyboard)
        except TelegramError as e:
            logger.error(f"Telegram edit_message error: {e}. Falling back to send_message.")
            await self.send_message(user_id, text, keyboard)
        except Exception as e:
            logger.error(f"Unexpected error in edit_message: {e}")
            await self.send_message(user_id, text, keyboard)

    def run(self):
        logger.info("Запуск Telegram бота...")
        self.application.run_polling()


# Адаптер для VK
class VKAdapter:
    def __init__(self, token: str, group_id: str, bot_core: FurnitureBotCore):
        self.bot_core = bot_core
        self.vk_session = vk_api.VkApi(token=token)
        self.vk = self.vk_session.get_api()
        self.group_id = group_id
        self.photo_cache: Dict[str, str] = {}
        self.start_background_preload()

    def start_background_preload(self):
        try:
            all_photo_urls = list(WELCOME_PHOTOS) + list(MATERIAL_PHOTOS.values())
            if not all_photo_urls:
                logger.info("[VK] Нет фото для предзагрузки")
                return

            logger.info(f"[VK] Начинаю предзагрузку {len(all_photo_urls)} фото...")
            threading.Thread(
                target=lambda: asyncio.run(self.preload_photos(all_photo_urls)),
                daemon=True,
                name="VKPhotoPreload"
            ).start()

        except Exception as e:
            logger.error(f"[VK] Ошибка запуска предзагрузки: {e}")

    async def preload_photos(self, photo_urls: List[str]):
        total = len(photo_urls)
        logger.info(f"[VK] Предзагрузка {total} фото...")

        for index, photo_url in enumerate(photo_urls, 1):
            try:
                attachment = await self.upload_photo(photo_url)
                if attachment:
                    logger.info(f"[VK] Загружено {index}/{total} → {attachment}")
                else:
                    logger.warning(f"[VK] Не удалось загрузить {index}/{total}: {photo_url}")
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"[VK] Ошибка при предзагрузке {photo_url}: {e}")

        logger.info(f"[VK] Предзагрузка завершена! Загружено {len(self.photo_cache)}/{total} фото")

    async def upload_photo(self, photo_url: str) -> Optional[str]:
        if photo_url in self.photo_cache:
            cached_attachment = self.photo_cache[photo_url]
            logger.debug(f"[VK] Использую кэшированное фото: {cached_attachment}")
            return cached_attachment

        try:
            logger.info(f"[VK] Загрузка фото из URL: {photo_url}")
            response = requests.get(photo_url, timeout=30)
            response.raise_for_status()

            upload_url = self.vk.photos.getMessagesUploadServer()["upload_url"]
            files = {"photo": ("photo.jpg", response.content, "image/jpeg")}
            upload_response = requests.post(upload_url, files=files, timeout=30)
            upload_response.raise_for_status()
            upload_data = upload_response.json()

            save_response = self.vk.photos.saveMessagesPhoto(
                server=upload_data["server"],
                photo=upload_data["photo"],
                hash=upload_data["hash"]
            )

            if save_response:
                photo = save_response[0]
                attachment = f"photo{photo['owner_id']}_{photo['id']}"
                self.photo_cache[photo_url] = attachment
                logger.info(f"[VK] Фото успешно загружено и закэшировано: {attachment}")
                return attachment
            else:
                logger.error("[VK] Ошибка сохранения фото")
                return None

        except Exception as e:
            logger.error(f"[VK] Ошибка загрузки фото: {e}")
            return None

    async def send_photo_album(self, user_id: int, photo_urls: list, text: str, keyboard=None):
        try:
            attachments = []
            for photo_url in photo_urls[:10]:
                attachment = await self.upload_photo(photo_url)
                if attachment:
                    attachments.append(attachment)

            params = {
                "user_id": user_id,
                "message": text,
                "random_id": get_random_id(),
                "dont_parse_links": 1
            }

            if attachments:
                params["attachment"] = ",".join(attachments)
                logger.info(f"[VK] Отправка альбома с {len(attachments)} фото")

            if keyboard:
                params["keyboard"] = keyboard

            result = self.vk.messages.send(**params)
            logger.info(f"[VK] Фотоальбом отправлен! ID: {result}")
            return result

        except Exception as e:
            logger.error(f"[VK] Ошибка отправки фотоальбома: {e}")
            await self.send_message(user_id, text, keyboard)

    def run(self):
        logger.info("Запуск VK бота через Long Poll...")
        try:
            longpoll = VkBotLongPoll(self.vk_session, self.group_id)
            logger.info("✓ Long Poll подключен успешно!")
            logger.info(f"✓ VK бот готов! В кэше предзагружено {len(self.photo_cache)} фото")

            for event in longpoll.listen():
                logger.info(f"VK: Получено событие типа: {event.type}")
                if event.type == VkBotEventType.MESSAGE_NEW and not event.from_chat:
                    self.handle_message(event)
                elif event.type == VkBotEventType.MESSAGE_EVENT:
                    self.handle_callback(event)
                else:
                    logger.info(f"VK: Необработанный тип события: {event.type}")

        except Exception as e:
            logger.error(f"Ошибка VK бота: {e}")
            import traceback
            logger.error(f"Детали: {traceback.format_exc()}")

    def run_with_restart(self):
        """Запускает VK бота с автоматическим перезапуском при ошибках и защитой от дубликатов"""
        import threading

        if hasattr(self, "_is_running") and self._is_running:
            logger.warning("⚠️ VK бот уже запущен — второй экземпляр не стартует.")
            return

        self._is_running = True
        logger.info("✅ VK бот запускается с автоматическим перезапуском...")

        while True:
            try:
                self.run()
            except Exception as e:
                msg = str(e)
                if "Rate limit" in msg:
                    logger.error(f"⚠️ VK API лимит! Ждём 60 секунд перед повтором...")
                    time.sleep(60)
                else:
                    logger.error(f"❌ VK бот упал с ошибкой: {msg}")
                    logger.info("Перезапуск VK бота через 10 секунд...")
                    time.sleep(10)
            finally:
                # если поток был принудительно остановлен
                if threading.main_thread().is_alive() is False:
                    logger.info("🧹 Основной поток завершён, VK бот останавливается.")
                    break

    def handle_message(self, event):
        try:
            user_id = event.obj.message["from_id"]
            text = event.obj.message["text"]
            logger.info(f"VK: Сообщение от {user_id}: '{text}'")
            threading.Thread(target=lambda: asyncio.run(self.process_message(user_id, text))).start()

        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")

    def handle_callback(self, event):
        try:
            logger.info(f"VK: Callback событие получено!")
            user_id = event.obj.user_id
            payload = event.obj.payload
            logger.info(f"VK: Callback от пользователя {user_id}")
            logger.info(f"VK: Payload: {payload}")

            if isinstance(payload, dict):
                command = payload.get("command", "")
            elif isinstance(payload, str):
                try:
                    payload_dict = json.loads(payload)
                    command = payload_dict.get("command", "")
                except:
                    command = payload
            else:
                command = str(payload)

            logger.info(f"VK: Извлеченная команда: '{command}'")

            self.vk.messages.sendMessageEventAnswer(
                event_id=event.obj.event_id,
                user_id=user_id,
                peer_id=event.obj.peer_id,
                event_data=json.dumps({"type": "show_snackbar", "text": "Обрабатываю..."}),
            )

            logger.info("VK: Ответ на callback отправлен")
            threading.Thread(target=lambda: asyncio.run(self.process_callback(user_id, command))).start()

        except Exception as e:
            logger.error(f"Ошибка обработки callback: {e}")
            import traceback
            logger.error(f"Детали: {traceback.format_exc()}")

    async def process_message(self, user_id: int, text: str):
        try:
            normalized_text = text.lower().strip()
            if normalized_text in ["/start", "start", "начать", "меню"]:
                await self.bot_core.handle_start(Platform.VK, user_id)
            else:
                await self.bot_core.handle_text_message(Platform.VK, user_id, text)
        except Exception as e:
            logger.error(f"Ошибка process_message: {e}")

    async def process_callback(self, user_id: int, command: str):
        try:
            logger.info(f"VK: Обработка callback команды: '{command}'")
            await self.bot_core.handle_callback(Platform.VK, user_id, command)
        except Exception as e:
            logger.error(f"Ошибка process_callback: {e}")
            import traceback
            logger.error(f"Детали: {traceback.format_exc()}")

    async def send_message(self, user_id: int, text: str, keyboard=None):
        try:
            logger.info(f"VK: Отправка сообщения пользователю {user_id}")
            logger.info(f"VK: Текст: {text}")
            params = {"user_id": user_id, "message": text, "random_id": get_random_id(), "dont_parse_links": 1}

            if keyboard:
                logger.info("VK: Добавляю клавиатуру")
                params["keyboard"] = keyboard

                try:
                    if isinstance(keyboard, str):
                        keyboard_obj = json.loads(keyboard)
                    else:
                        keyboard_obj = keyboard
                    logger.info(
                        f"VK: Кнопки: {[btn['action']['label'] for row in keyboard_obj['buttons'] for btn in row]}")
                except Exception as e:
                    logger.error(f"VK: Ошибка логирования клавиатуры: {e}")

            result = self.vk.messages.send(**params)
            logger.info(f"VK: Сообщение отправлено! ID: {result}")
            return result

        except Exception as e:
            logger.error(f"VK: Ошибка отправки: {e}")
            import traceback
            logger.error(f"VK: Детали: {traceback.format_exc()}")

    async def edit_message(self, user_id: int, message_id: int, text: str, keyboard=None):
        await self.send_message(user_id, text, keyboard)


def main():
    logger.info("Запуск мультиплатформенного бота...")
    bot_core = FurnitureBotCore()

    telegram_adapter = TelegramAdapter(TELEGRAM_TOKEN, bot_core)
    vk_adapter = VKAdapter(VK_TOKEN, VK_GROUP_ID, bot_core)

    bot_core.register_adapter(Platform.TELEGRAM, telegram_adapter)
    bot_core.register_adapter(Platform.VK, vk_adapter)

    def run_vk():
        """Запуск VK бота с автоматическим перезапуском"""
        while True:
            try:
                logger.info("Запуск VK бота через Long Poll...")
                vk_adapter.run()
            except Exception as e:
                logger.error(f"VK бот упал с ошибкой: {e}")
                logger.info("Перезапуск VK бота через 10 секунд...")
                time.sleep(10)

    def run_telegram():
        """Запуск Telegram бота с автоматическим перезапуском"""
        while True:
            try:
                logger.info("Запуск Telegram бота...")
                telegram_adapter.run()
            except Exception as e:
                logger.error(f"Telegram бот упал с ошибкой: {e}")
                logger.info("Перезапуск Telegram бота через 10 секунд...")
                time.sleep(10)

    # Запускаем оба бота в отдельных потоках с автоматическим перезапуском
    vk_thread = threading.Thread(target=run_vk, daemon=True)
    telegram_thread = threading.Thread(target=run_telegram, daemon=True)

    vk_thread.start()
    telegram_thread.start()

    logger.info("✅ Оба бота запущены в режиме автоматического перезапуска!")
    logger.info("📱 VK бот работает в отдельном потоке")
    logger.info("📱 Telegram бот работает в отдельном потоке")
    logger.info("🔄 Боты автоматически перезапустятся при любых ошибках")

    # Главный поток ждет завершения (которого никогда не будет)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("\n🛑 Получен сигнал прерывания. Остановка ботов...")


if __name__ == "__main__":
    main()
