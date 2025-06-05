import random
import httpx
import asyncio
import logging
import json
import re
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMemberAdministrator, ChatMemberOwner
from telegram.constants import ChatAction
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from telegram.error import TelegramError
import functools
import time
from googlesearch import search
import validators
from dotenv import load_dotenv
from fastapi import FastAPI, Request
import uvicorn

# Load environment variables
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() == "true"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8000))

# Set up logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, log_level, logging.INFO)
)
logger = logging.getLogger(__name__)

# Load responses and dynamic words with fallbacks
try:
    with open("responses.json", "r", encoding="utf-8") as f:
        HEY_RESPONSES = json.load(f)
except FileNotFoundError:
    logger.warning("responses.json not found, using default responses")
    HEY_RESPONSES = {}
    with open("responses.json", "w", encoding="utf-8") as f:
        json.dump(HEY_RESPONSES, f)

try:
    with open("dynamic_words.json", "r", encoding="utf-8") as f:
        DYNAMIC_WORDS = json.load(f)
except FileNotFoundError:
    logger.warning("dynamic_words.json not found, using default words")
    DYNAMIC_WORDS = {}
    with open("dynamic_words.json", "w", encoding="utf-8") as f:
        json.dump(DYNAMIC_WORDS, f)

# Default lists
DEFAULT_OBJECTS = [
    "a golden throne", "a pile of crypto coins", "a giant pizza", "a flaming dumpster", "a rocket ship",
    "a bean bag", "a stack of memes", "a cloud of glitter", "a disco ball", "a vintage typewriter",
    "a glowing lightsaber", "a treasure chest", "a giant rubber duck", "a holographic globe",
    "a floating island", "a neon sign", "a steampunk airship", "a crystal skull", "a massive cupcake",
    "a levitating book", "a robotic arm", "a glowing portal", "a pirate ship wheel",
    "a diamond-encrusted crown", "a retro arcade machine", "a mystical obelisk", "a floating lantern",
    "a giant hourglass"
]

DEFAULT_STYLES = [
    "cartoon-style", "pixel art", "anime-style", "retro meme aesthetic", "realistic", "cyberpunk",
    "watercolor", "surrealist", "steampunk", "minimalist", "oil painting", "vaporwave", "gothic",
    "abstract", "pop art", "baroque", "futuristic", "pastel", "graffiti", "stained glass",
    "line art", "3D render", "chalkboard sketch"
]

DEFAULT_SCENES = [
    "explosion", "fireworks", "storm", "rainbow", "space", "underwater", "volcano", "party", "wwe ring",
    "haunted forest", "city skyline at night", "desert oasis", "frozen tundra", "neon-lit alley",
    "ancient ruins", "floating city", "cosmic void", "enchanted castle", "bamboo forest",
    "post-apocalyptic wasteland", "underwater coral reef", "sky temple", "alien marketplace",
    "victorian ballroom", "cybernetic jungle", "lunar surface", "carnival at dusk"
]

DEFAULT_COLORS = [
    "red", "blue", "green", "yellow", "purple", "orange", "pink", "black", "white", "turquoise",
    "gold", "silver", "violet", "cyan", "magenta", "lime", "teal", "emerald", "ruby", "sapphire",
    "amber", "coral", "lavender", "bronze", "ivory", "charcoal", "peach", "mint"
]

# Cooldown and rate limit settings
SUIMEME_COOLDOWN = 5  # seconds
TYPING_DELAY = 3  # seconds
GLOBAL_RATE_LIMIT_KEY = 'global_rate_limit'
GLOBAL_RATE_LIMIT_COUNT = 30  # max requests per minute
GLOBAL_RATE_LIMIT_WINDOW = 60  # seconds
USER_RATE_LIMIT_COUNT = 5  # max requests per user per minute
MIN_REQUEST_GAP = 0.1  # minimum seconds between requests

# Storage for cooldowns and active requests
COOLDOWN_STORAGE = {}  # {f"{chat_id}_{user_id}": timestamp}
ACTIVE_REQUESTS = {}  # {f"{chat_id}_{user_id}": bool}
USER_REQUEST_COUNTS = {}  # {f"{chat_id}_{user_id}": [timestamps]}

