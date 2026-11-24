import os

import random

import asyncio

import logging

from aiogram import Bot, Dispatcher, types, F

from aiogram.filters import Command

from aiogram.fsm.context import FSMContext

from aiogram.fsm.state import State, StatesGroup

from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from google import genai

from google.genai import types as genai_types

from pydantic import BaseModel, Field

from database import (

    init_db, get_user, update_user, get_setting, set_setting,

    register_group, get_all_users, get_all_groups, get_stats_data

)

 

BOT_TOKEN = "8835996385:AAFbYgX6Jc-PRnfEsBPoX040FLh0Uu6OL1c"

GEMINI_API_KEY = "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"

ADMIN_ID = "6921885296", "0"

 

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)

dp = Dispatcher()

client = genai.Client(api_key=GEMINI_API_KEY)

 

GIFTS = {

    "choco": ("🍫 Молочный шоколад", 30, 8),

    "tea": ("🧋 Бабл-ти", 60, 18),

    "plush": ("🧸 Плюшевый котик", 150, 45),

    "ring": ("💍 Серебряное колечко", 350, 110),

}

 

class AdminStates(StatesGroup):

    waiting_broadcast_pm = State()

    waiting_broadcast_groups = State()

    waiting_channel = State()

 

class TsundereReply(BaseModel):

    reply: str = Field(description="Ответ персонажа с РП-действиями в звёздочках *действие*")

    affection_change: int = Field(description="Изменение симпатии: строго от -3 до +2 за сообщение игрока")

 

def main_menu() -> types.ReplyKeyboardMarkup:

    kb = ReplyKeyboardBuilder()

    kb.button(text="📊 Профиль")

    kb.button(text="🎮 Мини-игра")

    kb.button(text="🎁 Магазин")

    kb.button(text="🔄 Сброс")

    kb.adjust(2, 2)

    return kb.as_markup(resize_keyboard=True)

 

def get_personality_prompt(affection: int) -> str:

    base = (

        "Ты — девушка-цундере в текстовой РП-игре. Отвечай на русском языке, коротко, живо и эмоционально. "

        "Обязательно используй РП-действия в звёздочках (например: *скрестила руки*, *отвернулась, густо покраснев*). "

        "Оцени сообщение игрока и верни affection_change: +1 или +2 (только если игрок реально милый, заботится или смешит), "

        "0 (если обычный разговор) или от -1 до -3 (если грубит или тупит). Доверие заслужить очень трудно!\n"

    )

    if affection <= 100:

        stage = f"Симпатия: {affection}/500 (Стадия 1: Злая хамка). Ты грубая, язвительная, обзывай игрока дураком (без матов), огрызайся."

    elif affection <= 250:

        stage = f"Симпатия: {affection}/500 (Стадия 2: Ворчливая цундере). Грубишь по привычке, но на комплименты сильно смущаешься, заикаешься ('Ч-чего?!'), краснеешь."

    elif affection <= 400:

        stage = f"Симпатия: {affection}/500 (Стадия 3: Скрытая симпатия). Тебе нравится игрок, но гордость мешает признаться. Заботишься под видом критики."

    else:

        stage = f"Симпатия: {affection}/500 (Стадия 4: Влюблённая). Общаешься нежно и тепло, лишь изредка мило дуешься по старой привычке."

    return base + stage

 

async def check_subscription(user_id: int) -> bool:

    if user_id == ADMIN_ID or get_setting("sub_required") != "1":

        return True

    channel = get_setting("sub_channel")

    if not channel:

        return True

    try:

        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)

        return member.status in ("member", "administrator", "creator")

    except Exception:

        return True

 

async def send_sub_prompt(message: types.Message):

    link = get_setting("sub_link") or "https://t.me"

    kb = InlineKeyboardBuilder()

    kb.button(text="📢 Подписаться на канал", url=link)

    kb.button(text="✅ Я подписался", callback_data="check_sub")

    kb.adjust(1)

    await message.answer("*скрестила руки*\nЭй, бака! Я не буду с тобой говорить, пока не подпишешься на канал!", reply_markup=kb.as_markup())

 

