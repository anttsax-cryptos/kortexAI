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
    
    # 1. Primary Live Web Search via DuckDuckGo
    try:
        with DDGS() as ddgs:
            results = ddgs.text(clean_query, max_results=max_results)
            if results:
                for item in results:
                    title = item.get("title", "")
                    snippet = item.get("body", "")
                    link = item.get("href", "")
                    context_list.append(f"• {title} ({link}): {snippet}")
                    
                if context_list:
                    final_context = "\n\n".join(context_list)
                    st.session_state.search_cache[clean_query] = final_context
                    return final_context
    except Exception as e:
        st.sidebar.warning(f"⚠️ DuckDuckGo Search failed: {e}. Trying Wikipedia...")

    # 2. Wikipedia Fallback Strategy (Fully Protected & Fixed Index)
    try:
        headers = {"User-Agent": "StrictexAIChatbot/2.0 (contact@example.com)"}
        formatted_query = urllib.parse.quote_plus(clean_query)
        for lang in ["el", "en"]:
            search_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={formatted_query}&srlimit=1&format=json"
            response = requests.get(search_url, headers=headers, timeout=4)
            
            # Έλεγχος αν η απάντηση είναι έγκυρη πριν το JSON parsing
            if response.status_code == 200 and response.text.strip():
                search_res = response.json()
                results = search_res.get("query", {}).get("search", [])
                
                if results and len(results) > 0:
                    # ΔΙΟΡΘΩΣΗ: Προσθήκη [0] επειδή το results είναι λίστα
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

