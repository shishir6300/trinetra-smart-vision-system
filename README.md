# 👁️ TRINETRA – AI Smart Assistive System

## 📌 Overview
Trinetra is a real-time smart assistive system designed to help visually impaired users interact with their surroundings using AI, voice commands, and computer vision.

The system integrates:
- Conversational AI  
- Voice input & output  
- Real-time image analysis  
- Live captions and translation  
- IoT-based wearable interface (ESP32 + OLED)

---

## 🚀 Features

### 🤖 AI Assist Mode
- Voice-activated assistant ("Hey Jarvis")
- Captures real-time images using ESP32 camera
- Uses AI (Vertex AI / Gemini) to analyze surroundings
- Provides spoken and displayed responses

---

### 📺 Live Captions
- Converts speech to text in real-time  
- Displays text on OLED screen  
- Helps hearing-impaired users  

---

### 🌍 Live Translation
- Detects multiple languages automatically  
- Translates speech into English  
- Supports 20+ global languages  
- Outputs both voice and text  

---

### 🔊 Voice Interaction
- Speech recognition using Google Speech API  
- Text-to-speech using pyttsx3  
- Hands-free interaction  

---

### 📡 IoT Integration (ESP32)
- ESP32 Camera captures real-time images  
- OLED display shows processed output  
- WiFi-based communication with backend  

---

## 🛠️ Tech Stack

### Backend
- Python  
- Flask  
- SpeechRecognition  
- pyttsx3  
- Vertex AI (Generative AI)  
- Deep Translator  

### Hardware
- ESP32-CAM  
- OLED Display (SSD1306)  

### Frontend
- HTML  
- CSS  
- JavaScript  

---
## ⚙️ Setup Instructions

### 1. Clone Repository
git clone https://github.com/your-username/trinetra-ai-smart-glasses.git  
cd trinetra-ai-smart-glasses  

---

### 2. Install Dependencies
pip install -r requirements.txt  

---

### 3. Setup Google Vertex AI
- Create a Google Cloud project  
- Enable Vertex AI  
- Authenticate:  
gcloud auth application-default login  

---

### 4. Configure Backend

Edit in your Python file:

ESP32_IP = "your esp32 IP address"  
vertexai.init(project="your-project-id", location="us-central1")  
model = GenerativeModel("your-model-name")  

---

### 5. Run Backend
python trinetra_backend.py  

---

### 6. Open Frontend
Open `index.html` in your browser  

---

## 🌐 API Endpoints

- /start/captions → Start live captions  
- /start/ai → Start AI assist  
- /start/translation → Start translation  

---