# Placeholder for searching an image URL
async def search_image_url(ticker):
    try:
        query = f"{ticker} logo character site:*.org | site:*.com -inurl:(signup | login)"
        logger.info(f"Searching for image URL with query: {query}")
        for url in search(query, num_results=5):
            if url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                logger.info(f"Found image URL: {url}")
                return url
        if "SUIMEME" in ticker.upper():
            return "https://example.com/suimeme_character.jpg"
        elif "TOILET" in ticker.upper():
            return "https://example.com/toilet_image.jpg"
        elif "LOFI" in ticker.upper():
            return "https://example.com/lofi_image.jpg"
        logger.warning(f"No image found for query: {query}")
        return None
    except Exception as e:
        logger.error(f"Error searching image URL for {ticker}: {str(e)}")
        return None

# Placeholder for image analysis
async def analyze_image_from_url(image_url):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)
            if response.status_code != 200:
                logger.error(f"Failed to fetch image from {image_url}: {response.status_code}")
                return None
            if "toilet" in image_url.lower():
                return {
                    'objects': ["a golden toilet", "a pile of toilet paper", "a plunger", "a toilet brush"],
                    'styles': ["toilet paper aesthetic", "grungy bathroom vibe"],
                    'scenes': ["sewer explosion", "toilet flush storm"],
                    'colors': ["poop brown", "toilet blue", "slime green"]
                }
            elif "lofi" in image_url.lower():
                return {
                    'objects': ["a chill record player", "a stack of vinyl records", "a retro lamp"],
                    'styles': ["lofi aesthetic", "vaporwave style"],
                    'scenes': ["vaporwave sunset", "chill night city"],
                    'colors': ["pastel purple", "neon pink", "soft blue"]
                }
            else:
                return {
                    'objects': random.sample(DEFAULT_OBJECTS, 4),
                    'styles': random.sample(DEFAULT_STYLES, 2),
                    'scenes': random.sample(DEFAULT_SCENES, 2),
                    'colors': random.sample(DEFAULT_COLORS, 3)
                }
    except Exception as e:
        logger.error(f"Error analyzing image from {image_url}: {str(e)}")
        return None

# Retry decorator
def retry_on_timeout(retries=3, delay=1):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                except TelegramError as e:
                    last_exception = e
                    if attempt < retries:
                        logger.warning(f"Request timed out, retrying ({attempt + 1}/{retries})...")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"Failed after {retries} retries: {e}")
                        raise last_exception
        return wrapper
    return decorator

# Helper function to check if user is admin
async def is_user_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type == "private":
        logger.info(f"User {user_id} in private chat {chat_id}, admin check bypassed")
        return True
    
    if update.effective_chat.type not in ["group", "supergroup"]:
        logger.warning(f"Chat {chat_id} is not a group or supergroup, denying admin access")
        return False
    
    try:
        chat_member = await context.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        is_admin = isinstance(chat_member, (ChatMemberAdministrator, ChatMemberOwner))
        logger.info(f"User {user_id} in chat {chat_id} admin status: {is_admin}")
        return is_admin
    except TelegramError as e:
        logger.error(f"Error checking admin status for user {user_id} in chat {chat_id}: {str(e)}")
        return False

# Check global rate limit
async def check_global_rate_limit(context: ContextTypes.DEFAULT_TYPE) -> bool:
    current_time = time.time()
    if GLOBAL_RATE_LIMIT_KEY not in context.bot_data:
        context.bot_data[GLOBAL_RATE_LIMIT_KEY] = []
    
    context.bot_data[GLOBAL_RATE_LIMIT_KEY] = [
        ts for ts in context.bot_data[GLOBAL_RATE_LIMIT_KEY]
        if current_time - ts < GLOBAL_RATE_LIMIT_WINDOW
    ]
    
    if len(context.bot_data[GLOBAL_RATE_LIMIT_KEY]) >= GLOBAL_RATE_LIMIT_COUNT:
        logger.warning(f"Global rate limit exceeded: {len(context.bot_data[GLOBAL_RATE_LIMIT_KEY])} requests")
        return False
    
    context.bot_data[GLOBAL_RATE_LIMIT_KEY].append(current_time)
    return True

