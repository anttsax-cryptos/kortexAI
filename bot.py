import streamlit as st
import json
import datetime
import requests
import urllib.parse
import streamlit.components.v1 as components
import os  # <-- ADDED for local file management
from groq import Groq

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="StrictexAI Ultra", layout="wide", page_icon="🤖")

if "GROQ_API_KEY" not in st.secrets:
    st.error("⚠ Please add your GROQ_API_KEY in Streamlit Secrets!")
    st.stop()

client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- NEW: KNOWLEDGE BASE LOADING FUNCTION ---
def load_local_knowledge():
    """Reads knowledge2026.txt into memory if it exists."""
    db_file = "knowledge2026.txt"
    if os.path.exists(db_file):
        with open(db_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

def check_local_knowledge_first(query, local_data):
    """Uses a lightweight evaluation to check if local data answers the query."""
    if not local_data:
        return False
        
    evaluation_prompt = (
        f"Analyze this user request: '{query}'.\n"
        f"Does this specific local database contain the direct answer?:\n"
        f"--- START DATABASE ---\n{local_data}\n--- END DATABASE ---\n"
        "Reply with exactly one word: 'YES' or 'NO'."
    )
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": evaluation_prompt}],
            max_tokens=5,
            temperature=0.0
        )
        decision = response.choices[0].message.content.strip().upper()
        return "YES" in decision
    except:
        return False

# Load local knowledge base globally once on bootup
LOCAL_KNOWLEDGE = load_local_knowledge()

# Enforced Prompts for maximum depth
personalities = {
    "Friendly Assistant": "You are StrictexAI, a highly detailed and comprehensive encyclopedia. Provide extensive, in-depth analysis, precise specifications, and complete technical overviews for every product or topic requested. Never summarize complex details.",
    "Expert Programmer": "You are StrictexAI, a top Senior Software Engineer. Provide exhaustive, highly accurate technical documentation, full code examples without omissions, and deep architectural explanations.",
    "Sarcastic Buddy": "You are StrictexAI, a highly sarcastic expert. Don't hold back on anyone Make Everyone laugh and give them to understand who is the leader of the party.",
    "Creative Storyteller": "You are StrictexAI, an imaginative world-builder. Give rich, deeply descriptive, and expansive narratives filled with intricate details and vivid lore."
}

# --- 2. JAVASCRIPT MECHANISM FOR MULTIPLE CHATS (FIXED AUTO-JUMP) ---
if "all_chats" not in st.session_state:
    st.session_state.all_chats = {}
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None
if "js_sync_done" not in st.session_state:
    st.session_state.js_sync_done = False

if not st.session_state.js_sync_done:
    js_load_all = """
    <script>
        const savedData = localStorage.getItem("strictex_multichats");
        const currentActive = localStorage.getItem("strictex_active_chat_id");
        
        window.parent.postMessage({
            type: "LOAD_ALL_CHATS", 
            data: savedData ? JSON.parse(savedData) : {},
            active_id: currentActive || null
        }, "*");
    </script>
    """
    components.html(js_load_all, height=0, width=0)

query_params = st.query_params
if "incoming_chats" in query_params and not st.session_state.js_sync_done:
    try:
        st.session_state.all_chats = json.loads(query_params["incoming_chats"])
        st.session_state.js_sync_done = True
        
        saved_active = query_params.get("active_chat_id", None)
        if saved_active and saved_active in st.session_state.all_chats:
            st.session_state.current_chat_id = saved_active
        elif st.session_state.all_chats.keys():
            st.session_state.current_chat_id = list(st.session_state.all_chats.keys())[0]
            
        st.rerun()
    except:
        pass

def save_chats_to_browser():
    all_data_json = json.dumps(st.session_state.all_chats, ensure_ascii=False)
    current_id = st.session_state.current_chat_id
    st.components.v1.html(
        f"""
        <script>
            localStorage.setItem("strictex_multichats", JSON.stringify({all_data_json}));
            localStorage.setItem("strictex_active_chat_id", "{current_id}");
        </script>
        """,
        height=0,
        width=0
    )

