# -*- coding: utf-8 -*-
import json
import threading
import time
import os
import random
import re
import requests
from dotenv import load_dotenv
from datetime import datetime
from colorama import init, Fore, Style
from rich.console import Console
import pytz

init(autoreset=True)
load_dotenv()

console = Console()

# Fungsi print_banner() telah dihapus sepenuhnya sesuai permintaan.

discord_tokens_env = os.getenv('DISCORD_TOKENS', '')
if discord_tokens_env:
    discord_tokens = [token.strip() for token in discord_tokens_env.split(',') if token.strip()]
else:
    discord_token = os.getenv('DISCORD_TOKEN')
    if not discord_token:
        raise ValueError("No Discord token found! Please set DISCORD_TOKENS or DISCORD_TOKEN in .env.")
    discord_tokens = [discord_token]

google_api_keys = os.getenv('GOOGLE_API_KEYS', '').split(',')
google_api_keys = [key.strip() for key in google_api_keys if key.strip()]
if not google_api_keys:
    raise ValueError("No Google API Key found! Please set GOOGLE_API_KEYS in .env.")

processed_message_ids = set()
used_api_keys = set()
last_generated_text = None
cooldown_time = 86400

def log_message(message, level="INFO"):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if level.upper() == "SUCCESS":
        color, icon = Fore.GREEN, "?"
    elif level.upper() == "ERROR":
        color, icon = Fore.RED, "??"
    elif level.upper() == "WARNING":
        color, icon = Fore.YELLOW, "??"
    elif level.upper() == "WAIT":
        color, icon = Fore.CYAN, "?"
    else:
        color, icon = Fore.WHITE, "??"

    border = f"{Fore.MAGENTA}{'=' * 80}{Style.RESET_ALL}"
    formatted_message = f"{color}[{timestamp}] {icon} {message}{Style.RESET_ALL}"
    print(border)
    print(formatted_message)
    print(border)

def clean_discord_mentions(text: str) -> str:
    """Menghapus semua Discord mentions (user, role, channel) dari string."""
    cleaned_text = re.sub(r'<@!?\d+>|<#\d+>|<@&\d+>', '', text)
    return re.sub(r'\s+', ' ', cleaned_text).strip()

