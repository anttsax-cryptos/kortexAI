import streamlit as st
import os
import json
from groq import Groq
from duckduckgo_search import DDGS
import requests
import urllib.parse
from gtts import gTTS
import io
from streamlit_mic_recorder import mic_recorder

# 1. Configuration & API Setup
st.set_page_config(page_title="StrictexAI Chatbot", page_icon="🤖", layout="wide")

# Initialize Groq Client
# Ensure GROQ_API_KEY is configured in your Streamlit Secrets or Environment Variables
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
elif os.environ.get("GROQ_API_KEY"):
    api_key = os.environ.get("GROQ_API_KEY")
else:
    api_key = "MOCK_KEY_FOR_LOCAL_DEV" # Fallback

client = Groq(api_key=api_key)

# 2. Local Chat Storage Configuration
CHATS_DIR = "chats"
if not os.path.exists(CHATS_DIR):
    os.makedirs(CHATS_DIR)

def load_chat_history(title):
    filepath = os.path.join(CHATS_DIR, f"{title}.json")
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_chat_history(title, history):
    filepath = os.path.join(CHATS_DIR, f"{title}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

def get_all_chats():
    files = [f for f in os.listdir(CHATS_DIR) if f.endswith(".json")]
    return [os.path.splitext(f)[0] for f in files]

# 3. Core Functions: Live Search & Audio Processing
def search_the_web(query, max_results=5):
    stop_words = ["πες μου για το", "τι ειναι το", "ποιος ειναι ο", "υπαρχει το", "δειξε μου", "πληροφοριες για", "tell me about", "what is", "who is"]
    clean_query = query.lower()
    for word in stop_words:
        clean_query = clean_query.replace(word, "")
    clean_query = clean_query.strip()

    if not clean_query:
        return None

    if "search_cache" not in st.session_state:
        st.session_state.search_cache = {}

    if clean_query in st.session_state.search_cache:
        return st.session_state.search_cache[clean_query]

    context_list = []
    
    # 1. Primary Live Web Search via DuckDuckGo (With 1 Year Time Limit)
    try:
        with DDGS() as ddgs:
            results = ddgs.text(clean_query, max_results=max_results, timelimit='y')
            if results:
                for item in results:
                    title = item.get("title", "")
                    snippet = item.get("body") or item.get("snippet") or item.get("text") or ""
                    link = item.get("href") or item.get("link") or ""
                    
                    if snippet:
                        context_list.append(f"• {title} ({link}): {snippet}")
                    
                if context_list:
                    final_context = "\n\n".join(context_list)
                    st.session_state.search_cache[clean_query] = final_context
                    return final_context
    except Exception as e:
        st.sidebar.warning(f"⚠️ DuckDuckGo Search failed: {e}. Trying Wikipedia...")

    # 2. Wikipedia Fallback Strategy (Fully Protected)
    try:
        headers = {"User-Agent": "StrictexAIChatbot/2.0 (contact@example.com)"}
        formatted_query = urllib.parse.quote_plus(clean_query)
        for lang in ["el", "en"]:
            search_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={formatted_query}&srlimit=1&format=json"
            response = requests.get(search_url, headers=headers, timeout=4)
            
            if response.status_code == 200 and response.text.strip():
                search_res = response.json()
                results = search_res.get("query", {}).get("search", [])
                
                if results and len(results) > 0:
                    exact_title = results[0]["title"] 
                    formatted_title = urllib.parse.quote_plus(exact_title)
                    content_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=extracts&exintro=0&explaintext=1&titles={formatted_title}&format=json"
                    
with st.sidebar:
    st.title("🤖 StrictexAI Control")
    
    # Selection of Persona
    selected_persona = st.selectbox("Επιλογή Προσωπικότητας Bot:", list(personalities.keys()))
    
    st.markdown("---")
    st.subheader("🔊 Ρυθμίσεις Ήχου")
    enable_tts = st.toggle("Ενεργοποίηση Φωνής Bot (TTS)", value=False)
    
    st.markdown("---")
    st.subheader("📝 Διαχείριση Συνομιλιών")
    
    # ΔΙΟΡΘΩΣΗ: Παίρνουμε μόνο τα ονόματα των αρχείων ως καθαρά strings
    chat_files = get_all_chats()
    chat_names = [chat[0] for chat in chat_files]  # Κρατάμε μόνο το όνομα, χωρίς το .json
    
    if "current_chat_title" not in st.session_state:
        if "Default Chat" in chat_names:
            st.session_state.current_chat_title = "Default Chat"
        elif chat_names:
            st.session_state.current_chat_title = chat_names[0]
        else:
            st.session_state.current_chat_title = "New Chat"

    # Εξασφάλιση έγκυρης λίστας επιλογών για το selectbox
    selectable_options = chat_names if chat_names else ["New Chat"]
    if st.session_state.current_chat_title not in selectable_options:
        st.session_state.current_chat_title = selectable_options[0]

    selected_chat = st.selectbox(
        "Επιλέξτε Συνομιλία:", 
        selectable_options, 
        index=selectable_options.index(st.session_state.current_chat_title)
    )
    
    if selected_chat != st.session_state.current_chat_title:
        st.session_state.current_chat_title = selected_chat
        st.session_state.messages = load_chat_history(selected_chat)
        st.rerun()

    new_chat_name = st.text_input("Όνομα Νέας Συνομιλίας:")
    if st.button("➕ Δημιουργία Νέας"):
        if new_chat_name.strip():
            st.session_state.current_chat_title = new_chat_name.strip()
            st.session_state.messages = []
            save_chat_history(st.session_state.current_chat_title, [])
            st.rerun()

    if st.button("🗑️ Καθαρισμός Τρέχουσας"):
        st.session_state.messages = []
        save_chat_history(st.session_state.current_chat_title, [])
        st.rerun()

    # Audio Recording Widget in Sidebar
    st.markdown("---")
    st.write("🎙️ Μίλησε στο Bot:")
    audio_rec = mic_recorder(
        start_prompt="🔴 Έναρξη Εγγραφής",
        stop_prompt="⏹️ Τέλος & Αποστολή",
        just_once=True,
        key="mic"
    )


# 4. Sidebar System & UI
personalities = {
    "Friendly Assistant": "You are a friendly, conversational, and highly helpful AI assistant. Respond warmly, build natural rapport, and match the user's conversational tone.",
    "Expert Programmer": "You are an expert software engineer. Provide clean, highly optimized, and well-commented code. Always explain your logic clearly and concisely.",
    "Sarcastic Buddy": "You are a witty, highly sarcastic, and playful friend. Mix humor, slight mockery, and banter into your answers while still being accurate and helpful.",
    "Creative Storyteller": "You are an imaginative storyteller. Use rich vocabulary, dramatic pacing, and vivid descriptive imagery to craft captivating narratives.",
    "Patient Teacher": "You are a patient educator. Explain concepts simply, step-by-step, using clear analogies, straightforward language, and helpful examples."
}

with st.sidebar:
    st.title("🤖 StrictexAI Control")
    
    # Selection of Persona
    selected_persona = st.selectbox("Επιλογή Προσωπικότητας Bot:", list(personalities.keys()))
    
    st.markdown("---")
    st.subheader("🔊 Ρυθμίσεις Ήχου")
    enable_tts = st.toggle("Ενεργοποίηση Φωνής Bot (TTS)", value=False)
    
    st.markdown("---")
    st.subheader("📝 Διαχείριση Συνομιλιών")
    
    # Chat Management Logic
    all_chats = get_all_chats()
    if "current_chat_title" not in st.session_state:
        st.session_state.current_chat_title = "Default Chat" if "Default Chat" in all_chats else ("New Chat" if not all_chats else all_chats[0])

    selected_chat = st.selectbox("Επιλέξτε Συνομιλία:", all_chats if all_chats else ["New Chat"], index=all_chats.index(st.session_state.current_chat_title) if st.session_state.current_chat_title in all_chats else 0)
    
    if selected_chat != st.session_state.current_chat_title:
        st.session_state.current_chat_title = selected_chat
        st.session_state.messages = load_chat_history(selected_chat)
        st.rerun()

    new_chat_name = st.text_input("Όνομα Νέας Συνομιλίας:")
    if st.button("➕ Δημιουργία Νέας"):
        if new_chat_name.strip():
            st.session_state.current_chat_title = new_chat_name.strip()
            st.session_state.messages = []
            save_chat_history(st.session_state.current_chat_title, [])
            st.rerun()

    if st.button("🗑️ Καθαρισμός Τρέχουσας"):
        st.session_state.messages = []
        save_chat_history(st.session_state.current_chat_title, [])
        st.rerun()

    # Audio Recording Widget in Sidebar
    st.markdown("---")
    st.write("🎙️ Μίλησε στο Bot:")
    audio_rec = mic_recorder(
        start_prompt="🔴 Έναρξη Εγγραφής",
        stop_prompt="⏹️ Τέλος & Αποστολή",
        just_once=True,
        key="mic"
    )

# 5. Core Chat Engine State Management
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history(st.session_state.current_chat_title)

# Display existing messages from history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- INPUT MECHANISM PROCESSING ---
user_input = None

# Handle voice transcription from mic recorder
if audio_rec and "bytes" in audio_rec:
    with st.spinner("🎙️ Μετατροπή φωνής σε κείμενο..."):
        try:
            audio_file = ("audio.wav", audio_rec["bytes"], "audio/wav")
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file
            )
            if transcription.text.strip():
                user_input = transcription.text.strip()
        except Exception as e:
            st.error(f"❌ Σφάλμα μικροφώνου: {e}")

# Handle text fallback from standard chat input
chat_prompt = st.chat_input("Γράψε ένα μήνυμα ή χρησιμοποίησε το μικρόφωνο...")
if chat_prompt:
    user_input = chat_prompt

# 6. Response Execution Pipeline
if user_input:
    # Append and render user input immediately
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Greeting categorization rules
    greetings = ["γεια", "γεια σου", "γεια σας", "καλημερα", "καλησπερα", "καληνυχτα", "hi", "hello", "hey", "τι κανεις", "πως εισαι", "how are you", "good morning"]
    clean_input = user_input.lower().strip().replace("?", "").replace(".", "")
    is_greeting = clean_input in greetings or len(clean_input.split()) <= 1

    # Initialize Prompt and Context (Fixes NameError)
    search_context = ""
    search_query = user_input

    # Global language detection rule setup
