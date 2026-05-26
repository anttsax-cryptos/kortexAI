import streamlit as st
import json
import os
import datetime
import requests
import urllib.parse
from groq import Groq
from duckduckgo_search import DDGS
from streamlit_mic_recorder import mic_recorder

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="StrictexAI v2", layout="wide", page_icon="🤖")

# Directory for saving chat history locally
CHATS_DIR = "chats"
if not os.path.exists(CHATS_DIR):
    os.makedirs(CHATS_DIR)

# Check for API Key in Streamlit Secrets
if "GROQ_API_KEY" not in st.secrets:
    st.error("⚠ Please add your GROQ_API_KEY in Streamlit Secrets!")
    st.stop()

# Initialize Groq Client
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# System Prompts / Personas
personalities = {
    "Friendly Assistant": "You are StrictexAI, a very friendly, polite, and helpful assistant.",
    "Expert Programmer": "You are a top Senior Software Engineer. Provide highly accurate answers and clean code blocks.",
    "Sarcastic Buddy": "You are a smart, ironic, and sarcastic friend. Use clever humor and light teasing.",
    "Creative Storyteller": "You are an imaginative storyteller. Give a highly creative and engaging tone to your responses.",
}

# --- 2. HISTORY & SEARCH FUNCTIONS ---
def get_all_chats():
    if not os.path.exists(CHATS_DIR):
        return []
    files = [f for f in os.listdir(CHATS_DIR) if f.endswith(".json")]
    files.sort(key=lambda x: os.path.getmtime(os.path.join(CHATS_DIR, x)), reverse=True)
    return [os.path.splitext(f) for f in files]

def load_chat_history(chat_id):
    file_path = os.path.join(CHATS_DIR, f"{chat_id}.json")
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_chat_history(chat_id, messages):
    file_path = os.path.join(CHATS_DIR, f"{chat_id}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=4)

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
    
    # 1. Primary Live Web Search via DuckDuckGo
    try:
        with DDGS() as ddgs:
            results = ddgs.text(clean_query, max_results=max_results, timelimit='y')

            if results:
                for item in results:
                    title = item.get("title", "")
                    # ΕΛΕΓΧΟΣ ΓΙΑ ΟΛΑ ΤΑ ΠΙΘΑΝΑ ΚΛΕΙΔΙΑ ΤΟΥ DUCKDUCKGO API
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

    # 2. Wikipedia Fallback Strategy
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
                    # Σωστή λήψη του τίτλου από τη λίστα
                    exact_title = results[0]["title"] 
                    formatted_title = urllib.parse.quote_plus(exact_title)
                    content_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=extracts&exintro=0&explaintext=1&titles={formatted_title}&format=json"
                    
                    content_response = requests.get(content_url, headers=headers, timeout=4)
                    if content_response.status_code == 200 and content_response.text.strip():
                        content_res = content_response.json()
                        pages = content_res.get("query", {}).get("pages", {})
                        
                        for page_id, page_info in pages.items():
                            extract = page_info.get("extract", "")
                            if extract.strip():
                                final_context = f"[WIKIPEDIA FALLBACK]: {extract[:1500]}"
                                st.session_state.search_cache[clean_query] = final_context
                                return final_context
    except Exception as e:
        st.sidebar.error(f"❌ Wikipedia Fallback failed: {e}")
        
    return None


# --- 3. INITIALIZE SESSION STATE ---
if "current_chat" not in st.session_state:
    all_chats = get_all_chats()
    if all_chats:
        st.session_state.current_chat = all_chats
    else:
        st.session_state.current_chat = f"Chat_{datetime.datetime.now().strftime('%d%m_%H%M%S')}"

if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history(st.session_state.current_chat)
# --- 4. SIDEBAR GRAPHICS (TRANSLATED TO ENGLISH) ---
with st.sidebar:
    st.header("⚙ Settings")
    
    selected_persona = st.selectbox(
        "🎭 Select Personality:",
        list(personalities.keys()),
        key="persona_selector"
    )
    st.divider()
    
    all_chats = get_all_chats()
    chat_ids = [c for c, ext in all_chats]
    
    if chat_ids:
        if st.session_state.current_chat not in chat_ids:
            st.session_state.current_chat = chat_ids[0]
        
        current_index = chat_ids.index(st.session_state.current_chat)
        selected_chat = st.selectbox(
            "💬 Select Chat:",
            chat_ids,
            index=current_index,
            key="chat_selector"
        )
        if selected_chat != st.session_state.current_chat:
            st.session_state.current_chat = selected_chat
            st.session_state.messages = load_chat_history(selected_chat)
            st.rerun()

    if st.button("➕ New Chat", use_container_width=True):
        new_id = f"Chat_{datetime.datetime.now().strftime('%d%m_%H%M%S')}"
        st.session_state.current_chat = new_id
        st.session_state.messages = []
        save_chat_history(new_id, [])
        st.rerun()

    if st.button("🗑 Delete Chat", use_container_width=True, type="primary"):
        file_path = os.path.join(CHATS_DIR, f"{st.session_state.current_chat}.json")
        if os.path.exists(file_path):
            os.remove(file_path)
        remaining_chats = get_all_chats()
        if remaining_chats:
            st.session_state.current_chat = remaining_chats[0][0]
            st.session_state.messages = load_chat_history(st.session_state.current_chat)
        else:
            new_id = f"Chat_{datetime.datetime.now().strftime('%d%m_%H%M%S')}"
            st.session_state.current_chat = new_id
            st.session_state.messages = []
            save_chat_history(new_id, [])
  
    st.markdown("---")
    st.subheader("🔊 Ρυθμίσεις Ήχου")
    # Κουμπί On/Off για την ομιλία του Bot
    enable_tts = st.toggle("Ενεργοποίηση Φωνής Bot (TTS)", value=False)


# --- 5. MAIN INTERFACE & CHAT DISPLAY ---
st.title("🤖 StrictexAI ChatBot")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# --- ΜΗΧΑΝΙΣΜΟΣ ΕΙΣΑΓΩΓΗΣ (ΚΕΙΜΕΝΟ Ή ΜΙΚΡΟΦΩΝΟ) ---
user_input = None

# 1. Εμφάνιση του Μικροφώνου (Στο sidebar ή πάνω από το chat input)
st.sidebar.markdown("---")
st.sidebar.write("🎙️ Μίλησε στο Bot:")
audio_rec = mic_recorder(
    start_prompt="🔴 Έναρξη Εγγραφής",
    stop_prompt="⏹️ Τέλος & Αποστολή",
    just_once=True,
    key="mic"
)

# Αν ο χρήστης χρησιμοποίησε το μικρόφωνο
if audio_rec and "bytes" in audio_rec:
    with st.spinner("🎙️ Μετατροπή φωνής σε κείμενο..."):
        try:
            # Στέλνουμε τα bytes του ήχου στο Whisper API της Groq
            audio_file = ("audio.wav", audio_rec["bytes"], "audio/wav")
            transcription = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file
            )
            if transcription.text.strip():
                user_input = transcription.text.strip()
        except Exception as e:
            st.error(f"❌ Σφάλμα μικροφώνου: {e}")

