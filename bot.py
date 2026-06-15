import asyncio
import logging
import re
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Импортируем наши функции для БД из соседнего файла
from database import init_db, add_appointment

logging.basicConfig(level=logging.INFO)

# Роутер для обработки событий
router = Router()

# ID Администратора (ЗАМЕНИ НА СВОЙ TELEGRAM ID)
ADMIN_ID = 123456789  # Напиши @getmyid_bot, чтобы узнать свой ID


# --- FSM СОСТОЯНИЯ ---
class Appointment(StatesGroup):
    reason = State()
    datetime = State()
    name = State()
    phone = State()
    confirmation = State()  # Новый шаг: подтверждение


# --- ГЛОБАЛЬНАЯ ОТМЕНА ---
@router.message(Command("cancel"))
@router.message(F.text.lower() == "отмена")
async def cmd_cancel(message: Message, state: FSMContext):
    """Позволяет прервать запись в любой момент."""
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("Действие отменено. Вы можете начать заново командой /start.",
                         reply_markup=ReplyKeyboardRemove())


# --- ШАГ 1: СТАРТ ---
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Земельный участок"), KeyboardButton(text="Документы и справки")],
            [KeyboardButton(text="Льготы и выплаты"), KeyboardButton(text="Жилищные вопросы")],
            [KeyboardButton(text="Прочее")],
            [KeyboardButton(text="Отмена")]  # Добавили кнопку отмены
        ],
        resize_keyboard=True
    )
    welcome_text = (
        "Добро пожаловать в приём Акимата Каракестекского округа!\n"
        "Пожалуйста, выберите причину вашего обращения:"
    )
    await message.answer(welcome_text, reply_markup=keyboard)
    await state.set_state(Appointment.reason)


# --- ШАГ 2: ПРИЧИНА ---
@router.message(Appointment.reason, F.text)
async def process_reason(message: Message, state: FSMContext):
    await state.update_data(reason=message.text)
    await message.answer(
        "Укажите удобную для вас дату и время приёма в формате ДД.ММ.ГГГГ ЧЧ:ММ\n"
        "(например, 25.01.2025 14:30):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(Appointment.datetime)


# --- ШАГ 3: ДАТА И ВРЕМЯ (С ВАЛИДАЦИЕЙ) ---
@router.message(Appointment.datetime, F.text)
async def process_datetime(message: Message, state: FSMContext):
    # Пытаемся проверить, правильно ли введена дата
    try:
        valid_date = datetime.strptime(message.text, "%d.%m.%Y %H:%M")
        # Проверяем, не ввел ли пользователь дату из прошлого
        if valid_date < datetime.now():
            await message.answer("Эта дата уже прошла! Пожалуйста, введите будущую дату и время:")
            return
    except ValueError:
        await message.answer("Ошибка формата! Пожалуйста, введите дату строго как в примере: 25.01.2025 14:30")
        return

    await state.update_data(datetime=message.text)
    await message.answer("Как вас зовут? (ФИО)")
    await state.set_state(Appointment.name)


# --- ШАГ 4: ИМЯ ---
@router.message(Appointment.name, F.text)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Укажите ваш номер телефона (начиная с +7 или 8):")
    await state.set_state(Appointment.phone)


# --- ШАГ 5: ТЕЛЕФОН (С ВАЛИДАЦИЕЙ) И ПОДТВЕРЖДЕНИЕ ---
@router.message(Appointment.phone, F.text)
async def process_phone(message: Message, state: FSMContext):
    # Простая проверка: очищаем от пробелов и тире, проверяем длину
    phone_clean = re.sub(r'\D', '', message.text)
    if len(phone_clean) < 10:
        await message.answer("Кажется, в номере ошибка. Пожалуйста, введите корректный номер телефона:")
        return

    await state.update_data(phone=message.text)
    data = await state.get_data()

    # Инлайн клавиатура для подтверждения
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Всё верно, отправить", callback_data="confirm_yes")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="confirm_no")]
    ])

    summary = (
        "Пожалуйста, проверьте ваши данные перед отправкой:\n\n"
        f"📋 <b>Причина:</b> {data['reason']}\n"
        f"📅 <b>Дата и время:</b> {data['datetime']}\n"
        f"👤 <b>ФИО:</b> {data['name']}\n"
        f"📞 <b>Телефон:</b> {data['phone']}"
    )

    # Отправляем с HTML-парсером для жирного шрифта
    await message.answer(summary, reply_markup=confirm_kb, parse_mode="HTML")
    await state.set_state(Appointment.confirmation)


# --- ШАГ 6: ОБРАБОТКА ПОДТВЕРЖДЕНИЯ ---
@router.callback_query(Appointment.confirmation)
async def process_confirmation(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if callback.data == "confirm_yes":
        data = await state.get_data()
        username = f"@{callback.from_user.username}" if callback.from_user.username else "Нет юзернейма"

        # 1. Сохраняем в базу данных
        await add_appointment(
            user_id=callback.from_user.id,
            username=username,
            reason=data['reason'],
            dt=data['datetime'],
            name=data['name'],
            phone=data['phone']
        )

        # 2. Уведомляем администратора (в Акимат)
        admin_text = (
            "🚨 <b>НОВАЯ ЗАЯВКА НА ПРИЁМ!</b>\n\n"
            f"📋 <b>Причина:</b> {data['reason']}\n"
            f"📅 <b>Время:</b> {data['datetime']}\n"
            f"👤 <b>Заявитель:</b> {data['name']} ({username})\n"
            f"📞 <b>Телефон:</b> {data['phone']}"
        )
        try:
            await bot.send_message(chat_id=1120709802, text=admin_text, parse_mode="HTML")
        except Exception as e:
            logging.error(f"Не удалось отправить админу: {e}")

        # 3. Отвечаем пользователю
        await callback.message.edit_text("✅ Ваша заявка успешно отправлена! Мы свяжемся с вами.", parse_mode="HTML")

    elif callback.data == "confirm_no":
        await callback.message.edit_text("❌ Заявка отменена. Напишите /start, чтобы начать заново.")

    await state.clear()


# --- ЗАПУСК БОТА ---
async def main():
    # Замени на свой токен
    BOT_TOKEN = "8719675974:AAGZ8DWuUhS4tA68sF_DW0gRbwHEjYLCYvs"

    # Инициализация базы данных
    await init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())