@dp.callback_query(F.data == "check_sub")

async def cb_check_sub(callback: types.CallbackQuery):

    if await check_subscription(callback.from_user.id):

        await callback.message.delete()

        await callback.message.answer("*фыркнула* Ладно, вижу подписку. Можешь писать, дурак.", reply_markup=main_menu())

    else:

        await callback.answer("Ты всё ещё не подписан!", show_alert=True)

 

@dp.message(Command("setphoto"), F.photo)

async def cmd_setphoto(message: types.Message):

    if message.from_user.id != ADMIN_ID:

        return

    set_setting("start_photo", message.photo[-1].file_id)

    await message.answer("✅ Новое фото персонажа сохранено!")

 

@dp.message(Command("start"))

async def cmd_start(message: types.Message):

    if message.chat.type in ("group", "supergroup"):

        register_group(message.chat.id, message.chat.title or "Группа")

    get_user(message.from_user.id)

    text = "*недовольно хмыкнула и скрестила руки*\nЧего уставился? Думаешь, я сразу растаю от пары слов? Как бы не так, бака!"

    photo_id = get_setting("start_photo")

    kb = main_menu() if message.chat.type == "private" else None

    if photo_id:

        await message.answer_photo(photo=photo_id, caption=text, reply_markup=kb)

    else:

        await message.answer(text, reply_markup=kb)

 

@dp.message(Command("stats"))

@dp.message(F.text == "📊 Профиль")

async def cmd_stats(message: types.Message):

    if not await check_subscription(message.from_user.id):

        return await send_sub_prompt(message)

    affection, coins, _ = get_user(message.from_user.id)

    status = "Злая хамка 💢" if affection <= 100 else "Ворчливая цундере 😳" if affection <= 250 else "Скрывает чувства 💓" if affection <= 400 else "По уши влюблена 💖"

    await message.answer(f"❤️ **Симпатия:** {affection}/500\n🪙 **Цун-коины:** {coins}\n🎭 **Статус:** {status}", parse_mode="Markdown")

 

@dp.message(Command("reset"))

@dp.message(F.text == "🔄 Сброс")

async def cmd_reset(message: types.Message):

    update_user(message.from_user.id, 10, 20, [])

    await message.answer("*закатила глаза* Ладно, забыли всё. Начинаем с нуля, дурак. (Симпатия: 10/500, Коины: 20 🪙)")

@dp.message(Command("game"))

@dp.message(F.text == "🎮 Мини-игра")

async def cmd_game(message: types.Message):

    if not await check_subscription(message.from_user.id):

        return await send_sub_prompt(message)

    kb = InlineKeyboardBuilder()

    kb.button(text="🪨 Камень", callback_data="rps_rock")

    kb.button(text="✂️ Ножницы", callback_data="rps_scissors")

    kb.button(text="📄 Бумага", callback_data="rps_paper")

    kb.adjust(3)

    await message.answer("*усмехнулась* Сыграем в «Камень, ножницы, бумага»? Победишь — дам 15 🪙. Выбирай!", reply_markup=kb.as_markup())

 

@dp.callback_query(F.data.startswith("rps_"))

async def process_rps(callback: types.CallbackQuery):

    user_choice = callback.data.split("_")[1]

    bot_choice = random.choice(["rock", "scissors", "paper"])

    names = {"rock": "🪨 Камень", "scissors": "✂️ Ножницы", "paper": "📄 Бумага"}

    affection, coins, history = get_user(callback.from_user.id)

 

    if user_choice == bot_choice:

        result = f"Мы оба выбрали {names[bot_choice]}.\n*фыркнула* Ничья! Повторяешь за мной, дурак?"

    elif (user_choice == "rock" and bot_choice == "scissors") or (user_choice == "scissors" and bot_choice == "paper") or (user_choice == "paper" and bot_choice == "rock"):

        coins += 15

        update_user(callback.from_user.id, affection, coins, history)

        result = f"Ты: {names[user_choice]} | Я: {names[bot_choice]}\n*покраснела от злости* Ч-чего?! Ты подглядывал! На свои 15 🪙, жулик! (Баланс: {coins} 🪙)"

    else:

        result = f"Ты: {names[user_choice]} | Я: {names[bot_choice]}\n*самодовольно ухмыльнулась* Ха! Проиграл! Учись, бака~"

    await callback.message.edit_text(result)

    await callback.answer()

 

