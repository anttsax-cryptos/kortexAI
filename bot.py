import streamlit as st
import json
import os
import datetime
import requests
import urllib.parse
from groq import Groq
from duckduckgo_search import DDGS

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
    "Patient Teacher": "You are a patient educator. Explain concepts simply, step-by-step, using clear examples."
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
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(clean_query, max_results=max_results)]
            if results:
                for item in results:
                    title = item.get("title", "")
                    snippet = item.get("body", "")
                    link = item.get("href", "")
                    context_list.append(f"• {title} ({link}): {snippet}")
                
                final_context = "\n\n".join(context_list)
                st.session_state.search_cache[clean_query] = final_context
                return final_context
    except Exception:
        pass

    # Wikipedia Fallback
    try:
        headers = {"User-Agent": "StrictexAIChatbot/2.0 (contact@example.com)"}
        formatted_query = urllib.parse.quote_plus(clean_query)
        for lang in ["el", "en"]:
            search_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={formatted_query}&srlimit=1&format=json"
            search_res = requests.get(search_url, headers=headers, timeout=4).json()
            results = search_res.get("query", {}).get("search", [])
            if results:
                exact_title = results["title"]
                formatted_title = urllib.parse.quote_plus(exact_title)
                content_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=extracts&exintro=0&explaintext=1&titles={formatted_title}&format=json"
                content_res = requests.get(content_url, headers=headers, timeout=4).json()
                pages = content_res.get("query", {}).get("pages", {})
                for page_id, page_info in pages.items():
                    extract = page_info.get("extract", "")
                    if extract.strip():
                        final_context = f"[WIKIPEDIA FALLBACK]: {extract[:1500]}"
                        st.session_state.search_cache[clean_query] = final_context
                        return final_context
    except Exception:
        pass
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
    st.header("⚙ Settings & History")
    
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
# --- 6. INTELLIGENT ROUTING & RESPONSE ---
if user_input := st.chat_input("Type your message here..."):
    
    # 1. Εμφάνιση μηνύματος χρήστη
    with st.chat_message("user"):
        st.write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Λίστα χαιρετισμών
    greetings = ["γεια", "γεια σου", "γεια σας", "καλημερα", "καλησπερα", "καληνυχτα", "hi", "hello", "hey", "τι κανεις", "πως εισαι", "how are you", "good morning"]
    clean_input = user_input.lower().strip().replace("?", "").replace(".", "")
    is_greeting = clean_input in greetings or len(clean_input.split()) <= 1

    search_context = ""
    search_query = user_input

    # 2. Εκτέλεση αναζήτησης ΜΟΝΟ αν ΔΕΝ είναι απλός χαιρετισμός
    if not is_greeting:
        if len(st.session_state.messages) > 1:
            rewriter_prompt = (
                "You are a search assistant. Based on the user's latest input and conversation history, "
                "write a short, optimized search query (keywords) for DuckDuckGo or Wikipedia. "
                "If the query is technical or about international products, prefer English keywords. "
                "Respond STRICTLY with the keywords only, nothing else. Do not change the user's intent.\n\n"
                f"User input: {user_input}"
            )
            
            rewrite_messages = []
            for msg in st.session_state.messages[-5:-1]:
                rewrite_messages.append({"role": msg["role"], "content": msg["content"]})
            rewrite_messages.append({"role": "user", "content": rewriter_prompt})
            
            try:
                rewrite_res = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=rewrite_messages,
                    temperature=0.0
                )
                # ΔΙΟΡΘΩΣΗ: Προσθήκη του [0] στα choices
                search_query = rewrite_res.choices[0].message.content.strip()
            except Exception:
                search_query = user_input

        # 3. Live Web Search
        with st.spinner(f"🔍 Searching the web for '{search_query}'..."):
            results = search_the_web(search_query, max_results=5)
            if results:
                search_context = (
                    f"\n\n[LIVE WEB DATA]:\n{results}\n\n"
                    "👉 ΟΔΗΓΙΑ ΓΙΑ ΤΗΝ ΑΠΑΝΤΗΣΗ (Urgently Detailed):\n"
                    "1. CRITICAL MANDATE: Automatically detect the language that the user used in their last message. You MUST write your entire response STRICTLY in that exact same language (e.g., if the user wrote in Greek, reply in Greek. If they wrote in English, reply in English). Never default to English if the user wrote in Greek.\n"
                    "2. Θέλω να γράψεις μια εξαιρετικά αναλυτική και πλήρη παρουσίαση, χωρίς να παραλείψεις καμία λεπτομέρεια από τα παραπάνω δεδομένα.\n"
                    "3. Ανάλογα με το θέμα της ερώτησης, οργάνωσε την απάντησή σου ΑΥΣΤΗΡΑ χρησιμοποιώντας έντονη γραφή (Bold) και Bullet Points ως εξής:\n\n"
                    "📦 ΑΝ ΠΡΟΚΕΙΤΑΙ ΓΙΑ ΠΡΟΪΟΝ (π.χ. τηλέφωνο, gadget, αυτοκίνητο, συσκευή):\n"
                    "- **Γενικές πληροφορίες** / **General Information**\n"
                    "- **Σχεδιασμός & Χαρακτηριστικά** / **Design & Features** (διαστάσεις, λειτουργίες, πλεονεκτήματα, μειονεκτήματα)\n"
                    "- **Τιμή** / **Price** (κόστος και διαθεσιμότητα προϊόντος)\n\n"
                    "📢 ΑΝ ΠΡΟΚΕΙΤΑΙ ΓΙΑ ΓΕΓΟΝΟΣ / ΕΙΔΗΣΗ (π.χ. αγώνας, συναυλία, φυσικό φαινόμενο, είδηση):\n"
                    "- **Γενικό Πλαίσιο** / **General Context** (Πότε και πού συνέβη, ποιοι εμπλέκονται)\n"
                    "- **Χρονικό & Λεπτομέρειες** / **Timeline & Details** (Αναλυτικά τι συνέβη, σημαντικές στιγμές)\n"
                    "- **Αποτέλεσμα / Αντίκτυπος** / **Result / Impact** (Σκορ, δηλώσεις, συνέπειες)\n\n"
                    "Αν κάποια πληροφορία λείπει από τα δεδομένα, μην την εφεύρεις, απλά ανάφερε ό,τι είναι διαθέσιμο με όσο το δυνατόν περισσότερες λεπτομέρειες."
                )

    # 4. Χτίσιμο των τελικών μηνυμάτων
    lang_mirror_rule = "\n\nCRITICAL: Automatically detect the language of the user's latest message and reply ONLY in that language. If the user wrote in Greek, translate all the web data into Greek and reply in Greek."
    full_system_prompt = personalities[selected_persona] + search_context + lang_mirror_rule
    
    api_messages = [{"role": "system", "content": full_system_prompt}]
    api_messages.extend(st.session_state.messages[-12:])

    # 5. Κλήση Groq για την τελική απάντηση
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                chat_completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=api_messages,
                    temperature=0.4
                )
                # ΔΙΟΡΘΩΣΗ: Προσθήκη του [0] στα choices
                assistant_response = chat_completion.choices[0].message.content
                st.write(assistant_response)
                
                st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                save_chat_history(st.session_state.current_chat, st.session_state.messages)
            except Exception as e:
                st.error(f"Error communicating with Groq: {e}")
        st.rerun()

# --- 5. MAIN INTERFACE ---
st.title("🤖 StrictexAI ChatBot")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

