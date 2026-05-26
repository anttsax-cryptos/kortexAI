import streamlit as st
import json
import datetime
import requests
import urllib.parse
import streamlit.components.v1 as components
from groq import Groq

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="StrictexAI Ultra", layout="wide", page_icon="🤖")

if "GROQ_API_KEY" not in st.secrets:
    st.error("⚠ Please add your GROQ_API_KEY in Streamlit Secrets!")
    st.stop()

client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# Ενισχυμένα Prompts για μέγιστη ανάλυση και λεπτομέρεια
personalities = {
    "Friendly Assistant": "You are StrictexAI, a highly detailed and comprehensive encyclopedia. Provide extensive, in-depth analysis, precise specifications, and complete technical overviews for every product or topic requested. Never summarize complex details.",
    "Expert Programmer": "You are StrictexAI, a top Senior Software Engineer. Provide exhaustive, highly accurate technical documentation, full code examples without omissions, and deep architectural explanations.",
    "Sarcastic Buddy": "You are StrictexAI, a highly sarcastic expert. Don't hold back on anyone Make Everyone laugh and give them to understand who is the leader of the party.",
    "Creative Storyteller": "You are StrictexAI, an imaginative world-builder. Give rich, deeply descriptive, and expansive narratives filled with intricate details and vivid lore.",
}

# --- 2. JAVASCRIPT MECHANISM FOR MULTIPLE CHATS (FIXED AUTO-JUMP) ---
if "all_chats" not in st.session_state:
    st.session_state.all_chats = {}
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None
if "js_sync_done" not in st.session_state:
    st.session_state.js_sync_done = False

# Διορθωμένη JavaScript: Φορτώνει ΜΟΝΟ κατά την εκκίνηση, δεν ξαναπαρεμβαίνει κατά τα μηνύματα
if not st.session_state.js_sync_done:
    js_load_all = """
    <script>
        const savedData = localStorage.getItem("strictex_multichats");
        const currentActive = localStorage.getItem("strictex_active_chat_id");
        
        window.parent.postMessage({
            type: "LOAD_ALL_CHATS", 
            data: savedData ? JSON.parse(savedData) : {},
            active_id: currentActive || null
        }, "*");
    </script>
    """
    components.html(js_load_all, height=0, width=0)

# Συγχρονισμός δεδομένων από Browser προς Streamlit
query_params = st.query_params
if "incoming_chats" in query_params and not st.session_state.js_sync_done:
    try:
        st.session_state.all_chats = json.loads(query_params["incoming_chats"])
        st.session_state.js_sync_done = True
        
        # Κλείδωμα στο προηγούμενο ενεργό Chat ID για να μην πηγαίνει πάνω
        saved_active = query_params.get("active_chat_id", None)
        if saved_active and saved_active in st.session_state.all_chats:
            st.session_state.current_chat_id = saved_active
        elif st.session_state.all_chats.keys():
            st.session_state.current_chat_id = list(st.session_state.all_chats.keys())[0]
            
        st.rerun()
    except:
        pass

def save_chats_to_browser():
    """Αποθηκεύει άμεσα τα δεδομένα και κλειδώνει το τρέχον Chat ID"""
    all_data_json = json.dumps(st.session_state.all_chats, ensure_ascii=False)
    current_id = st.session_state.current_chat_id
    st.components.v1.html(
        f"""
        <script>
            localStorage.setItem("strictex_multichats", JSON.stringify({all_data_json}));
            localStorage.setItem("strictex_active_chat_id", "{current_id}");
        </script>
        """,
        height=0,
        width=0
    )

# --- 3. WIKIPEDIA SEARCH FUNCTION ---
def search_the_web(query, max_results=1):
    stop_words = ["πες μου για το", "τι ειναι το", "ποιος ειναι ο", "υπαρχει το", "δειξε μου", "πληροφοριες για","information about","tell me about", "what is", "who is"]
    clean_query = query.lower()
    for word in stop_words:
        clean_query = clean_query.replace(word, "")
    clean_query = clean_query.strip()
    
    if not clean_query:
        return None
        
    try:
        headers = {"User-Agent": "StrictexAIChatbot/2.0 (contact@example.com)"}
        formatted_query = urllib.parse.quote_plus(clean_query)
        
        for lang in ["el", "en"]:
            search_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&srsearch={formatted_query}&srlimit=1&format=json"
            response = requests.get(search_url, headers=headers, timeout=4)
            
            if response.status_code == 200 and response.text.strip():
                search_res = response.json()
                results = search_res.get("query", {}).get("search", [])
                
                if results and len(results) > 0:
                    exact_title = results[0]["title"]
                    formatted_title = urllib.parse.quote_plus(exact_title)
                    
                    content_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles={formatted_title}&format=json"
                    content_response = requests.get(content_url, headers=headers, timeout=4)
                    
                    if content_response.status_code == 200 and content_response.text.strip():
                        content_res = content_response.json()
                        pages = content_res.get("query", {}).get("pages", {})
                        for page_id, page_info in pages.items():
                            extract = page_info.get("extract", "")
                            if extract.strip():
                                wiki_link = f"https://{lang}.wikipedia.org/wiki/{formatted_title}"
                                if len(extract) > 2000 and clean_query in extract.lower():
                                    start_idx = extract.lower().find(clean_query)
                                    extract = extract[max(0, start_idx-200):start_idx+1500]
                                return f"• {exact_title} ({wiki_link}): {extract}"
    except:
        pass
    return None

