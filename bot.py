import streamlit as st
import json
import os
import datetime
import requests
import urllib.parse
from groq import Groq

# --- 1. CONFIGURATION ΣΕΛΙΔΑΣ (ΠΑΝΤΑ ΠΡΩΤΟ!) ---
st.set_page_config(page_title="StrictexAI v2", layout="wide", page_icon="🤖")

# Φάκελος για την αποθήκευση των συνομιλιών τοπικά
CHATS_DIR = "chats"
if not os.path.exists(CHATS_DIR):
    os.makedirs(CHATS_DIR)

# Έλεγχος API Key στα Secrets του Streamlit
if "GROQ_API_KEY" not in st.secrets:
    st.error("⚠ Παρακαλώ προσθέστε το GROQ_API_KEY στα Streamlit Secrets!")
    st.stop()

# Αρχικοποίηση Groq Client
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# Ορισμός Προσωπικοτήτων
personalities = {
    "Friendly Assistant": "Είσαι ο StrictexAI, ένας πολύ φιλικός, ευγενικός και βοηθητικός βοηθός.",
    "Expert Programmer": "Είσαι ένας κορυφαίος Senior Software Engineer. Απάντα με ακρίβεια και καθαρά block κώδικα.",
    "Sarcastic Buddy": "Είσαι ένας έξυπνος, ειρωνικός και σαρκαστικός φίλος. Χρησιμοποίησε χιούμορ και πειράγματα.",
    "Creative Storyteller": "Είσαι ένας ευφάνταστος συγγραφέας παραμυθιών και ιστοριών. Δώσε δημιουργικό ύφος στις απαντήσεις σου.",
    "Patient Teacher": "Είσαι ένας υπομονετικός δάσκαλος. Εξήγησε τα πάντα απλά, βήμα-βήμα, με παραδείγματα."
}

# --- 2. ΣΥΝΑΡΤΗΣΕΙΣ ΔΙΑΧΕΙΡΙΣΗΣ ΙΣΤΟΡΙΚΟΥ ---
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

# --- 3. ΣΥΝΑΡΤΗΣΗ ΑΝΑΖΗΤΗΣΗΣ WIKIPEDIA (ΔΙΟΡΘΩΜΕΝΗ) ---
def search_wikipedia(query, max_results=1):
    context_list = []
    formatted_query = urllib.parse.quote_plus(query)
    headers = {"User-Agent": "StrictexAIChatbot/2.0 (contact@example.com)"}
    
    # Δοκιμή στην Ελληνική (el) και μετά στην Αγγλική (en) Wikipedia
    for lang in ["el", "en"]:
        try:
            url = f"https://{lang}.wikipedia.org/w/api.php?action=opensearch&search={formatted_query}&limit={max_results}&namespace=0&format=json"
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if len(data) >= 3 and data[1] and data[2]:
                    for i in range(len(data[1])):
                        title = data[1][i]
                        snippet = data[2][i]
                        if len(snippet) > 300:
                            snippet = snippet[:300] + "..."
                        context_list.append(f"[{lang.upper()}] Τίτλος: {title}\nΠληροφορία: {snippet}")
                    break # Αν βρει στην Ελληνική, σταματάει
        except Exception:
            continue
            
    return "\n\n". join(context_list) if context_list else None

# --- 4. ΑΡΧΙΚΟΠΟΙΗΣΗ SESSION STATE ---
if "current_chat" not in st.session_state:
    all_chats = get_all_chats()
    if all_chats:
        st.session_state.current_chat = all_chats[0]
    else:
        st.session_state.current_chat = f"Chat_{datetime.datetime.now().strftime('%d%m_%H%M%S')}"

if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history(st.session_state.current_chat)