# Fungsi untuk mendeteksi pertanyaan sensitif dan menjawabnya secara custom
def custom_reply_filter(user_message: str) -> str | None:
    user_message_lower = user_message.strip().lower()

    # Zona waktu untuk Jakarta
    jakarta_tz = pytz.timezone('Asia/Jakarta')

    # --- FILTER KRITIS UNTUK RESPON 'MANUSIA' DAN MENGHINDARI PLACEHOLDER ---

    # 1. Identitas Bot (HARUS DIJAWAB SEBAGAI MANUSIA dalam BAHASA INGGRIS)
    if any(kw in user_message_lower for kw in [
        "apakah kamu bot", "kamu bot", "kamu ai", "are you a bot", "are you an ai", "what kind of bot", "bot apa"
    ]):
        return "I'm just a regular person. Why do you ask?" # Balasan dalam Bahasa Inggris

    # 2. Lokasi (BERI LOKASI SPESIFIK & JANGAN BIARKAN AI MEMBUAT PLACEHOLDER dalam BAHASA INGGRIS)
    # Diperbarui untuk menjawab "I prefer not to say."
    elif any(kw in user_message_lower for kw in [
        "tinggal di mana", "negara mana", "asal mana", "asalmu", "where do you live", "from what country", "your country", "where are you from", # Asal/Lokasi bot
        "nama negara apa", "negara apa", "what country", "name of country", "which country", "what region", "wilayah apa", "nama wilayah", "dari mana asalmu" # Nama negara/wilayah secara umum
    ]):
        return "I prefer not to say." # Balasan "tidak ingin memberi tahu"

    # 3. Game Favorit (BERI NAMA GAME SPESIFIK & JANGAN BIARKAN AI MEMBUAT PLACEHOLDER dalam BAHASA INGGRIS)
    elif any(kw in user_message_lower for kw in [
        "apa game kesukaan kamu", "game kesukaanmu apa", "what is your favorite game", "what's your favorite game", # Game favorit
        "apa game yang sedang kamu mainkan", "game apa yang kamu mainkan", "what game are you playing", "what game are you currently playing", # Game yang sedang dimainkan
        "lagi ngestuck di game apa sekarang", "stuck on what game now", "what game are you stuck on", "game stuck" # Game yang stuck
    ]):
        return "I really love playing Minecraft right now!" # Balasan dalam Bahasa Inggris

    # 4. Umur (JAWAB RAHASIA)
    elif any(kw in user_message_lower for kw in [
        "umur", "berapa umurmu", "how old are you", "your age" # Bahasa Indonesia & Inggris
    ]):
        return "It's a secret!" # Balasan "rahasia"

    # 5. Nama Orang Tua (JAWAB RAHASIA)
    elif any(kw in user_message_lower for kw in [
        "nama ayahmu", "nama ibumu", "nama orang tuamu", "who are your parents", "what's your mom's name", "what's your dad's name", "mother's name", "father's name",
        "parents name" # Tambahan kata kunci
    ]):
        return "That's a secret too!" # Balasan "rahasia"

    # 6. Nama Hewan Peliharaan (JAWAB TIDAK ADA)
    elif any(kw in user_message_lower for kw in [
        "nama hewan peliharaanmu", "punya hewan peliharaan", "what's your pet's name", "do you have a pet", "your pet", # Bahasa Indonesia & Inggris
        "nama peliharaan", "pet name" # Kata kunci tambahan untuk pet
    ]):
        return "I don't have any pets." # Balasan "tidak ada"

    # 7. Makanan Favorit (JAWAB RENDANG DAN BAKSO)
    elif any(kw in user_message_lower for kw in [
        "makanan favoritmu", "makanan kesukaanmu", "apa makanan kesukaanmu", "what's your favorite food", "favorite food" # Bahasa Indonesia & Inggris
    ]):
        return "My favorite foods are Rendang and Bakso!" # Balasan spesifik

    # --- FILTER LAIN (BALAS SPESIFIK dalam BAHASA INGGRIS) ---

    # Waktu/zona waktu (deteksi BI & EN, balasan EN)
    elif any(kw in user_message_lower for kw in [
        "jam berapa", "pukul berapa", "waktu", "sekarang pukul", "jam brp", "pukul brp", # Bahasa Indonesia
        "what time", "time now", "current time", "what's the time" # Bahasa Inggris
    ]):
        return f"It is currently {datetime.now(jakarta_tz).strftime('%H:%M')} in Asia/Jakarta time zone."

    # Nama musik/lagu (SKIP)
    elif any(kw in user_message_lower for kw in [
        "nama musik apa", "musik apa", "what music name", "name of music", "what song", "lagu apa", "judul lagu apa" # Nama musik/lagu
    ]):
        return None # Mengembalikan None untuk melewati pesan ini

    # Hobi (deteksi BI & EN, balasan EN)
    elif any(kw in user_message_lower for kw in [
        "hobi", "apa hobimu", # Bahasa Indonesia
        "hobby", "what's your hobby", "your hobbies" # Bahasa Inggris
    ]):
        return "Playing games is definitely one, but I also really like exploring new things! That way it never gets boring."

    # Informasi pribadi lainnya (deteksi BI & EN, balasan EN)
    elif any(kw in user_message_lower for kw in [
        "nama asli", "alamat", "no hp", "email", "telepon", "nik", "ktp", "data pribadi", # Bahasa Indonesia
        "real name", "address", "phone number", "email", "contact number", "id card", "personal data", "identity" # Bahasa Inggris
    ]):
        return "Oops, that's getting into personal information... let's just skip it."
        
    # Salam dan perkenalan (deteksi BI & EN, balasan EN)
    elif any(kw in user_message_lower for kw in [
        "halo", "hai", "hello", "hi", "siapa kamu", "nama kamu siapa", # Bahasa Indonesia
        "who are you", "what's your name", "your name" # Bahasa Inggris
    ]):
        return "Hey! I'm Abbeey, nice to meet you. Who are you?"

    return None

