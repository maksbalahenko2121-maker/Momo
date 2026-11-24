import os, random, asyncio, sqlite3, json, time, logging

from aiogram import Bot, Dispatcher, types, F

from aiogram.filters import Command

from aiogram.fsm.context import FSMContext

from aiogram.fsm.state import State, StatesGroup

from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from google import genai

from google.genai import types as gtypes

from pydantic import BaseModel, Field

 

BOT_TOKEN = os.getenv("BOT_TOKEN") or "8835996385:AAHXGJfH4TewLUFIDNXrBtdomKT1plizfcg"

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or "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"

ADMIN_ID = int(os.getenv("ADMIN_ID") or "6921885296")

 

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)

async def fake_me():

    bot_id = int(BOT_TOKEN.split(":")[0]) if ":" in BOT_TOKEN else 0

    return types.User(id=bot_id, is_bot=True, first_name="TsundereBot", username="my_bot")

bot.me = fake_me

dp = Dispatcher()

ai = genai.Client(api_key=GEMINI_API_KEY)

DB = "bot.db"

 

GIFTS = {"choco": ("🍫 Шоколадка", 30, 8), "tea": ("🧋 Бабл-ти", 60, 18), "plush": ("🧸 Плюшевый кот", 150, 45), "ring": ("💍 Колечко", 350, 110)}

 

class AdminState(StatesGroup):

    cast_pm = State()

    cast_grp = State()

    set_ch = State()

 

class ReplySchema(BaseModel):

    reply: str = Field(description="Ответ цундере с РП-действиями в *звёздочках*")

    affection_change: int = Field(description="Оценка фразы игрока: строго от -3 до +2")

 

def db_init():

    with sqlite3.connect(DB) as c:

        c.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, aff INTEGER DEFAULT 10, coins INTEGER DEFAULT 20, hist TEXT DEFAULT '[]', last INTEGER DEFAULT 0)")

        c.execute("CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY)")

        c.execute("CREATE TABLE IF NOT EXISTS cfg (k TEXT PRIMARY KEY, v TEXT)")

        for k, v in [("photo", ""), ("sub_on", "0"), ("sub_ch", ""), ("sub_url", "")]:

            c.execute("INSERT OR IGNORE INTO cfg VALUES (?, ?)", (k, v))

 

def get_cfg(k: str) -> str:

    with sqlite3.connect(DB) as c:

        row = c.execute("SELECT v FROM cfg WHERE k=?", (k,)).fetchone()

        return row[0] if row else ""

 

def set_cfg(k: str, v: str):

    with sqlite3.connect(DB) as c:

        c.execute("INSERT OR REPLACE INTO cfg VALUES (?, ?)", (k, v))

 

def get_user(uid: int):

    now = int(time.time())

    with sqlite3.connect(DB) as c:

        row = c.execute("SELECT aff, coins, hist FROM users WHERE id=?", (uid,)).fetchone()

        if not row:

            c.execute("INSERT INTO users VALUES (?, 10, 20, '[]', ?)", (uid, now))

            return 10, 20, []

        aff, coins, h_str = row

        c.execute("UPDATE users SET last=? WHERE id=?", (now, uid))

        return aff, coins, json.loads(h_str)

 

def save_user(uid: int, aff: int, coins: int, hist: list):

    with sqlite3.connect(DB) as c:

        c.execute("UPDATE users SET aff=?, coins=?, hist=?, last=? WHERE id=?", (max(0, min(500, aff)), max(0, coins), json.dumps(hist[-15:], ensure_ascii=False), int(time.time()), uid))

 

def menu_kb():

    kb = ReplyKeyboardBuilder()

    for b in ["📊 Профиль", "🎮 Мини-игра", "🎁 Магазин", "🔄 Сброс"]: kb.button(text=b)

    kb.adjust(2, 2)

    return kb.as_markup(resize_keyboard=True)

 

async def is_sub(uid: int) -> bool:

    if uid == ADMIN_ID or get_cfg("sub_on") != "1" or not get_cfg("sub_ch"): return True

    try: return (await bot.get_chat_member(get_cfg("sub_ch"), uid)).status in ("member", "administrator", "creator")

    except Exception: return True

 

