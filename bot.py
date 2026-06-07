import os
import json
import random
import logging

import discord
from discord.ext import commands, tasks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("hekam-bot")

# ===== الإعدادات (من متغيرات البيئة على Railway) =====
TOKEN = os.getenv("DISCORD_TOKEN")
QUOTE_CHANNEL_ID = os.getenv("QUOTE_CHANNEL_ID")
INTERVAL_MINUTES = int(os.getenv("INTERVAL_MINUTES", "180"))

PREFIX = "#"
GOLD = 0xE9C46A

# ===== تحميل الاقتباسات =====
def load_quotes():
    with open("quotes.json", "r", encoding="utf-8") as f:
        return json.load(f)

QUOTES = load_quotes()
logger.info("تم تحميل %d اقتباس", len(QUOTES))

# ===== إعداد البوت =====
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

runtime_channel_id = None


def all_categories():
    return sorted({q.get("category", "") for q in QUOTES if q.get("category")})


def random_quote(category=None):
    if category:
        pool = [q for q in QUOTES if q.get("category") == category]
        if not pool:
            return None
        return random.choice(pool)
    return random.choice(QUOTES)


def format_quote(quote):
    # نص عادي عشان يبيّن كامل في إشعار الجوال
    text = quote["text"]
    author = quote.get("author") or "غير معروف"
    return "\U0001F319 **\u00ab{}\u00bb**\n\u2014 {}".format(text, author)


def current_channel_id():
    if runtime_channel_id is not None:
        return runtime_channel_id
    if QUOTE_CHANNEL_ID:
        try:
            return int(QUOTE_CHANNEL_ID)
        except ValueError:
            logger.warning("QUOTE_CHANNEL_ID غير صالح: %s", QUOTE_CHANNEL_ID)
    return None


# ===== الإرسال التلقائي =====
@tasks.loop(minutes=INTERVAL_MINUTES)
async def send_auto_quote():
    channel_id = current_channel_id()
    if not channel_id:
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            logger.warning("ما قدرت أوصل للقناة %s: %s", channel_id, e)
            return
    try:
        await channel.send(format_quote(random_quote()))
    except Exception as e:
        logger.warning("فشل الإرسال التلقائي: %s", e)


@send_auto_quote.before_loop
async def before_auto():
    await bot.wait_until_ready()


# ===== الأحداث =====
@bot.event
async def on_ready():
    logger.info("تم تسجيل الدخول كـ %s", bot.user)
    send_auto_quote.change_interval(minutes=INTERVAL_MINUTES)
    if not send_auto_quote.is_running():
        send_auto_quote.start()
    activity = discord.Activity(type=discord.ActivityType.listening, name="#حكمة")
    await bot.change_presence(activity=activity)


# ===== الأوامر =====
@bot.command(name="حكمة", aliases=["اقتباس", "حكم"])
async def hekma(ctx, *, category: str = None):
    cat = category.strip() if category else None
    quote = random_quote(cat)
    if quote is None:
        cats = "، ".join(all_categories())
        await ctx.send("ما لقيت تصنيف بهذا الاسم \U0001F605\nالتصنيفات المتاحة: {}".format(cats))
        return
    await ctx.send(format_quote(quote))


@bot.command(name="قناة")
@commands.has_permissions(administrator=True)
async def set_channel(ctx, channel: discord.TextChannel = None):
    global runtime_channel_id
    target = channel or ctx.channel
    runtime_channel_id = target.id
    await ctx.send(
        "تمام \u2705 بصير الإرسال التلقائي في {}\n"
        "\U0001F4A1 عشان يثبت بعد إعادة التشغيل، حطي ID القناة (`{}`) "
        "في متغير `QUOTE_CHANNEL_ID` على Railway.".format(target.mention, target.id)
    )


@set_channel.error
async def set_channel_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("هذا الأمر للمشرفين فقط \U0001F512")


@bot.command(name="مساعدة", aliases=["اوامر", "help"])
async def help_cmd(ctx):
    embed = discord.Embed(title="\U0001F4DC أوامر بوت الحكم", color=GOLD)
    embed.add_field(name="#حكمة", value="يرسل حكمة عشوائية", inline=False)
    embed.add_field(
        name="#حكمة <التصنيف>",
        value="حكمة من تصنيف معيّن، مثال: `#حكمة نجاح`",
        inline=False,
    )
    embed.add_field(
        name="#قناة [#اسم_القناة]",
        value="(للمشرفين) تحديد قناة الإرسال التلقائي",
        inline=False,
    )
    embed.add_field(name="التصنيفات", value="، ".join(all_categories()), inline=False)
    embed.set_footer(text="الإرسال التلقائي كل {} دقيقة".format(INTERVAL_MINUTES))
    await ctx.send(embed=embed)


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("ضعي توكن البوت في متغير البيئة DISCORD_TOKEN")
    bot.run(TOKEN)
