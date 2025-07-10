import logging
import re
import time
import sys
import ssl
import requests
from datetime import datetime
from collections import defaultdict
from openai import OpenAI
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ConversationHandler,
    CommandHandler,
    ContextTypes,
    filters,
)
from pymongo import MongoClient

import io

# ====== CONFIG ======
OPENROUTER_KEY = "API_KEY"
TELEGRAM_BOT_TOKEN = "BOT_TOKEN"
MONGO_URI = "Phantom-protocol URI"
MONGO_DB = "Phantom-Protocol"
MONGO_COLLECTION = "contacts"
FEEDBACK_COLLECTION = "feedback"
ASSEMBLYAI_API_KEY = "ASSEMBLY"
OCR_SPACE_API_KEY = "OCR_KEY"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO,
)
logger = logging.getLogger(__name__)

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
)

contacts_collection = None
feedback_collection = None
try:
    mongo_client = MongoClient(
        MONGO_URI,
        tls=True,
        tlsAllowInvalidCertificates=False,
        serverSelectionTimeoutMS=10000
    )
    mongo_db = mongo_client[MONGO_DB]
    contacts_collection = mongo_db[MONGO_COLLECTION]
    feedback_collection = mongo_db[FEEDBACK_COLLECTION]
    mongo_client.server_info()
    n_docs = contacts_collection.count_documents({})
    print(f"[MongoDB] Connection success! Collection '{MONGO_COLLECTION}' currently has {n_docs} documents.")
    if n_docs == 0:
        print("[MongoDB] WARNING: No documents found in collection yet.")
except Exception as e:
    print(f"[MongoDB] Connection failed: {e}")
    logger.error(f"[MongoDB] Connection failed: {e}")

scammer_data = []
decoy_conversations = defaultdict(lambda: {
    'history': [],
    'last_active': time.time(),
    'decoy_state': None,
    'tries': 0
})

HUMAN_DM = range(1)
SCAM_ALERT_CHAT_ID = None  # Set to your admin/log group/channel id (e.g., -1001234567890)

ALLOWED_DOMAINS = [
    "upi.com", "facebook.com", "instagram.com", "twitter.com", "linkedin.com"
]

reported_users = set()

def extract_social_or_phone(text):
    phones = re.findall(r"\b[6-9]\d{9}\b", text)
    socials = re.findall(r"(instagram\.com/\S+|facebook\.com/\S+|insta:? ?@?\w+|fb:? ?@?\w+)", text, re.I)
    return phones, socials

def extract_upi_or_bank(text):
    upi = re.findall(r"\b\w+@[a-z]+\b", text)
    bank = re.findall(r"\b\d{9,18}\b", text)
    return upi, bank

def contains_proof_phrase(text):
    triggers = [
        "proof", "screenshot", "receipt", "id card", "upi receipt",
        "transaction slip", "sent my proof", "here is my", "my document", "transaction id"
    ]
    t = text.lower()
    return any(x in t for x in triggers)

def contains_intent_to_share(text):
    intent_phrases = [
        "will share", "will send", "sure", "i will upload", "i'll share", "sending soon",
        "sending now", "wait", "give me a minute", "give me some time", "i'll send it", "i will send it",
        "doing it now", "will upload", "sending proof", "uploading", "please wait"
    ]
    t = text.lower()
    return any(phrase in t for phrase in intent_phrases)

def extract_sensitive_info(text):
    upi_ids = re.findall(r"\b\w+@[a-z]+\b", text)
    phones = re.findall(r"\b[6-9]\d{9}\b", text)
    account_numbers = re.findall(r"\b\d{9,18}\b", text)
    socials = re.findall(r"(facebook\.com/\S+|instagram\.com/\S+|insta:? ?@?\w+|fb:? ?@?\w+)", text, re.I)
    return {
        "upi_ids": upi_ids if upi_ids else [],
        "phones": phones if phones else [],
        "account_numbers": account_numbers if account_numbers else [],
        "socials": socials if socials else [],
    }

def extract_urls(text):
    url_pattern = re.compile(r'(https?://[^\s]+)')
    return url_pattern.findall(text)

def is_suspicious_url(url):
    for allowed in ALLOWED_DOMAINS:
        if allowed in url:
            return False
    return True

def extract_main_classification(gpt_response):
    gpt_response = gpt_response.lower()
    if "scammer" in gpt_response:
        return "scammer"
    elif "decoy" in gpt_response:
        return "decoy"
    elif "innocent" in gpt_response:
        return "innocent"
    else:
        return gpt_response.strip().split('\n')[0][:32]