# Check per-user rate limit
async def check_user_rate_limit(chat_id, user_id) -> tuple[bool, float]:
    current_time = time.time()
    key = f"{chat_id}_{user_id}"
    if key not in USER_REQUEST_COUNTS:
        USER_REQUEST_COUNTS[key] = []
    
    USER_REQUEST_COUNTS[key] = [
        ts for ts in USER_REQUEST_COUNTS[key]
        if current_time - ts < GLOBAL_RATE_LIMIT_WINDOW
    ]
    
    if len(USER_REQUEST_COUNTS[key]) >= USER_RATE_LIMIT_COUNT:
        logger.warning(f"User rate limit exceeded for {key}: {len(USER_REQUEST_COUNTS[key])} requests")
        return False, 0
    
    USER_REQUEST_COUNTS[key].append(current_time)
    return True, 0

# Search for unknown terms
async def search_term(term):
    try:
        logger.info(f"Searching for term: {term}")
        for result in search(term, num_results=1):
            return f"{term} (based on web context)"
        return term
    except Exception as e:
        logger.error(f"Search failed for {term}: {str(e)}")
        return term

def generate_meme_prompt(description=None, scene=None, custom_text=None, color=None, additional_characters=None, theme=None, chat_data=None):
    main_character = chat_data.get('main_character', "Blue Slime King")
    theme = theme or {
        'objects': DEFAULT_OBJECTS,
        'styles': DEFAULT_STYLES,
        'scenes': DEFAULT_SCENES,
        'colors': DEFAULT_COLORS
    }

    objects = theme['objects']
    styles = theme['styles']
    scenes = theme['scenes']
    colors = theme['colors']

    selected_color = color if color in colors else random.choice(colors)
    selected_scene = scene if scene in scenes else random.choice(scenes)
    object_sitting = random.choice(objects)
    style = random.choice(styles)
    ticker = chat_data.get('ticker', '$SUIMEME')

    base_prompt = f"A {style} illustration of {main_character}"
    if additional_characters:
        base_prompt += f" with {', '.join(additional_characters)}"
    if description:
        base_prompt += f" {description}"
    else:
        base_prompt += f" sitting confidently on {object_sitting}"
    base_prompt += f", with a golden crown and {ticker} symbol"
    if selected_scene:
        base_prompt += f", in a dramatic {selected_scene} setting"
    if selected_color:
        base_prompt += f", colored in vibrant {selected_color}"
    if custom_text:
        base_prompt += f", with the text '{custom_text}' prominently displayed on the image"
    base_prompt += ", vibrant, humorous, high-quality, meme-inspired"
    logger.info(f"Generated prompt: {base_prompt}")
    return base_prompt

async def generate_image(prompt):
    try:
        url = "https://api.replicate.com/v1/predictions"
        headers = {
            "Authorization": f"Token {REPLICATE_API_TOKEN}",
            "Content-Type": "application/json"
        }
        data = {
            "version": "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            "input": {"prompt": prompt}
        }
        logger.info(f"Sending request to Replicate API with prompt: {prompt}")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=data)
            if response.status_code == 429:
                logger.error("Replicate API rate limit exceeded")
                return None, "Rate limit exceeded, please try again later"
            if response.status_code != 201:
                logger.error(f"Replicate API error: {response.status_code} - {response.text}")
                return None, f"Replicate API error: {response.status_code} - {response.text}"
            
            prediction = response.json()
            prediction_id = prediction.get("id")
            if not prediction_id:
                logger.error("No prediction ID in response")
                return None, "Failed to get prediction ID"
            logger.info(f"Prediction ID: {prediction_id}")
            
            max_wait_time = 120
            start_time = time.time()
            while time.time() - start_time < max_wait_time:
                status_response = await client.get(f"{url}/{prediction_id}", headers=headers)
                if status_response.status_code != 200:
                    logger.error(f"Status check error: {status_response.status_code} - {status_response.text}")
                    return None, f"Status check error: {status_response.status_code}"
                result = status_response.json()
                if result["status"] in ["succeeded", "failed", "canceled"]:
                    break
                await asyncio.sleep(1)
            else:
                logger.error("Replicate API took too long to respond")
                return None, "Image generation timed out"
            
            if result["status"] == "succeeded" and "output" in result and result["output"]:
                logger.info("Image generation succeeded")
                return result["output"][0], None
            logger.error(f"Image generation failed: {result.get('error', 'Unknown error')}")
            return None, f"Image generation failed: {result.get('error', 'Unknown error')}"
    except httpx.TimeoutException as e:
        logger.error(f"Replicate API timeout: {str(e)}")
        return None, f"Replicate API timeout: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in generate_image: {str(e)}")
        return None, f"Unexpected error: {str(e)}"