async def ask_sub(msg: types.Message):

    kb = InlineKeyboardBuilder()

    kb.button(text="📢 Подписаться", url=get_cfg("sub_url") or "https://t.me")

    kb.button(text="✅ Проверить", callback_data="chk_sub")

    kb.adjust(1)

    await msg.answer("*скрестила руки* Эй, бака! Сначала подпишись на канал, потом поговорим!", reply_markup=kb.as_markup())

 

@dp.callback_query(F.data == "chk_sub")

async def cb_sub(cb: types.CallbackQuery):

    if await is_sub(cb.from_user.id):

        await cb.message.delete()

        await cb.message.answer("*фыркнула* Ладно, вижу подписку. Пиши, дурак.", reply_markup=menu_kb())

    else: await cb.answer("Ты ещё не подписался!", show_alert=True)

 

@dp.message(Command("setphoto"), F.photo)

async def cmd_photo(msg: types.Message):

    if msg.from_user.id == ADMIN_ID:

        set_cfg("photo", msg.photo.pop().file_id)

        await msg.answer("✅ Фото персонажа установлено!")

 

@dp.message(Command("start"))

async def cmd_start(msg: types.Message):

    if msg.chat.type in ("group", "supergroup"):

        with sqlite3.connect(DB) as c: c.execute("INSERT OR IGNORE INTO groups VALUES (?)", (msg.chat.id,))

    get_user(msg.from_user.id)

    txt = "*недовольно хмыкнула* Чего уставился? Думаешь, я сразу растаю? Как бы не так, бака!"

    kb = menu_kb() if msg.chat.type == "private" else None

    photo = get_cfg("photo")

    if photo: await msg.answer_photo(photo, caption=txt, reply_markup=kb)

    else: await msg.answer(txt, reply_markup=kb)

@dp.message(F.text.in_(["/stats", "📊 Профиль"]))

async def cmd_stats(msg: types.Message):

    if not await is_sub(msg.from_user.id): return await ask_sub(msg)

    aff, coins, _ = get_user(msg.from_user.id)

    st = "Злая хамка 💢" if aff <= 100 else "Ворчливая цундере 😳" if aff <= 250 else "Скрывает чувства 💓" if aff <= 400 else "Влюблена 💖"

    await msg.answer(f"❤️ Симпатия: **{aff}/500**\n🪙 Цун-коины: **{coins}**\n🎭 Статус: **{st}**", parse_mode="Markdown")

 

@dp.message(F.text.in_(["/reset", "🔄 Сброс"]))

async def cmd_reset(msg: types.Message):

    save_user(msg.from_user.id, 10, 20, [])

    await msg.answer("*закатила глаза* Ладно, начинаем заново, дурак. (Симпатия: 10/500, Коины: 20 🪙)")

 

@dp.message(F.text.in_(["/game", "🎮 Мини-игра"]))

async def cmd_game(msg: types.Message):

    if not await is_sub(msg.from_user.id): return await ask_sub(msg)

    kb = InlineKeyboardBuilder()

    for t, d in [("🪨 Камень", "rps_rock"), ("✂️ Ножницы", "rps_scissors"), ("📄 Бумага", "rps_paper")]: kb.button(text=t, callback_data=d)

    kb.adjust(3)

    await msg.answer("*усмехнулась* Сыграем? Победишь — дам 15 🪙. Выбирай!", reply_markup=kb.as_markup())

 

@dp.callback_query(F.data.startswith("rps_"))

async def cb_rps(cb: types.CallbackQuery):

    _, u = cb.data.split("_", 1)

    b = random.choice(["rock", "scissors", "paper"])

    n = {"rock": "🪨 Камень", "scissors": "✂️ Ножницы", "paper": "📄 Бумага"}

    aff, coins, hist = get_user(cb.from_user.id)

    if u == b: res = f"Оба выбрали {n.get(b)}. *фыркнула* Ничья, повторюшка!"

    elif (u=="rock" and b=="scissors") or (u=="scissors" and b=="paper") or (u=="paper" and b=="rock"):

        coins += 15; save_user(cb.from_user.id, aff, coins, hist)

        res = f"Ты: {n.get(u)} | Я: {n.get(b)}\n*покраснела* Ч-чего?! Ты жульничал! На 15 🪙! (Баланс: {coins} 🪙)"

    else: res = f"Ты: {n.get(u)} | Я: {n.get(b)}\n*ухмыльнулась* Ха! Проиграл, бака~"

    await cb.message.edit_text(res)

 

