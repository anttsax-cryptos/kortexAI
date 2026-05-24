import streamlit as st
import json
import os
import datetime
from groq import Groq 
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import streamlit_authenticator as stauth
from supabase import create_client, Client

# Ρύθμιση σελίδας (ΠΡΕΠΕΙ να είναι η πρώτη εντολή Streamlit)
st.set_page_config(page_title="StrictexAI", layout="wide", page_icon="🤖")

# 1. Έλεγχος και Σύνδεση με Supabase & Groq
if "SUPABASE_URL" not in st.secrets or "SUPABASE_KEY" not in st.secrets:
    st.error("⚠️ Παρακαλώ προσθέστε τα SUPABASE_URL και SUPABASE_KEY στα Streamlit Secrets!")
    st.stop()

if "GROQ_API_KEY" not in st.secrets:
    st.error("⚠️ Παρακαλώ προσθέστε το GROQ_API_KEY στα Streamlit Secrets!")
    st.stop()

supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- ΣΥΝΑΡΤΗΣΕΙΣ ΔΙΑΧΕΙΡΙΣΗΣ ΣΥΝΟΜΙΛΙΩΝ (SUPABASE) ---
def get_all_chats(username):
    try:
        response = supabase.table("user_chats").select("chat_id").eq("username", username).order("updated_at", descending=True).execute()
        return [row["chat_id"] for row in response.data] if response.data else []
    except Exception as e:
        st.error(f"Error fetching chats: {e}")
        return []

def load_chat_history(username, chat_id):
    try:
        response = supabase.table("user_chats").select("messages").eq("username", username).eq("chat_id", chat_id).execute()
        if response.data and len(response.data) > 0:
            return response.data[0]["messages"]
    except Exception as e:
        st.error(f"Error loading chat: {e}")
    return []

def save_chat_history(username, chat_id, messages):
    try:
        check = supabase.table("user_chats").select("id").eq("username", username).eq("chat_id", chat_id).execute()
        if check.data and len(check.data) > 0:
            supabase.table("user_chats").update({"messages": messages, "updated_at": "now()"}).eq("username", username).eq("chat_id", chat_id).execute()
        else:
            supabase.table("user_chats").insert({"username": username, "chat_id": chat_id, "messages": messages}).execute()
    except Exception as e:
        st.error(f"Error saving chat: {e}")

def rename_chat_file(username, old_chat_id, user_input, selected_model, messages):
    new_title = "Saved Chat"
    try:
        rename_prompt = f"Summarize this in 2 words: {user_input}"
        title_response = client.chat.completions.create(
            model=selected_model,
            messages=[{"role": "user", "content": rename_prompt}]
        )
        new_title = title_response.choices[0].message.content.strip().replace('"', '').replace('.', '')
        new_title = "".join(c for c in new_title if c.isalnum() or c in " _-").strip()
    except Exception:
        pass
        
    if not new_title:
        new_title = "Saved Chat"
        
    if new_title in get_all_chats(username):
        new_title += f"_{datetime.datetime.now().strftime('%H%M%S')}"
        
    try:
        # Ενημέρωση του τίτλου στη βάση
        supabase.table("user_chats").update({"chat_id": new_title, "messages": messages, "updated_at": "now()"}).eq("username", username).eq("chat_id", old_chat_id).execute()
    except Exception as e:
        st.error(f"Error renaming chat: {e}")
    return new_title

# --- ΣΥΝΑΡΤΗΣΗ ΑΝΑΖΗΤΗΣΗΣ WEB ---
def search_web(query, max_results=5):
    try:
        context_list = []
        formatted_query = urllib.parse.quote_plus(query)
        url = f"https://duckduckgo.com{formatted_query}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
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


