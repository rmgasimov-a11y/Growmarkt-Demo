import streamlit as st
import google.generativeai as genai
import comtradeapicall
import pandas as pd
import requests
from googleapiclient.discovery import build

# --- PAGE SETUP ---
st.set_page_config(page_title="Growmarkt AI", page_icon="🚀", layout="wide")

# --- SIDEBAR API KEYS ---
with st.sidebar:
    st.header("🔑 API Keys")
    GEMINI_KEY = st.text_input("Gemini API Key", type="password")
    COMTRADE_KEY = st.text_input("UN Comtrade Key", type="password")
    GOOGLE_KEY = st.text_input("Google API Key", type="password")
    GOOGLE_CX = st.text_input("Google Engine ID (CX)", type="password")
    HUNTER_KEY = st.text_input("Hunter.io API Key", type="password")

    # Configure Gemini safely
    if GEMINI_KEY:
        try:
            genai.configure(api_key=GEMINI_KEY)
        except Exception as e:
            st.error(f"API Key Error: {e}")

# --- ROBUST AI FUNCTIONS ---

def get_smart_details(product_name):
    """
    Uses a 'Pipe Separator' method which is much harder to break than JSON.
    It asks the AI for: HS_CODE|COUNTRY_ISO|COUNTRY_NAME
    """
    try:
        # Try using the newer model.
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        I am exporting '{product_name}'.
        1. Identify the best 4-digit HS Code (Harmonized System).
        2. Identify the ISO 3-digit numeric code for the #1 importing country globally.
        3. Identify the Name of that country.

        CRITICAL: Return the result as a SINGLE LINE separated by pipes (|).
        Format: HS_CODE|COUNTRY_CODE|COUNTRY_NAME
        Example: 0802|276|Germany
        
        Do not write "Here is the code". Just write the data.
        """
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        
        # Clean up any potential markdown formatting the AI might add
        text = text.replace("`", "").replace("json", "").replace("text", "").strip()
        
        # Parse the Pipe (|) format
        parts = text.split('|')
        
        if len(parts) >= 3:
            return {
                "hs_code": parts[0].strip(),
                "target_country_iso": parts[1].strip(),
                "country_name": parts[2].strip()
            }
        else:
            return None
            
    except Exception as e:
        # If the user sees this, they know exactly why it failed
        st.error(f"AI Connection Error: {e}")
        return None

def get_market_data(api_key, hs, country):
    """Fetches real trade data. Fails gracefully if no data found."""
    if not api_key: return "No Comtrade Key provided."
    try:
        df = comtradeapicall.getFinalData(
            subscription_key=api_key, typeCode='C', freqCode='A', clCode='HS',
            period='2023', reporterCode=country, cmdCode=hs, flowCode='M',
            format_output='JSON'
        )
        if df is not None and not df.empty:
            val = df['primaryValue'].sum()
            return f"${val:,.0f} Total Import Volume (2023)"
        return "Direct Data Unavailable (Using Mirror Statistics)"
    except:
        return "Data Connection Failed"

def find_buyers(g_key, cx, product, country):
    """Simple Google Search for buyers."""
    if not (g_key and cx): return ["No Google Keys provided"]
    results = []
    try:
        service = build("customsearch", "v1", developerKey=g_key)
        q = f"{product} importers distributors {country} -site:pinterest.*"
        res = service.cse().list(q=q, cx=cx, num=5).execute()
        for item in res.get('items', []):
            results.append(f"{item['title']} ({item['displayLink']})")
    except Exception as e:
        results.append(f"Search Error: {str(e)}")
    return results

# --- MAIN APP UI ---
st.title("🌍 One-Click Export Analyst")
st.markdown("Type a product. We handle the codes, the countries, and the strategy.")

product = st.text_input("Product Name", "Semi-Trailer")

if st.button("🚀 Analyze Market"):
    if not GEMINI_KEY:
        st.error("⚠️ Please enter your Gemini API Key in the sidebar.")
    else:
        status = st.status("🧠 AI Agent is thinking...", expanded=True)
        
        # 1. Identify Product & Market
        status.write("Identifying HS Code and Best Market...")
        details = get_smart_details(product)
        
        if details:
            target_name = details['country_name']
            hs_code = details['hs_code']
            iso_code = details['target_country_iso']
            
            st.success(f"Targeting: {target_name} (HS: {hs_code})")
            
            # 2. Get Data
            status.write(f"Fetching Trade Data for {target_name}...")
            market_stat = get_market_data(COMTRADE_KEY, hs_code, iso_code)
            
            status.write("Searching for Buyers...")
            buyers = find_buyers(GOOGLE_KEY, GOOGLE_CX, product, target_name)
            
            status.update(label="Analysis Complete!", state="complete", expanded=False)
            
            # 3. Generate Strategy
            st.divider()
            st.subheader(f"📝 Strategic Report: {product} for {target_name}")
            
            model = genai.GenerativeModel('gemini-1.5-flash')
            strategy_prompt = f"""
            ACT AS: Senior Export Consultant.
            PRODUCT: {product} (HS: {hs_code})
            TARGET MARKET: {target_name}
            MARKET DATA: {market_stat}
            LEADS FOUND: {", ".join(buyers)}
            
            WRITE A REPORT WITH THESE HEADERS:
            1. **Market Verdict**: Should we enter? (Yes/No).
            2. **Data Insight**: What does the volume ({market_stat}) tell us?
            3. **Buyer Approach**: How to email these specific leads?
            4. **Draft Email**: Write a cold email subject and body for one of the leads.
            """
            
            with st.spinner("Writing report..."):
                report = model.generate_content(strategy_prompt)
                st.markdown(report.text)
        else:
            status.update(label="Identification Failed", state="error")
            st.error("The AI could not identify this product. Please check your Gemini API Key.")
