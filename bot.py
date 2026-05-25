import streamlit as st
import json
import os
import datetime
from groq import Groq
import requests
import urllib.parse

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

# --- ΣΥΝΑΡΤΗΣΗ ΑΝΑΖΗΤΗΣΗΣ WIKIPEDIA (ΜΕ ΦΙΛΤΡΟ ΜΕΓΕΘΟΥΣ) ---
# --- ΔΙΟΡΘΩΜΕΝΗ ΣΥΝΑΡΤΗΣΗ WIKIPEDIA ---
def search_wikipedia(query, max_results=1):
    context_list = []
    formatted_query = urllib.parse.quote_plus(query)
    headers = {"User-Agent": "StrictexAIChatbot/2.0 (contact@example.com)"}
    
    # 1. Δοκιμή στην Ελληνική Wikipedia με σωστό Opensearch Parsing
    try:
        url_el = f"https://wikipedia.org{formatted_query}&limit={max_results}&namespace=0&format=json"
        response = requests.get(url_el, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Το data[1] είναι οι τίτλοι, το data[2] είναι τα αποσπάσματα κειμένου (snippets)
            if len(data) >= 3 and data[1]:
                for i in range(len(data[1])):
                    title = data[1][i]
                    snippet = data[2][i] if i < len(data[2]) else ""
                    if len(snippet) > 300:  # Αυστηρό όριο χαρακτήρων
                        snippet = snippet[:300] + "..."
                    context_list.append(f"Τίτλος: {title}\nΠληροφορία: {snippet}")
    except Exception:
        pass

    # 2. Αν δεν βρέθηκε τίποτα, δοκιμή στην Αγγλική Wikipedia
    if not context_list:
        try:
            url_en = f"https://wikipedia.org{formatted_query}&limit={max_results}&namespace=0&format=json"
            response = requests.get(url_en, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if len(data) >= 3 and data[1]:
                    for i in range(len(data[1])):
                        title = data[1][i]
                        snippet = data[2][i] if i < len(data[2]) else ""
                        if len(snippet) > 300:
                            snippet = snippet[:300] + "..."
                        context_list.append(f"Title: {title}\nInformation: {snippet}")
        except Exception:
            pass

    return "\n\n".join(context_list) if context_list else None


# --- ΚΥΡΙΑ ΛΕΙΤΟΥΡΓΙΑ CHAT INPUT (Αντικαταστήστε μόνο αυτό το block στο τέλος) ---
if user_input := st.chat_input("Γράψτε το μήνυμά σας εδώ..."):
    
    # 1. Εμφάνιση και αποθήκευση του μηνύματος του χρήστη
    with st.chat_message("user"):
        st.write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 2. Αναζήτηση στη Wikipedia (Φέρνει αυστηρά 1 αποτέλεσμα)
    wiki_context = search_wikipedia(user_input, max_results=1)
    
    # 3. Προετοιμασία εμπλουτισμένου μηνύματος για το AI
    if wiki_context:
        user_content = f"""Χρησιμοποίησε τις παρακάτω σύντομες πληροφορίες από τη Wikipedia για να απαντήσεις:
        
{wiki_context}

Ερώτηση: {user_input}"""
    else:
        user_content = user_input

    # 4. ΦΙΛΤΡΑΡΙΣΜΑ ΙΣΤΟΡΙΚΟΥ (Κρατάμε μόνο 4 προηγούμενα μηνύματα για απόλυτη ασφάλεια)
    recent_messages = [{"role": "system", "content": personalities[selected_persona]}]
    recent_messages.extend(st.session_state.messages[-4:-1])  
    recent_messages.append({"role": "user", "content": user_content}) 

    # 5. Κλήση Groq API με τη νέα φιλτραρισμένη λίστα
    with st.chat_message("assistant"):
        try:
            response = client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=recent_messages,  
                temperature=0.6,
            )
            
            answer = response.choices.message.content
            st.write(answer)
            
            # Αποθήκευση απάντησης
            st.session_state.messages.append({"role": "assistant", "content": answer})
            save_chat_history(st.session_state.current_chat, st.session_state.messages)
            
        except Exception as e:
            st.error(f"Σφάλμα κατά την επικοινωνία με το Groq: {e}")
            
    
    # 1. Δοκιμή στην Ελληνική Wikipedia
    try:
        url_el = f"https://wikipedia.org{formatted_query}&limit={max_results}&namespace=0&format=json"
        response = requests.get(url_el, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            # Η Wikipedia επιστρέφει: [query, [titles], [descriptions], [urls]]
            if len(data) >= 4 and data[1]:  
                for i in range(len(data[1])):
                    title = data[1][i]
                    snippet = data[2][i] if i < len(data[2]) else ""
                    # Κόβουμε το κείμενο αν είναι πολύ μεγάλο για ασφάλεια
                    if len(snippet) > 500:
                        snippet = snippet[:500] + "..."
                    context_list.append(f"Τίτλος: {title}\nΠληροφορία: {snippet}")
    except Exception:
        pass

    # 2. Αν δεν βρέθηκε τίποτα, δοκιμή στην Αγγλική Wikipedia
    if not context_list:
        try:
            url_en = f"https://wikipedia.org{formatted_query}&limit={max_results}&namespace=0&format=json"
            response = requests.get(url_en, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if len(data) >= 4 and data[1]:
                    for i in range(len(data[1])):
                        title = data[1][i]
                        snippet = data[2][i] if i < len(data[2]) else ""
                        if len(snippet) > 500:
                            snippet = snippet[:500] + "..."
                        context_list.append(f"Title: {title}\nInformation: {snippet}")
        except Exception:
            pass
 return "\n\n".join(context_list) if context_list else None:

# --- CONFIGURATION ΣΕΛΙΔΑΣ ---
st.set_page_config(page_title="StrictexAI v2", layout="wide", page_icon="🤖")
st.title("🤖 StrictexAI ChatBot")

# Ορισμός Προσωπικοτήτων
personalities = {
    "Friendly Assistant": "Είσαι ο StrictexAI, ένας πολύ φιλικός, ευγενικός και βοηθητικός βοηθός.",
    "Expert Programmer": "Είσαι ένας κορυφαίος Senior Software Engineer. Απάντα με ακρίβεια και καθαρά block κώδικα.",
    "Sarcastic Buddy": "Είσαι ένας έξυπνος, ειρωνικός και σαρκαστικός φίλος. Χρησιμοποίησε χιούμορ και πειράγματα.",
    "Creative Storyteller": "Είσαι ένας ευφάνταστος συγγραφέας παραμυθιών και ιστοριών. Δώσε δημιουργικό ύφος στις απαντήσεις σου.",
    "Patient Teacher": "Είσαι ένας υπομονετικός δάσκαλος. Εξήγησε τα πάντα απλά, βήμα-βήμα, με παραδείγματα."
}

# Αρχικοποίηση μεταβλητών στο Session State
if "current_chat" not in st.session_state:
    all_chats = get_all_chats()
    if all_chats:
        st.session_state.current_chat = all_chats[0]
    else:
        st.session_state.current_chat = f"Chat_{datetime.datetime.now().strftime('%d%m_%H%M%S')}"

if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history(st.session_state.current_chat)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Ρυθμίσεις & Ιστορικό")
    
    # Επιλογή Προσωπικότητας
    selected_persona = st.selectbox(
        "🎭 Επιλογή Προσωπικότητας:", 
        list(personalities.keys()), 
        key="persona_selector"
    )
    
    st.divider()
    
    # Διαχείριση Συνομιλιών
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
# --- ΚΥΡΙΑ ΛΕΙΤΟΥΡΓΙΑ CHAT INPUT (ΑΝΤΙΚΑΤΑΣΤΑΣΗ ΜΟΝΟ ΕΔΩ) ---
if user_input := st.chat_input("Γράψτε το μήνυμά σας εδώ..."):
    
    # 1. Εμφάνιση και αποθήκευση του μηνύματος του χρήστη
    with st.chat_message("user"):
        st.write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # 2. Αναζήτηση στη Wikipedia για φρέσκια πληροφορία
    wiki_context = search_wikipedia(user_input)
    
    # 3. Προετοιμασία εμπλουτισμένου μηνύματος για το AI
    if wiki_context:
        user_content = f"""Χρησιμοποίησε τις παρακάτω πρόσφατες πληροφορίες από τη Wikipedia για να απαντήσεις στην ερώτηση του χρήστη.

Πληροφορίες Wikipedia:
{wiki_context}

Ερώτηση Χρήστη: {user_input}"""
    else:
        user_content = user_input

    # 4. ΦΙΛΤΡΑΡΙΣΜΑ ΙΣΤΟΡΙΚΟΥ (Λύνει το σφάλμα 413)
    # Κρατάμε το System Prompt της προσωπικότητας και τα τελευταία 6 μηνύματα συνομιλίας
    recent_messages = [{"role": "system", "content": personalities[selected_persona]}]
    recent_messages.extend(st.session_state.messages[-6:-1])  # Το προηγούμενο ιστορικό χωρίς το τρέχον μήνυμα
    recent_messages.append({"role": "user", "content": user_content}) # Το τρέχον μήνυμα μαζί με το Wiki context

    # 5. Κλήση Groq API με τη νέα φιλτραρισμένη λίστα
    with st.chat_message("assistant"):
        try:
            response = client.chat.completions.create(
                messages=recent_messages,  # Χρήση της περιορισμένης λίστας recent_messages
                temperature=0.6,
            )
            
            answer = response.choices.message.content
            st.write(answer)
            
            # Αποθήκευση απάντησης του Assistant στο ιστορικό
            st.session_state.messages.append({"role": "assistant", "content": answer})
            save_chat_history(st.session_state.current_chat, st.session_state.messages)
            
        except Exception as e:
            st.error(f"Σφάλμα κατά την επικοινωνία με το Groq: {e}")
    
    # 2. Έξυπνη απόφαση για Αναζήτηση (Routing)
    router_prompt = (
        f"Ανάλυσε την ερώτηση του χρήστη: '{user_input}'. "
        "Αν η ερώτηση αφορά συγκεκριμένα ιστορικά γεγονότα, πρόσωπα, επιστήμη, γεωγραφία, ορισμούς, "
        "ή εγκυκλοπαιδικές γνώσεις που χρειάζονται επιβεβαίωση, απάντησε ΑΥΣΤΗΡΑ YES. "
        "Αν είναι απλή κουβέντα, κώδικας ή προσωπική γνώμη, απάντησε NO. "
        "Απάντησε με μία μόνο λέξη: YES ή NO."
    )
    
    try:
        route_check = client.chat.completions.create(
            model="groq/compound-mini",
            messages=[{"role": "user", "content": router_prompt}],
            temperature=0.0
        )
        decision = route_check.choices[0].message.content.strip().upper()
    except Exception:
        decision = "YES"

    # Αν το μοντέλο πει YES, ψάχνουμε στην Wikipedia
    search_context = ""
    if "YES" in decision:
        with st.spinner("🔍 Αναζήτηση στην Wikipedia..."):
            results = search_wikipedia(user_input)
            if results:
                search_context = f"\n\n[Πληροφορίες από την Wikipedia]:\n{results}\n\nΧρησιμοποίησε τα παραπάνω δεδομένα για να απαντήσεις."

    # 3. Κατασκευή των μηνυμάτων για το Groq API
    full_system_prompt = personalities[selected_persona] + search_context
    
    api_messages = [{"role": "system", "content": full_system_prompt}]
    for msg in st.session_state.messages:
        api_messages.append({"role": msg["role"], "content": msg["content"]})
        
    # 4. Κλήση Groq για την τελική απάντηση
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                chat_completion = client.chat.completions.create(
                    model="groq/compound",
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
        