# --- 2. ΣΥΣΤΗΜΑ AUTHENTICATION (SIGN IN / SIGN UP) ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.title("🤖 StrictexAI - Login / Sign Up")
    tab1, tab2 = st.tabs(["🔑 Είσοδος (Sign In)", "📝 Εγγραφή (Sign Up)"])

    with tab1:
        st.subheader("Σύνδεση στο StrictexAI")
        login_username = st.text_input("Username", key="login_user")
        login_password = st.text_input("Password", type="password", key="login_pass")
        
        if st.button("Σύνδεση", use_container_width=True):
            user_query = supabase.table("app_users").select("*").eq("username", login_username).execute()
            if user_query.data and len(user_query.data) > 0:
                stored_password = user_query.data[0]["password"]
                if stauth.Hasher.check_pw(stored_password, login_password):
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = login_username
                    st.session_state["name"] = user_query.data[0]["name"]
                    st.success(f"Καλώς ορίσατε {st.session_state['name']}!")
                    st.rerun()
                else:
                    st.error("❌ Λάθος κωδικός πρόσβασης.")
            else:
                st.error("❌ Το username δεν υπάρχει.")

    with tab2:
        st.subheader("Δημιουργία Νέου Λογαριασμού")
        new_username = st.text_input("Επιλέξτε Username", key="new_user")
        new_email = st.text_input("Το E-mail σας", key="new_email")
        new_name = st.text_input("Το Όνομά σας (εμφανιζόμενο)", key="new_name")
        new_password = st.text_input("Επιλέξτε Password", type="password", key="new_pass")
        confirm_password = st.text_input("Επιβεβαίωση Password", type="password", key="conf_pass")
        
        if st.button("Δημιουργία Λογαριασμού", use_container_width=True):
            if not (new_username and new_email and new_name and new_password):
                st.warning("⚠️ Παρακαλώ συμπληρώστε όλα τα πεδία.")
            elif new_password != confirm_password:
                st.error("❌ Οι κωδικοί δεν ταιριάζουν.")
            else:
                check_user = supabase.table("app_users").select("username").eq("username", new_username).execute()
                if check_user.data and len(check_user.data) > 0:
                    st.error("❌ Αυτό το username χρησιμοποιείται ήδη.")
                else:
                    hashed_password = stauth.Hasher.hash(new_password)
                    try:
                        supabase.table("app_users").insert({
                            "username": new_username,
                            "email": new_email,
                            "name": new_name,
                            "password": hashed_password
                        }).execute()
                        st.success("🎉 Ο λογαριασμός δημιουργήθηκε! Συνδεθείτε στο πρώτο Tab.")
                    except Exception as e:
                        st.error(f"Σφάλμα κατά την εγγραφή: {e}")
    st.stop() # Σταματάει εδώ αν δεν έχει γίνει επιτυχές login

# --- ΑΠΟ ΕΔΩ ΚΑΙ ΠΕΡΑ Ο ΧΡΗΣΤΗΣ ΕΙΝΑΙ ΣΥΝΔΕΔΕΜΕΝΟΣ ---
current_user = st.session_state["username"]
st.title("🤖 StrictexAI Chatbot")

system_prompts = {
    "Friendly Assistant": "You are StrictexAI, a helpful, polite, and kind AI assistant.",
    "Expert Programmer": "You are StrictexAI, an elite senior software engineer. Give precise, clean code blocks.",
    "Creative Storyteller": "You are StrictexAI, a whimsical author. Answer with creative flair.",
    "Sarcastic Buddy": "You are StrictexAI, a witty, slightly sarcastic friend. Use humor."
}

# --- 3. SIDEBAR (Ιστορικό & Ρυθμίσεις) ---
with st.sidebar:
    st.write(f"Καλώς ήρθες, **{st.session_state['name']}** 👋")
    if st.button("🚪 Αποσύνδεση (Logout)", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        st.rerun()
        
    st.divider()
    st.header("💬 Chat History")
    
    if st.button("➕ New Chat", use_container_width=True):
        new_chat_id = f"New Chat {datetime.datetime.now().strftime('%H%M%S')}"
        st.session_state.current_chat = new_chat_id
        st.session_state.messages = []
        st.rerun()
    
    st.divider()
    saved_chats = get_all_chats(current_user)
    
    if "current_chat" not in st.session_state:
        if saved_chats:
            st.session_state.current_chat = saved_chats[0]
        else:
            st.session_state.current_chat = f"New Chat {datetime.datetime.now().strftime('%H%M%S')}"

    for chat in saved_chats:
        label = f"📝 {chat}" if chat != st.session_state.current_chat else f"💬 {chat} (Active)"
        if st.button(label, key=chat, use_container_width=True):
            st.session_state.current_chat = chat
            st.session_state.messages = load_chat_history(current_user, chat)
            st.rerun()
            
    st.divider()
    selected_model = st.selectbox("🤖 Choose Model", ["llama3-8b-8192", "llama3-70b-8192", "mixtral-8x7b-32768"])
    selected_persona = st.selectbox("🎭 Choose Persona", list(system_prompts.keys()))