@retry_on_timeout(retries=3, delay=1)
async def suimeme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    command_text = update.message.text.strip()
    logger.info(f"Received /SUIMEME command from user {user_id} in chat {chat_id}: {command_text}")

    key = f"{chat_id}_{user_id}"
    current_time = time.time()

    # Check if user is already processing a request
    if ACTIVE_REQUESTS.get(key, False):
        ticker = context.chat_data.get('ticker', '$SUIMEME')
        await update.message.reply_text(
            f"Yo, slime fam! 😎 Hold on, you're spamming too fast! Wait for your current {ticker} meme to finish! 💦"
        )
        logger.info(f"User {user_id} in chat {chat_id} has active request, blocked")
        return

    try:
        ACTIVE_REQUESTS[key] = True

        # Check per-user rate limit
        user_ok, _ = await check_user_rate_limit(chat_id, user_id)
        if not user_ok:
            ticker = context.chat_data.get('ticker', '$SUIMEME')
            await update.message.reply_text(
                f"Yo, slime fam! 😎 You're going too fast! Wait a bit for the next {ticker} meme drop! 💦"
            )
            logger.info(f"User rate limit hit for {key}")
            return

        # Check global rate limit
        if not await check_global_rate_limit(context):
            ticker = context.chat_data.get('ticker', '$SUIMEME')
            await update.message.reply_text(
                f"Yo, slime fam! 😎 The bot's too hot right now! 🔥 Wait a bit for the next {ticker} meme drop! 💦"
            )
            logger.info(f"Global rate limit hit for chat {chat_id}")
            return

        # Check cooldown
        last_request_time = COOLDOWN_STORAGE.get(key, 0)
        time_since_last = current_time - last_request_time
        logger.info(f"User {user_id} in chat {chat_id}, time since last: {time_since_last:.3f}s, cooldown: {SUIMEME_COOLDOWN}s")
        if time_since_last < SUIMEME_COOLDOWN or time_since_last < MIN_REQUEST_GAP:
            cooldown_left = SUIMEME_COOLDOWN - time_since_last if time_since_last < SUIMEME_COOLDOWN else MIN_REQUEST_GAP - time_since_last
            ticker = context.chat_data.get('ticker', '$SUIMEME')
            await update.message.reply_text(
                f"Yo, slime fam! 😎 Hold on, you're spamming too fast! Wait {cooldown_left:.1f}s for the next {ticker} meme drop! 💦"
            )
            logger.info(f"User {user_id} in chat {chat_id} is on cooldown, {cooldown_left:.1f}s remaining")
            return

        # Update cooldown
        COOLDOWN_STORAGE[key] = current_time
        logger.info(f"Updated cooldown timestamp for {key}: {current_time}")

        # Initialize default settings
        if 'main_character' not in context.chat_data:
            context.chat_data['main_character'] = "Blue Slime King"
            context.chat_data['characters'] = ["Blue Slime King"]
        if 'ticker' not in context.chat_data:
            context.chat_data['ticker'] = "$SUIMEME"
        if 'character_image' not in context.chat_data:
            ticker = context.chat_data['ticker']
            image_url = await search_image_url(ticker)
            context.chat_data['character_image'] = image_url if image_url else None

        # Send typing action
        await update.message.chat.send_action(ChatAction.TYPING)
        await asyncio.sleep(TYPING_DELAY)

        args = context.args or []
        user_input = " ".join(args).strip().lower()
        logger.info(f"Raw user input: {user_input}")

        # Parse quoted text
        quote_match = re.search(r'["\'](.*?)["\']', user_input, re.IGNORECASE)
        custom_text = quote_match.group(1).strip() if quote_match else None

        # Initialize variables
        description = None
        scene = None
        color = None
        additional_characters = []
        object_sitting = None

        # Process input and handle image theme
        theme = {
            'objects': DEFAULT_OBJECTS,
            'styles': DEFAULT_STYLES,
            'scenes': DEFAULT_SCENES,
            'colors': DEFAULT_COLORS
        }
        character_image = context.chat_data.get('character_image', None)
        if character_image and validators.url(character_image):
            image_theme = await analyze_image_from_url(character_image)
            if image_theme:
                theme = image_theme

        scenes = theme['scenes']
        colors = theme['colors']
        objects = theme['objects']

        # Process input
        if user_input:
            description_input = user_input
            if custom_text:
                description_input = re.sub(re.escape(f"'{custom_text.lower()}'"), '', description_input, flags=re.IGNORECASE)
                description_input = re.sub(re.escape(f'"{custom_text.lower()}"'), '', description_input, flags=re.IGNORECASE)
                description_input = description_input.strip()

            terms = description_input.split()
            main_character = context.chat_data.get('main_character', 'Blue Slime King').lower()

            for term in terms:
                term_lower = term.lower()
                found_scene = False
                for s in scenes:
                    if re.search(rf'\b{s}\b', term_lower, re.IGNORECASE) or term_lower == 'moon':
                        scene = term_lower if term_lower == 'moon' else s
                        found_scene = True
                        description_input = re.sub(rf'\b{term_lower}\b', '', description_input, flags=re.IGNORECASE).strip()
                        break
                if found_scene:
                    continue
                for c in colors:
                    if re.search(rf'\b{c}\b', term_lower, re.IGNORECASE):
                        color = c
                        description_input = re.sub(rf'\b{term_lower}\b', '', description_input, flags=re.IGNORECASE).strip()
                        break
                else:
                    for obj in objects:
                        obj_name = obj.replace('a ', '').replace('an ', '').lower()
                        if term_lower in obj_name or term_lower == 'rocketship':
                            object_sitting = obj if term_lower in obj_name else 'a rocket ship'
                            description_input = re.sub(rf'\b{term_lower}\b', '', description_input, flags=re.IGNORECASE).strip()
                            break
                    else:
                        if term_lower != main_character:
                            searched_term = await search_term(term)
                            if searched_term != term:
                                additional_characters.append(searched_term)
                            else:
                                description = term if not description else f"{description} {term}"

            description_input = description_input.strip()
            if description_input and description_input.lower() != main_character:
                description = description_input
            logger.info(f"Parsed - Description: {description}, Scene: {scene}, Color: {color}, Custom Text: {custom_text}, Additional Characters: {additional_characters}, Object: {object_sitting}")

        ticker = context.chat_data.get('ticker', '$SUIMEME')
        await update.message.reply_text(f"Generating your {ticker} meme")
        prompt = generate_meme_prompt(description, scene, custom_text, color, additional_characters, theme, context.chat_data)
        if object_sitting:
            prompt = prompt.replace(f"sitting confidently on {random.choice(objects)}", f"sitting confidently on {object_sitting}")
        image_url, error = await generate_image(prompt)
        if error:
            logger.error(f"Failed to generate image: {error}")
            await update.message.reply_text(f"Oops, failed to generate meme: {error}")
            return
        logger.info(f"Successfully generated image: {image_url}")
        await update.message.reply_photo(
            photo=image_url,
            caption=f"{ticker} Meme: {prompt}"
        )

    finally:
        ACTIVE_REQUESTS[key] = False
        logger.info(f"Released active request lock for {key}")

