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
from streamlit_authenticator.utilities.hasher import Hasher
from supabase import create_client, Client

# Ρύθμιση σελίδας
st.set_page_config(page_title="StrictexAI", layout="wide", page_icon="🤖")

# Έλεγχος αν υπάρχουν τα απαραίτητα Secrets
if "SUPABASE_URL" not in st.secrets or "SUPABASE_KEY" not in st.secrets:
    st.error("⚠️ Παρακαλώ προσθέστε τα SUPABASE_URL και SUPABASE_KEY στα Streamlit Secrets!")
    st.stop()

if "GROQ_API_KEY" not in st.secrets:
    st.error("⚠️ Παρακαλώ προσθέστε το GROQ_API_KEY στα Streamlit Secrets!")
    st.stop()

# --- ΑΠΟΛΥΤΟΣ ΚΑΘΑΡΙΣΜΟΣ URL ΓΙΑ ΤΗΝ ΑΠΟΦΥΓΗ ΤΟΥ PGRST125 ---
supabase_url = st.secrets["SUPABASE_URL"].strip().strip('"').strip("'")
if supabase_url.endswith("/"):
    supabase_url = supabase_url[:-1]
if supabase_url.endswith("/rest/v1"):
    supabase_url = supabase_url.replace("/rest/v1", "")

supabase_key = st.secrets["SUPABASE_KEY"].strip().strip('"').strip("'")

# Αρχικοποίηση των Clients
supabase: Client = create_client(supabase_url, supabase_key)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])
# ---------------------------------------------------

# --- ΣΥΝΑΡΤΗΣΕΙΣ ΔΙΑΧΕΙΡΙΣΗΣ ΣΥΝΟΜΙΛΙΩΝ (SUPABASE) ---
def get_all_chats(user_email):
    try:
        response = supabase.table("user_chats").select("chat_id").eq("username", user_email).order("updated_at", descending=True).execute()
        records = response.data if hasattr(response, 'data') else response
        return [row["chat_id"] for row in records] if records else []
    except Exception as e:
        st.error(f"Error fetching chats: {e}")
        return []

def load_chat_history(user_email, chat_id):
    try:
        response = supabase.table("user_chats").select("messages").eq("username", user_email).eq("chat_id", chat_id).execute()
        records = response.data if hasattr(response, 'data') else response
        if records and len(records) > 0:
            return records[0]["messages"]
    except Exception as e:
        st.error(f"Error loading chat: {e}")
    return []

def save_chat_history(user_email, chat_id, messages):
    try:
        check = supabase.table("user_chats").select("id").eq("username", user_email).eq("chat_id", chat_id).execute()
        records = check.data if hasattr(check, 'data') else check
        if records and len(records) > 0:
            supabase.table("user_chats").update({"messages": messages, "updated_at": "now()"}).eq("username", user_email).eq("chat_id", chat_id).execute()
        else:
            supabase.table("user_chats").insert({"username": user_email, "chat_id": chat_id, "messages": messages}).execute()
    except Exception as e:
        st.error(f"Error saving chat: {e}")

def rename_chat_file(user_email, old_chat_id, user_input, selected_model, messages):
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
        
    if new_title in get_all_chats(user_email):
        new_title += f"_{datetime.datetime.now().strftime('%H%M%S')}"
        
    try:
        supabase.table("user_chats").update({"chat_id": new_title, "messages": messages, "updated_at": "now()"}).eq("username", user_email).eq("chat_id", old_chat_id).execute()
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


# --- 2. ΣΥΣΤΗΜΑ AUTHENTICATION (ΜΟΝΟ EMAIL & PASSWORD) ---
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.title("🤖 StrictexAI - Welcome")
    tab1, tab2 = st.tabs(["🔑 Είσοδος (Sign In)", "📝 Εγγραφή (Sign Up)"])

    with tab1:
        st.subheader("Σύνδεση με το Email σας")
        login_email = st.text_input("E-mail", key="login_email").strip().lower()
        login_password = st.text_input("Password", type="password", key="login_pass")
        
        if st.button("Σύνδεση", use_container_width=True):
            if not login_email or not login_password:
                st.warning("⚠️ Παρακαλώ συμπληρώστε όλα τα πεδία.")
            else:
                try:
                    response = supabase.table("app_users").select("*").eq("email", login_email).execute()
                    records = response.data if hasattr(response, 'data') else response
                    
                    if records and len(records) > 0:
                        user_data = records[0]  # Διαβάζουμε σωστά το πρώτο στοιχείο της λίστας
                        stored_password = user_data.get("password")
                        
                        if Hasher.verify_password(login_password, stored_password):
                            st.session_state["authenticated"] = True
                            st.session_state["username"] = login_email
                            st.success("Successful Login!")
                            st.rerun()
                        else:
                            st.error("❌ Λάθος κωδικός πρόσβασης.")
                    else:
                        st.error("❌ Αυτό το email δεν είναι εγγεγραμμένο.")
                except Exception as db_err:
                    st.error(f"Σφάλμα κατά τη σύνδεση: {str(db_err)}")

    with tab2:
        st.subheader("Δημιουργία Νέου Λογαριασμού")
        new_email = st.text_input("Το E-mail σας", key="new_email").strip().lower()
        new_password = st.text_input("Επιλέξτε Password", type="password", key="new_pass")
        confirm_password = st.text_input("Επιβεβαίωση Password", type="password", key="conf_pass")
        
        if st.button("Δημιουργία Λογαριασμού", use_container_width=True):
            if not new_email or not new_password or not confirm_password:
                st.warning("⚠️ Παρακαλώ συμπληρώστε όλα τα πεδία.")
            elif not re.match(r"[^@]+@[^@]+\.[^@]+", new_email):
                st.error("❌ Παρακαλώ εισάγετε μια έγκυρη διεύθυνση email.")
            elif new_password != confirm_password:
                st.error("❌ Οι κωδικοί δεν ταιριάζουν.")
            else:
                try:
                    check_user = supabase.table("app_users").select("email").eq("email", new_email).execute()
                    existing_records = check_user.data if hasattr(check_user, 'data') else check_user
                    
                    if existing_records and len(existing_records) > 0:
                        st.error("❌ Αυτό το email χρησιμοποιείται ήδη.")
                    else:
                        hashed_password = Hasher.hash_password(new_password)
                        supabase.table("app_users").insert({
                            "email": new_email,
                            "password": hashed_password
                        }).execute()
                        st.success("🎉 Ο λογαριασμός δημιουργήθηκε! Μπορείτε να συνδεθείτε στο πρώτο Tab.")
                except Exception as e:
                    st.error(f"Σφάλμα κατά την εγγραφή: {e}")
    st.stop()

# --- ΑΠΟ ΕΔΩ ΚΑΙ ΠΕΡΑ Ο ΧΡΗΣΤΗΣ ΕΧΕΙ ΣΥΝΔΕΘΕΙ ---
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
    st.write(f"📧 Connected as: **{current_user}**")
    if st.button("🚪 Αποσύνδεση (Logout)", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        st.rerun()
        
    st.divider()
    st.header("💬 Chat History")
    
    saved_chats = get_all_chats(current_user)
    
