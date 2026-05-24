import streamlit as st
import json
import os
import datetime
from groq import Groq 
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re

# Φάκελος για την αποθήκευση όλων των συνομιλιών
CHATS_DIR = "chats"
if not os.path.exists(CHATS_DIR):
    os.makedirs(CHATS_DIR)

# 1. Έλεγχος API Key στα Secrets του Streamlit
if "GROQ_API_KEY" not in st.secrets:
    st.error("⚠️ Παρακαλώ προσθέστε το GROQ_API_KEY στα Streamlit Secrets!")
    st.stop()

# 2. Αρχικοποίηση του Groq Client
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# Συναρτήσεις για διαχείριση πολλαπλών αρχείων συνομιλιών
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

# Αυτοματοποιημένη μετονομασία αρχείου συνομιλίας με δομή Groq
def rename_chat_file(old_chat_id, user_input, selected_model, messages):
    try:
        rename_prompt = f"Summarize this in 2 words: {user_input}"
        title_response = client.chat.completions.create(
            model=selected_model,
            messages=[{"role": "user", "content": rename_prompt}]
        )
        new_title = title_response.choices[0].message.content.strip().replace('"', '').replace('.', '')
        new_title = "".join(c for c in new_title if c.isalnum() or c in " _-").strip()
    except Exception:
        new_title = "Saved Chat"
        
    if not new_title:
        new_title = "Saved Chat"
        
    if new_title in get_all_chats():
        new_title += f"_{datetime.datetime.now().strftime('%H%M%S')}"
        
    old_file = os.path.join(CHATS_DIR, f"{old_chat_id}.json")
    new_file = os.path.join(CHATS_DIR, f"{new_title}.json")
    
    save_chat_history(old_chat_id, messages)
    if os.path.exists(old_file):
        os.rename(old_file, new_file)
    return new_title

# Σταθερή αναζήτηση μέσω DuckDuckGo HTML
def search_web(query, max_results=5):
    try:
        context_list = []
        # Χρήση του επίσημου, δωρεάν Lite API της DuckDuckGo (JSON μορφή)
        url = f"https://duckduckgo.com{urllib.parse.quote_plus(query)}&format=json&no_html=1&skip_disambig=1"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code != 200:
            return "No results found due to connection status."
            
        data = response.json()
        
        # 1. Έλεγχος για άμεση απάντηση (Abstract)
        if data.get("AbstractText"):
            title = data.get("Heading", "Abstract")
            source_url = data.get("AbstractURL", "")
            snippet = data.get("AbstractText")
            context_list.append(f"Title: {title}\nURL: {source_url}\nSnippet: {snippet}")
            
        # 2. Έλεγχος για σχετικά αποτελέσματα (Related Topics)
        if "RelatedTopics" in data:
            for result in data["RelatedTopics"][:max_results]:
                # Παράκαμψη υποκατηγοριών (Topics)
                if "FirstURL" in result and "Text" in result:
                    title = result.get("Text", "").split(" - ")[0]
                    clean_url = result.get("FirstURL", "")
                    snippet = result.get("Text", "")
                    context_list.append(f"Title: {title}\nURL: {clean_url}\nSnippet: {snippet}")
                    
        if context_list:
            return "\n\n".join(context_list)
            
    except Exception as e:
        return f"Error during search: {str(e)}"
    return "No results found."

    try:
        context_list = []
        formatted_query = urllib.parse.quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={formatted_query}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return f"Error: Received status code {response.status_code}"
            
        soup = BeautifulSoup(response.text, "html.parser")
        result_elements = soup.select("#links .result")
        
        for element in result_elements[:max_results]:
            title_tag = element.select_one(".result__title a")
            snippet_tag = element.select_one(".result__snippet")
            
            if title_tag:
                title = title_tag.get_text(strip=True)
                raw_url = title_tag.get("href", "")
                parsed_url = urllib.parse.urlparse(raw_url)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                
                clean_url = query_params.get("uddg", [raw_url])[0]
                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
                
                context_list.append(f"Title: {title}\nURL: {clean_url}\nSnippet: {snippet}")
                
        if context_list:
            return "\n\n".join(context_list)
            
    except Exception as e:
        return f"Error during search: {str(e)}"
    return "No results found."

# Ρύθμιση σελίδας
st.set_page_config(page_title="StrictexAI", layout="wide", page_icon="🤖")
st.title("🤖 StrictexAI Chatbot")

# Αρχικά system prompts
system_prompts = {
    "Friendly Assistant": "You are StrictexAI, a helpful, polite, and kind AI assistant.",
    "Expert Programmer": "You are StrictexAI, an elite senior software engineer. Give precise, clean code blocks.",
    "Creative Storyteller": "You are StrictexAI, a whimsical author. Answer with creative flair.",
    "Sarcastic Buddy": "You are StrictexAI, a witty, slightly sarcastic friend. Use humor."
}