# --- 4. SIDEBAR & CHAT SELECTOR ---
with st.sidebar:
    st.caption("[Ai can make mistakes]")
    st.header("💬 My chats")
    
    if st.button("➕ New chat", use_container_width=True, type="primary"):
        new_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        st.session_state.all_chats[new_id] = {
            "title": f"Συνομιλία {datetime.datetime.now().strftime('%d/%m %H:%M')}",
            "messages": []
        }
        st.session_state.current_chat_id = new_id
        save_chats_to_browser()
        st.rerun()
        
    st.divider()
    
    if st.session_state.all_chats:
        chat_options = {k: v["title"] for k, v in st.session_state.all_chats.items()}
        
        # Radio Selector που παραμένει σταθερός στο current_chat_id
        selected_chat = st.radio(
            "👉 Choose chat:",
            options=list(chat_options.keys()),
            index=list(chat_options.keys()).index(st.session_state.current_chat_id) if st.session_state.current_chat_id in chat_options else 0,
            format_func=lambda x: chat_options[x]
        )
        if selected_chat != st.session_state.current_chat_id:
            st.session_state.current_chat_id = selected_chat
            save_chats_to_browser()
            st.rerun()
            
        st.divider()
        
        if st.button("🗑 Delete this chat", use_container_width=True):
            del st.session_state.all_chats[st.session_state.current_chat_id]
            st.session_state.current_chat_id = list(st.session_state.all_chats.keys())[0] if st.session_state.all_chats else None
            save_chats_to_browser()
            st.rerun()
    else:
        st.info("There is not a chat, press 'New chat'.")

    st.divider()
    selected_persona = st.selectbox("🎭 Personality:", list(personalities.keys()))
    st.caption("made by Antonis Tsachpinis | powered by streamlit and Groq")

# --- 5. MAIN INTERFACE ---
st.title("🤖 StrictexAI Hub")

if not st.session_state.current_chat_id:
    st.warning("👈 Tap on the 'New Chat button to start!'")
    st.stop()

active_messages = st.session_state.all_chats[st.session_state.current_chat_id]["messages"]

for msg in active_messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# --- 6. CHAT INPUT & PROCESSING ---
if user_input := st.chat_input("Type your message..."):
    with st.chat_message("user"):
        st.write(user_input)
        
    active_messages.append({"role": "user", "content": user_input})
    if len(active_messages) == 1:
        st.session_state.all_chats[st.session_state.current_chat_id]["title"] = user_input[:25] + "..."
        
    st.session_state.all_chats[st.session_state.current_chat_id]["messages"] = active_messages
    save_chats_to_browser()

    greetings = ["γεια","πως τα πας","γεια σου","wat's up","γεια σας", "καλημερα", "καλησπερα", "hi", "hello", "hey", "τι κανεις","good morning","how are you"]
    clean_input = user_input.lower().strip().replace("?", "").replace(".", "")
    is_greeting = clean_input in greetings or len(clean_input.split()) <= 1

    search_context = ""
    search_query = user_input
    has_greek = any('α' <= char <= 'ώ' or 'Α' <= char <= 'Ω' for char in user_input)
    lang_mirror_rule = "\n\n CRITICAL: Speak strictly in Greek." if has_greek else "\n\n CRITICAL: Speak strictly in English."

    if not is_greeting:
        try:
            rewrite_res = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": f"Convert to 2-4 keywords for Wikipedia: {user_input}"}],
                temperature=0.1
            )
            # ΔΙΟΡΘΩΣΗ: Προσθήκη του [0] εδώ
            search_query = rewrite_res.choices[0].message.content.strip()
        except:
            search_query = user_input

        with st.spinner("🔍 Αναζήτηση..."):
            results = search_the_web(search_query)

        detailed_instruction = (
            "\n👉 DETAILED SPECIFICATION MANDATE:\n"
            "- Provide an exhaustive and ultra-detailed answer. Include every single technical specification available (processor, screen technology, RAM, storage, camera sensors, charging speed, battery capacity, materials, and features).\n"
            "- Structure your response logically using bold sections and detailed bullet points."
        )

        if results:
            search_context = f"\n\n[LIVE DATA]:\n{results}\n\n- TIMELINE: Year 2026." + detailed_instruction
        else:
            search_context = "\n\n[SYSTEM FALLBACK]: Web search unavailable. You are in 2026. Use your deep internal knowledge to provide an exhaustive, multi-paragraph spec sheet for the requested current product. DO NOT say it doesn't exist." + detailed_instruction
    else:
        search_context = "\n\n[SYSTEM NOTICE]: The user is just saying hello or greeting you. Respond with a short, polite, and friendly greeting in the same language. Do not output any technical specifications or bullet points."

    full_system_prompt = personalities[selected_persona] + "\n[SYSTEM: Year is 2026]" + search_context + lang_mirror_rule
    api_messages = [{"role": "system", "content": full_system_prompt}]
    api_messages.extend(active_messages[-10:])

    with st.chat_message("assistant"):
        with st.spinner("Σκέφτομαι..."):
            try:
                chat_completion = client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=api_messages,
                    temperature=0.3
                )
                # ΔΙΟΡΘΩΣΗ: Προσθήκη του [0] και εδώ για ασφάλεια
                assistant_response = chat_completion.choices[0].message.content
                st.write(assistant_response)
                
                active_messages.append({"role": "assistant", "content": assistant_response})
                st.session_state.all_chats[st.session_state.current_chat_id]["messages"] = active_messages
                st.caption("[Ai can make mistakes]")
                
                save_chats_to_browser()
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