@retry_on_timeout(retries=3, delay=1)
async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    logger.info(f"/settings from {user_id} in chat {chat_id}")

    if not await is_user_admin(update, context):
        ticker = context.chat_data.get('ticker', '$SUIMEME')
        await update.message.reply_text(
            f"Yo, slime fam! 😅 /settings is only for group admins. Ask an admin to customize the {ticker} vibe! 👑"
        )
        logger.info(f"User {user_id} in chat {chat_id} is not an admin, denied /settings access")
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1)

    if 'main_character' not in context.chat_data:
        context.chat_data['main_character'] = "Blue Slime King"
        context.chat_data['characters'] = ["Blue Slime King"]
    if 'ticker' not in context.chat_data:
        context.chat_data['ticker'] = "$SUIMEME"
    if 'contract_address' not in context.chat_data:
        context.chat_data['contract_address'] = "0xeded589fe72aef12b3b22a826723854820c8480023f3a0ef49460f8429b8d080::suimeme::SUIMEME"
    if 'telegram' not in context.chat_data:
        context.chat_data['telegram'] = "https://t.me/suimeme"
    if 'twitter' not in context.chat_data:
        context.chat_data['twitter'] = "https://x.com/sui_meme_sui/"
    if 'website' not in context.chat_data:
        context.chat_data['website'] = "https://sui-meme.com/"
    if 'character_image' not in context.chat_data:
        ticker = context.chat_data['ticker']
        image_url = await search_image_url(ticker)
        context.chat_data['character_image'] = image_url if image_url else None

    main_character = context.chat_data.get('main_character', 'Blue Slime King')
    character_image = context.chat_data.get('character_image', 'Not set')
    contract_address = context.chat_data.get('contract_address', '0xeded589fe72aef12b3b22a826723854820c8480023f3a0ef49460f8429b8d080::suimeme::SUIMEME')
    telegram = context.chat_data.get('telegram', 'https://t.me/suimeme')
    twitter = context.chat_data.get('twitter', 'https://x.com/sui_meme_sui/')
    website = context.chat_data.get('website', 'https://sui-meme.com/')
    ticker = context.chat_data.get('ticker', '$SUIMEME')

    settings_text = (
        f"Yo, slime fam! 😎 Current settings for this group: 💦\n"
        f"------------------------\n"
        f"Main Character: {main_character}\n"
        f"Character Image: {character_image}\n"
        f"Contract Address: {contract_address}\n"
        f"Telegram: {telegram}\n"
        f"Twitter/X: {twitter}\n"
        f"Website: {website}\n"
        f"Ticker: {ticker}\n"
        f"------------------------\n"
        "Click a button below to update a setting:"
    )

    keyboard = [
        [
            InlineKeyboardButton("Character", callback_data='set_character'),
            InlineKeyboardButton("Image URL", callback_data='set_image_url')
        ],
        [
            InlineKeyboardButton("Contract Address", callback_data='set_ca'),
            InlineKeyboardButton("Telegram", callback_data='set_tg')
        ],
        [
            InlineKeyboardButton("Twitter/X", callback_data='set_x'),
            InlineKeyboardButton("Website", callback_data='set_web')
        ],
        [
            InlineKeyboardButton("Ticker", callback_data='set_ticker')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(settings_text, reply_markup=reply_markup)

@retry_on_timeout(retries=3, delay=1)
async def hey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"/hey from {user_id}")
    
    await update.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1)
    
    await update.message.reply_text("Yo, slime fam! I'm not available to talk for now, but keep the $SUIMEME vibes flowin'! 💦")