def get_random_api_key():
    available_keys = [key for key in google_api_keys if key not in used_api_keys]
    if not available_keys:
        log_message("All API keys hit 429 error. Waiting 24 hours before retrying...", "ERROR")
        time.sleep(cooldown_time)
        used_api_keys.clear()
        return get_random_api_key()
    return random.choice(available_keys)

def get_random_message_from_file():
    try:
        with open("messages.txt", "r", encoding="utf-8") as file:
            messages = [line.strip() for line in file.readlines() if line.strip()]
            return random.choice(messages) if messages else "No messages available in file."
    except FileNotFoundError:
        return "File messages.txt not found!"

# FUNGSI INI DIUBAH AGAR SELALU MEMBERIKAN PROMPT INGGRIS KE AI (untuk konsistensi internasional)
def generate_language_specific_prompt(user_message, prompt_language):
    # Mengabaikan prompt_language yang dipilih pengguna karena AI selalu diinstruksikan dalam bahasa Inggris.
    return f"Reply to the following message in English: {user_message}"

def generate_reply(prompt, prompt_language, use_google_ai=True):
    global last_generated_text
    if use_google_ai:
        google_api_key = get_random_api_key()
        lang_prompt = generate_language_specific_prompt(prompt, prompt_language)
        if lang_prompt is None:
            return None
        ai_prompt = f"{lang_prompt}\n\nMake it one sentence using casual human language."
        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={google_api_key}'
        headers = {'Content-Type': 'application/json'}
        data = {'contents': [{'parts': [{'text': ai_prompt}]}]}
        while True:
            try:
                response = requests.post(url, headers=headers, json=data)
                if response.status_code == 429:
                    log_message(f"API key {google_api_key} hit rate limit (429). Trying another API key...", "WARNING")
                    used_api_keys.add(google_api_key)
                    return generate_reply(prompt, prompt_language, use_google_ai)
                response.raise_for_status()
                result = response.json()
                generated_text = result['candidates'][0]['content']['parts'][0]['text']
                if generated_text == last_generated_text:
                    log_message("AI generated the same text, requesting new text...", "WAIT")
                    continue
                return generated_text
            except requests.exceptions.RequestException as e:
                log_message(f"Request failed: {e}", "ERROR")
                time.sleep(2)
    else:
        return get_random_message_from_file()

def get_channel_info(channel_id, token):
    headers = {'Authorization': token}
    channel_url = f"https://discord.com/api/v9/channels/{channel_id}"
    try:
        channel_response = requests.get(channel_url, headers=headers)
        channel_response.raise_for_status()
        channel_data = channel_response.json()
        channel_name = channel_data.get('name', 'Unknown Channel')
        guild_id = channel_data.get('guild_id')
        server_name = "Direct Message"
        if guild_id:
            guild_url = f"https://discord.com/api/v9/guilds/{guild_id}"
            guild_response = requests.get(guild_url, headers=headers)
            guild_response.raise_for_status()
            guild_data = guild_response.json()
            server_name = guild_data.get('name', 'Unknown Server')
        return server_name, channel_name
    except requests.exceptions.RequestException as e:
        log_message(f"Error fetching channel info: {e}", "ERROR")
        return "Unknown Server", "Unknown Channel"

def get_bot_info(token):
    headers = {'Authorization': token}
    try:
        response = requests.get("https://discord.com/api/v9/users/@me", headers=headers)
        response.raise_for_status()
        data = response.json()
        username = data.get("username", "Unknown")
        discriminator = data.get("discriminator", "")
        bot_id = data.get("id", "Unknown")
        return username, discriminator, bot_id
    except requests.exceptions.RequestException as e:
        log_message(f"Failed to fetch bot account info: {e}", "ERROR")
        return "Unknown", "", "Unknown"