@dp.message(Command("shop"))

@dp.message(F.text == "🎁 Магазин")

async def cmd_shop(message: types.Message):

    if not await check_subscription(message.from_user.id):

        return await send_sub_prompt(message)

    _, coins, _ = get_user(message.from_user.id)

    kb = InlineKeyboardBuilder()

    for key, (name, price, bonus) in GIFTS.items():

        kb.button(text=f"{name} — {price} 🪙 (+{bonus} ❤️)", callback_data=f"buy_{key}")

    kb.adjust(1)

    await message.answer(f"*отвернулась* Я-я вовсе не жду подарков! Просто мимо проходила... (У тебя: {coins} 🪙)", reply_markup=kb.as_markup())

 

@dp.callback_query(F.data.startswith("buy_"))

async def process_buy(callback: types.CallbackQuery):

    gift_key = callback.data.split("_")[1]

    name, price, bonus = GIFTS[gift_key]

    affection, coins, history = get_user(callback.from_user.id)

    if coins < price:

        return await callback.answer("Не хватает Цун-коинов! Поиграй в мини-игру или пообщайся со мной.", show_alert=True)

    coins -= price

    affection = min(500, affection + bonus)

    history.append({"role": "user", "text": f"*дарит тебе {name}*"})

    update_user(callback.from_user.id, affection, coins, history)

    await callback.message.edit_text(

        f"🎁 Ты подарил: **{name}**\n\n*взяла подарок и густо покраснела* Д-дурак... Зачем ты тратишься?! Н-но спасибо...\n\n📈 Симпатия +{bonus} ({affection}/500) | Остаток: {coins} 🪙",

        parse_mode="Markdown"

    )

    await callback.answer()

 

def admin_keyboard():

    sub_on = get_setting("sub_required") == "1"

    kb = InlineKeyboardBuilder()

    kb.button(text="📊 Статистика и активность", callback_data="adm_stats")

    kb.button(text="✉️ Рассылка в ЛС", callback_data="adm_cast_pm")

    kb.button(text="👥 Рассылка в группы", callback_data="adm_cast_grp")

    kb.button(text="🟢 ОП: ВКЛ" if sub_on else "🔴 ОП: ВЫКЛ", callback_data="adm_toggle_sub")

    kb.button(text="📢 Настроить канал ОП", callback_data="adm_set_channel")

    kb.adjust(1, 2, 2)

    return kb.as_markup()

 

@dp.message(Command("admin"))

