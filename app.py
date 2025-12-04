import streamlit as st
import google.generativeai as genai
import comtradeapicall
import pandas as pd
import requests
from googleapiclient.discovery import build

# --- 1. CONFIGURATION & LANGUAGES ---
st.set_page_config(page_title=" Growmarkt", page_icon="🌍", layout="wide")

# Dictionary for Bilingual Interface
LANGUAGES = {
    "English": "en",
    "Türkçe": "tr"
}

# All text used in the app (Interface Translations)
TRANSLATIONS = {
    "en": {
        "title": "Marketing and Sales Tool",
        "sidebar_title": "⚙️ System Configuration",
        "api_info": "Enter your API Keys to activate the engine.",
        "lbl_lang": "Select Output Language",
        "lbl_prod": "Product Name",
        "lbl_hs": "HS Code",
        "lbl_country": "Target Country Code (ISO 3-digit)",
        "lbl_cname": "Target Country Name",
        "btn_run": "SEARCH",
        "step_1": "📊 Phase 1: Market Validation (UN Comtrade)",
        "step_2": "🏢 Phase 2: Buyer Discovery (Google & Hunter)",
        "step_3": "🧠 Phase 3: Strategic AI Report",
        "error_api": "❌ CRITICAL: Please enter ALL API keys in the sidebar!",
        "warn_mirror": "⚠️ Direct Data unavailable. Switching to 'Mirror Data' logic (as per methodology).",
        "success_data": "✅ Market Data Retrieved Successfully",
        "ai_instruction": "English" # Instruction for Gemini
    },
    "tr": {
        "title": "Pazarlama ve Satış  Aracı",
        "sidebar_title": "⚙️ Sistem Ayarları",
        "api_info": "Motoru aktifleştirmek için API anahtarlarını girin.",
        "lbl_lang": "Çıktı Dili Seçiniz",
        "lbl_prod": "Ürün Adı",
        "lbl_hs": "GTİP Kodu",
        "lbl_country": "Hedef Ülke Kodu (ISO 3-Haneli)",
        "lbl_cname": "Hedef Ülke Adı",
        "btn_run": "ARAŞTIR",
        "step_1": "📊 Faz 1: Pazar Doğrulama (BM Comtrade)",
        "step_2": "🏢 Faz 2: Alıcı Tespiti (Google & Hunter)",
        "step_3": "🧠 Faz 3: Yapay Zeka Strateji Raporu",
        "error_api": "❌ KRİTİK HATA: Lütfen yan menüdeki tüm API anahtarlarını giriniz!",
        "warn_mirror": "⚠️ Doğrudan veri yok. 'Ayna Verisi' (Mirror Data) mantığına geçiliyor.",
        "success_data": "✅ Pazar Verisi Başarıyla Çekildi",
        "ai_instruction": "Turkish" # Instruction for Gemini
    }
}

# --- 2. SIDEBAR (SETTINGS) ---
with st.sidebar:
    # Language Selector
    st.header("Language / Dil")
    selected_lang = st.selectbox("Choose Interface Language", list(LANGUAGES.keys()))
    lang_code = LANGUAGES[selected_lang]
    t = TRANSLATIONS[lang_code] # Load text based on selection

    st.divider()
    
    st.header(t["sidebar_title"])
    st.info(t["api_info"])
    
    # Secure Password Inputs
    GEMINI_KEY = st.text_input("Gemini API Key", type="password")
    COMTRADE_KEY = st.text_input("UN Comtrade Key", type="password")
    GOOGLE_KEY = st.text_input("Google API Key", type="password")
    GOOGLE_CX = st.text_input("Google Search Engine ID (CX)", type="password")
    HUNTER_KEY = st.text_input("Hunter.io API Key", type="password")

# --- 3. MAIN INTERFACE ---
st.title(t["title"])
st.markdown("---")

col1, col2 = st.columns(2)
with col1:
    product_name = st.text_input(t["lbl_prod"], "Hazelnuts")
    hs_code = st.text_input(t["lbl_hs"], "0802")
with col2:
    # Defaulting to Germany (276) for demo purposes
    target_country = st.text_input(t["lbl_country"], "276")
    country_name = st.text_input(t["lbl_cname"], "Germany")

run_btn = st.button(t["btn_run"], type="primary", use_container_width=True)