@dp.message(F.text.in_(["/shop", "🎁 Магазин"]))

async def cmd_shop(msg: types.Message):

    if not await is_sub(msg.from_user.id): return await ask_sub(msg)

    _, coins, _ = get_user(msg.from_user.id)

    kb = InlineKeyboardBuilder()

    for k, (name, price, bonus) in GIFTS.items(): kb.button(text=f"{name} — {price} 🪙 (+{bonus} ❤️)", callback_data=f"buy_{k}")

    kb.adjust(1)

    await msg.answer(f"*отвернулась* Я не жду подарков! Просто мимо проходила... (У тебя: {coins} 🪙)", reply_markup=kb.as_markup())

 

@dp.callback_query(F.data.startswith("buy_"))

async def cb_buy(cb: types.CallbackQuery):

    _, k = cb.data.split("_", 1)

    name, price, bonus = GIFTS.get(k)

    aff, coins, hist = get_user(cb.from_user.id)

    if coins < price: return await cb.answer("Мало Цун-коинов!", show_alert=True)

    coins -= price; aff = min(500, aff + bonus)

    hist.append({"role": "user", "text": f"*дарит {name}*"})

    save_user(cb.from_user.id, aff, coins, hist)

    await cb.message.edit_text(f"🎁 Подарено: **{name}**\n*густо покраснела* Д-дурак... Зачем тратишься?! Н-но спасибо...\n📈 Симпатия +{bonus} ({aff}/500)", parse_mode="Markdown")

 

def adm_kb():

    kb = InlineKeyboardBuilder()

    kb.button(text="📊 Статистика", callback_data="a_stat")

    kb.button(text="✉️ Рассылка ЛС", callback_data="a_pm")

    kb.button(text="👥 Рассылка Группы", callback_data="a_grp")

    kb.button(text="🟢 ОП: ВКЛ" if get_cfg("sub_on")=="1" else "🔴 ОП: ВЫКЛ", callback_data="a_sub")

    kb.button(text="📢 Канал ОП", callback_data="a_ch")

    kb.adjust(1, 2, 2)

    return kb.as_markup()

 

@dp.message(Command("admin"))

async def cmd_adm(msg: types.Message, state: FSMContext):

    if msg.from_user.id == ADMIN_ID: await state.clear(); await msg.answer("⚙️ **Админка**", reply_markup=adm_kb(), parse_mode="Markdown")

 

@dp.callback_query(F.data == "a_stat")

async def cb_astat(cb: types.CallbackQuery):

    now = int(time.time())

    with sqlite3.connect(DB) as c:

        tot, = c.execute("SELECT COUNT(*) FROM users").fetchone()

        d1, = c.execute("SELECT COUNT(*) FROM users WHERE last>=?", (now-86400,)).fetchone()

        d7, = c.execute("SELECT COUNT(*) FROM users WHERE last>=?", (now-604800,)).fetchone()

        gr, = c.execute("SELECT COUNT(*) FROM groups").fetchone()

    await cb.message.edit_text(f"📊 Всего: **{tot}**\n🔥 За 24ч: **{d1}**\n📅 За 7д: **{d7}**\n💤 Неактивны: **{max(0, tot-d7)}**\n👥 Групп: **{gr}**", reply_markup=adm_kb(), parse_mode="Markdown")

 

@dp.callback_query(F.data == "a_sub")

async def cb_asub(cb: types.CallbackQuery):

    set_cfg("sub_on", "0" if get_cfg("sub_on")=="1" else "1")

    await cb.message.edit_reply_markup(reply_markup=adm_kb())

 

@dp.callback_query(F.data == "a_ch")

async def cb_ach(cb: types.CallbackQuery, state: FSMContext):

    await state.set_state(AdminState.set_ch)

    await cb.message.answer("Напиши через пробел: `@канал https://t.me` (Отмена: /cancel)")

 

@dp.message(AdminState.set_ch)

async def st_ch(msg: types.Message, state: FSMContext):

    if msg.text == "/cancel": await state.clear(); return await msg.answer("Отменено")

    parts = msg.text.split()

    if len(parts) < 2: return await msg.answer("Нужно через пробел: `@канал ссылка`")

    ch, url, *_ = parts

    set_cfg("sub_ch", ch); set_cfg("sub_url", url); await state.clear()

    await msg.answer(f"✅ Канал {ch} сохранён!", reply_markup=adm_kb())

 