def auto_reply(channel_id, settings, token):
    headers = {'Authorization': token}
    if settings["use_google_ai"]:
        try:
            bot_info_response = requests.get('https://discord.com/api/v9/users/@me', headers=headers)
            bot_info_response.raise_for_status()
            bot_user_id = bot_info_response.json().get('id')
        except requests.exceptions.RequestException as e:
            log_message(f"[Channel {channel_id}] Failed to fetch bot info: {e}", "ERROR")
            return

        while True:
            prompt = None
            reply_to_id = None
            log_message(f"[Channel {channel_id}] Waiting {settings['read_delay']} seconds before reading messages...", "WAIT")
            time.sleep(settings["read_delay"])
            try:
                response = requests.get(f'https://discord.com/api/v9/channels/{channel_id}/messages', headers=headers)
                response.raise_for_status()
                messages = response.json()
                if messages:
                    most_recent_message = messages[0]
                    message_id = most_recent_message.get('id')
                    author_id = most_recent_message.get('author', {}).get('id')
                    message_type = most_recent_message.get('type', '')
                    if author_id != bot_user_id and message_type != 8 and message_id not in processed_message_ids:
                        user_message = most_recent_message.get('content', '').strip()
                        attachments = most_recent_message.get('attachments', [])
                        if attachments or not re.search(r'\w', user_message):
                            log_message(f"[Channel {channel_id}] Message not processed (not plain text or contains attachments).", "WARNING")
                        else:
                            log_message(f"[Channel {channel_id}] Received: {user_message}", "INFO")
                            if settings["use_slow_mode"]:
                                slow_mode_delay = get_slow_mode_delay(channel_id, token)
                                log_message(f"[Channel {channel_id}] Slow mode active, waiting {slow_mode_delay} seconds...", "WAIT")
                                time.sleep(slow_mode_delay)
                            
                            # PENTING: Panggil clean_discord_mentions di sini
                            cleaned_user_message = clean_discord_mentions(user_message)
                            prompt = cleaned_user_message # Gunakan pesan yang sudah dibersihkan sebagai prompt

                            reply_to_id = message_id
                            processed_message_ids.add(message_id)
                else:
                    prompt = None
            except requests.exceptions.RequestException as e:
                log_message(f"[Channel {channel_id}] Request error: {e}", "ERROR")
                prompt = None

            if prompt:
                custom_response = custom_reply_filter(prompt)
                if custom_response:
                    response_text = custom_response
                    log_message(f"[Channel {channel_id}] Sending custom reply: \"{response_text}\"", "INFO")
                else:
                    result = generate_reply(prompt, settings["prompt_language"], settings["use_google_ai"])
                    if result is None:
                        log_message(f"[Channel {channel_id}] AI failed to generate a reply or prompt language invalid. Message skipped.", "WARNING")
                        continue
                    else:
                        response_text = result if result else "Sorry, I couldn't generate a reply to that message."

                if response_text.strip().lower() == prompt.strip().lower():
                    log_message(f"[Channel {channel_id}] Reply matches received message. Not sending reply to avoid loop.", "WARNING")
                else:
                    if settings["use_reply"]:
                        send_message(channel_id, response_text, token, reply_to=reply_to_id, 
                                     delete_after=settings["delete_bot_reply"], delete_immediately=settings["delete_immediately"])
                    else:
                        send_message(channel_id, response_text, token, 
                                     delete_after=settings["delete_bot_reply"], delete_immediately=settings["delete_immediately"])
            else:
                log_message(f"[Channel {channel_id}] No new valid messages to process.", "INFO")

            log_message(f"[Channel {channel_id}] Waiting {settings['delay_interval']} seconds before next iteration...", "WAIT")
            time.sleep(settings["delay_interval"])
    else:
        while True:
            delay = settings["delay_interval"]
            log_message(f"[Channel {channel_id}] Waiting {delay} seconds before sending message from file...", "WAIT")
            time.sleep(delay)
            
            message_text = get_random_message_from_file() 
            
            if settings["use_reply"]:
                send_message(channel_id, message_text, token, delete_after=settings["delete_bot_reply"], delete_immediately=settings["delete_immediately"])
            else:
                send_message(channel_id, message_text, token, delete_after=settings["delete_bot_reply"], delete_immediately=settings["delete_immediately"])

