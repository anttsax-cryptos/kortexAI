import streamlit as st
import json
import os
import datetime
import requests
import urllib.parse
from groq import Groq
from duckduckgo_search import DDGS

# --- 1. CONFIGURATION ΣΕΛΙΔΑΣ ---
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

# --- 3. ΝΕΑ ΣΥΝΑΡΤΗΣΗ LIVE WEB SEARCH (DUCKDUCKGO) ---
def search_the_web(query, max_results=4):
    context_list = []
    try:
        # Live αναζήτηση στο web χωρίς API Key
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=max_results)]
            for item in results:
                title = item.get("title", "")
                snippet = item.get("body", "")
                link = item.get("href", "")
                context_list.append(f"Τίτλος: {title}\nΠηγή: {link}\nΠληροφορία: {snippet}")
    except Exception as e:
        print(f"Search Error: {e}")
        
    return "\n\n".join(context_list) if context_list else None

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

# --- 7. ΕΞΑΝΑΓΚΑΣΜΕΝΗ ΑΝΑΖΗΤΗΣΗ ΜΕ AI QUERY REWRITING & ΑΠΑΝΤΗΣΗ ---
if user_input := st.chat_input("Γράψτε το μήνυμά σας εδώ..."):
    
    # 1. Εμφάνιση μηνύματος χρήστη
    with st.chat_message("user"):
        st.write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    # 2. AI QUERY REWRITING: Μετατροπή της ερώτησης σε καθαρά Keywords αναζήτησης με βάση το ιστορικό
    search_query = user_input
    if len(st.session_state.messages) > 1:
        rewriter_prompt = (
            "Είσαι ένας βοηθός αναζήτησης. Με βάση την τελευταία ερώτηση του χρήστη και το πρόσφατο ιστορικό, "
            "γράψε ένα σύντομο κείμενο αναζήτησης (keywords) για τη Wikipedia στα Αγγλικά ή Ελληνικά. "
            "Αν ο χρήστης χρησιμοποιεί αντωνυμίες όπως 'αυτό', 'το', 'του', αντικατάστησέ τις με το σωστό όνομα του προϊόντος ή προσώπου. "
            "Απάντησε ΑΥΣΤΗΡΑ μόνο με τις λέξεις-κλειδιά αναζήτησης, τίποτα άλλο.\n\n"
            f"Τελευταία ερώτηση: {user_input}"
        )
        
        # Παίρνουμε τα τελευταία 4 μηνύματα για πλαίσιο
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
            # ΔΙΟΡΘΩΣΗ: Προσθήκη [0] στα choices
            search_query = rewrite_res.choices[0].message.content.strip()
        except Exception:
            search_query = user_input

    # 3. Live Αναζήτηση στο Web με τα έξυπνα Keywords
    search_context = ""
    with st.spinner(f"🔍 Ζωντανή αναζήτηση στο Web για '{search_query}'..."):
        # Καλούμε τη νέα συνάρτηση web search
        results = search_the_web(search_query, max_results=4) 
        if results:
            search_context = (
                f"\n\n[ΠΡΟΣΦΑΤΑ ΔΕΔΟΜΕΝΑ ΑΠΟ ΤΟ WEB]:\n{results}\n\n"
                "Οδηγία: Απάντησε με αρκετή λεπτομέρεια. "
                "Φτιάξε κατηγορίες (π.χ. Σχεδιασμός, Τεχνικά χαρακτηριστικά, λειτουργείες, πλεονεκτήματα και μειωνεκτήματα) "
                "χρησιμοποίησε bullet points (κουκκίδες) για να παρουσιάσεις αναλυτικά τα χαρακτηριστικά."
            )

    # 4. Δημιουργία Μηνυμάτων για το Groq API
    full_system_prompt = personalities[selected_persona] + search_context
    api_messages = [{"role": "system", "content": full_system_prompt}]
    
    # Κρατάμε τα τελευταία 12 μηνύματα για μνήμη
    api_messages.extend(st.session_state.messages[-12:])

    # 5. Κλήση Groq για την τελική απάντηση
    with st.chat_message("assistant"):
        with st.spinner("Σκέφτομαι..."):
            try:
                chat_completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=api_messages,
                    temperature=0.4
                )
                # ΔΙΟΡΘΩΣΗ: Προσθήκη [0] στα choices
                assistant_response = chat_completion.choices[0].message.content
                st.write(assistant_response)
                
                # Αποθήκευση στο ιστορικό
                st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                save_chat_history(st.session_state.current_chat, st.session_state.messages)
            except Exception as e:
                st.error(f"Σφάλμα κατά την επικοινωνία με το Groq: {e}")