# --- 3. WIKIPEDIA SEARCH FUNCTION ---
def search_the_web(query, max_results=1):
    stop_words = ["πες μου για το", "τι ειναι το", "ποιος ειναι ο", "υπαρχει το", "δειξε μου", "πληροφοριες για","information about","tell me about", "what is", "who is"]
    clean_query = query.lower()
    for word in stop_words:
        clean_query = clean_query.replace(word, "")
    clean_query = clean_query.strip()
    
    if not clean_query:
        return None
        
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
                    
                    content_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles={formatted_title}&format=json"
                    content_response = requests.get(content_url, headers=headers, timeout=4)
                    
                    if content_response.status_code == 200 and content_response.text.strip():
                        content_res = content_response.json()
                        pages = content_res.get("query", {}).get("pages", {})
                        for page_id, page_info in pages.items():
                            extract = page_info.get("extract", "")
                            if extract.strip():
                                wiki_link = f"https://{lang}.wikipedia.org/wiki/{formatted_title}"
                                if len(extract) > 2000 and clean_query in extract.lower():
                                    start_idx = extract.lower().find(clean_query)
                                    extract = extract[max(0, start_idx-200):start_idx+1500]
                                return f"• {exact_title} ({wiki_link}): {extract}"
    except:
        pass
    return None

# --- 4. SIDEBAR & CHAT SELECTOR ---
with st.sidebar:
    st.caption("[Ai can make mistakes]")
    st.header("💬 My chats")
    
    if st.button("➕ New chat", use_container_width=True, type="primary"):
        new_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.all_chats[new_id] = {
            "title": f"Συνομιλία {datetime.datetime.now().strftime('%d/%m %H:%M')}",
            "messages": []
        }
        st.session_state.current_chat_id = new_id
        save_chats_to_browser()
        st.rerun()
        
    st.divider()
    
    if st.session_state.all_chats:
        chat_options = {k: v["title"] for k, v in st.session_state.all_chats.items()}
        
        selected_chat = st.radio(
            "👉 Choose chat:",
            options=list(chat_options.keys()),
            index=list(chat_options.keys()).index(st.session_state.current_chat_id) if st.session_state.current_chat_id in chat_options else 0,
            format_func=lambda x: chat_options[x]
        )
        if selected_chat != st.session_state.current_chat_id:
            st.session_state.current_chat_id = selected_chat
            save_chats_to_browser()
            st.rerun()
            
        st.divider()
        
        if st.button("🗑 Delete this chat", use_container_width=True):
            del st.session_state.all_chats[st.session_state.current_chat_id]
            st.session_state.current_chat_id = list(st.session_state.all_chats.keys())[0] if st.session_state.all_chats else None
            save_chats_to_browser()
            st.rerun()
    else:
        st.info("There is not a chat, press 'New chat'.")

    st.divider()
    selected_persona = st.selectbox("🎭 Personality:", list(personalities.keys()))
    st.caption("made by Antonis Tsachpinis | powered by streamlit and Groq")

# --- 5. MAIN INTERFACE ---
st.title("🤖 StrictexAI Chatbot")

if not st.session_state.current_chat_id:
    st.warning("👈 Tap on the 'New Chat button on the sidebar to start!'")
    st.stop()

active_messages = st.session_state.all_chats[st.session_state.current_chat_id]["messages"]

# --- 6. CHAT COMPLETION INTEGRATION (EXAMPLE IMPLEMENTATION) ---
# Note: You can paste the rest of your prompt-building code below this block.
# Whenever a user inputs a query, execute the routing block:
#
# has_local = check_local_knowledge_first(user_query, LOCAL_KNOWLEDGE)
# if has_local:
#     system_prompt = f"{personalities[selected_persona]} Use this local data to answer: {LOCAL_KNOWLEDGE}"
# else:
#     wiki_context = search_the_web(user_query)
#     system_prompt = f"{personalities[selected_persona]} Use this web data to answer: {wiki_context}"
