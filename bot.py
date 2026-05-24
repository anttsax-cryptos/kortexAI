import streamlit as st
import json
import os
import datetime
from groq import Groq
from duckduckgo_search import DDGS

# 1. Φάκελος για την αποθήκευση των συνομιλιών τοπικά
CHATS_DIR = "chats"
if not os.path.exists(CHATS_DIR):
    os.makedirs(CHATS_DIR)

# 2. Έλεγχος API Key στα Secrets του Streamlit
if "GROQ_API_KEY" not in st.secrets:
    st.error("⚠️ Παρακαλώ προσθέστε το GROQ_API_KEY στα Streamlit Secrets!")
    st.stop()

# Αρχικοποίηση Groq Client
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- ΣΥΝΑΡΤΗΣΕΙΣ ΔΙΑΧΕΙΡΙΣΗΣ ΙΣΤΟΡΙΚΟΥ ---
def get_all_chats():
    if not os.path.exists(CHATS_DIR):
        return []
    files = [f for f in os.listdir(CHATS_DIR) if f.endswith(".json")]
    files.sort(key=lambda x: os.path.getmtime(os.path.join(CHATS_DIR, x)), reverse=True)
    return [os.path.splitext(f)[0] for f in files]

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

# --- ΣΥΝΑΡΤΗΣΗ ΑΝΑΖΗΤΗΣΗΣ DUCKDUCKGO ---
def search_web(query, max_results=3):
    try:
        context_list = []
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
            if results:
                for r in results:
                    context_list.append(f"Τίτλος: {r.get('title')}\nLink: {r.get('href')}\nΠληροφορία: {r.get('body')}")
        return "\n\n".join(context_list) if context_list else None
    except Exception:
        return None

# --- CONFIGURATION ΣΕΛΙΔΑΣ ---
st.set_page_config(page_title="StrictexAI", layout="wide", page_icon="🤖")
st.title("🤖 StrictexAI Chatbot")

# Ορισμός Προσωπικοτήτων
personalities = {
    "Friendly Assistant": "Είσαι ο StrictexAI, ένας πολύ φιλικός, ευγενικός και βοηθητικός βοηθός.",
    "Expert Programmer": "Είσαι ένας κορυφαίος Senior Software Engineer. Απάντα με ακρίβεια και καθαρά block κώδικα.",
    "Sarcastic Buddy": "Είσαι ένας έξυπνος, ειρωνικός και σαρκαστικός φίλος. Χρησιμοποίησε χιούμορ και πειράγματα.",
    "Creative Storyteller": "Είσαι ένας ευφάνταστος συγγραφέας παραμυθιών και ιστοριών. Δώσε δημιουργικό ύφος στις απαντήσεις σου.",
    "Patient Teacher": "Είσαι ένας υπομονετικός και βοηθητηκος δάσκαλος. Εξήγησε τα πάντα απλά, βήμα-βήμα, με παραδείγματα."
}

# Αρχικοποίηση Τρέχουσας Συνομιλίας στο Session State
if "current_chat" not in st.session_state:
    all_chats = get_all_chats()
    st.session_state.current_chat = all_chats[0] if all_chats else f"Chat_{datetime.datetime.now().strftime('%Y%M%S')}"

