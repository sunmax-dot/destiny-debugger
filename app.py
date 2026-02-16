import streamlit as st
import ephem
import google.generativeai as genai
import math
from geopy.geocoders import Nominatim
import datetime
import time
import pandas as pd
from fpdf import FPDF
import json
import os

# --- CONFIGURATION ---
st.set_page_config(page_title="Destiny Dossier", page_icon="🔮", layout="wide")
st.title("🔮 The Destiny Dossier: Memory Edition")

# --- DATABASE MANAGEMENT (JSON) ---
DB_FILE = "profiles.json"

def load_profiles():
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return []

def save_profile(name, dob, tob_str, city):
    profiles = load_profiles()
    # Check if profile exists and update it, or append new
    new_entry = {
        "name": name,
        "dob": dob.strftime("%Y-%m-%d"),
        "tob": tob_str,
        "city": city
    }
    # Remove existing if name matches (Update logic)
    profiles = [p for p in profiles if p["name"] != name]
    profiles.append(new_entry)
    
    with open(DB_FILE, "w") as f:
        json.dump(profiles, f, indent=4)

# --- SESSION STATE ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "context" not in st.session_state:
    st.session_state.context = None

# --- SIDEBAR: INPUTS & PROFILES ---
with st.sidebar:
    st.header("1. Profile Manager")
    
    # LOAD EXISTING PROFILE
    existing_profiles = load_profiles()
    profile_names = ["-- New Profile --"] + [p["name"] for p in existing_profiles]
    selected_profile = st.selectbox("Load Saved Profile", profile_names)
    
    # DEFAULTS
    default_dob = datetime.date(1980, 1, 1)
    default_tob = datetime.time(12, 0)
    default_city = "Houston, TX"
    
    # If a profile is selected, override defaults
    if selected_profile != "-- New Profile --":
        # Find data
        data = next(p for p in existing_profiles if p["name"] == selected_profile)
        default_dob = datetime.datetime.strptime(data["dob"], "%Y-%m-%d").date()
        t = datetime.datetime.strptime(data["tob"], "%H:%M:%S").time()
        default_tob = t
        default_city = data["city"]
        st.success(f"Loaded: {selected_profile}")

    st.divider()
    
    st.header("2. Subject Data")
    # Inputs (Pre-filled if profile loaded)
    name_input = st.text_input("Subject Name", value=selected_profile if selected_profile != "-- New Profile --" else "")
    dob = st.date_input("Date of Birth", value=default_dob, min_value=datetime.date(1900, 1, 1))
    tob = st.time_input("Time of Birth", value=default_tob, step=60)
    city_name = st.text_input("Birth City", value=default_city)
    
    # SAVE BUTTON
    if st.button("💾 Save Profile"):
        if name_input:
            save_profile(name_input, dob, tob.strftime("%H:%M:%S"), city_name)
            st.success(f"Saved {name_input} to Database!")
            time.sleep(1)
            st.rerun()
        else:
            st.error("Enter a name to save.")

    st.divider()
    st.header("3. Settings")
    forecast_years = st.slider("Forecast Horizon", 1, 20, 15)
    
    # API Key Logic
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
    else:
        api_key = st.text_input("API Key", type="password")


# --- LOGIC: HELPER FUNCTIONS ---
def get_lat_lon(city):
    try:
        geolocator = Nominatim(user_agent="destiny_debugger_v5")
        location = geolocator.geocode(city)
        if location:
            return location.latitude, location.longitude
    except:
        return None, None
    return None, None

def get_zodiac_sign(lon_radians):
    degrees = math.degrees(lon_radians) % 360
    zodiacs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", 
               "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    return zodiacs[int(degrees / 30)], int(degrees / 30)