@dp.callback_query(F.data.in_(["a_pm", "a_grp"]))

async def cb_acast(cb: types.CallbackQuery, state: FSMContext):

    await state.set_state(AdminState.cast_pm if cb.data=="a_pm" else AdminState.cast_grp)

    await cb.message.answer("Отправь пост (текст или фото) для рассылки. Отмена: /cancel")

 

@dp.message(AdminState.cast_pm)

@dp.message(AdminState.cast_grp)

async def st_cast(msg: types.Message, state: FSMContext):

    if msg.text == "/cancel": await state.clear(); return await msg.answer("Отменено")

    is_pm = (await state.get_state()) == AdminState.cast_pm

    await state.clear()

    with sqlite3.connect(DB) as c: rows = c.execute("SELECT id FROM users" if is_pm else "SELECT id FROM groups").fetchall()

    ok, err = 0, 0

    m = await msg.answer(f"⏳ Рассылка ({len(rows)})...")

    for (cid,) in rows:

        try: await msg.copy_to(cid); ok += 1; await asyncio.sleep(0.05)

        except Exception: err += 1

    await m.edit_text(f"✅ Доставлено: **{ok}**, ошибок: **{err}**", parse_mode="Markdown")

 

@dp.message()

async def chat(msg: types.Message):

    if msg.chat.type in ("group", "supergroup"):

        with sqlite3.connect(DB) as c: c.execute("INSERT OR IGNORE INTO groups VALUES (?)", (msg.chat.id,))

        me = await bot.get_me()

        if not ((msg.reply_to_message and msg.reply_to_message.from_user.id == me.id) or (msg.text and f"@{me.username}" in msg.text)): return

    if not msg.text or not await is_sub(msg.from_user.id):

        if msg.text: await ask_sub(msg)

        return

    aff, coins, hist = get_user(msg.from_user.id)

    await bot.send_chat_action(msg.chat.id, "typing")

    stage = "Злая хамка, груби и обзывай дураком" if aff<=100 else "Ворчливая цундере, груби, но сильно смущайся и заикайся на комплименты" if aff<=250 else "Скрытая симпатия, заботься под видом критики" if aff<=400 else "Влюблена, общайся нежно и тепло"

    prompt = f"Ты девушка-цундере в РП. Пиши коротко на русском, используй *действия*. Симпатия: {aff}/500 ({stage}). Оцени фразу игрока: affection_change от -3 до +2."

    contents = [gtypes.Content(role=m.get("role"), parts=[gtypes.Part.from_text(text=m.get("text"))]) for m in hist]

    contents.append(gtypes.Content(role="user", parts=[gtypes.Part.from_text(text=msg.text)]))

    try:

        res = ai.models.generate_content(model="gemini-2.5-flash", contents=contents, config=gtypes.GenerateContentConfig(system_instruction=prompt, response_mime_type="application/json", response_schema=ReplySchema, temperature=0.9))

        data = ReplySchema.model_validate_json(res.text)

        chg = max(-3, min(2, data.affection_change))

        aff = max(0, min(500, aff + chg))

        earned = 5 if chg > 0 else 0

        hist.extend([{"role": "user", "text": msg.text}, {"role": "model", "text": data.reply}])

        save_user(msg.from_user.id, aff, coins + earned, hist)

        badge = f"\n\n📈 *Симпатия +{chg} ({aff}/500) | +{earned} 🪙*" if chg > 0 else f"\n\n📉 *Симпатия {chg} ({aff}/500)*" if chg < 0 else ""

        await msg.reply(data.reply + badge, parse_mode="Markdown")

    except Exception as e:

        logging.error(e)

        await msg.answer("*отвернулась* Тц, голова разболелась... Повтори позже.")

 

from aiohttp import web

from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

 

WEBHOOK_URL = "bot-1795495938-3693-hopsik.bothost.tech"

 

async def on_startup(bot: Bot):

    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)

 

def main():

    db_init()

    dp.startup.register(on_startup)

    app = web.Application()

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")

    setup_application(app, dp, bot=bot)

    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

 

if __name__ == "__main__":

    main()
