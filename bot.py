import streamlit as st
import json
import os
import datetime
from groq import Groq
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
from duckduckgo_search import DDGS

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

# ΔΙΟΡΘΩΜΕΝΗ ΣΥΝΑΡΤΗΣΗ ΑΝΑΖΗΤΗΣΗΣ (Με DuckDuckGo)
def search_web(query, max_results=5):
    try:
        context_list = []
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
            if results:
                for r in results:
                    title = r.get('title', 'No Title')
                    href = r.get('href', 'No URL')
                    body = r.get('body', 'No Description')
                    context_list.append(f"Title: {title}\nURL: {href}\nSnippet: {body}")
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
        
    # ΣΩΣΤΑ ΣΤΟΙΧΙΣΜΕΝΟ ΚΟΥΜΠΙ ΔΙΑΓΡΑΦΗΣ
    if st.button("🗑️ Delete Current Chat", use_container_width=True, type="primary"):
        if "current_chat" in st.session_state:
            file_to_delete = os.path.join(CHATS_DIR, f"{st.session_state.current_chat}.json")
            if os.path.exists(file_to_delete):
                os.remove(file_to_delete)
            st.session_state.messages = []
            if "current_chat" in st.session_state:
                del st.session_state.current_chat
            st.rerun()
        
