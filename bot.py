import streamlit as st
import json
import os
import datetime
from googlesearch import search

# Φάκελος για την αποθήκευση όλων των συνομιλιών
CHATS_DIR = "chats"
if not os.path.exists(CHATS_DIR):
    os.makedirs(CHATS_DIR)

# Συναρτήσεις για διαχείριση πολλαπλών αρχείων συνομιλιών
def get_all_chats():
    # Επιστρέφει ΜΟΝΟ τα καθαρά ονόματα των συνομιλιών χωρίς την επέκταση .json
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

def delete_chat(chat_id):
    file_path = os.path.join(CHATS_DIR, f"{chat_id}.json")
    if os.path.exists(file_path):
        os.remove(file_path)

# Αυτοματοποιημένη μετονομασία αρχείου συνομιλίας
def rename_chat_file(old_chat_id, user_input, selected_model, messages):
    rename_prompt = f"Summarize this in 2 words: {user_input}"
    title_response = ollama.generate(model=selected_model, prompt=rename_prompt)
    new_title = title_response['response'].strip().replace('"', '').replace('.', '')
    new_title = "".join(c for c in new_title if c.isalnum() or c in " _-").strip()
    
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

# Συνάρτηση για αναζήτηση στο Google
def search_google(query, max_results=3):
    try:
        results = search(query, num_results=max_results, advanced=True)
        context_list = []
        for r in results:
            context_list.append(f"Title: {r.title}\nURL: {r.url}\nDescription: {r.description}")
        if context_list:
            return "\n\n".join(context_list)
    except Exception as e:
        return f"Error during Google search: {str(e)}"
    return ""

# Ρύθμιση σελίδας
st.set_page_config(page_title="kortexAI", layout="wide", page_icon="🤖")
st.title("🤖 kortexAI Chatbot")

# Αρχικά system prompts προσαρμοσμένα στο όνομα του bot
system_prompts = {
    "Friendly Assistant": "You are kortexAI, a helpful, polite, and kind AI assistant.",
    "Expert Programmer": "You are kortexAI, an elite senior software engineer. Give precise, clean code blocks.",
    "Creative Storyteller": "You are kortexAI, a whimsical author. Answer with creative flair.",
    "Sarcastic Buddy": "You are kortexAI, a witty, slightly sarcastic friend. Use humor."
}

# --- 1. SIDEBAR ---
with st.sidebar:
    st.header("💬 Chat History")
    
    if st.button("➕ New Chat", use_container_width=True):
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
    st.header("⚙️ Bot Configurations")
    selected_model = st.selectbox("Choose Model:", ["llama3.2:1b"], index=0)
    personality = st.selectbox("Bot Personality:", list(system_prompts.keys()))
    web_search_enabled = st.toggle("🌐 Enable Google Search", value=False)
    st.divider()
    
    if st.button("🗑️ Delete Current Chat", use_container_width=True):
        delete_chat(st.session_state.current_chat)
        if "messages" in st.session_state:
            del st.session_state.messages
        if "current_chat" in st.session_state:
            del st.session_state.current_chat
        st.rerun()

# --- 2. ΑΡΧΙΚΟΠΟΙΗΣΗ ---
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history(st.session_state.current_chat)

# --- 3. ΕΜΦΑΝΙΣΗ ΙΣΤΟΡΙΚΟΥ ---
for message in st.session_state.messages:
    if message["role"] != "system" and not message.get("is_search_context", False):
        avatar = "🤖" if message["role"] == "assistant" else "👤"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

# --- 4. ΛΟΓΙΚΗ CHAT ---
if user_input := st.chat_input("Type your message here..."):
    
    user_messages_count = sum(1 for m in st.session_state.messages if m["role"] == "user")
    is_first_message = (user_messages_count == 0)
    
    st.session_state.messages = [m for m in st.session_state.messages if m["role"] != "system" and not m.get("is_search_context", False)]
    st.session_state.messages.insert(0, {"role": "system", "content": system_prompts[personality]})
    
    if web_search_enabled:
        with st.spinner("🔍 Searching Google..."):
            search_results = search_google(user_input)
            if search_results:
                web_prompt = (
                    "CRITICAL INSTRUCTION: Use ONLY these live Google results. Current year is 2026.\n"
                    f"Results:\n{search_results}"
                )
                st.session_state.messages.append({"role": "system", "content": web_prompt, "is_search_context": True})
        
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user", avatar="👤"):
        st.markdown(user_input)

    clean_input = user_input.strip().lower().replace("?", "")
    creator_questions = ["who is your creator", "who made you","Who created you", "ποιος σε εφτιαξε", "ποιος ειναι ο δημιουργος σου"]
    
    with st.chat_message("assistant", avatar="🤖"):
        message_placeholder = st.empty()
        
        # Easter Egg (Με τριπλά εισαγωγικά για ασφάλεια)
        if "//2012//" in clean_input:
            full_response = """🤖 **MY CREATOR!** 🤖

```text
      0110
     01  10
    01    10
   0101101010
  010      010
 010        010
```
"""
            message_placeholder.markdown(full_response)
        elif any(q in clean_input for q in creator_questions):
            full_response = "I am kortexAI, made by Antonis Tsachpinis! A custom AI chatbot powered by Streamlit and Ollama."
            message_placeholder.markdown(full_response)
        else:
            full_response = ""
            try:
                response_stream = ollama.chat(model=selected_model, messages=st.session_state.messages, stream=True)
                for chunk in response_stream:
                    full_response += chunk['message']['content']
                    message_placeholder.markdown(full_response + "▌")
                message_placeholder.markdown(full_response)
            except Exception as e:
                st.error("⚠️ Σφάλμα Ollama.")
                full_response = "Could not connect to Ollama."

        st.session_state.messages.append({"role": "assistant", "content": full_response})
        save_chat_history(st.session_state.current_chat, st.session_state.messages)

    if is_first_message and "New Chat" in st.session_state.current_chat:
        try:
            new_name = rename_chat_file(st.session_state.current_chat, user_input, selected_model, st.session_state.messages)
            if new_name != st.session_state.current_chat:
                st.session_state.current_chat = new_name
                st.rerun()
        except Exception as e:
            pass

# --- 5. FOOTER ---
st.divider()
st.markdown("<p style='text-align: center; color: gray; font-size: 13px;'><b>kortexAI</b> | Created by Antonis Tsachpinis | Powered by Streamlit & Ollama 3.2:1b</p>", unsafe_allow_html=True)