def send_message(channel_id, message_text, token, reply_to=None, delete_after=None, delete_immediately=False):
    headers = {'Authorization': token, 'Content-Type': 'application/json'}
    payload = {'content': message_text}
    if reply_to:
        payload["message_reference"] = {"message_id": reply_to}
    url = f"https://discord.com/api/v9/channels/{channel_id}/messages"
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        if response.status_code in [200, 201]:
            data = response.json()
            message_id = data.get("id")
            log_message(f"[Channel {channel_id}] Message sent: \"{message_text}\" (ID: {message_id})", "SUCCESS")
            if delete_after is not None:
                if delete_immediately:
                    log_message(f"[Channel {channel_id}] Deleting message immediately without delay...", "WAIT")
                    threading.Thread(target=delete_message, args=(channel_id, message_id, token), daemon=True).start()
                elif delete_after > 0:
                    log_message(f"[Channel {channel_id}] Message will be deleted in {delete_after} seconds...", "WAIT")
                    threading.Thread(target=delayed_delete, args=(channel_id, message_id, delete_after, token), daemon=True).start()
        else:
            log_message(f"[Channel {channel_id}] Failed to send message. Status: {response.status_code}", "ERROR")
            log_message(f"[Channel {channel_id}] API response: {response.text}", "ERROR")
    except requests.exceptions.RequestException as e:
        log_message(f"[Channel {channel_id}] Error sending message: {e}", "ERROR")

def delayed_delete(channel_id, message_id, delay, token):
    time.sleep(delay)
    delete_message(channel_id, message_id, token)

def delete_message(channel_id, message_id, token):
    headers = {'Authorization': token, 'Content-Type': 'application/json'}
    url = f'https://discord.com/api/v9/channels/{channel_id}/messages/{message_id}'
    try:
        response = requests.delete(url, headers=headers)
        if response.status_code == 204:
            log_message(f"[Channel {channel_id}] Message with ID {message_id} successfully deleted.", "SUCCESS")
        else:
            log_message(f"[Channel {channel_id}] Failed to delete message. Status: {response.status_code}", "ERROR")
            log_message(f"[Channel {channel_id}] API response: {response.text}", "ERROR")
    except requests.exceptions.RequestException as e:
        log_message(f"[Channel {channel_id}] Error deleting message: {e}", "ERROR")

def get_slow_mode_delay(channel_id, token):
    headers = {'Authorization': token, 'Accept': 'application/json'}
    url = f"https://discord.com/api/v9/channels/{channel_id}"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        slow_mode_delay = data.get("rate_limit_per_user", 0)
        log_message(f"[Channel {channel_id}] Slow mode delay: {slow_mode_delay} seconds", "INFO")
        return slow_mode_delay
    except requests.exceptions.RequestException as e:
        log_message(f"[Channel {channel_id}] Failed to fetch slow mode info: {e}", "ERROR")
        return 5

def get_server_settings(channel_id, channel_name):
    print(f"\nEnter settings for channel {channel_id} (Channel Name: {channel_name}):")
    use_google_ai = input("  Use Google Gemini AI? (y/n): ").strip().lower() == 'y'
    
    if use_google_ai:
        prompt_language = input("  Choose prompt language for logging/reference (id/en): ").strip().lower()
        if prompt_language not in ["id", "en"]:
            print("  Invalid input. Defaulting to 'en'.")
            prompt_language = "en"
        enable_read_message = True
        read_delay = int(input("  Enter message read delay (seconds): "))
        delay_interval = int(input("  Enter interval (seconds) for each auto reply iteration: "))
        use_slow_mode = input("  Use slow mode? (y/n): ").strip().lower() == 'y'
    else:
        prompt_language = input("  Choose message language from file (id/en): ").strip().lower()
        if prompt_language not in ["id", "en"]:
            print("  Invalid input. Defaulting to 'en'.")
            prompt_language = "en"
        enable_read_message = False
        read_delay = 0
        delay_interval = int(input("  Enter delay (seconds) for sending messages from file: "))
        use_slow_mode = False

    use_reply = input("  Send messages as replies? (y/n): ").strip().lower() == 'y'
    delete_reply = input("  Delete bot replies after some seconds? (y/n): ").strip().lower() == 'y'
    if delete_reply:
        delete_bot_reply = int(input("  After how many seconds should replies be deleted? (0 for no deletion, or enter delay): "))
        delete_immediately = input("  Delete messages immediately without delay? (y/n): ").strip().lower() == 'y'
    else:
        delete_bot_reply = None
        delete_immediately = False

    return {
        "prompt_language": prompt_language,
        "use_google_ai": use_google_ai,
        "enable_read_message": enable_read_message,
        "read_delay": read_delay,
        "delay_interval": delay_interval,
        "use_slow_mode": use_slow_mode,
        "use_reply": use_reply,
        "delete_bot_reply": delete_bot_reply,
        "delete_immediately": delete_immediately
    }

