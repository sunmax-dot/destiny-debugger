import streamlit as st
import ephem
import google.generativeai as genai
import math
from geopy.geocoders import Nominatim
import datetime
import time
import pandas as pd

# --- CONFIGURATION ---
st.set_page_config(page_title="Destiny Debugger", page_icon="🔮", layout="wide")

st.title("🔮 The Destiny Debugger: Universal Edition")
st.subheader("AI-Augmented Vedic Forecasting")

# --- SIDEBAR: INPUTS ---
with st.sidebar:
    st.header("1. Credentials")
    
    # Check if the key is in the "Secrets" vault
    if "GOOGLE_API_KEY" in st.secrets:
        api_key = st.secrets["GOOGLE_API_KEY"]
        st.success("✅ API Key loaded from System Secrets")
    else:
        # Fallback: Ask the user
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
    st.header("3. Forecast Settings")
    forecast_years = st.slider("Forecast Horizon (Years)", 1, 20, 15)

# --- LOGIC: HELPER FUNCTIONS ---
def get_lat_lon(city):
    try:
        geolocator = Nominatim(user_agent="destiny_debugger_v2")
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
    # This simulates the "Forward Curve"
    data = []
    current_date = datetime.datetime.now()
    end_date = current_date + datetime.timedelta(days=years*365)
    
    # Iterate month by month
    while current_date < end_date:
        date_str = current_date.strftime('%Y/%m/%d')
        
        # Calculate Transits
        t_jupiter = ephem.Jupiter()
        t_saturn = ephem.Saturn()
        t_jupiter.compute(date_str)
        t_saturn.compute(date_str)
        
        j_sign, j_idx = get_zodiac_sign(t_jupiter.hlon)
        s_sign, s_idx = get_zodiac_sign(t_saturn.hlon)
        
        # "Cosmic Score" Logic (Simplified for MVP)
        # Jupiter matching Natal Moon = High Growth (+2)
        # Saturn matching Natal Moon = High Pressure (-2)
        score = 0
        status = "Neutral"
        
        if j_idx == natal_moon_idx:
            score += 2
            status = "✨ Jupiter Return (Growth)"
        elif s_idx == natal_moon_idx:
            score -= 2
            status = "⚠️ Saturn Return (Pressure)"
        
        # Trines (120 degrees / 4 signs away) are also lucky
        if (j_idx - natal_moon_idx) % 4 == 0:
             score += 1
             
        data.append({
            "Date": current_date,
            "Energy Score": score,
            "Jupiter Sign": j_sign,
            "Saturn Sign": s_sign,
            "Status": status
        })
        
        # Advance 30 days
        current_date += datetime.timedelta(days=30)
        
    return pd.DataFrame(data)

# --- MAIN APP ---
if st.button("Run Universal Analysis"):
    if not api_key:
        st.error("⚠️ Please enter an API Key.")
    elif dob and tob and city_name:
        with st.spinner("Calculating Planetary Matrices..."):
            # 1. Geocode
            lat, lon = get_lat_lon(city_name)
            
            if lat:
                st.success(f"📍 Location Locked: {city_name}")
                
                # 2. Natal Chart
                date_str = f"{dob.strftime('%Y/%m/%d')} {tob.strftime('%H:%M:%S')}"
                obs = ephem.Observer()
                obs.lat, obs.lon, obs.date = str(lat), str(lon), date_str
                
                sun, moon = ephem.Sun(), ephem.Moon()
                sun.compute(obs)
                moon.compute(obs)
                
                sun_sign, sun_idx = get_zodiac_sign(sun.hlon)
                moon_sign, moon_idx = get_zodiac_sign(moon.hlon)
                
                # Layout: Top Row (Natal)
                c1, c2, c3 = st.columns(3)
                c1.metric("☀️ Sun Sign", sun_sign)
                c2.metric("🌙 Moon Sign", moon_sign)
                c3.metric("📅 Forecast Horizon", f"{forecast_years} Years")
                
                # 3. The Forward Curve (Data Engineering)
                df = calculate_transits(dob, forecast_years, moon_idx)
                
                # 4. Visualization (The "Curve")
                st.subheader("📈 The Energy Forward Curve")
                st.line_chart(df.set_index("Date")["Energy Score"])
                
                # Show key events table
                st.write("### Key Transit Events")
                events = df[df["Energy Score"] != 0].drop_duplicates(subset=["Status"])
                st.dataframe(events[["Date", "Status", "Jupiter Sign", "Saturn Sign"]], hide_index=True)
                
                # 5. AI Interpretation (Generic)
                st.divider()
                st.subheader("🤖 AI Oracle Analysis")
                
                genai.configure(api_key=api_key)
                model_candidates = ['gemini-flash-latest', 'gemini-pro-latest', 'gemini-2.0-flash-exp']
                
             # --- NEW: RAG LOADING ---
                try:
                    with open("knowledge.txt", "r") as f:
                        knowledge_base = f.read()
                except FileNotFoundError:
                    knowledge_base = "No specific rules found. Use general knowledge."

                # --- NEW: CONTEXTUAL PROMPT ---
                prompt = f"""
                Act as a Vedic Scholar. Use the following "Classical Rules" to analyze the user's chart.
                
                --- KNOWLEDGE BASE ---
                {knowledge_base}
                ----------------------
                
                User Data:
                - Sun Sign: {sun_sign}
                - Moon Sign: {moon_sign}
                - Transit Status: {events['Status'].tolist()}
                
                Task:
                1. Analyze the user's upcoming period.
                2. CITATION REQUIRED: You MUST quote a specific 'Rule' from the Knowledge Base if it applies. (e.g., "As per Rule 2...")
                3. If no rule perfectly fits, use your general knowledge but mention "General Interpretation".
                
                Keep it strict, scholarly, and strategic.
                """
                
                success = False
                status_box = st.empty()
                
                for model_name in model_candidates:
                    if success: break
                    try:
                        status_box.info(f"Consulting {model_name}...")
                        model = genai.GenerativeModel(model_name)
                        response = model.generate_content(prompt)
                        status_box.empty()
                        st.markdown(response.text)
                        success = True
                    except:
                        continue

                if not success:
                    st.error("AI Models busy. Please retry.")
            else:
                st.error("City not found.")
    else:
        st.warning("Enter birth details.")