import streamlit as st
import json
import datetime
import requests
import urllib.parse
import streamlit.components.v1 as components
from groq import Groq

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="StrictexAI Local Chats", layout="wide", page_icon="🤖")

if "GROQ_API_KEY" not in st.secrets:
    st.error("⚠ Please add your GROQ_API_KEY in Streamlit Secrets!")
    st.stop()

client = Groq(api_key=st.secrets["GROQ_API_KEY"])

personalities = {
    "Friendly Assistant": "You are StrictexAI, a very friendly, polite, and helpful assistant.",
    "Expert Programmer": "You are a top Senior Software Engineer. Provide highly accurate answers and clean code blocks.",
    "Sarcastic Buddy": "You are a smart, ironic, and sarcastic friend. Use clever humor and light teasing.",
    "Creative Storyteller": "You are an imaginative storyteller. Give a highly creative and engaging tone to your responses.",
}

# --- 2. JAVASCRIPT MECHANISM FOR MULTIPLE CHATS ---
# Αρχικοποίηση των δομών στη μνήμη του Streamlit
if "all_chats" not in st.session_state:
    st.session_state.all_chats = {}  # {chat_id: {"title": ..., "messages": [...]}}
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None
if "js_sync_done" not in st.session_state:
    st.session_state.js_sync_done = False

# JavaScript για ανάκτηση όλων των συνομιλιών από τον Browser κατά το Load
if not st.session_state.js_sync_done:
    js_load_all = """
    <script>
        const savedData = localStorage.getItem("strictex_multichats");
        if (savedData) {
            window.parent.postMessage({type: "LOAD_ALL_CHATS", data: JSON.parse(savedData)}, "*");
        } else {
            window.parent.postMessage({type: "LOAD_ALL_CHATS", data: {}}, "*");
        }
    </script>
    """
    components.html(js_load_all, height=0, width=0)

# Διαχείριση των μηνυμάτων JavaScript από την Python (μέσω query params για συγχρονισμό)
query_params = st.query_params
if "incoming_chats" in query_params and not st.session_state.js_sync_done:
    try:
        st.session_state.all_chats = json.loads(query_params["incoming_chats"])
        st.session_state.js_sync_done = True
        # Αν υπάρχουν chats, επιλέγουμε το πρώτο διαθέσιμο
        if st.session_state.all_chats.keys():
            st.session_state.current_chat_id = list(st.session_state.all_chats.keys())[0]
        st.rerun()
    except:
        pass

def save_chats_to_browser():
    """Συνάρτηση που στέλνει όλες τις συνομιλίες πίσω στο Local Storage του Browser"""
    all_data_json = json.dumps(st.session_state.all_chats, ensure_ascii=False)
    js_save = f"""
    <script>
        localStorage.setItem("strictex_multichats", JSON.stringify({all_data_json}));
    </script>
    """
    components.html(js_save, height=0, width=0)

# --- 3. WIKIPEDIA SEARCH FUNCTION ---
def search_the_web(query, max_results=1):
    stop_words = ["πες μου για το", "τι ειναι το", "ποιος ειναι ο", "υπαρχει το", "δειξε μου", "πληροφοριες για", "tell me about", "what is", "who is"]
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
                                    extract = extract[max(0, start_idx-200):start_idx+1300]
                                return f"• {exact_title} ({wiki_link}): {extract}"
    except:
        pass
    return None