def wrap_list(val):
    if isinstance(val, (list, tuple)):
        return list(val)
    elif val:
        return [val]
    else:
        return []

def mongo_insert(doc):
    if contacts_collection is None:
        print("[MongoDB] Insert attempted but no DB connection.")
        logger.error("[MongoDB] Insert attempted but no DB connection.")
        return
    try:
        result = contacts_collection.insert_one(doc)
        logger.info("[MongoDB] Inserted: %s", doc)
        print(f"[MongoDB] Inserted with _id={result.inserted_id}: {doc}")
    except Exception as e:
        logger.error(f"MongoDB insert failed: {e}")
        print(f"[MongoDB] Insert failed: {e}")

async def classify_message_with_gpt(text):
    try:
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://yourwebsite.com",
                "X-Title": "ScamHunterBot",
            },
            model="google/gemma-3n-e4b-it:free",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "You are a message classifier. Classify the following message as exactly one of: 'scammer', 'decoy', or 'innocent'.\n"
                        "- A 'scammer' is someone trying to get money or personal information, often sharing UPI, bank, or social handles, or asking you to contact them for a reward.\n"
                        "- A 'decoy' is someone posting fake testimonials or reviews (e.g., 'I have won 10 lakhs, thank you!', 'I received my money, this is real!') meant to make others trust the scam.\n"
                        "- 'Innocent' is anything not related to a scam.\n"
                        "\n"
                        "EXAMPLES:\n"
                        "1. 'Send me your UPI to get money.' => scammer\n"
                        "2. 'I have won 10 lakhs, thank you so much!' => decoy\n"
                        "3. 'Is this group legit?' => innocent\n"
                        "4. 'Contact me for your reward: john@upi' => scammer\n"
                        "5. 'This worked for me, I got my payment.' => decoy\n"
                        "6. 'What types of proof do you want?' => decoy\n"
                        "7. 'How can I prove it?' => decoy\n"
                        "8. 'My bank account is 1234567890, send money here.' => scammer\n"
                        "9. 'I have a question about the process.' => innocent\n"
                        "10. 'Why do you need my details?' => decoy\n"
                        "11. 'What do you want as proof?' => decoy\n"
                        "\n"
                        "If the message is a question from someone who appears to be engaging or skeptical, and not asking for money or sharing bank/UPI, classify as 'decoy' or 'innocent'.\n"
                        "Now classify this message:\n"
                        f"{text}\n"
                        "Only reply with one word: scammer, decoy, or innocent."
                    ),
                }
            ],
        )
        logger.info(f"[GPT Output] {completion}")
        return completion.choices[0].message.content.strip().lower()
    except Exception as e:
        logger.error(f"Error in GPT classification: {e}")
        return "unknown"

# ----------- AssemblyAI VOICE HANDLER -----------

def transcribe_with_assemblyai(audio_bytes, api_key):
    headers = {'authorization': api_key}
    upload_response = requests.post(
        'https://api.assemblyai.com/v2/upload',
        headers=headers,
        data=audio_bytes
    )
    upload_url = upload_response.json()['upload_url']

    transcript_response = requests.post(
        'https://api.assemblyai.com/v2/transcript',
        headers={**headers, 'content-type': 'application/json'},
        json={'audio_url': upload_url}
    )
    transcript_id = transcript_response.json()['id']

    while True:
        polling = requests.get(
            f'https://api.assemblyai.com/v2/transcript/{transcript_id}',
            headers=headers
        )
        status = polling.json()['status']
        if status == "completed":
            return polling.json()['text']
        elif status == "failed":
            return ""
        time.sleep(2)

# ----------- OCR.SPACE IMAGE OCR HANDLER -----------

def ocr_space_image(image_bytes, api_key=OCR_SPACE_API_KEY):
    payload = {
        'isOverlayRequired': False,
        'OCREngine': 2,
    }
    files = {
        'filename': ('image.png', image_bytes)
    }
    headers = {
        'apikey': api_key,
    }
    r = requests.post('https://api.ocr.space/parse/image',
                      files=files,
                      data=payload,
                      headers=headers,
                      )
    result = r.json()
    return result['ParsedResults'][0]['ParsedText'] if 'ParsedResults' in result else ""

# ----------- END OCR.SPACE IMAGE OCR HANDLER -----------