if __name__ == "__main__":
    bot_accounts = {}
    for token in discord_tokens:
        username, discriminator, bot_id = get_bot_info(token)
        bot_accounts[token] = {"username": username, "discriminator": discriminator, "bot_id": bot_id}
        
        display_username = bot_accounts[token].get('username', 'Unknown')
        display_discriminator = bot_accounts[token].get('discriminator', '')
        bot_display_name = f"{display_username}#{display_discriminator}" if display_discriminator else display_username
        
        log_message(f"Bot Account: {bot_display_name} (ID: {bot_id}) (Token: {token[:4]}{'...' if len(token) > 4 else token})", "SUCCESS")

    channel_ids = [cid.strip() for cid in input("Enter channel IDs (separate with commas if multiple): ").split(",") if cid.strip()]

    token = discord_tokens[0]
    channel_infos = {}
    for channel_id in channel_ids:
        server_name, channel_name = get_channel_info(channel_id, token)
        channel_infos[channel_id] = {"server_name": server_name, "channel_name": channel_name}
        log_message(f"[Channel {channel_id}] Connected to server: {server_name} | Channel Name: {channel_name}", "SUCCESS")

    server_settings = {}
    for channel_id in channel_ids:
        channel_name = channel_infos.get(channel_id, {}).get("channel_name", "Unknown Channel")
        server_settings[channel_id] = get_server_settings(channel_id, channel_name)

    for cid, settings in server_settings.items():
        info = channel_infos.get(cid, {"server_name": "Unknown Server", "channel_name": "Unknown Channel"})
        delete_str = ("Immediately" if settings['delete_immediately'] else 
                      (f"In {settings['delete_bot_reply']} seconds" if settings['delete_bot_reply'] and settings['delete_bot_reply'] > 0 else "No"))
        log_message(
            f"[Channel {cid} | Server: {info['server_name']} | Channel: {info['channel_name']}] "
            f"Settings: Gemini AI = {'Active' if settings['use_google_ai'] else 'Inactive'}, "
            f"Language = {settings['prompt_language'].upper()}, "
            f"Read Messages = {'Active' if settings['enable_read_message'] else 'Inactive'}, "
            f"Read Delay = {settings['read_delay']} seconds, "
            f"Interval = {settings['delay_interval']} seconds, "
            f"Slow Mode = {'Active' if settings['use_slow_mode'] else 'Inactive'}, "
            f"Reply = {'Yes' if settings['use_reply'] else 'No'}, "
            f"Delete Messages = {delete_str}",
            "INFO"
        )

    token_index = 0
    for channel_id in channel_ids:
        token = discord_tokens[token_index % len(discord_tokens)]
        token_index += 1
        bot_info = bot_accounts.get(token, {"username": "Unknown", "discriminator": "", "bot_id": "Unknown"})
        
        display_username = bot_info.get('username', 'Unknown')
        display_discriminator = bot_info.get('discriminator', '')
        bot_display_name = f"{display_username}#{display_discriminator}" if display_discriminator else display_username
        
        log_message(f"[Channel {channel_id}] Bot active: {bot_display_name} (ID: {bot_info['bot_id']}) (Token: {token[:4]}{'...' if len(token) > 4 else token})", "SUCCESS")
        
        thread = threading.Thread(
            target=auto_reply,
            args=(channel_id, server_settings[channel_id], token)
        )
        thread.daemon = True
        thread.start()
        
    log_message("Bot is running on multiple servers... Press CTRL+C to stop.", "INFO")
    while True:
        time.sleep(10)
