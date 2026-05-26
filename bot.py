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
    return [os.path.splitext(f)[0] for f in files]  # Κρατάει μόνο το όνομα ως string

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
    
    # DuckDuckGo Search with 1 Year time limit
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

    # Wikipedia Fallback
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
                    exact_title = results[0]["title"]  # Σωστός δείκτης λίστας
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

def text_to_speech(text, lang_code="el"):
    try:
        clean_text = text.replace("**", "").replace("*", "").replace("-", "").strip()
        tts = gTTS(text=clean_text, lang=lang_code, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp.read()
    except Exception as e:
        st.sidebar.error(f"❌ TTS Error: {e}")
        return None

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
    
    selected_persona = st.selectbox("Επιλογή Προσωπικότητας Bot:", list(personalities.keys()))
    
    st.markdown("---")
    st.subheader("🔊 Ρυθμίσεις Ήχου")
    enable_tts = st.toggle("Ενεργοποίηση Φωνής Bot (TTS)", value=False)
    
    st.markdown("---")
    st.subheader("📝 Διαχείριση Συνομιλιών")
    
    chat_names = get_all_chats()
    
    if "current_chat_title" not in st.session_state:
        if "Default Chat" in chat_names:
            st.session_state.current_chat_title = "Default Chat"
        elif chat_names:
            st.session_state.current_chat_title = chat_names[0]
        else:
            st.session_state.current_chat_title = "New Chat"

    selectable_options = chat_names if chat_names else ["New Chat"]
    if st.session_state.current_chat_title not in selectable_options:
        st.session_state.current_chat_title = selectable_options[0]

    selected_chat = st.selectbox(
        "Επιλέξτε Συνομιλία:", 
        selectable_options, 
        index=selectable_options.index(st.session_state.current_chat_title) if st.session_state.current_chat_title in selectable_options else 0
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

# Display history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input Handling
user_input = None

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

chat_prompt = st.chat_input("Γράψε ένα μήνυμα ή χρησιμοποίησε το μικρόφωνο...")
if chat_prompt:
    user_input = chat_prompt

# 6. Response Execution Pipeline
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    greetings = ["γεια", "γεια σου", "γεια σας", "καλημερα", "καλησπερα", "καληνυχτα", "hi", "hello", "hey", "τι κανεις", "πως εισαι", "how are you", "good morning"]
    clean_input = user_input.lower().strip().replace("?", "").replace(".", "")
    is_greeting = clean_input in greetings or len(clean_input.split()) <= 1

    search_context = ""
    search_query = user_input

    has_greek = any('α' <= char <= 'ώ' or 'Α' <= char <= 'Ω' for char in user_input)
    if has_greek:
        lang_mirror_rule = "\n\nCRITICAL MANDATE: The user is speaking in Greek. You MUST write your ENTIRE response strictly in Greek."
    else:
        lang_mirror_rule = "\n\nCRITICAL MANDATE: The user is speaking in English. You MUST write your ENTIRE response strictly in English."

    time_context = "\n\n[SYSTEM NOTE: The current year is 2026. Keep this timeline in mind for all status and release updates.]"
    full_system_prompt = personalities[selected_persona] + time_context + lang_mirror_rule

    if not is_greeting:
        if len(st.session_state.messages) > 1:
            rewriter_prompt = (
                "You are a search query optimizer. The current year is 2026.\n"
                "Your job is to convert the user's request into 2-4 English keywords for a search engine.\n"
                "CRITICAL RULES:\n"
                "- NEVER remove product generation numbers or model names (e.g., if user says 'iPhone 17', you MUST keep 'iPhone 17').\n"
                "- Strip only conversational filler words.\n"
                "- Keep tech queries in English keywords.\n"
                "- Output ONLY the final keywords. No explanation, no quotes, no conversational text."
            )
            rewrite_messages = []
            for msg in st.session_state.messages[-5:-1]:
                rewrite_messages.append({"role": msg["role"], "content": msg["content"]})
            rewrite_messages.append({"role": "user", "content": rewriter_prompt})
            try:
                rewrite_res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=rewrite_messages,
                    temperature=0.0
                )
                search_query = rewrite_res.choices.message.content.strip()
            except Exception:
                search_query = user_input

        with st.spinner(f"🔍 Searching the web for '{search_query}'..."):
            results = search_the_web(search_query, max_results=5)
            
            if results:
                if has_greek:
                    formatting_rules = (
                        "👉 ΟΔΗΓΙΑ ΓΙΑ ΤΗΝ ΑΠΑΝΤΗΣΗ:\n"
                        "1. Γράψε την απάντησή σου ΑΠΟΚΛΕΙΣΤΙΚΑ στα Ελληνικά.\n"
                        "2. Οργάνωσε την απάντησή σου ΑΥΣΤΗΡΑ χρησιμοποιώντας έντονη γραφή (Bold) και Bullet Points.\n"
                        "3. TIMELINE RULE: Καθώς βρισκόμαστε στο 2026, συσκευές όπως η σειρά Samsung Galaxy S26 ή η σειρά iPhone 17 έχουν ΉΔΗ κυκλοφορήσει στην αγορά. Μην αναφέρεσαι σε αυτές ως 'φήμες', αλλά ως τρέχοντα προϊόντα.\n"
                    )
                else:
                    formatting_rules = (
                        "👉 RESPONSE INSTRUCTIONS:\n"
                        "1. Write your entire response STRICTLY in English.\n"
                        "2. Organize your response STRICTLY using Bold text and Bullet Points.\n"
                        "3. TIMELINE RULE: Since we are in 2026, devices like the Samsung Galaxy S26 series or iPhone 17 series have ALREADY been officially released. Do NOT refer to them as 'rumors'. Treat them as active market products.\n"
                    )
                search_context = f"\n\n[LIVE WEB DATA]:\n{results}\n\n{formatting_rules}"
            else:
                if has_greek:
                    search_context = (
                        "\n\n[SYSTEM NOTICE]: Η αναζήτηση στο διαδίκτυο δεν επέστρεψε αποτελέσματα. "
                        "Γνωρίζεις ότι το τρέχον έτος είναι το 2026. Μην πεις ότι το προϊόν δεν υπάρχει. "
                        "Απάντησε στα Ελληνικά με βάση τις γνωστές προδιαγραφές ή επίσημες κυκλοφορίες μέχρι σήμερα."
                    )
                else:
                    search_context = (
                        "\n\n[SYSTEM NOTICE]: Web search returned no results. "
                        "You know the current year is 2026. Do NOT say the product doesn't exist. "
                        "Answer in English based on established specifications or official releases up to this point."
                    )
            
            full_system_prompt = personalities[selected_persona] + time_context + search_context + lang_mirror_rule

    # 7. Model Inference Setup & Processing
    api_messages = [{"role": "system", "content": full_system_prompt}]
    for msg in st.session_state.messages[-10:]:
        api_messages.append({"role": msg["role"], "content": msg["content"]})

    try:
        with st.spinner("🤖 Thinking..."):
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=api_messages,
                temperature=0.7
            )
            full_response = response.choices.message.content.strip()

        with st.chat_message("assistant"):
            st.markdown(full_response)
            
            if enable_tts:
                response_has_greek = any('α' <= char <= 'ώ' or 'Α' <= char <= 'Ω' for char in full_response)
                audio_lang = "el" if response_has_greek else "en"
                
                audio_bytes = text_to_speech(full_response, lang_code=audio_lang)
                if audio_bytes:
                    st.audio(audio_bytes, format="audio/mp3")

        st.session_state.messages.append({"role": "assistant", "content": full_response})
        chat_title = st.session_state.get("current_chat_title", "Untitled Chat")
        save_chat_history(chat_title, st.session_state.messages)

    except Exception as e:
        st.error(f"❌ Error communicating with Groq: {e}")