def calculate_transits(start_date, years, natal_moon_idx):
    data = []
    current_date = datetime.datetime.now()
    end_date = current_date + datetime.timedelta(days=years*365)
    
    while current_date < end_date:
        date_str = current_date.strftime('%Y/%m/%d')
        
        t_jupiter = ephem.Jupiter()
        t_saturn = ephem.Saturn()
        t_jupiter.compute(date_str)
        t_saturn.compute(date_str)
        
        j_sign, j_idx = get_zodiac_sign(t_jupiter.hlon)
        s_sign, s_idx = get_zodiac_sign(t_saturn.hlon)
        
        score = 0
        status = "Neutral"
        
        if j_idx == natal_moon_idx:
            score += 2
            status = "Jupiter Return (Growth)"
        elif s_idx == natal_moon_idx:
            score -= 2
            status = "Saturn Return (Pressure)"
        
        if (j_idx - natal_moon_idx) % 4 == 0:
             score += 1
             
        data.append({
            "Date": current_date,
            "Energy Score": score,
            "Jupiter Sign": j_sign,
            "Saturn Sign": s_sign,
            "Status": status
        })
        current_date += datetime.timedelta(days=30)
        
    return pd.DataFrame(data)

def create_pdf(analysis_text, sun_sign, moon_sign, events):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="The Destiny Dossier", ln=True, align='C')
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Profile: Sun in {sun_sign} | Moon in {moon_sign}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", size=11)
    clean_text = analysis_text.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 10, txt=clean_text)
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="Strategic Timeline:", ln=True)
    pdf.set_font("Arial", size=10)
    
    for index, row in events.iterrows():
        date_str = row['Date'].strftime('%Y-%m')
        line = f"{date_str}: {row['Status']} (Jupiter: {row['Jupiter Sign']})"
        clean_line = line.encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(0, 8, txt=clean_line, ln=True)
        
    return pdf.output(dest='S').encode('latin-1')

def handle_chat_query(query, api_key_val):
    st.session_state.messages.append({"role": "user", "content": query})
    try:
        genai.configure(api_key=api_key_val)
        chat_model = genai.GenerativeModel('gemini-flash-latest')
        final_prompt = f"{st.session_state.context}\nUSER QUESTION: {query}\nTASK: Answer concisely."
        response = chat_model.generate_content(final_prompt)
        st.session_state.messages.append({"role": "assistant", "content": response.text})
    except Exception as e:
        st.session_state.messages.append({"role": "assistant", "content": f"Error: {e}"})

# --- MAIN APP UI ---
if st.button("Run Analysis"):
    if not api_key:
        st.error("⚠️ Please enter an API Key.")
    elif dob and tob and city_name:
        with st.spinner("Analyzing..."):
            lat, lon = get_lat_lon(city_name)
            if lat:
                # 1. Calculate Planetary Positions
                date_str = f"{dob.strftime('%Y/%m/%d')} {tob.strftime('%H:%M:%S')}"
                obs = ephem.Observer()
                obs.lat, obs.lon, obs.date = str(lat), str(lon), date_str
                sun, moon = ephem.Sun(), ephem.Moon()
                sun.compute(obs)
                moon.compute(obs)
                sun_sign, sun_idx = get_zodiac_sign(sun.hlon)
                moon_sign, moon_idx = get_zodiac_sign(moon.hlon)
                
                # 2. Calculate Transits (The Forward Curve)
                df = calculate_transits(dob, forecast_years, moon_idx)
                events = df[df["Energy Score"] != 0].drop_duplicates(subset=["Status"])
                
                # 3. READ THE KNOWLEDGE BASE (Must happen BEFORE the prompt!)
                try:
                    with open("knowledge.txt", "r") as f:
                        knowledge_base = f.read()
                except FileNotFoundError:
                    knowledge_base = "General Vedic Rules apply."
                
                # 4. Configure AI & Create Prompt
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-flash-latest')
                
                # Now 'knowledge_base' is defined and safe to use here:
                prompt = f"""
                ROLE: Act as a strict Vedic Astrologer and Career Strategist.
                
                --- KNOWLEDGE BASE ---
                {knowledge_base}
                ----------------------
                
                SUBJECT DATA:
                - Sun Sign: {sun_sign}
                - Moon Sign: {moon_sign}
                - Upcoming Planetary Shifts: {events['Status'].tolist()}
                - Shift Dates: {events['Date'].dt.strftime('%Y-%m').tolist()}
                
                --- CONSTRAINTS (CRITICAL) ---
                1. DO NOT provide real-world financial data (e.g., current stock prices).
                2. DO NOT mention specific politicians, news events, or non-astrological facts.
                3. Base your predictions ONLY on the provided Planetary Data and Knowledge Base rules.
                
                TASK:
                1. Write an 'Executive Summary' of their destiny for the next {forecast_years} years.
                2. Cite specific rules from the Knowledge Base.
                3. Keep it text-based (no markdown bolding) for PDF compatibility.
                """
                
                try:
                    # 5. Generate Content
                    response = model.generate_content(prompt)
                    analysis_text = response.text
                    
                    # Store Context for Chatbot
                    st.session_state.context = f"CONTEXT: User Sun {sun_sign}, Moon {moon_sign}.\nANALYSIS: {analysis_text}"
                    
                    # Display Results
                    c1, c2 = st.columns(2)
                    c1.metric("☀️ Sun", sun_sign)
                    c2.metric("🌙 Moon", moon_sign)
                    st.line_chart(df.set_index("Date")["Energy Score"])
                    st.write("### 🤖 Analysis")
                    st.write(analysis_text)
                    
                    # Generate PDF
                    pdf_bytes = create_pdf(analysis_text, sun_sign, moon_sign, events)
                    st.download_button("📄 Download PDF", pdf_bytes, "dossier.pdf", "application/pdf")
                    
                except Exception as e:
                    st.error(f"Error: {e}")
            else:
                st.error("City not found.")