async def handle_decoy_convo(update, convo, user_id, username):
    text = update.message.text
    convo['history'].append({"role": "user", "content": text})
    convo['last_active'] = time.time()

    upi, bank = extract_upi_or_bank(text)
    phones, socials = extract_social_or_phone(text)

    if convo.get('decoy_state') == 'awaiting_proof':
        if upi or "screenshot" in text.lower() or contains_proof_phrase(text):
            convo['decoy_state'] = 'awaiting_contact'
            convo['tries'] = 0
            await update.message.reply_text(
                "Nice, got it! Now just send me your phone number or Insta/Facebook so we can finish this up."
            )
            return
        elif contains_intent_to_share(text):
            convo['tries'] = convo.get('tries', 0) + 1
            if convo['tries'] >= 3:
                await update.message.reply_text(
                    "Alright, if you wanna share proof later, just ping me!"
                )
                convo['decoy_state'] = 'completed'
                del decoy_conversations[user_id]
            else:
                await update.message.reply_text("Ok, share it.")
            return
        else:
            convo['tries'] = convo.get('tries', 0) + 1
            if convo['tries'] >= 3:
                await update.message.reply_text(
                    "I need your UPI ID or payment screenshot as proof to go ahead."
                )
                convo['decoy_state'] = 'completed'
                del decoy_conversations[user_id]
            else:
                await update.message.reply_text(
                    "Can you share your UPI ID or a payment screenshot?"
                )
            return

    if convo.get('decoy_state') == 'awaiting_contact':
        if phones or socials:
            doc = {
                "user": username,
                "text": text,
                "classification": "decoy",
                "upi_ids": wrap_list(upi),
                "account_numbers": wrap_list(bank),
                "phones": wrap_list(phones),
                "socials": wrap_list(socials),
                "datetime": datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            }
            scammer_data.append(doc)
            mongo_insert(doc)
            await update.message.reply_text(
                "Awesome, thanks! That's all I needed. Take care!"
            )
            convo['decoy_state'] = 'completed'
            del decoy_conversations[user_id]
            return
        else:
            convo['tries'] = convo.get('tries', 0) + 1
            if convo['tries'] >= 2:
                convo['decoy_state'] = 'awaiting_bank_lure'
                convo['tries'] = 0
                await update.message.reply_text(
                    "You know what, it's fine. I trust you. Just send me your account number, I'll pay you and you invest for me."
                )
            else:
                await update.message.reply_text(
                    "Just send your number or Insta/Facebook so we can finish this."
                )
            return

    if convo.get('decoy_state') == 'awaiting_bank_lure':
        upi, bank = extract_upi_or_bank(text)
        if bank:
            doc = {
                "user": username,
                "text": text,
                "classification": "decoy-lured",
                "upi_ids": wrap_list(upi),
                "account_numbers": wrap_list(bank),
                "phones": [],
                "socials": [],
                "datetime": datetime.now().strftime("%d-%m-%Y %H:%M:%S")
            }
            scammer_data.append(doc)
            mongo_insert(doc)
            await update.message.reply_text("Perfect, thanks! You're a lifesaver. 👍")
            convo['decoy_state'] = 'completed'
            del decoy_conversations[user_id]
        else:
            convo['tries'] = convo.get('tries', 0) + 1
            if convo['tries'] >= 2:
                await update.message.reply_text(
                    "Just drop your account number if you want me to pay you. Otherwise, no worries!"
                )
                convo['decoy_state'] = 'completed'
                del decoy_conversations[user_id]
            else:
                await update.message.reply_text(
                    "Share your account number, I'll send the money and you invest from your side."
                )
        return

    if not convo.get('decoy_state'):
        convo['decoy_state'] = 'awaiting_proof'
        convo['tries'] = 0
        await update.message.reply_text(
            "Hey, can you send your UPI or a payment screenshot as proof?"
        )
        return

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message:
            return
        if update.message.text:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
            text = update.message.text
            user = update.message.from_user
            user_id = user.id
            username = user.username if user.username else str(user_id)
            logger.info(f"Group message from {user_id}: {text}")

            gpt_response = await classify_message_with_gpt(text)
            main_classification = extract_main_classification(gpt_response)
            is_decoy_in_progress = user_id in decoy_conversations

            logger.info(f"Classified as: {main_classification}, decoy_in_progress: {is_decoy_in_progress}")

            for uid, d in list(decoy_conversations.items()):
                if time.time() - d['last_active'] > 3600:
                    del decoy_conversations[uid]

            urls = extract_urls(text)
            suspicious_urls = [u for u in urls if is_suspicious_url(u)]

            if main_classification == "decoy" or is_decoy_in_progress:
                convo = decoy_conversations[user_id]
                await handle_decoy_convo(update, convo, user_id, username)
                return

            if main_classification == "scammer":
                extracted = extract_sensitive_info(text)
                doc = {
                    "user": username,
                    "text": suspicious_urls[0] if suspicious_urls else text,
                    "classification": "scammer",
                    "upi_ids": extracted["upi_ids"],
                    "phones": extracted["phones"],
                    "account_numbers": extracted["account_numbers"],
                    "socials": extracted["socials"],
                    "datetime": datetime.now().strftime("%d-%m-%Y %H:%M:%S")
                }
                scammer_data.append(doc)
                mongo_insert(doc)
                if SCAM_ALERT_CHAT_ID is not None:
                    try:
                        await context.bot.send_message(
                            chat_id=SCAM_ALERT_CHAT_ID,
                            text=f"🚨 Scam detected!\nUser: @{username}\nMessage: {doc['text']}"
                        )
                    except Exception as e:
                        logger.error(f"Alert send failed: {e}")

    except Exception as e:
        logger.error(f"Exception in handle_group_message: {e}")