# --- 4. SIDEBAR & CHAT SELECTOR ---
with st.sidebar:
    st.header("💬 Οι Συνομιλίες μου")
    
    # Κουμπί για Δημιουργία Νέου Chat
    if st.button("➕ Νέα Συνομιλία", use_container_width=True, type="primary"):
        new_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.all_chats[new_id] = {
            "title": f"Συνομιλία {datetime.datetime.now().strftime('%d/%m %H:%M')}",
            "messages": []
        }
        st.session_state.current_chat_id = new_id
        save_chats_to_browser()
        st.rerun()
        
    st.divider()
    
    # Λίστα Επιλογής Chat (Chat Selector)
    if st.session_state.all_chats:
        chat_options = {k: v["title"] for k, v in st.session_state.all_chats.items()}
        selected_chat = st.radio(
            "👉 Επιλέξτε συνομιλία:",
            options=list(chat_options.keys()),
            format_func=lambda x: chat_options[x]
        )
        if selected_chat != st.session_state.current_chat_id:
            st.session_state.current_chat_id = selected_chat
            st.rerun()
            
        st.divider()
        
        # Κουμπί Διαγραφής του Επιλεγμένου Chat
        if st.button("🗑 Διαγραφή τρέχουσας συνομιλίας", use_container_width=True):
            del st.session_state.all_chats[st.session_state.current_chat_id]
            st.session_state.current_chat_id = list(st.session_state.all_chats.keys())[0] if st.session_state.all_chats else None
            save_chats_to_browser()
            st.rerun()
    else:
        st.info("Δεν υπάρχουν αποθηκευμένες συνομιλίες. Πατήστε 'Νέα Συνομιλία'.")

    st.divider()
    selected_persona = st.selectbox("🎭 Προσωπικότητα:", list(personalities.keys()))

# --- 5. MAIN INTERFACE ---
st.title("🤖 StrictexAI Hub")

if not st.session_state.current_chat_id:
    st.warning("👈 Πατήστε στο κουμπί 'Νέα Συνομιλία' στο Sidebar για να ξεκινήσετε!")
    st.stop()

# Φόρτωση των μηνυμάτων του επιλεγμένου Chat
active_messages = st.session_state.all_chats[st.session_state.current_chat_id]["messages"]

for msg in active_messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# --- 6. CHAT INPUT & PROCESSING ---
if user_input := st.chat_input("Γράψτε το μήνυμά σας..."):
    with st.chat_message("user"):
        st.write(user_input)
        
    # Προσθήκη μηνύματος και αυτόματη μετονομασία του τίτλου του Chat αν είναι το πρώτο μήνυμα
    active_messages.append({"role": "user", "content": user_input})
    if len(active_messages) == 1:
        st.session_state.all_chats[st.session_state.current_chat_id]["title"] = user_input[:25] + "..."
        
    st.session_state.all_chats[st.session_state.current_chat_id]["messages"] = active_messages
    save_chats_to_browser()

    # (Η υπόλοιπη λογική αναζήτησης και Groq API παραμένει ίδια)
    greetings = ["γεια", "γεια σου", "γεια σας", "καλημερα", "καλησπερα", "hi", "hello"]
    clean_input = user_input.lower().strip()
    is_greeting = clean_input in greetings or len(clean_input.split()) <= 1

    search_context = ""
    search_query = user_input
    has_greek = any('α' <= char <= 'ώ' or 'Α' <= char <= 'Ω' for char in user_input)
    lang_mirror_rule = "\n\n CRITICAL: Speak strictly in Greek." if has_greek else "\n\n CRITICAL: Speak strictly in English."

    if not is_greeting:
        try:
            rewrite_res = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": f"Convert to 2-4 keywords for Wikipedia: {user_input}"}],
                temperature=0.1
            )
            search_query = rewrite_res.choices.message.content.strip()
        except:
            search_query = user_input

        with st.spinner("🔍 Αναζήτηση..."):
            results = search_the_web(search_query)

        if results:
            search_context = f"\n\n[LIVE DATA]:\n{results}\n\n- TIMELINE: Year 2026. iPhone 17 series released late 2025. Treat as real product."
        else:
            search_context = "\n\n[SYSTEM NOTICE]: No results found."

    full_system_prompt = personalities[selected_persona] + "\n[SYSTEM: Year is 2026]" + search_context + lang_mirror_rule
    api_messages = [{"role": "system", "content": full_system_prompt}]
    api_messages.extend(active_messages[-10:])

    with st.chat_message("assistant"):
        with st.spinner("Σκέφτομαι..."):
            try:
                chat_completion = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=api_messages,
                    temperature=0.3
                )
                assistant_response = chat_completion.choices.message.content
                st.write(assistant_response)