# --- INTERACTIVE CHAT SECTION ---
if st.session_state.context:
    st.divider()
    st.header("💬 Consultation")

    # 1. Display Chat History
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 2. Suggested Questions (Chips)
    # We use a session state variable to capture chip clicks
    if "chip_prompt" not in st.session_state:
        st.session_state.chip_prompt = None

    st.write("###### Suggested Questions:")
    col1, col2, col3, col4 = st.columns(4)
    
    if col1.button("📈 Career Roadmap"): st.session_state.chip_prompt = "Give me a 3-point Career Roadmap."
    if col2.button("⚠️ Risk Analysis"): st.session_state.chip_prompt = "What is the biggest risk in my chart?"
    if col3.button("🚀 Startup Timing"): st.session_state.chip_prompt = "When is the best time to launch a startup?"
    if col4.button("💰 Wealth Outlook"): st.session_state.chip_prompt = "Analyze my wealth potential."

    # 3. Handle Input (Text Input OR Chip Click)
    user_input = st.chat_input("Type your question here...")
    
    # Determine if we have a new question to process
    active_prompt = user_input or st.session_state.chip_prompt
    
    if active_prompt:
        # A. Display User Message Immediately
        st.session_state.messages.append({"role": "user", "content": active_prompt})
        with st.chat_message("user"):
            st.markdown(active_prompt)
            
        # B. Clear the chip prompt so it doesn't fire again
        st.session_state.chip_prompt = None

        # C. The "Thinking" Block
        if api_key:
            with st.chat_message("assistant"):
                # --- THIS IS THE PART YOU ASKED FOR ---
                with st.spinner("✨ Consulting the Astral Plane..."):
                    try:
                        genai.configure(api_key=api_key)
                        chat_model = genai.GenerativeModel('gemini-flash-latest')
                        
                        final_prompt = f"""
                        {st.session_state.context}
                        
                        USER QUESTION: {active_prompt}
                        
                        TASK: Answer concisely using the provided context rules.
                        """
                        
                        response = chat_model.generate_content(final_prompt)
                        bot_reply = response.text
                        
                        # Display result
                        st.markdown(bot_reply)
                        
                        # Save to history
                        st.session_state.messages.append({"role": "assistant", "content": bot_reply})
                        
                    except Exception as e:
                        st.error(f"Error: {e}")
        else:
            st.error("Please enter an API Key to chat.")