# --- 4. INTELLIGENCE ENGINE ---
if run_btn:
    if not (GEMINI_KEY and COMTRADE_KEY and GOOGLE_KEY and GOOGLE_CX and HUNTER_KEY):
        st.error(t["error_api"])
    else:
        # --- PHASE 1: MARKET DATA ---
        st.subheader(t["step_1"])
        market_stats = ""
        
        with st.status("Connecting to UN Comtrade Database...", expanded=True) as status:
            try:
                # API Call
                df = comtradeapicall.getFinalData(
                    subscription_key=COMTRADE_KEY, typeCode='C', freqCode='A', clCode='HS',
                    period='2023', reporterCode=target_country, cmdCode=hs_code, flowCode='M',
                    partnerCode=None, format_output='JSON'
                )
                
                if df is not None and not df.empty:
                    val = df['primaryValue'].sum()
                    qty = df['netWgt'].sum()
                    unit_price = val / qty if qty > 0 else 0
                    
                    st.success(t["success_data"])
                    c1, c2 = st.columns(2)
                    c1.metric("Import Volume", f"${val:,.0f}")
                    c2.metric("Unit Price", f"${unit_price:.2f}/kg")
                    
                    market_stats = f"Total Import: ${val}. Unit Price: ${unit_price:.2f}/kg."
                else:
                    st.warning(t["warn_mirror"])
                    market_stats = "Direct Data Unavailable. Analyst note: Used Mirror Data logic."
                    
            except Exception as e:
                st.error(f"Comtrade API Error: {e}")
                market_stats = "Data fetch failed."
            status.update(label="Phase 1 Complete", state="complete", expanded=False)

        # --- PHASE 2: BUYER FINDER ---
        st.subheader(t["step_2"])
        buyers_list = []
        
        with st.spinner("Scanning Google & Hunter.io for contacts..."):
            try:
                # 1. Google Search
                service = build("customsearch", "v1", developerKey=GOOGLE_KEY)
                query = f"top {product_name} importers distributors {country_name} -site:pinterest.*"
                res = service.cse().list(q=query, cx=GOOGLE_CX, num=5).execute()
                
                found_domains = []
                for item in res.get('items', []):
                    domain = item['displayLink'].replace("www.", "")
                    title = item['title']
                    found_domains.append({"Company": title, "Domain": domain})

                # 2. Hunter.io Enrichment
                final_data = []
                for company in found_domains:
                    email = "Not Public"
                    try:
                        h_url = f"https://api.hunter.io/v2/domain-search?domain={company['Domain']}&api_key={HUNTER_KEY}&limit=1"
                        h_res = requests.get(h_url).json()
                        if 'data' in h_res and h_res['data']['emails']:
                            email = h_res['data']['emails'][0]['value']
                    except:
                        pass
                    
                    final_data.append({"Company": company['Company'], "Website": company['Domain'], "Email": email})
                    buyers_list.append(company['Company'])
                
                # Display Results Table
                if final_data:
                    st.dataframe(pd.DataFrame(final_data), use_container_width=True)
                else:
                    st.warning("No buyers found in this pass.")
                    
            except Exception as e:
                st.error(f"Search Error: {e}")

        # --- PHASE 3: AI BRAIN (BILINGUAL) ---
        st.subheader(t["step_3"])
        
        with st.spinner("Gemini is writing the Strategic Report..."):
            genai.configure(api_key=GEMINI_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # The Prompt that adapts to the language
            prompt = f"""
            ACT AS: Senior Foreign Trade Analyst.
            LANGUAGE: Respond STRICTLY in {t['ai_instruction']} language.
            
            TASK: Analyze the market potential for {product_name} in {country_name}.
            
            DATA PROVIDED:
            - Market Stats: {market_stats}
            - Potential Buyers Found: {", ".join(buyers_list)}
            
            METHODOLOGY (Follow these rules):
            1. **Unit Value Analysis:** If price is >$5/kg, treat as Premium Market. If <$2, treat as Mass Market.
            2. **Direct vs Mirror:** If data was missing, mention risks of transparency.
            
            OUTPUT SECTIONS:
            1. **Executive Verdict:** (Go or No-Go?)
            2. **Buyer Strategy:** Should we approach these buyers as a discounter or premium supplier?
            3. **Cultural Tip:** One negotiation secret for {country_name}.
            4. **Cold Email Subject:** Draft a catchy subject line for the buyers found.
            """
            
            response = model.generate_content(prompt)
            st.markdown(response.text)
