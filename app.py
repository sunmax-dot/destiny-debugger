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

# --- SIDEBAR: INPUTS ---
with st.sidebar:
    st.header("1. Credentials")
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

# --- LOGIC: HELPER FUNCTIONS ---
def get_lat_lon(city):
    try:
        geolocator = Nominatim(user_agent="destiny_debugger_v3")
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

# --- PDF GENERATOR ---
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
    
    # Analysis Body (Sanitized for PDF)
    pdf.set_font("Arial", size=11)
    # Replace emojis/special chars that crash PDFs
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
        pdf.cell(0, 8, txt=line, ln=True)
        
    return pdf.output(dest='S').encode('latin-1')

# --- MAIN APP ---
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
                
                # 3. AI Analysis (RAG Enhanced)
                try:
                    with open("knowledge.txt", "r") as f:
                        knowledge_base = f.read()
                except FileNotFoundError:
                    knowledge_base = "General Vedic Rules apply."

                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-flash-latest') # Using standard alias
                
                prompt = f"""
                Act as a Vedic Strategist for a Tech Executive.
                
                --- KNOWLEDGE BASE INSTRUCTIONS ---
                1. Read the provided "knowledge.txt" content below carefully.
                2. You MUST cite specific rules (e.g., "[SOURCE: Phaladeepika, Ch 26]") when making claims.
                3. Use "Section 5: Modern Tech Translation" to convert ancient terms into corporate strategy.
                
                --- DATA ---
                Subject Profile: Sun in {sun_sign}, Moon in {moon_sign}
                Current Transits: {events['Status'].tolist()}
                Transit Dates: {events['Date'].dt.strftime('%Y-%m').tolist()}
                
                --- KNOWLEDGE BASE CONTENT ---
                {knowledge_base}
                -------------------------------
                
                TASK:
                1. ANALYZE: Look for "Yogas" in the chart (e.g., if Sun/Mercury are close, mention Budhaditya).
                2. FORECAST: Look at the Transit list. Compare it to "Section 4" rules. (e.g., Is Saturn in the 3rd/6th/11th from Moon?).
                3. STRATEGIZE: Combine the ancient rule with the Modern Tech Translation.
                   - Example: "Saturn in the 3rd House (Rule: Victory) suggests a successful deployment of new Infrastructure (Section 5)."
                
                OUTPUT FORMAT:
                - Executive Summary (3-4 sentences)
                - Key Technical Indicators (Bulleted list of Yogas/Transits with Citations)
                - Strategic Roadmap (Timeline based on the dates provided)
                """
                
                try:
                    response = model.generate_content(prompt)
                    analysis_text = response.text
                    
                    # Display On Screen
                    c1, c2 = st.columns(2)
                    c1.metric("☀️ Sun", sun_sign)
                    c2.metric("🌙 Moon", moon_sign)
                    st.line_chart(df.set_index("Date")["Energy Score"])
                    st.write("### 🤖 Executive Summary")
                    st.write(analysis_text)
                    
                    # 4. GENERATE PDF
                    pdf_bytes = create_pdf(analysis_text, sun_sign, moon_sign, events)
                    
                    st.download_button(
                        label="📄 Download Official Destiny Dossier (PDF)",
                        data=pdf_bytes,
                        file_name="destiny_dossier.pdf",
                        mime="application/pdf"
                    )
                    
                except Exception as e:
                    st.error(f"AI/PDF Error: {e}")

            else:
                st.error("City not found.")
    else:
        st.warning("Enter details.")