async def cmd_admin(message: types.Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:

        return

    await state.clear()

    await message.answer("⚙️ **Панель администратора**", reply_markup=admin_keyboard(), parse_mode="Markdown")

 

@dp.callback_query(F.data == "adm_stats")

async def adm_stats(callback: types.CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        return

    total, act_24, act_7, groups = get_stats_data()

    text = f"📊 **Статистика:**\n👤 Всего: **{total}**\n🔥 За 24ч: **{act_24}**\n📅 За 7д: **{act_7}**\n💤 Неактивны: **{max(0, total - act_7)}**\n👥 Групп: **{groups}**"

    await callback.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="Markdown")

    await callback.answer()

 

@dp.callback_query(F.data == "adm_toggle_sub")

async def adm_toggle_sub(callback: types.CallbackQuery):

    if callback.from_user.id != ADMIN_ID:

        return

    set_setting("sub_required", "0" if get_setting("sub_required") == "1" else "1")

    await callback.message.edit_reply_markup(reply_markup=admin_keyboard())

    await callback.answer("Статус ОП изменён!")

 

@dp.callback_query(F.data == "adm_set_channel")

async def adm_set_channel(callback: types.CallbackQuery, state: FSMContext):

    if callback.from_user.id != ADMIN_ID:

        return

    await state.set_state(AdminStates.waiting_channel)

    await callback.message.answer("Отправь через пробел:\n`@канал https://t.me`\n(Бот должен быть админом канала. Отмена: /cancel)")

    await callback.answer()

 

@dp.message(AdminStates.waiting_channel)

async def save_channel(message: types.Message, state: FSMContext):

    if message.text == "/cancel":

        await state.clear()

        return await message.answer("Отменено.")

    parts = message.text.split()

    if len(parts) < 2:

        return await message.answer("Нужно через пробел: `@канал https://t.me`")

    set_setting("sub_channel", parts[0])

    set_setting("sub_link", parts[1])

    await state.clear()

    await message.answer(f"✅ Канал ОП сохранён: {parts[0]}", reply_markup=admin_keyboard())

 

@dp.callback_query(F.data.in_(["adm_cast_pm", "adm_cast_grp"]))

async def adm_cast_start(callback: types.CallbackQuery, state: FSMContext):

    if callback.from_user.id != ADMIN_ID:

        return

    await state.set_state(AdminStates.waiting_broadcast_pm if callback.data == "adm_cast_pm" else AdminStates.waiting_broadcast_groups)

    await callback.message.answer("Отправь пост (текст или фото) для рассылки. Отмена: /cancel")

    await callback.answer()

 

@dp.message(AdminStates.waiting_broadcast_pm)

@dp.message(AdminStates.waiting_broadcast_groups)

async def execute_broadcast(message: types.Message, state: FSMContext):

    if message.text == "/cancel":

        await state.clear()

        return await message.answer("Отменено.")

    targets = get_all_users() if await state.get_state() == AdminStates.waiting_broadcast_pm else get_all_groups()

    await state.clear()

    sent, failed = 0, 0

    msg = await message.answer(f"⏳ Рассылка по {len(targets)} чатам...")

    for cid in targets:

        try:

            await message.copy_to(chat_id=cid)

            sent += 1

            await asyncio.sleep(0.05)

        except Exception:

            failed += 1

    await msg.edit_text(f"✅ Готово! Доставлено: **{sent}**, ошибок: **{failed}**", parse_mode="Markdown")

 

@dp.message()

async def chat_handler(message: types.Message):

    if message.chat.type in ("group", "supergroup"):

        register_group(message.chat.id, message.chat.title or "Группа")

        bot_info = await bot.get_me()

        is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id

        is_mentioned = message.text and f"@{bot_info.username}" in message.text

        if not (is_reply or is_mentioned):

            return

    if not message.text:

        return

    if not await check_subscription(message.from_user.id):

        return await send_sub_prompt(message)

 

    user_id = message.from_user.id

    affection, coins, history = get_user(user_id)

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")

 

    contents = [genai_types.Content(role=m["role"], parts=[genai_types.Part.from_text(text=m["text"])]) for m in history]

    contents.append(genai_types.Content(role="user", parts=[genai_types.Part.from_text(text=message.text)]))

 

    try:

        response = client.models.generate_content(

            model="gemini-2.5-flash",

            contents=contents,

            config=genai_types.GenerateContentConfig(

                system_instruction=get_personality_prompt(affection),

                response_mime_type="application/json",

                response_schema=TsundereReply,

                temperature=0.9,

            ),

        )

        data = TsundereReply.model_validate_json(response.text)

        change = max(-3, min(2, data.affection_change))

        new_affection = max(0, min(500, affection + change))

        earned = 5 if change > 0 else 0

        history.append({"role": "user", "text": message.text})

        history.append({"role": "model", "text": data.reply})

        update_user(user_id, new_affection, coins + earned, history)

 

        badge = f"\n\n📈 *Симпатия +{change} ({new_affection}/500) | +{earned} 🪙*" if change > 0 else f"\n\n📉 *Симпатия {change} ({new_affection}/500)*" if change < 0 else ""

        await message.reply(data.reply + badge, parse_mode="Markdown")

    except Exception as e:

        logging.error(f"Gemini error: {e}")

        await message.answer("*отвернулась* Тц, голова разболелась... Повтори позже.")

 

async def main():

    init_db()

    await dp.start_polling(bot)

 

if __name__ == "__main__":

    asyncio.run(main())