@retry_on_timeout(retries=3, delay=1)
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    setting = query.data
    
    if not await is_user_admin(update, context):
        ticker = context.chat_data.get('ticker', '$SUIMEME')
        await query.message.reply_text(
            f"Yo, slime fam! 😅 Only admins can update {ticker} settings. Ask an admin to make changes! 👑"
        )
        logger.info(f"User {user_id} in chat {chat_id} is not an admin, denied settings update")
        return
    
    context.chat_data['current_setting_to_update'] = setting
    
    prompts = {
        'set_character': "Yo, slime fam! 😎 Enter the new character name (e.g., 'Fire Slime')",
        'set_image_url': "Yo, slime fam! 😎 Enter the new image URL (e.g., 'https://example.com/image.jpg')",
        'set_ca': "Yo, slime fam! 😎 Enter the new contract address (e.g., '0x123::module::TYPE')",
        'set_tg': "Yo, slime fam! 😎 Enter the new Telegram URL (e.g., 'https://t.me/newgroup')",
        'set_x': "Yo, slime fam! 😎 Enter the new Twitter/X URL (e.g., 'https://x.com/newaccount')",
        'set_web': "Yo, slime fam! 😎 Enter the new website URL (e.g., 'https://newwebsite.com')",
        'set_ticker': "Yo, slime fam! 😎 Enter the new ticker (e.g., '$NEWCOIN')"
    }
    
    await query.message.reply_text(prompts.get(setting, "Yo, slime fam! 😎 Enter the new value"))