# --- 1. SIDEBAR (Διαχείριση Ιστορικού) ---
with st.sidebar:
    st.header("💬 Chat History")
    
    if st.button("➕ New Chat", use_container_width=True):
        new_chat_id = f"New Chat {datetime.datetime.now().strftime('%H%M%S')}"
        st.session_state.current_chat = new_chat_id
        st.session_state.messages = []
        st.rerun()
    
    # ΠΡΟΣΘΗΚΗ: Κουμπί Διαγραφής Τρέχουσας Συνομιλίας
    if st.button("🗑️ Delete Current Chat", use_container_width=True, type="primary"):
        if "current_chat" in st.session_state:
            file_to_delete = os.path.join(CHATS_DIR, f"{st.session_state.current_chat}.json")
            if os.path.exists(file_to_delete):
                os.remove(file_to_delete)
            
            # Καθαρισμός session state και εύρεση επόμενου chat
            remaining_chats = [c for c in get_all_chats() if c != st.session_state.current_chat]
            if remaining_chats:
                st.session_state.current_chat = remaining_chats[0]
                st.session_state.messages = load_chat_history(remaining_chats[0])
            else:
                new_chat_id = f"New Chat {datetime.datetime.now().strftime('%H%M%S')}"
                st.session_state.current_chat = new_chat_id
                st.session_state.messages = []
            st.rerun()

    st.divider()
    saved_chats = get_all_chats()
    
    if "current_chat" not in st.session_state:
        if saved_chats:
            st.session_state.current_chat = saved_chats[0]
        else:
            st.session_state.current_chat = f"New Chat {datetime.datetime.now().strftime('%H%M%S')}"

    for chat in saved_chats:
        label = f"📝 {chat}" if chat != st.session_state.current_chat else f"💬 {chat} (Active)"
        if st.button(label, key=chat, use_container_width=True):
            st.session_state.current_chat = chat
            st.session_state.messages = load_chat_history(chat)
            st.rerun()
            
    st.divider()
    
    # Επιλογή Μοντέλου και Persona μέσα στο Sidebar
    selected_model = st.selectbox("🤖 Choose Model", ["llama-3.3-70b-versatile", "llama-3.1-8b-instant",])
    selected_persona = st.selectbox("🎭 Choose Persona", list(system_prompts.keys()))
    web_search_enabled = st.toggle("🌐 Enable Web Search", value=False)

# --- 2. ΚΥΡΙΩΣ ΠΕΡΙΕΧΟΜΕΝΟ (Chat Interface) ---
# Φόρτωση μηνυμάτων αν δεν υπάρχουν στο session state
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history(st.session_state.current_chat)

# Εμφάνιση προηγούμενων μηνυμάτων
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Είσοδος νέου μηνύματος από τον χρήστη
if user_input := st.chat_input("Type your message here..."):
    
    # Εμφάνιση του μηνύματος του χρήστη
    with st.chat_message("user"):
        st.write(user_input)
    
    # Αποθήκευση στο ιστορικό
    is_first_message = (len(st.session_state.messages) == 0)
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Προετοιμασία των μηνυμάτων για το API (συμπεριλαμβανομένου του System Prompt)
    api_messages = [{"role": "system", "content": system_prompts[selected_persona]}]
    
    # Αν η αναζήτηση είναι ενεργή, φέρε αποτελέσματα και εμπλούτισε το prompt
    if web_search_enabled:
        with st.spinner("Searching the web..."):
            search_results = search_web(user_input)
            augmented_input = f"Web Search Results:\n{search_results}\n\nUser Question: {user_input}"
            api_messages.append({"role": "user", "content": augmented_input})
    else:
        # Αλλιώς βάλε το ιστορικό
        for msg in st.session_state.messages:
            api_messages.append(msg)

    # Κλήση στο Groq API
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                response = client.chat.completions.create(
                    model=selected_model,
                    messages=api_messages
                )
                assistant_response = response.choices[0].message.content
                st.write(assistant_response)
                st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                
                # Αποθήκευση/Μετονομασία μετά την επιτυχή απάντηση
                if is_first_message:
                    new_id = rename_chat_file(st.session_state.current_chat, user_input, selected_model, st.session_state.messages)
                    st.session_state.current_chat = new_id
                else:
                    save_chat_history(st.session_state.current_chat, st.session_state.messages)
                    
                st.rerun()
            except Exception as e:
                st.error(f"Error calling Groq API: {str(e)}")