if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history(st.session_state.current_chat)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Ρυθμίσεις & Ιστορικό")
    
    # Επιλογή Προσωπικότητας
    selected_personality = st.selectbox("🎭 Επιλογή Προσωπικότητας:", list(personalities.keys()))
    
    st.divider()
    
    # Διαχείριση Συνομιλιών
    all_chats = get_all_chats()
    
    # Επιλογή υπάρχουσας συνομιλίας
    if all_chats:
        selected_chat = st.selectbox("💬 Επιλέξτε Συνομιλία:", all_chats, index=all_chats.index(st.session_state.current_chat) if st.session_state.current_chat in all_chats else 0)
        if selected_chat != st.session_state.current_chat:
            st.session_state.current_chat = selected_chat
            st.session_state.messages = load_chat_history(selected_chat)
            st.rerun()

    # Κουμπί Νέας Συνομιλίας
    if st.button("➕ Νέα Συνομιλία", use_container_width=True):
        new_id = f"Chat_{datetime.datetime.now().strftime('%d%m_%H%M%S')}"
        st.session_state.current_chat = new_id
        st.session_state.messages = []
        save_chat_history(new_id, [])
        st.rerun()
        
    # Κουμπί Διαγραφής Τρέχουσας Συνομιλίας
    if st.button("🗑️ Διαγραφή Συνομιλίας", use_container_width=True, type="primary"):
        file_path = os.path.join(CHATS_DIR, f"{st.session_state.current_chat}.json")
        if os.path.exists(file_path):
            os.remove(file_path)
        
        remaining_chats = get_all_chats()
        if remaining_chats:
            st.session_state.current_chat = remaining_chats[0]
            st.session_state.messages = load_chat_history(remaining_chats[0])
        else:
            new_id = f"Chat_{datetime.datetime.now().strftime('%d%m_%H%M%S')}"
            st.session_state.current_chat = new_id
            st.session_state.messages = []
            save_chat_history(new_id, [])
        st.rerun()

# --- ΚΥΡΙΩΣ CHAT INTERFACE ---

# Εμφάνιση παλιών μηνυμάτων
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Εισαγωγή νέου μηνύματος από τον χρήστη
if user_input := st.chat_input("Γράψτε το μήνυμά σας εδώ..."):
    
    # 1. Εμφάνιση & Αποθήκευση μηνύματος χρήστη
    with st.chat_message("user"):
        st.write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    save_chat_history(st.session_state.current_chat, st.session_state.messages)
    
    # 2. Έξυπνη απόφαση για Αναζήτηση στο Internet (Routing)
    router_prompt = (
        f"Ανάλυσε την ερώτηση του χρήστη: '{user_input}'. "
        "Χρειάζεται πρόσφατες πληροφορίες, γεγονότα, νέα, live δεδομένα ή αναζήτηση στο internet για να απαντηθεί σωστά; "
        "Απάντησε ΑΥΣΤΗΡΑ με μία μόνο λέξη: YES ή NO."
    )
    
    try:
        route_check = client.chat.completions.create(
            model="llama-3.3-70b-specdec",
            messages=[{"role": "user", "content": router_prompt}],
            temperature=0.0
        )
        decision = route_check.choices[0].message.content.strip().upper()
    except Exception:
        decision = "NO"

    # Αν το μοντέλο πει YES, ψάχνουμε στο DuckDuckGo
    search_context = ""
    if "YES" in decision:
        with st.spinner("🔍 Αναζήτηση πληροφοριών στο διαδίκτυο..."):
            results = search_web(user_input)
            if results:
                search_context = f"\n\n[Πληροφορίες από το Internet]:\n{results}\n\nΧρησιμοποίησε τις παραπάνω πληροφορίες για να απαντήσεις αν κρίνεις απαραίτητο."

    # 3. Κατασκευή των μηνυμάτων για το Groq API
    full_system_prompt = personality[selected_personality] + search_context
    
    api_messages = [{"role": "system", "content": full_system_prompt}]
    for msg in st.session_state.messages:
        api_messages.append({"role": msg["role"], "content": msg["content"]})
        
    # 4. Κλήση Groq για την τελική απάντηση
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                chat_completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile", 
                    messages=api_messages,
                    temperature=0.7
                )
                assistant_response = chat_completion.choices[0].message.content
                st.write(assistant_response)
                
                # Αποθήκευση απάντησης
                st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                save_chat_history(st.session_state.current_chat, st.session_state.messages)
            except Exception as e:
                st.error(f"Σφάλμα κατά την επικοινωνία με το Groq: {e}")
               
