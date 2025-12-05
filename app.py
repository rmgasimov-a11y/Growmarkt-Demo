import streamlit as st
import google.generativeai as genai
import comtradeapicall
import pandas as pd
import requests
import json
from googleapiclient.discovery import build

# --- PAGE SETUP ---
st.set_page_config(page_title="Growmarkt AI", page_icon="🚀", layout="wide")

# --- SIDEBAR: API KEYS ---
with st.sidebar:
    st.header("🔑 API Keys")
    GEMINI_KEY = st.text_input("Gemini API Key", type="password")
    COMTRADE_KEY = st.text_input("UN Comtrade Key", type="password")
    GOOGLE_KEY = st.text_input("Google API Key", type="password")
    GOOGLE_CX = st.text_input("Google Engine ID (CX)", type="password")
    HUNTER_KEY = st.text_input("Hunter.io API Key", type="password")

    if GEMINI_KEY:
        genai.configure(api_key=GEMINI_KEY)

# --- FUNCTIONS ---

def get_product_intelligence(product_name):
    """
    Asks AI to identify the correct HS Code and Best Target Market 
    so the user doesn't have to do it manually.
    """
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    I want to export '{product_name}'.
    Identify the most specific 4-digit or 6-digit HS Code for this product.
    Identify the top #1 importing country for this product (globally).
    
    Return ONLY a JSON string. No markdown. Format:
    {{
        "hs_code": "0802", 
        "target_country_iso": "276", 
        "country_name": "Germany"
    }}
    * Note: target_country_iso must be the ISO 3-digit numeric code (e.g. 276 for Germany, 840 for USA).
    """
    try:
        response = model.generate_content(prompt)
        # Clean the response to ensure valid JSON
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        return None

def get_comtrade_data(api_key, hs_code, country_code):
    """Fetches trade volume and price from UN Comtrade."""
    try:
        df = comtradeapicall.getFinalData(
            subscription_key=api_key, typeCode='C', freqCode='A', clCode='HS',
            period='2023', reporterCode=country_code, cmdCode=hs_code, flowCode='M',
            format_output='JSON'
        )
        if df is not None and not df.empty:
            val = df['primaryValue'].sum()
            qty = df['netWgt'].sum()
            unit_price = val / qty if qty > 0 else 0
            return f"Total Import Volume: ${val:,.0f}, Average Price: ${unit_price:.2f}/kg"
        return "Direct trade data not available (or zero trade)."
    except Exception as e:
        return f"Database Error: {e}"

def get_buyers(google_key, cx, product, country, hunter_key):
    """Finds buyers on Google and emails on Hunter."""
    buyers = []
    try:
        service = build("customsearch", "v1", developerKey=google_key)
        query = f"top {product} importers distributors {country} -site:pinterest.*"
        res = service.cse().list(q=query, cx=cx, num=5).execute()
        
        for item in res.get('items', []):
            domain = item['displayLink'].replace("www.", "")
            email = "Not Found"
            # Optional: Hunter.io check
            if hunter_key:
                try:
                    h_url = f"https://api.hunter.io/v2/domain-search?domain={domain}&api_key={hunter_key}&limit=1"
                    h_data = requests.get(h_url).json()
                    if 'data' in h_data and h_data['data']['emails']:
                        email = h_data['data']['emails'][0]['value']
                except:
                    pass
            buyers.append(f"{item['title']} (Web: {domain}, Email: {email})")
    except Exception as e:
        buyers.append(f"Search Error: {str(e)}")
    return buyers

# --- MAIN APP ---
st.title("🌍 Growmarkt AI: Automated Market Analyst")
st.markdown("Enter a product. We will find the HS code, the best country, and the strategy.")

product_input = st.text_input("Product Name", "Hazelnuts")

if st.button("Generate Full Report"):
    if not (GEMINI_KEY and COMTRADE_KEY and GOOGLE_KEY and GOOGLE_CX):
        st.error("Please enter your API Keys in the sidebar first.")
    else:
        status_box = st.status("🚀 Starting AI Agent...", expanded=True)
        
        # 1. AI IDENTIFICATION
        status_box.write("🤖 Identifying HS Code and Target Market...")
        intelligence = get_product_intelligence(product_input)
        
        if intelligence:
            hs_code = intelligence['hs_code']
            country_iso = intelligence['target_country_iso']
            country_name = intelligence['country_name']
            st.success(f"Target Identified: {country_name} (HS: {hs_code})")
            
            # 2. DATABASE SEARCH
            status_box.write(f"📊 Fetching Trade Data for {country_name}...")
            market_data = get_comtrade_data(COMTRADE_KEY, hs_code, country_iso)
            
            status_box.write("🔍 Searching for Buyers & Competitors...")
            buyers_list = get_buyers(GOOGLE_KEY, GOOGLE_CX, product_input, country_name, HUNTER_KEY)
            
            status_box.update(label="Data Collection Complete!", state="complete", expanded=False)
            
            # 3. FINAL REPORT GENERATION
            st.divider()
            st.header(f"Strategic Report: {product_input} -> {country_name}")
            
            model = genai.GenerativeModel('gemini-1.5-flash')
            report_prompt = f"""
            ACT AS: Senior Trade Consultant.
            TASK: Write a strategic export report.
            PRODUCT: {product_input} (HS: {hs_code})
            TARGET MARKET: {country_name}
            REAL DATA FOUND: {market_data}
            POTENTIAL BUYERS FOUND: {", ".join(buyers_list)}
            
            OUTPUT STRUCTURE (Strictly follow this):
            1. **Executive Summary**: Should we enter this market? (Yes/No and why).
            2. **Market Analysis**: Interpret the trade volume and price. Is it premium or low cost?
            3. **Buyer Strategy**: How to approach the buyers found?
            4. **Draft Email**: Write a cold email to one of the buyers found above.
            """
            
            with st.spinner("Writing final report..."):
                report = model.generate_content(report_prompt)
                st.markdown(report.text)
                
        else:
            status_box.update(label="Failed", state="error")
            st.error("AI could not identify the product. Please try a clearer name.")