@retry_on_timeout(retries=3, delay=1)
async def handle_setting_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    user_id = update.effective_user.id
    
    if 'current_setting_to_update' not in context.chat_data:
        return
    
    if not await is_user_admin(update, context):
        ticker = context.chat_data.get('ticker', '$SUIMEME')
        await update.message.reply_text(
            f"Yo, slime fam! 😅 Only admins can update {ticker} settings. Ask an admin to make changes! 👑"
        )
        logger.info(f"User {user_id} in chat {chat_id} is not an admin, denied setting input")
        return
    
    setting = context.chat_data['current_setting_to_update']
    new_value = update.message.text.strip()
    
    if setting == 'set_character':
        context.chat_data['main_character'] = new_value
        context.chat_data['characters'] = [new_value]
        logger.info(f"Updated main character to {new_value} for chat {chat_id}")
        await update.message.reply_text(f"Yo, slime fam! Updated Main Character to {new_value} 💦")
    
    elif setting == 'set_image_url':
        if validators.url(new_value):
            context.chat_data['character_image'] = new_value
            logger.info(f"Updated character image to {new_value} for chat {chat_id}")
            await update.message.reply_text(f"Yo, slime fam! Updated Character Image to {new_value} 💦")
        else:
            await update.message.reply_text("Yo, slime! 😅 Invalid URL. Try again with a valid URL (e.g., 'https://example.com/image.jpg')")
            return
    
    elif setting == 'set_ca':
        if re.match(r'0x[a-fA-F0-9]+::[a-zA-Z0-9]+::[a-zA-Z0-9]+', new_value):
            context.chat_data['contract_address'] = new_value
            logger.info(f"Updated contract address to {new_value} for chat {chat_id}")
            await update.message.reply_text(f"Yo, slime fam! Updated Contract Address to {new_value} 💦")
        else:
            await update.message.reply_text("Yo, slime! 😅 Invalid contract address. Try again with a valid address (e.g., '0x123::module::TYPE')")
            return
    
    elif setting == 'set_tg':
        if validators.url(new_value):
            context.chat_data['telegram'] = new_value
            logger.info(f"Updated Telegram to {new_value} for chat {chat_id}")
            await update.message.reply_text(f"Yo, slime fam! Updated Telegram to {new_value} 💦")
        else:
            await update.message.reply_text("Yo, slime! 😅 Invalid URL. Try again with a valid Telegram URL (e.g., 'https://t.me/newgroup')")
            return
    
    elif setting == 'set_x':
        if validators.url(new_value):
            context.chat_data['twitter'] = new_value
            logger.info(f"Updated Twitter/X to {new_value} for chat {chat_id}")
            await update.message.reply_text(f"Yo, slime fam! Updated Twitter/X to {new_value} 💦")
        else:
            await update.message.reply_text("Yo, slime! 😅 Invalid URL. Try again with a valid Twitter/X URL (e.g., 'https://x.com/newaccount')")
            return
    
    elif setting == 'set_web':
        if validators.url(new_value):
            context.chat_data['website'] = new_value
            logger.info(f"Updated website to {new_value} for chat {chat_id}")
            await update.message.reply_text(f"Yo, slime fam! Updated Website to {new_value} 💦")
        else:
            await update.message.reply_text("Yo, slime! 😅 Invalid URL. Try again with a valid website URL (e.g., 'https://newwebsite.com')")
            return
    
    elif setting == 'set_ticker':
        if re.match(r'\$[A-Z]+', new_value):
            context.chat_data['ticker'] = new_value
            logger.info(f"Updated ticker to {new_value} for chat {chat_id}")
            image_url = await search_image_url(new_value)
            context.chat_data['character_image'] = image_url if image_url else None
            await update.message.reply_text(f"Yo, slime fam! Updated Ticker to {new_value} 💦")
        else:
            await update.message.reply_text("Yo, slime! 😅 Invalid ticker. Try again with a valid ticker (e.g., '$NEWCOIN')")
            return
    
    del context.chat_data['current_setting_to_update']

@retry_on_timeout(retries=3, delay=1)
async def start_com(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1)
    if 'character_image' not in context.chat_data:
        ticker = context.chat_data.get(' ticker', '$SUIMEME')
        image_url = await search_image_url(ticker)
        context.chat_data['character_image'] = image_url if image_url else None
    welcome = (
        "Yo, welcome to SuiMemeBot! 👑💦 I’m the Blue Slime King, droppin’ memes!\n\n"
        "/SUIMEME to make memes\n/how for tips\n/hey to vibe\n/settings to customize this group\n\n"
        "Let’s make the blockchain bounce!"
    )
    logger.info(f"Started by user {update.effective_user.id}")
    await update.message.reply_text(welcome)