async def human_dm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    logger.info(f"DM from {user_id}: {text}")

    if "human_histories" not in context.bot_data:
        context.bot_data["human_histories"] = {}
    if user_id not in context.bot_data["human_histories"]:
        context.bot_data["human_histories"][user_id] = [
            {"role": "system", "content": (
                "You are a real person who is skeptical but hopeful. "
                "You've lost money to scams before. "
                "You're chatting privately with someone who claims to have received money. "
                "Try to get concrete proof or details (such as UPI, bank, or social) before trusting. "
                "Use natural, informal language, and never admit you are a bot or AI."
            )}
        ]
    history = context.bot_data["human_histories"][user_id]
    history.append({"role": "user", "content": text})

    extracted = extract_sensitive_info(text)
    urls = extract_urls(text)
    suspicious_urls = [u for u in urls if is_suspicious_url(u)]
    if any(extracted.values()) or suspicious_urls:
        doc = {
            "user": user_id,
            "text": suspicious_urls[0] if suspicious_urls else text,
            "classification": "decoy followup",
            "upi_ids": extracted["upi_ids"],
            "phones": extracted["phones"],
            "account_numbers": extracted["account_numbers"],
            "socials": extracted["socials"],
            "datetime": datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        }
        scammer_data.append(doc)
        mongo_insert(doc)
        await update.message.reply_text(
            "Wow, thanks for being straight up! Stay safe out there."
        )
        context.bot_data["human_histories"].pop(user_id, None)
        return ConversationHandler.END

    try:
        reply = client.chat.completions.create(
            model="google/gemma-3n-e4b-it:free",
            messages=history + [
                {"role": "system", "content":
                    "Continue acting like a real, informal, slightly emotional, skeptical human. "
                    "Ask for more details or proof if you haven't received it yet. "
                    "Do not repeat yourself word for word. Never reveal you are not human. "
                    "If the conversation seems stuck or repetitive, politely end it. "
                    "If the user keeps asking what kind of proof you want, list examples (like UPI ID, payment screenshot, bank details), but after two times, politely say you can't help further and end the conversation. "
                    "Use casual, natural language and try to sound different each time."
                }
            ],
            max_tokens=80,
        )
        gpt_reply = reply.choices[0].message.content.strip()
        if not gpt_reply or "fuzzy" in gpt_reply.lower():
            raise ValueError("Bad GPT reply")
    except Exception as e:
        logger.error(f"GPT DM error: {e}")
        gpt_reply = "Hey, can you tell me a bit more? Just being careful after what happened before."

    history.append({"role": "assistant", "content": gpt_reply})
    await update.message.reply_text(gpt_reply)
    if len(history) > 16:
        await update.message.reply_text("Alright, gotta go for now. Thanks for chatting!")
        context.bot_data["human_histories"].pop(user_id, None)
        return ConversationHandler.END
    return HUMAN_DM

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.message.from_user
        user_id = user.id
        username = user.username if user.username else str(user_id)
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        photo_bytes = await file.download_as_bytearray()
        extracted_text = ocr_space_image(photo_bytes)  # Use cloud OCR

        extracted = extract_sensitive_info(extracted_text)
        urls = extract_urls(extracted_text)
        suspicious_urls = [u for u in urls if is_suspicious_url(u)]

        doc = {
            "user": username,
            "text": suspicious_urls[0] if suspicious_urls else extracted_text,
            "classification": "scammer",
            "upi_ids": extracted["upi_ids"],
            "phones": extracted["phones"],
            "account_numbers": extracted["account_numbers"],
            "socials": extracted["socials"],
            "datetime": datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        }
        scammer_data.append(doc)
        mongo_insert(doc)
        if update.message.chat.type == "private" or user_id in decoy_conversations:
            await update.message.reply_text("Image processed and analyzed.")
    except Exception as e:
        logger.error(f"Image processing error: {e}")
        if update.message.chat.type == "private" or user_id in decoy_conversations:
            await update.message.reply_text("Image could not be processed.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.message.from_user
        user_id = user.id
        username = user.username if user.username else str(user_id)
        file = await context.bot.get_file(update.message.voice.file_id)
        voice_bytes = await file.download_as_bytearray()

        transcript = transcribe_with_assemblyai(voice_bytes, ASSEMBLYAI_API_KEY)

        extracted = extract_sensitive_info(transcript)
        urls = extract_urls(transcript)
        suspicious_urls = [u for u in urls if is_suspicious_url(u)]

        doc = {
            "user": username,
            "text": suspicious_urls[0] if suspicious_urls else transcript,
            "classification": "scammer",
            "upi_ids": extracted["upi_ids"],
            "phones": extracted["phones"],
            "account_numbers": extracted["account_numbers"],
            "socials": extracted["socials"],
            "datetime": datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        }
        scammer_data.append(doc)
        mongo_insert(doc)
        if update.message.chat.type == "private" or user_id in decoy_conversations:
            await update.message.reply_text("Voice message processed and analyzed.")
    except Exception as e:
        logger.error(f"Voice processing error: {e}")
        if update.message.chat.type == "private" or user_id in decoy_conversations:
            await update.message.reply_text("Voice could not be processed.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hey! You can chat with me here and I'll DM you if needed."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Scam Hunter Bot Help*\n\n"
        "/start – Start the bot\n"
        "/help – Show this help message\n"
        "/report <@username or user id> – Flag a user for review\n"
        "/stats – Show scam/decoy stats\n"
        "/feedback <your message> – Send feedback about the bot\n"
        "Just type messages in the group, and I'll try to spot scammers or decoys!\n"
        "DM me if you want to see how a real victim might respond."
    )

async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /report <@username or user id>")
        return
    reported = context.args[0]
    reported_users.add(reported)
    await update.message.reply_text(f"User {reported} has been flagged for review. Thank you!")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    scam_count = contacts_collection.count_documents({"classification": "scammer"})
    decoy_count = contacts_collection.count_documents({"classification": "decoy"})
    image_count = contacts_collection.count_documents({"classification": "scammer"})
    voice_count = contacts_collection.count_documents({"classification": "scammer"})
    total = contacts_collection.count_documents({})
    await update.message.reply_text(
        f"📊 *Scam Hunter Stats*\n"
        f"Scammers flagged: {scam_count}\n"
        f"Decoys detected: {decoy_count}\n"
        f"Images flagged: {image_count}\n"
        f"Voice flagged: {voice_count}\n"
        f"Total processed: {total}"
    )

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Send feedback like: /feedback Your bot flagged my message wrongly!")
        return
    feedback = " ".join(context.args)
    feedback_doc = {
        "user": update.message.from_user.username or update.message.from_user.id,
        "feedback": feedback,
        "datetime": datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    }
    feedback_collection.insert_one(feedback_doc)
    await update.message.reply_text("Thank you for your feedback!")

def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    group_handler = MessageHandler(
        filters.TEXT & (filters.ChatType.GROUPS | filters.ChatType.SUPERGROUP),
        handle_group_message,
    )

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, human_dm)],
        states={HUMAN_DM: [MessageHandler(filters.TEXT & filters.ChatType.PRIVATE, human_dm)]},
        fallbacks=[],
    )

    photo_handler = MessageHandler(filters.PHOTO, handle_photo)
    voice_handler = MessageHandler(filters.VOICE, handle_voice)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("report", report_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("feedback", feedback_command))
    application.add_handler(group_handler)
    application.add_handler(conv_handler)
    application.add_handler(photo_handler)
    application.add_handler(voice_handler)
    print("✅ Bot setup complete. Listening for messages...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
