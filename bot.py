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
TOKEN = os.getenv("DISCORD_TOKEN")                       # توكن البوت (إجباري)
QUOTE_CHANNEL_ID = os.getenv("QUOTE_CHANNEL_ID")         # ID قناة الحِكَم (اختياري)
INTERVAL_MINUTES = int(os.getenv("INTERVAL_MINUTES", "180"))  # كل كم دقيقة ترسل الحِكَم

QUESTION_CHANNEL_ID = os.getenv("QUESTION_CHANNEL_ID")   # ID قناة الأسئلة الفلسفية (اختياري)
QUESTION_INTERVAL_MINUTES = int(os.getenv("QUESTION_INTERVAL_MINUTES", "1440"))  # كل كم دقيقة ترسل الأسئلة (1440 = كل 24 ساعة)

PREFIX = "#"
GOLD = 0xE9C46A  # لون ذهبي يناسب ثيم "ميدنايت رويال"

# ===== تحميل الاقتباسات =====
def load_quotes():
    with open("quotes.json", "r", encoding="utf-8") as f:
        return json.load(f)

QUOTES = load_quotes()
logger.info("تم تحميل %d اقتباس", len(QUOTES))


def load_questions():
    try:
        with open("questions.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

QUESTIONS = load_questions()
logger.info("تم تحميل %d سؤال فلسفي", len(QUESTIONS))

# ===== إعداد البوت =====
intents = discord.Intents.default()
intents.message_content = True  # لازم تفعّلينه من بوابة المطورين أيضاً

bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# قناة يتم ضبطها وقت التشغيل عبر الأمر #قناة (مؤقتة حتى إعادة التشغيل)
runtime_channel_id = None
runtime_question_channel_id = None


def all_categories():
    return sorted({q.get("category", "") for q in QUOTES if q.get("category")})


def random_quote(category=None):
    if category:
        pool = [q for q in QUOTES if q.get("category") == category]
        if not pool:
            return None
        return random.choice(pool)
    return random.choice(QUOTES)


def make_embed(quote):
    text = quote["text"]
    author = quote.get("author") or "غير معروف"
    embed = discord.Embed(
        description="### \u201c{}\u201d".format(text),
        color=GOLD,
    )
    embed.set_author(name="\U0001F319 حكمة")
    embed.set_footer(text="\u2014 {}".format(author))
    return embed


def format_quote(quote):
    # نص عادي عشان يبيّن كامل في إشعار الجوال
    text = quote["text"]
    author = quote.get("author") or "غير معروف"
    return "\U0001F319 **\u00ab{}\u00bb**\n\u2014 {}".format(text, author)


def format_question(q):
    text = q["text"]
    author = q.get("author") or "السير جود"
    return "\U0001F914 **سؤال فلسفي:**\n\u00ab{}\u00bb\n\u2014 {}".format(text, author)


def current_channel_id():
    if runtime_channel_id is not None:
        return runtime_channel_id
    if QUOTE_CHANNEL_ID:
        try:
            return int(QUOTE_CHANNEL_ID)
        except ValueError:
            logger.warning("QUOTE_CHANNEL_ID غير صالح: %s", QUOTE_CHANNEL_ID)
    return None


def current_question_channel_id():
    if runtime_question_channel_id is not None:
        return runtime_question_channel_id
    if QUESTION_CHANNEL_ID:
        try:
            return int(QUESTION_CHANNEL_ID)
        except ValueError:
            logger.warning("QUESTION_CHANNEL_ID غير صالح: %s", QUESTION_CHANNEL_ID)
    return None


async def _resolve_channel(channel_id):
    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except Exception as e:
            logger.warning("ما قدرت أوصل للقناة %s: %s", channel_id, e)
            return None
    return channel


# ===== الإرسال التلقائي =====
@tasks.loop(minutes=INTERVAL_MINUTES)
async def send_auto_quote():
    channel_id = current_channel_id()
    if not channel_id:
        return
    channel = await _resolve_channel(channel_id)
    if channel is None:
        return
    try:
        await channel.send(format_quote(random_quote()))
    except Exception as e:
        logger.warning("فشل إرسال الحكمة التلقائي: %s", e)


@send_auto_quote.before_loop
async def before_auto():
    await bot.wait_until_ready()


@tasks.loop(minutes=QUESTION_INTERVAL_MINUTES)
async def send_auto_question():
    if not QUESTIONS:
        return
    channel_id = current_question_channel_id()
    if not channel_id:
        return
    channel = await _resolve_channel(channel_id)
    if channel is None:
        return
    try:
        await channel.send(format_question(random.choice(QUESTIONS)))
    except Exception as e:
        logger.warning("فشل إرسال السؤال التلقائي: %s", e)


@send_auto_question.before_loop
async def before_auto_question():
    await bot.wait_until_ready()


# ===== الأحداث =====
@bot.event
async def on_ready():
    logger.info("تم تسجيل الدخول كـ %s", bot.user)
    send_auto_quote.change_interval(minutes=INTERVAL_MINUTES)
    if not send_auto_quote.is_running():
        send_auto_quote.start()
    send_auto_question.change_interval(minutes=QUESTION_INTERVAL_MINUTES)
    if not send_auto_question.is_running():
        send_auto_question.start()
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


@bot.command(name="سؤال", aliases=["اسئلة", "أسئلة", "تأمل"])
async def question_cmd(ctx):
    if not QUESTIONS:
        await ctx.send("ما فيه أسئلة محمّلة حالياً.")
        return
    await ctx.send(format_question(random.choice(QUESTIONS)))


@bot.command(name="قناة")
@commands.has_permissions(administrator=True)
async def set_channel(ctx, channel: discord.TextChannel = None):
    global runtime_channel_id
    target = channel or ctx.channel
    runtime_channel_id = target.id
    await ctx.send(
        "تمام \u2705 بصير إرسال **الحِكَم** التلقائي في {}\n"
        "\U0001F4A1 عشان يثبت بعد إعادة التشغيل، حطي ID القناة (`{}`) "
        "في متغير `QUOTE_CHANNEL_ID` على Railway.".format(target.mention, target.id)
    )


@set_channel.error
async def set_channel_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("هذا الأمر للمشرفين فقط \U0001F512")


@bot.command(name="قناة_الأسئلة", aliases=["قناةالأسئلة", "قناة_اسئلة", "قناةالاسئلة"])
@commands.has_permissions(administrator=True)
async def set_question_channel(ctx, channel: discord.TextChannel = None):
    global runtime_question_channel_id
    target = channel or ctx.channel
    runtime_question_channel_id = target.id
    await ctx.send(
        "تمام \u2705 بصير إرسال **الأسئلة الفلسفية** التلقائي في {}\n"
        "\U0001F4A1 عشان يثبت بعد إعادة التشغيل، حطي ID القناة (`{}`) "
        "في متغير `QUESTION_CHANNEL_ID` على Railway.".format(target.mention, target.id)
    )


@set_question_channel.error
async def set_question_channel_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("هذا الأمر للمشرفين فقط \U0001F512")


@bot.command(name="مساعدة", aliases=["اوامر", "help"])
async def help_cmd(ctx):
    embed = discord.Embed(title="\U0001F4DC أوامر بوت الحكم", color=GOLD)
    embed.add_field(name="#حكمة", value="يرسل حكمة عشوائية", inline=False)
    embed.add_field(
        name="#حكمة <التصنيف>",
        value="حكمة من تصنيف معيّن، مثال: `#حكمة وجود`",
        inline=False,
    )
    embed.add_field(
        name="#سؤال",
        value="يرسل سؤالاً فلسفياً للنقاش والتأمّل",
        inline=False,
    )
    embed.add_field(
        name="#قناة [#اسم_القناة]",
        value="(للمشرفين) تحديد قناة إرسال الحِكَم التلقائي",
        inline=False,
    )
    embed.add_field(
        name="#قناة_الأسئلة [#اسم_القناة]",
        value="(للمشرفين) تحديد قناة إرسال الأسئلة الفلسفية التلقائي",
        inline=False,
    )
    embed.add_field(name="التصنيفات", value="، ".join(all_categories()), inline=False)
    embed.set_footer(
        text="الحِكَم كل {} دقيقة · الأسئلة كل {} دقيقة".format(
            INTERVAL_MINUTES, QUESTION_INTERVAL_MINUTES
        )
    )
    await ctx.send(embed=embed)


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("ضعي توكن البوت في متغير البيئة DISCORD_TOKEN")
    bot.run(TOKEN)
