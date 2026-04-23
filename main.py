import requests
import speech_recognition as sr
import pyttsx3
from PIL import Image
from io import BytesIO
import time
import threading
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from flask import Flask, jsonify
from flask_cors import CORS
from deep_translator import GoogleTranslator

# =========================
# 🔑 SETUP
# =========================

ESP32_IP = "http://10.249.189.113"

vertexai.init(project="dauntless-brace-457714-f7", location="us-central1")
model = GenerativeModel("gemini-2.5-flash")

recognizer = sr.Recognizer()

app = Flask(__name__)
CORS(app)

# =========================
# 🔀 EXCLUSIVE MODE CONTROL
# =========================

stop_event  = threading.Event()
active_mode = None
mode_lock   = threading.Lock()

# This flag blocks listening while Gemini is processing
gemini_busy = False

def switch_mode(new_mode, target_fn):
    global active_mode

    with mode_lock:
        if active_mode == new_mode:
            print(f"⚠️  {new_mode} is already active — ignoring duplicate request")
            return

        if active_mode is not None:
            print(f"🛑 Stopping [{active_mode}] before starting [{new_mode}]")
            stop_event.set()
            time.sleep(0.8)
            stop_event.clear()

        active_mode = new_mode

    t = threading.Thread(target=target_fn, daemon=True)
    t.start()
    print(f"✅ [{new_mode}] is now the only active mode")

# =========================
# 🔊 SPEAK
# =========================
def speak(text):
    try:
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as e:
        print("TTS error:", e)

# =========================
# 📺 SEND TEXT TO ESP32 OLED
# =========================
def send_to_esp32(text):
    try:
        requests.get(f"{ESP32_IP}/text", params={"msg": text}, timeout=3)
    except:
        print("⚠️ OLED send failed")

# =========================
# 🎤 VOICE LISTENER (standard)
# =========================
def listen(timeout=2, phrase_limit=5):
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.2)
            print("🎤 Listening...")
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)

        text = recognizer.recognize_google(audio)
        print("You said:", text)
        return text

    except sr.WaitTimeoutError:
        return ""
    except sr.UnknownValueError:
        return ""
    except Exception as e:
        print("Listen error:", e)
        return ""

# =========================
# 🌍 MULTILINGUAL LISTENER
# =========================

TRANSLATION_LANGUAGES = [
    "hi-IN", "te-IN", "ta-IN", "kn-IN", "ml-IN", "mr-IN", "bn-IN",
    "gu-IN", "pa-IN", "ur-IN", "fr-FR", "de-DE", "es-ES", "it-IT",
    "pt-PT", "ru-RU", "ja-JP", "ko-KR", "zh-CN", "ar-SA", "tr-TR",
    "nl-NL", "pl-PL", "sv-SE", "id-ID", "th-TH", "vi-VN", "en-US",
]

def listen_multilingual(timeout=4, phrase_limit=6):
    try:
        with sr.Microphone() as source:
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            print("🎤 Listening (multilingual)...")
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)

    except sr.WaitTimeoutError:
        return "", "unknown"
    except Exception as e:
        print("Mic error:", e)
        return "", "unknown"

    for lang_code in TRANSLATION_LANGUAGES:
        try:
            text = recognizer.recognize_google(audio, language=lang_code)
            if text.strip():
                print(f"✅ Recognized [{lang_code}]: {text}")
                return text, lang_code
        except sr.UnknownValueError:
            continue
        except Exception as e:
            print(f"Recognition error for {lang_code}: {e}")
            continue

    print("❌ Could not recognize speech in any language")
    return "", "unknown"

# =========================
# 📷 CAPTURE IMAGE
# =========================
def capture_image():
    try:
        response = requests.get(f"{ESP32_IP}/capture", timeout=5)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            img.save("captured.jpg")
            print("📸 Image saved")
            return "captured.jpg"
    except Exception as e:
        print("Camera error:", e)
    return None

# =========================
# 🤖 GEMINI ANALYSIS  (FIXED)
# — Complete summarized response
# — No punctuation or symbols
# — Does NOT return until fully done (blocks the loop)
# =========================
def analyze_image(path, query):
    global gemini_busy
    gemini_busy = True  # Block listener from restarting

    with open(path, "rb") as f:
        image_bytes = f.read()

    try:
        image_part = Part.from_data(data=image_bytes, mime_type="image/jpeg")

        # Prompt engineered for:
        # 1. Complete sentences (not cut off)
        # 2. No punctuation, commas, apostrophes, symbols
        # 3. Summarized in 2-3 sentences max
        # 4. Plain spoken words only — safe for OLED and TTS
        prompt = f"""
You are an AI assistant helping a visually impaired person.

Answer this question about the image: {query}

Rules you must follow strictly:
- Write a complete summarized answer in 2 to 3 sentences
- Do NOT cut off mid-sentence — finish your thought completely
- Use plain simple words only
- Do NOT use any punctuation at all — no commas no periods no apostrophes no colons no dashes no exclamation marks no question marks
- Do NOT use bullet points or numbered lists
- Do NOT use any special characters or symbols
- Write as if you are speaking out loud naturally
- Keep the total response under 200 characters
"""

        response = model.generate_content([prompt, image_part])

        # Clean up any punctuation that sneaks through
        import re
        result = response.text.strip()
        result = re.sub(r"[^\w\s]", "", result)   # remove all non-word, non-space chars
        result = re.sub(r"\s+", " ", result)       # collapse extra spaces
        result = result.strip()

        # Trim to 200 chars but only at a word boundary so it's never mid-word
        if len(result) > 200:
            result = result[:200].rsplit(" ", 1)[0]

        print("🤖 Gemini:", result)

        send_to_esp32(result)
        speak(result)

    except Exception as e:
        print("Gemini error:", e)

    finally:
        gemini_busy = False  # Release — listener can resume

