import streamlit as st
import json
import os
import datetime
import requests
import urllib.parse
from groq import Groq

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

# --- 3. ΣΥΝΑΡΤΗΣΗ ΑΝΑΖΗΤΗΣΗΣ WIKIPEDIA (ΜΕ ΕΞΥΠΝΗ ΑΝΑΖΗΤΗΣΗ KEYWORDS) ---
# --- 3. ΣΥΝΑΡΤΗΣΗ ΑΝΑΖΗΤΗΣΗΣ WIKIPEDIA (ΜΕ ΠΛΗΡΕΣ ΚΕΙΜΕΝΟ ΑΡΘΡΟΥ) ---
def search_wikipedia(query, max_characters=2000):
    # Καθαρισμός του query από περιττές φράσεις
    stop_words = ["πες μου για το", "τι ειναι το", "ποιος ειναι ο", "υπαρχει το", "δειξε μου", "πληροφοριες για"]
    clean_query = query.lower()
    for word in stop_words:
        clean_query = clean_query.replace(word, "")
    clean_query = clean_query.strip()

    formatted_query = urllib.parse.quote_plus(clean_query)
    headers = {"User-Agent": "StrictexAIChatbot/2.0 (contact@example.com)"}
    
    # Δοκιμή πρώτα στα Ελληνικά (el) και μετά στα Αγγλικά (en) για μεγαλύτερη βάση δεδομένων
    for lang in ["el", "en"]:
        try:
            # Βήμα 1: Αναζήτηση για να βρούμε τον ακριβή τίτλο του άρθρου
            search_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={formatted_query}&srlimit=1&format=json"
            search_response = requests.get(search_url, headers=headers, timeout=5)
            
            if search_response.status_code == 200:
                search_data = search_response.json()
                results = search_data.get("query", {}).get("search", [])
                
                if not results:
                    continue # Αν δεν βρει τίποτα σε αυτή τη γλώσσα, πάει στην επόμενη
                
                exact_title = results[0]["title"]
                formatted_title = urllib.parse.quote_plus(exact_title)
                
                # Βήμα 2: Λήψη ολόκληρου του κειμένου (extract) του συγκεκριμένου άρθρου
                content_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=extracts&exintro=0&explaintext=1&titles={formatted_title}&format=json"
                content_response = requests.get(content_url, headers=headers, timeout=5)
                
                if content_response.status_code == 200:
                    content_data = content_response.json()
                    pages = content_data.get("query", {}).get("pages", {})
                    
                    for page_id, page_info in pages.items():
                        extract = page_info.get("extract", "")
                        if extract.strip():
                            # Κρατάμε μέχρι το όριο χαρακτήρων για να μην ξεπεράσουμε τα όρια του prompt
                            if len(extract) > max_characters:
                                extract = extract[:max_characters] + "..."
                            return f"[{lang.upper()} WIKIPEDIA ARTICLE: {exact_title}]\n{extract}"
        except Exception:
            continue
            
    return None



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
        
        # Παίρνουμε τα τελευταία 4 μηνύματα για να ξέρει το AI για ποιο πράγμα μιλάμε
        rewrite_messages = []
        for msg in st.session_state.messages[-5:-1]:
            rewrite_messages.append({"role": msg["role"], "content": msg["content"]})
        rewrite_messages.append({"role": "user", "content": rewriter_prompt})
        
        try:
            rewrite_res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=rewrite_messages,
                temperature=0.0 # 0 για απόλυτη σταθερότητα
            )
            search_query = rewrite_res.choices[0].message.content.strip()
        except Exception:
            search_query = user_input

    # 3. Αναζήτηση στη Wikipedia με τα έξυπνα Keywords
    search_context = ""
    with st.spinner(f"🔍 Αναζήτηση για '{search_query}'..."):
        results = search_wikipedia(search_query, max_results=2)
        if results:
            search_context = f"\n\n[ΠΡΟΣΦΑΤΑ ΔΕΔΟΜΕΝΑ WIKIPEDIA]:\n{results}\n\nΟδηγία: Απάντησε βασιζόμενος αυστηρά στα παραπάνω δεδομένα της Wikipedia."

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
                assistant_response = chat_completion.choices[0].message.content
                st.write(assistant_response)
                
                # Αποθήκευση στο ιστορικό
                st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                save_chat_history(st.session_state.current_chat, st.session_state.messages)
            except Exception as e:
                st.error(f"Σφάλμα κατά την επικοινωνία με το Groq: {e}")
