import asyncio
import logging
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

logging.basicConfig(level=logging.INFO)

router = Router()


class Appointment(StatesGroup):
    reason = State()  # Шаг 1: Выбор причины
    datetime = State()  # Шаг 2: Ввод даты и времени
    name = State()  # Шаг 3: Ввод имени
    phone = State()  # Шаг 4: Ввод телефона


# --- ШАГ 1: Обработка команды /start ---
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    # Создаем Reply-клавиатуру с вариантами причин обращения
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Земельный участок"), KeyboardButton(text="Документы и справки")],
            [KeyboardButton(text="Льготы и выплаты"), KeyboardButton(text="Жилищные вопросы")],
            [KeyboardButton(text="Прочее")]
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите причину из списка..."
    )

    welcome_text = (
        "Добро пожаловать в приём Акимата Каракестекского округа!\n"
        "Я помогу вам записаться на приём и передам вашу заявку ответственному специалисту.\n"
        "Пожалуйста, начнём с выбора причины вашего обращения.\n"
        "Выберите причину вашего обращения:"
    )

    await message.answer(welcome_text, reply_markup=keyboard)
    # Переводим пользователя в состояние ожидания причины
    await state.set_state(Appointment.reason)


# --- ШАГ 2: Обработка выбора причины ---
@router.message(Appointment.reason, F.text)
async def process_reason(message: Message, state: FSMContext):
    await state.update_data(reason=message.text)

    await message.answer(
        "Укажите удобную для вас дату и время приёма (например, 25.01.2025, 14:30):",
        reply_markup=ReplyKeyboardRemove()
    )
    # Переводим в состояние ожидания даты и времени
    await state.set_state(Appointment.datetime)


# --- ШАГ 3: Обработка ввода даты и времени ---
@router.message(Appointment.datetime, F.text)
async def process_datetime(message: Message, state: FSMContext):
    # Сохраняем дату и время
    await state.update_data(datetime=message.text)

    # Запрашиваем имя
    await message.answer("Как вас зовут?")
    # Переводим в состояние ожидания имени
    await state.set_state(Appointment.name)


# --- ШАГ 4: Обработка ввода имени ---
@router.message(Appointment.name, F.text)
async def process_name(message: Message, state: FSMContext):
    # Сохраняем имя
    await state.update_data(name=message.text)

    # Запрашиваем телефон
    await message.answer("Укажите ваш номер телефона:")
    # Переводим в состояние ожидания телефона
    await state.set_state(Appointment.phone)


# --- ШАГ 5: Обработка ввода номера телефона и завершение ---
@router.message(Appointment.phone, F.text)
async def process_phone(message: Message, state: FSMContext):
    # Сохраняем номер телефона
    await state.update_data(phone=message.text)

    # Получаем все собранные данные
    data = await state.get_data()

    # Формируем итоговое сообщение
    summary_text = (
        "Спасибо!\n"
        "Ваша заявка принята. Вот ваши данные:\n"
        f"Причина обращения: {data['reason']}\n"
        f"Удобное время: {data['datetime']}\n"
        f"Имя: {data['name']}\n"
        f"Телефон: {data['phone']}\n"
        "Мы свяжемся с вами в ближайшее время для подтверждения записи на приём."
    )

    # Отправляем итог пользователю
    await message.answer(summary_text)

    # Очищаем состояние (завершаем FSM)
    await state.clear()


# --- Точка входа в приложение ---
async def main():
    # Замените на токен вашего бота
    BOT_TOKEN = "8719675974:AAGZ8DWuUhS4tA68sF_DW0gRbwHEjYLCYvs"

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    # Подключаем роутер к диспетчеру
    dp.include_router(router)

    # Пропускаем накопившиеся апдейты и запускаем polling
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())