@retry_on_timeout(retries=3, delay=1)
async def how(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1)
    ticker = context.chat_data.get('ticker', '$SUIMEME')
    main_character = context.chat_data.get('main_character', 'Blue Slime King')
    help_text = (
        f"Wanna meme with {main_character}? Use /SUIMEME and describe it! 😎\n\n"
        "Add:\n- Scenes: explosion, fireworks, storm, wwe ring\n- Colors: red, blue, green\n"
        "- Text: 'LFG!!'\n- Actions: 'eating pizza'\n\n"
        "Examples:\n- /SUIMEME slime on toilet\n- /SUIMEME explosion 'LFG!!'\n"
        "- /SUIMEME blue dancing underwater\n- /SUIMEME with pepe prog in wwe ring\n\n"
        f"Use /settings to change the main character, ticker (like {ticker}), or links for this group!\n/hey to vibe, /start to join!"
    )
    await update.message.reply_text(help_text)

@retry_on_timeout(retries=3, delay=1)
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1)
    ticker = context.chat_data.get('ticker', '$SUIMEME')
    await update.message.reply_text(
        f"Yo! /SUIMEME for memes, /how for tips, /hey to vibe, /settings to customize this group’s {ticker} vibe, /start to join! 😎👑"
    )

@retry_on_timeout(retries=3, delay=1)
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.message.chat_id
    command = update.message.text.strip()
    logger.info(f"Unknown command: {command} from {user_id} in {chat_id}")
    
    await update.message.chat.send_action(ChatAction.TYPING)
    await asyncio.sleep(1)
    ticker = context.chat_data.get('ticker', '$SUIMEME')
    await update.message.reply_text(
        f"Yo, slime fam! 😅 Unknown command. Try /SUIMEME for memes, /how for tips, /hey to vibe, /settings for {ticker} group, or /start! 👑"
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    if isinstance(context.error, TelegramError):
        logger.error("Telegram error, skipping")
        return
    try:
        await update.message.reply_text(f"Oops, slime failed! 😅 Error: {context.error}. Try again!")
    except Exception as e:
        logger.error(f"Error sending error message: {e}")

# FastAPI app for webhook mode
app = FastAPI()

@app.on_event("startup")
async def startup():
    if USE_WEBHOOK:
        logger.info("Setting up webhook...")
        await application.initialize()
        await application.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set to {WEBHOOK_URL}")

@app.on_event("shutdown")
async def shutdown():
    if USE_WEBHOOK:
        logger.info("Shutting down...")
        await application.shutdown()

@app.post("/webhook")
async def webhook(request: Request):
    update = Update.de_json(await request.json(), application.bot)
    await application.process_update(update)
    return {"status": "ok"}

# Initialize application
application = Application.builder().token(TELEGRAM_TOKEN).build()

# Add handlers
application.add_handler(CommandHandler(["SUIMEME", "suimeme"], suimeme))
application.add_handler(CommandHandler(["hey", "HEY"], hey))
application.add_handler(CommandHandler(["settings", "SETTINGS"], settings))
application.add_handler(CallbackQueryHandler(button_callback))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_setting_input))
application.add_handler(CommandHandler(["start", "START"], start_com))
application.add_handler(CommandHandler(["how", "HOW"], how))
application.add_handler(CommandHandler(["help", "HELP"], help_command))
application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
application.add_error_handler(error_handler)

def main():
    if not TELEGRAM_TOKEN or not REPLICATE_API_TOKEN:
        logger.error("Missing TELEGRAM_TOKEN or REPLICATE_API_TOKEN")
        return
    if USE_WEBHOOK and not WEBHOOK_URL:
        logger.error("Missing WEBHOOK_URL for webhook mode")
        return

    if USE_WEBHOOK:
        logger.info("Starting bot with webhook...")
        uvicorn.run(app, host="0.0.0.0", port=PORT)
    else:
        logger.info("Starting bot with polling...")
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(application.initialize())
            loop.run_until_complete(application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True))
        except KeyboardInterrupt:
            logger.info("Bot interrupted, shutting down...")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            loop.run_until_complete(application.shutdown())
            if not loop.is_closed():
                loop.close()
            logger.info("Bot shutdown complete.")

if __name__ == "__main__":
    main()