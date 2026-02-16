import streamlit as st
import ephem
import google.generativeai as genai
import math
from geopy.geocoders import Nominatim
import datetime
import time
import pandas as pd
from fpdf import FPDF

# --- CONFIGURATION ---
st.set_page_config(page_title="Destiny Dossier", page_icon="🔮", layout="wide")

st.title("🔮 The Destiny Debugger: Dossier Edition")
st.subheader("AI-Augmented Vedic Forecasting")

# --- SESSION STATE INITIALIZATION ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "context" not in st.session_state:
    st.session_state.context = None  # Stores the analysis for the bot

# --- SIDEBAR: INPUTS ---
with st.sidebar:
    st.header("1. Credentials")
    # Check Secrets first, then Fallback to Input
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ API Key loaded from System Secrets")
    else:
        api_key = st.text_input("Enter Google Gemini API Key", type="password")
        st.markdown("[Get a Free Key Here](https://aistudio.google.com/app/apikey)")
    
    st.divider()
    
    st.header("2. Subject Data")
    dob = st.date_input(
        "Date of Birth", 
        value=datetime.date(1980, 1, 1), 
        min_value=datetime.date(1900, 1, 1), 
        max_value=datetime.date(2026, 12, 31)
    )
    tob = st.time_input("Time of Birth", value=datetime.time(12, 00), step=60)
    city_name = st.text_input("Birth City", value="Houston, TX")
    
    st.divider()
    forecast_years = st.slider("Forecast Horizon (Years)", 1, 20, 15)
    
    # Reset Chat Button
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# --- LOGIC: HELPER FUNCTIONS ---
def get_lat_lon(city):
    try:
        geolocator = Nominatim(user_agent="destiny_debugger_v4")
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
        
        # Simple Scoring Logic
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
    
    # Title
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="The Destiny Dossier", ln=True, align='C')
    pdf.ln(10)
    
    # Profile
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=f"Profile: Sun in {sun_sign} | Moon in {moon_sign}", ln=True)
    pdf.ln(5)
    
    # Analysis Body (Sanitized)
    pdf.set_font("Arial", size=11)
    clean_text = analysis_text.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 10, txt=clean_text)
    
    # Key Dates Table
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
    """Processes a user question and appends response to chat history."""
    # Add User Message
    st.session_state.messages.append({"role": "user", "content": query})
    
    try:
        genai.configure(api_key=api_key_val)
        chat_model = genai.GenerativeModel('gemini-flash-latest')
        
        final_prompt = f"""
        {st.session_state.context}
        
        USER QUESTION: {query}
        
        TASK: Answer concisely using the provided context rules.
        """
        
        response = chat_model.generate_content(final_prompt)
        
        # Add Bot Message
        st.session_state.messages.append({"role": "assistant", "content": response.text})
        
    except Exception as e:
        st.session_state.messages.append({"role": "assistant", "content": f"Error: {e}"})

# --- MAIN ANALYSIS TRIGGER ---
if st.button("Run Dossier Analysis"):
    if not api_key:
        st.error("⚠️ Please enter an API Key.")
    elif dob and tob and city_name:
        with st.spinner("Compiling Cosmic Data..."):
            lat, lon = get_lat_lon(city_name)
            
            if lat:
                st.success(f"📍 Location Locked: {city_name}")
                
                # 1. Calc Natal
                date_str = f"{dob.strftime('%Y/%m/%d')} {tob.strftime('%H:%M:%S')}"
                obs = ephem.Observer()
                obs.lat, obs.lon, obs.date = str(lat), str(lon), date_str
                
                sun, moon = ephem.Sun(), ephem.Moon()
                sun.compute(obs)
                moon.compute(obs)
                
                sun_sign, sun_idx = get_zodiac_sign(sun.hlon)
                moon_sign, moon_idx = get_zodiac_sign(moon.hlon)
                
                # 2. Calc Transits
                df = calculate_transits(dob, forecast_years, moon_idx)
                events = df[df["Energy Score"] != 0].drop_duplicates(subset=["Status"])
                
                # 3. RAG Loading
                try:
                    with open("knowledge.txt", "r") as f:
                        knowledge_base = f.read()
                except FileNotFoundError:
                    knowledge_base = "General Vedic Rules apply."

                # 4. Generate Analysis
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-flash-latest')
                
                prompt = f"""
                Act as a Vedic Strategist.
                
                --- KNOWLEDGE BASE ---
                {knowledge_base}
                ----------------------
                
                Subject Data:
                - Sun: {sun_sign}, Moon: {moon_sign}
                - Key Upcoming Shifts: {events['Status'].tolist()}
                - Dates: {events['Date'].dt.strftime('%Y-%m').tolist()}
                
                Task:
                1. Write an 'Executive Summary' for the next {forecast_years} years.
                2. Cite specific rules from the Knowledge Base.
                3. Keep it text-based for PDF compatibility.
                """
                
                try:
                    response = model.generate_content(prompt)
                    analysis_text = response.text
                    
                    # 5. Store Context for Chatbot
                    st.session_state.context = f"""
                    SYSTEM CONTEXT:
                    You are analyzing a user with:
                    - Sun: {sun_sign}, Moon: {moon_sign}
                    - Upcoming Shifts: {events['Status'].tolist()}
                    - Rules: {knowledge_base}
                    
                    PREVIOUS ANALYSIS:
                    {analysis_text}
                    """
                    
                    # 6. Display UI
                    c1, c2 = st.columns(2)
                    c1.metric("☀️ Sun", sun_sign)
                    c2.metric("🌙 Moon", moon_sign)
                    st.line_chart(df.set_index("Date")["Energy Score"])
                    st.write("### 🤖 Executive Summary")
                    st.write(analysis_text)
                    
                    # 7. Generate PDF
                    pdf_bytes = create_pdf(analysis_text, sun_sign, moon_sign, events)
                    st.download_button(
                        label="📄 Download Official Destiny Dossier (PDF)",
                        data=pdf_bytes,
                        file_name="destiny_dossier.pdf",
                        mime="application/pdf"
                    )
                    
                except Exception as e:
                    st.error(f"AI Error: {e}")

            else:
                st.error("City not found.")
    else:
        st.warning("Enter details.")

# --- INTERACTIVE CHAT SECTION ---
if st.session_state.context:
    st.divider()
    st.header("💬 Ask the Astral Architect")
    st.caption("Explore your analysis further.")

    # 1. Display Chat History
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 2. Suggested Questions (Chips)
    # We use columns to create a row of buttons
    st.write("###### Suggested Questions:")
    col1, col2, col3, col4 = st.columns(4)
    
    # We use a callback logic: If button clicked, we treat it as a prompt
    chip_prompt = None
    
    if col1.button("📈 Career Roadmap"):
        chip_prompt = "Based on my chart, give me a 3-point Career Roadmap for the next 5 years."
    if col2.button("⚠️ Risk Analysis"):
        chip_prompt = "What is the biggest 'Bug' or risk in my chart I should watch out for?"
    if col3.button("🚀 Startup Timing"):
        chip_prompt = "When is the best time for me to launch a new venture or startup?"
    if col4.button("💰 Wealth Outlook"):
        chip_prompt = "Analyze my potential for wealth accumulation and investments."

    # 3. Handle Inputs (Chip OR Text Box)
    user_input = st.chat_input("Type your question here...")
    
    # Determine which input to use
    final_query = chip_prompt if chip_prompt else user_input
    
    if final_query:
        if api_key:
            handle_chat_query(final_query, api_key)
            st.rerun() # Refresh to show the new message
        else:
            st.error("API Key missing.")