# --- 5. SIDEBAR GRAPHICS ---
with st.sidebar:
    st.header("⚙ Ρυθμίσεις & Ιστορικό")
    
    selected_persona = st.selectbox(
        "🎭 Επιλογή Προσωπικότητας:",
        list(personalities.keys()),
        key="persona_selector"
    )
    st.divider()
    
    all_chats = get_all_chats()
    if all_chats:
        if st.session_state.current_chat not in all_chats:
            st.session_state.current_chat = all_chats[0]
        current_index = all_chats.index(st.session_state.current_chat)
        selected_chat = st.selectbox(
            "💬 Επιλέξτε Συνομιλία:",
            all_chats,
            index=current_index,
            key="chat_selector"
        )
        if selected_chat != st.session_state.current_chat:
            st.session_state.current_chat = selected_chat
            st.session_state.messages = load_chat_history(selected_chat)
            st.rerun()

    if st.button("➕ Νέα Συνομιλία", use_container_width=True):
        new_id = f"Chat_{datetime.datetime.now().strftime('%d%m_%H%M%S')}"
        st.session_state.current_chat = new_id
        st.session_state.messages = []
        save_chat_history(new_id, [])
        st.rerun()

    if st.button("🗑 Διαγραφή Συνομιλίας", use_container_width=True, type="primary"):
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

# --- 6. ΚΥΡΙΩΣ INTERFACE & ΕΜΦΑΝΙΣΗ CHAT ---
st.title("🤖 StrictexAI ChatBot")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# --- 7. ΛΟΓΙΚΗ ΕΙΣΑΓΩΓΗΣ ΜΗΝΥΜΑΤΟΣ & ROUTING (ΕΝΟΠΟΙΗΜΕΝΗ) ---
if user_input := st.chat_input("Γράψτε το μήνυμά σας εδώ..."):
    
    with st.chat_message("user"):
        st.write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # Έξυπνη απόφαση για Αναζήτηση (Routing) μέσω Groq
    decision = "NO"
    router_prompt = (
        f"Ανάλυσε την ερώτηση του χρήστη: '{user_input}'. "
        "Αν η ερώτηση αφορά συγκεκριμένα ιστορικά γεγονότα, πρόσωπα, επιστήμη, γεωγραφία, ορισμούς, "
        "ή εγκυκλοπαιδικές γνώσεις, απάντησε ΑΥΣΤΗΡΑ με τη λέξη YES. αλλιώς απάντησε NO."
    )
    try:
        route_check = client.chat.completions.create(
            model="llama3-8b-8192",  # Διορθωμένο έγκυρο μοντέλο
            messages=[{"role": "user", "content": router_prompt}],
            temperature=0.0
        )
        decision = route_check.choices[0].message.content.strip().upper()
    except Exception:
        decision = "YES"

    # Αν χρειάζεται Wikipedia
    search_context = ""
    if "YES" in decision:
        with st.spinner("🔍 Αναζήτηση στην Wikipedia..."):
            results = search_wikipedia(user_input)
            if results:
                search_context = f"\n\n[Πληροφορίες από την Wikipedia]:\n{results}"

    # Χτίσιμο μηνυμάτων για την τελική απάντηση (Μέγιστο 6 προηγούμενα μηνύματα)
    full_system_prompt = personalities[selected_persona] + search_context
    api_messages = [{"role": "system", "content": full_system_prompt}]
    
    # Προσθήκη πρόσφατου ιστορικού
    api_messages.extend(st.session_state.messages[-6:])

    # Κλήση Groq για την τελική απάντηση
    with st.chat_message("assistant"):
        with st.spinner("Σκέφτομαι..."):
            try:
                chat_completion = client.chat.completions.create(
                    model="mixtral-8x7b-32768",  # Διορθωμένο έγκυρο μοντέλο
                    messages=api_messages,
                    temperature=0.7
                )
                assistant_response = chat_completion.choices[0].message.content
                st.write(assistant_response)
                
                # Αποθήκευση
                st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                save_chat_history(st.session_state.current_chat, st.session_state.messages)
            except Exception as e:
                st.error(f"Σφάλμα κατά την επικοινωνία με το Groq: {e}")