# 2. Ελέγχουμε αν γράφτηκε κείμενο στο κανονικό Chat Input
chat_prompt = st.chat_input("Γράψε ένα μήνυμα ή χρησιμοποίησε το μικρόφωνο...")
if chat_prompt:
    user_input = chat_prompt

# ΑΝ ΥΠΑΡΧΕΙ ΕΙΣΑΓΩΓΗ (Είτε από κείμενο είτε από μικρόφωνο), ΕΚΤΕΛΕΙΤΑΙ ΤΟ BOT
# ΑΝ ΥΠΑΡΧΕΙ ΕΙΣΑΓΩΓΗ (Είτε από κείμενο είτε από μικρόφωνο), ΕΚΤΕΛΕΙΤΑΙ ΤΟ BOT
if user_input:
    # Προσθήκη του μηνύματος στο ιστορικό
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Προετοιμασία των μηνυμάτων για το API της Groq
    api_messages = [{"role": "system", "content": full_system_prompt}]
    for msg in st.session_state.messages[-10:]:  # Κρατάει τα τελευταία 10 μηνύματα για μνήμη
        api_messages.append({"role": msg["role"], "content": msg["content"]})

    # Κλήση του API και λήψη της απάντησης του Bot
    try:
        with st.spinner("🤖 Thinking..."):
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",  # Οικονομικό μοντέλο για αποφυγή rate limits
                messages=api_messages,
                temperature=0.7
            )
            full_response = response.choices[0].message.content.strip()

        # Εμφάνιση της απάντησης του AI στο Chat
        with st.chat_message("assistant"):
            st.markdown(full_response)
            
            # --- ΕΛΕΓΧΟΣ ΑΝ ΕΙΝΑΙ ΕΝΕΡΓΟΠΟΙΗΜΕΝΟ ΤΟ TOGGLE ΟΜΙΛΙΑΣ ---
            if enable_tts:
                response_has_greek = any('α' <= char <= 'ώ' or 'Α' <= char <= 'Ω' for char in full_response)
                audio_lang = "el" if response_has_greek else "en"
                
                audio_bytes = text_to_speech(full_response, lang_code=audio_lang)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3")

        # Αποθήκευση της απάντησης του bot στο ιστορικό
        st.session_state.messages.append({"role": "assistant", "content": full_response})

        # Αυτόματη αποθήκευση της συνομιλίας στο τοπικό JSON αρχείο
        chat_title = st.session_state.get("current_chat_title", "Untitled Chat")
        save_chat_history(chat_title, st.session_state.messages)

    except Exception as e:
        st.error(f"❌ Error communicating with Groq: {e}")