# --- 5. MAIN INTERFACE & CHAT DISPLAY ---
st.title("🤖 StrictexAI ChatBot")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# --- 6. INTELLIGENT ROUTING & RESPONSE ---
if user_input := st.chat_input("Type your message here..."):
    
    with st.chat_message("user"):
        st.write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Skip search logic for greetings
    greetings = ["γεια", "γεια σου", "γεια σας", "καλημερα", "καλησπερα", "καληνυχτα", "hi", "hello", "hey", "τι κανεις", "πως εισαι", "how are you", "good morning"]
    clean_input = user_input. lower(). strip(). replace("?", ""). replace(".", "")
    is_greeting = clean_input in greetings or len( clean_input. split()) <= 1

    # --- ΑΡΧΙΚΟΠΟΙΗΣΗ ΜΕΤΑΒΛΗΤΩΝ (DEFAULT VALUES) ---
    search_context = ""
    search_query = user_input

    # Ανίχνευση γλώσσας για να επιβληθεί σωστή συμπεριφορά και στους χαιρετισμούς
    has_greek = any('α' <= char <= 'ώ' or 'Α' <= char <= 'Ω' for char in user_input)
    if has_greek:
        lang_mirror_rule = "\n\nCRITICAL MANDATE: The user is speaking in Greek. You MUST write your ENTIRE response strictly in Greek."
    else:
        lang_mirror_rule = "\n\nCRITICAL MANDATE: The user is speaking in English. You MUST write your ENTIRE response strictly in English."

    if not is_greeting:
        if len(st.session_state.messages) > 1:
            rewriter_prompt = (
                "You are an AI search query generator. The current year is 2026.\n"
                "Extract the core subject, entity, or product from the user's input to create a simple, high-probability search query.\n"
                "RULES:\n"
                "- Strip out overly specific suffixes if they might limit search results (e.g., instead of 'iPhone 17 Pro Max 256gb', just use 'iPhone 17').\n"
                "- Keep tech and global products in English keywords.\n"
                "- Output ONLY the search keywords. No markdown, no quotes, no conversational text.\n\n"
                f"User input: {user_input}"
            )
            rewrite_messages = []
            for msg in st.session_state.messages[-5:-1]:
                rewrite_messages.append({"role": msg["role"], "content": msg["content"]})
            rewrite_messages.append({"role": "user", "content": rewriter_prompt})
            try:
                rewrite_res = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=rewrite_messages,
                    temperature=0.2
                )
                search_query = rewrite_res.choices.message.content.strip()
            except Exception:
                search_query = user_input

        # Live Web Search
        with st.spinner(f"🔍 Searching the web for '{search_query}'..."):
            results = search_the_web(search_query, max_results=5)
            
            # Ανίχνευση γλώσσας του χρήστη
            has_greek = any('α' <= char <= 'ώ' or 'Α' <= char <= 'Ω' for char in user_input)
            
            if results:
                if has_greek:
                    formatting_rules = (
                        "👉 ΟΔΗΓΙΑ ΓΙΑ ΤΗΝ ΑΠΑΝΤΗΣΗ:\n"
                        "1. Γράψε την απάντησή σου ΑΠΟΚΛΕΙΣΤΙΚΑ στα Ελληνικά.\n"
                        "2. Οργάνωσε την απάντησή σου ΑΥΣΤΗΡΑ χρησιμοποιώντας έντονη γραφή (Bold) και Bullet Points στις κατάλληλες κατηγορίες.\n"
                        "3. TIMELINE RULE: Καθώς βρισκόμαστε στον Μάιο του 2026, συσκευές όπως η σειρά Samsung Galaxy S26 έχουν ΉΔΗ κυκλοφορήσει στην αγορά (από τις αρχές του 2026). Μην αναφέρεσαι σε αυτές ως 'φήμες' ή 'μελλοντικά σχέδια', αλλά ως τρέχοντα, υπαρκτά προϊόντα με βάση τα live δεδομένα.\n"
                    )
                else:
                    formatting_rules = (
                        "👉 RESPONSE INSTRUCTIONS:\n"
                        "1. Write your entire response STRICTLY in English.\n"
                        "2. Organize your response STRICTLY using Bold text and Bullet Points in the appropriate categories.\n"
                        "3. TIMELINE RULE: Since we are in May 2026, devices like the Samsung Galaxy S26 series have ALREADY been officially released (early 2026). Do NOT refer to them as 'rumors' or 'speculation'. Treat them as current, active market products based on the web data.\n"
                    )
                search_context = f"\n\n[LIVE WEB DATA]:\n{results}\n\n{formatting_rules}"

            else:
                # --- ΕΞΥΠΝΟ FALLBACK ΑΝ ΑΠΟΤΥΧΟΥΝ ΟΛΕΣ ΟΙ ΑΝΑΖΗΤΗΣΕΙΣ ---
                if has_greek:
                    search_context = (
                        "\n\n[SYSTEM NOTICE]: Η αναζήτηση στο διαδίκτυο δεν επέστρεψε αποτελέσματα. "
                        "Γνωρίζεις ότι το τρέχον έτος είναι το 2026. Μην πεις ότι το προϊόν δεν υπάρχει ή ότι δεν έχεις πληροφορίες. "
                        "Απάντησε στα Ελληνικά με βάση τις γνωστές προδιαγραφές, επίσημες κυκλοφορίες ή ευρέως γνωστές βιομηχανικές φήμες "
                        "μέχρι σήμερα (π.χ. για τη σειρά iPhone 17 που κυκλοφόρησε στα τέλη του 2025, τον επεξεργαστή A19 Pro κλπ)."
                    )
                else:
                    search_context = (
                        "\n\n[SYSTEM NOTICE]: Web search returned no results. "
                        "You know the current year is 2026. Do NOT say the product doesn't exist or that you lack info. "
                        "Answer in English based on established specifications, official releases, or widely known industry rumors "
                        "up to this point (e.g., regarding the iPhone 17 series released in late 2025, A19 Pro chip, etc.)."
                    )

    # Τελικό χτίσιμο του prompt
    time_context = "\n\n[SYSTEM NOTE: The current year is 2026. Keep this timeline in mind for all release dates.]"
    full_system_prompt = personalities[selected_persona] + time_context + search_context + lang_mirror_rule

    api_messages = [{"role": "system", "content": full_system_prompt}]
    api_messages.extend(st.session_state.messages[-12:])

    # Final Chat Generation
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                chat_completion = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=api_messages,
                    temperature=0.3
                )
                assistant_response = chat_completion.choices[0].message.content
                st.write(assistant_response)
                
                # Save to state and directory
                st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                save_chat_history(st.session_state.current_chat, st.session_state.messages)
            except Exception as e:
                st.error(f"Error communicating with Groq: {e}")