# =========================
# 🤖 AI ASSIST MODE  (FIXED)
# — Waits for Gemini to finish before listening again
# =========================
def run_ai():
    global gemini_busy
    print("\n🤖 AI Assist Mode active (say 'hey jarvis ...')\n")

    while not stop_event.is_set():

        # Don't start listening if Gemini is still processing
        if gemini_busy:
            time.sleep(0.3)
            continue

        text = listen()

        if stop_event.is_set():
            break

        if text.lower().startswith("hey jarvis"):
            query = text.lower().replace("hey jarvis", "").strip()

            if query == "":
                query = "Describe surroundings"

            print("🧠 Query:", query)

            img = capture_image()
            if img:
                # analyze_image blocks until Gemini responds + TTS finishes
                analyze_image(img, query)

        else:
            if text:
                print("Ignored (no wake word):", text)

    print("🛑 AI Assist Mode stopped")

# =========================
# 📺 LIVE CAPTIONS MODE
# =========================
def run_live_captions():
    print("\n📺 Live Captions Mode active (continuous)\n")

    while not stop_event.is_set():
        text = listen(timeout=2, phrase_limit=5)

        if stop_event.is_set():
            break

        if text:
            print("📝 Caption:", text)
            send_to_esp32(text)

            if "stop captions" in text.lower():
                print("🛑 Voice-triggered captions stop")
                break

        time.sleep(0.2)

    print("🛑 Live Captions Mode stopped")

# =========================
# 🌍 LIVE TRANSLATION MODE
# =========================
def run_live_translation():
    print("\n🌍 Live Translation Mode active (Any language → English)\n")

    last_translated = ""

    while not stop_event.is_set():
        text, lang_code = listen_multilingual(timeout=4, phrase_limit=6)

        if stop_event.is_set():
            break

        if not text:
            time.sleep(0.2)
            continue

        try:
            if lang_code.startswith("en"):
                translated_text = text
                print(f"🌐 [English] No translation needed: {text}")
            else:
                base_lang = lang_code.split("-")[0]
                translated_text = GoogleTranslator(
                    source=base_lang,
                    target="en"
                ).translate(text)
                print(f"🌐 [{lang_code}] '{text}' → '{translated_text}'")

            oled_text = translated_text[:80]

            if oled_text != last_translated:
                send_to_esp32(oled_text)
                speak(translated_text)
                last_translated = oled_text

        except Exception as e:
            print(f"Translation error: {e}")
            send_to_esp32(text[:80])

        time.sleep(0.2)

    print("🛑 Live Translation Mode stopped")

# =========================
# 🌐 FLASK ROUTES
# =========================

@app.route("/start/captions", methods=["GET"])
def start_captions():
    print("🌐 Web triggered: Live Captions Mode")
    speak("Starting live captions")
    switch_mode("captions", run_live_captions)
    return jsonify({"status": "ok", "mode": "captions"})

@app.route("/start/ai", methods=["GET"])
def start_ai():
    print("🌐 Web triggered: AI Assist Mode")
    speak("Starting AI assist")
    switch_mode("ai", run_ai)
    return jsonify({"status": "ok", "mode": "ai"})

@app.route("/start/translation", methods=["GET"])
def start_translation():
    print("🌐 Web triggered: Live Translation Mode")
    speak("Starting live translation")
    switch_mode("translation", run_live_translation)
    return jsonify({"status": "ok", "mode": "translation"})

@app.route("/stop", methods=["GET"])
@app.route("/stop/captions", methods=["GET"])
@app.route("/stop/ai", methods=["GET"])
@app.route("/stop/translation", methods=["GET"])
def stop_all():
    global active_mode
    print("🌐 Web triggered: Stop all modes")
    stop_event.set()
    time.sleep(0.8)
    stop_event.clear()
    active_mode = None
    return jsonify({"status": "ok", "mode": None})

@app.route("/status", methods=["GET"])
def get_status():
    return jsonify({"status": "running", "active_mode": active_mode, "gemini_busy": gemini_busy})

# =========================
# ▶ START PROGRAM
# =========================
if __name__ == "__main__":
    print("================================")
    print("🚀 TRINETRA BACKEND SERVER")
    print("================================")
    print("🌐 Flask running on http://localhost:5000")
    print("   /start/captions    → Live Captions")
    print("   /start/ai          → AI Assist")
    print("   /start/translation → Live Translation")
    print("   /stop              → Stop all modes")
    print("   /status            → Check active mode")
    print("================================")

    app.run(host="0.0.0.0", port=5000, debug=False)