import os
import json
import re
import base64
import requests
import pandas as pd
import streamlit as st
from groq import Groq
from dotenv import load_dotenv
from PIL import Image
import io

load_dotenv()

# Load API Keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OCRSPACE_API_KEY = os.getenv("OCRSPACE_API_KEY") 

if not GROQ_API_KEY:
    st.error("GROQ_API_KEY not set. Please set it as an environment variable.")
    st.stop()
if not OCRSPACE_API_KEY:
    st.error("OCRSPACE_API_KEY not set. Please set it as an environment variable.")
    st.stop()

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# Helper functions
DEFAULT_COUNTRY = "Malaysia"
COUNTRY_CODE_MAP = {
    "malaysia": "60",
    "singapore": "65",
    "indonesia": "62",
    "thailand": "66",
    "united states": "1",
    "usa": "1",
    "united kingdom": "44",
    "uk": "44",
    "australia": "61",
    "china": "86",
    "hong kong": "852",
    "japan": "81",
    "south korea": "82",
}

def extract_text_from_image_bytes(image_bytes, filename="image.png"):
    """
    Use OCR.space API with file upload (multipart/form-data) to extract text.
    """
    # Determine MIME type from file extension
    ext = filename.split('.')[-1].lower()
    if ext in ['jpg', 'jpeg']:
        mime_type = 'image/jpeg'
    elif ext == 'png':
        mime_type = 'image/png'
    elif ext in ['bmp']:
        mime_type = 'image/bmp'
    elif ext in ['tiff', 'tif']:
        mime_type = 'image/tiff'
    else:
        mime_type = 'image/png'  # fallback

    files = {
        'file': (filename, image_bytes, mime_type)
    }
    data = {
        'apikey': OCRSPACE_API_KEY,
        'language': 'eng',
        'isOverlayRequired': False,
        'detectOrientation': True,
        'scale': True,
    }
    response = requests.post(
        'https://api.ocr.space/parse/image',
        files=files,
        data=data,
        timeout=30
    )

    if response.status_code != 200:
        raise Exception(f"OCR.space API error (HTTP {response.status_code}): {response.text}")

    result = response.json()
    if result.get('OCRExitCode') != 1:
        error_msg = result.get('ErrorMessage', 'Unknown error')
        raise Exception(f"OCR.space error: {error_msg}")

    parsed_text = ""
    for parsed in result.get('ParsedResults', []):
        parsed_text += parsed.get('ParsedText', '') + "\n"

    return parsed_text.strip()

def call_groq_extract(text):
    """Send OCR text to Groq and ask for structured JSON, including Country."""
    prompt = f"""
You are a contact card information extractor. Given the OCR text below, extract the following fields and return a JSON object with exactly these keys:
"Name", "Company Name", "Position", "Department", "Phone Number", "Office Number", "Extension", "Email", "Company Address", "Country".

Rules:
- If a field is not present, set to null.
- For phone numbers and office numbers, extract all numbers you find; we'll later format them.
- For "Office Number", if there are multiple office numbers, list them as an array (e.g., ["074546282", "074546666"]).
- For "Extension", if there is a separate extension number, extract it; otherwise set to null.
- For "Company Address", include full address as a string.
- For "Country", infer the country from the address or any other context (e.g., if address contains "NY" or "USA" -> "United States"). Use full country name (e.g., "Malaysia", "Singapore", "United States").

OCR Text:
{text}

Return ONLY valid JSON, no extra text.
"""
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",  # or another model
        messages=[
            {"role": "system", "content": "You are a helpful assistant that extracts structured data from OCR text."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    content = response.choices[0].message.content
    # For debugging (remove after testing)
    print("Groq raw response:", content)

    # Try to parse as JSON
    try:
        data = json.loads(content.strip())
        return data
    except json.JSONDecodeError:
        pass

    # Remove markdown code fences
    content = re.sub(r'^```(?:json)?\s*', '', content.strip(), flags=re.MULTILINE)
    content = re.sub(r'\s*```$', '', content, flags=re.MULTILINE)

    # Try to extract JSON with regex
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return data
        except json.JSONDecodeError as e:
            raise ValueError(f"Groq returned invalid JSON even after extraction: {e}\nRaw content: {content}")

    raise ValueError(f"Groq did not return valid JSON. Raw content: {content}")

def infer_country_from_address(address):
    """Fallback: detect country from address string."""
    if not address:
        return DEFAULT_COUNTRY
    address_lower = address.lower()
    for country in COUNTRY_CODE_MAP:
        if country in address_lower:
            return country
    return DEFAULT_COUNTRY

def format_phone_number(number, country_code):
    """
    Format phone number: remove non-digits, add country code if missing.
    Handles both string and list input (takes first non-empty if list).
    """
    if not number:
        return None
    # If it's a list, take the first non-empty element
    if isinstance(number, list):
        valid = [n for n in number if n]
        if not valid:
            return None
        number = valid[0]  # or join them with ", " if you prefer
    # Ensure it's a string
    number = str(number)
    digits = re.sub(r'\D', '', number)
    if not digits:
        return None
    if digits.startswith(country_code):
        return "+" + digits
    if digits.startswith('0'):
        digits = digits[1:]
    return "+" + country_code + digits

def format_office_number(number, country_code):
    return format_phone_number(number, country_code)

def compute_extensions(office_numbers):
    """Compute extension as differing suffix from a list of office numbers."""
    if not office_numbers or len(office_numbers) < 2:
        return None
    common_prefix = os.path.commonprefix(office_numbers)
    if not common_prefix:
        return None
    suffix = office_numbers[-1][len(common_prefix):]
    return suffix if suffix else None

def validate_and_format(data):
    # Determine country: try from extracted "Country" field first
    country = data.get("Country")
    if not country:
        # Fallback to address inference
        country = infer_country_from_address(data.get("Company Address"))
    # Normalize country name to lookup code
    country_lower = country.lower() if country else DEFAULT_COUNTRY.lower()
    country_code = COUNTRY_CODE_MAP.get(country_lower)
    if not country_code:
        # If not found, use default Malaysia (60)
        country_code = COUNTRY_CODE_MAP.get(DEFAULT_COUNTRY.lower(), "60")

    # ---- Phone Number ----
    if data.get("Phone Number"):
        data["Phone Number"] = format_phone_number(data["Phone Number"], country_code)

    # ---- Office Number ----
    office = data.get("Office Number")
    if office:
        if isinstance(office, str):
            office = [office]
        elif not isinstance(office, list):
            office = [str(office)]
        formatted_offices = [format_office_number(num, country_code) for num in office if num]
        data["Office Number"] = formatted_offices
        # Compute extension if multiple offices and extension missing
        if not data.get("Extension") and len(formatted_offices) > 1:
            data["Extension"] = compute_extensions(formatted_offices)
    else:
        data["Office Number"] = None

    if data.get("Extension") is not None:
        data["Extension"] = str(data["Extension"])

    return data

def process_image_bytes(image_bytes):
    text = extract_text_from_image_bytes(image_bytes)
    if not text:
        return None
    data = call_groq_extract(text)
    data = validate_and_format(data)
    return data

# ---------- Streamlit UI ----------
st.set_page_config(page_title="Contact Card Extractor", layout="wide")
st.title("📇 Contact Card Extractor")
st.markdown("Upload business card images – we'll extract contact details using OCR.space + Groq.")

uploaded_files = st.file_uploader(
    "Choose images (JPG, PNG, etc.)",
    type=["jpg", "jpeg", "png", "bmp", "tiff"],
    accept_multiple_files=True,
)

if uploaded_files:
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    for i, file in enumerate(uploaded_files):
        status_text.text(f"Processing {file.name}...")
        try:
            data = process_image_bytes(file.read())
            if data:
                results.append(data)
        except Exception as e:
            st.error(f"Error processing {file.name}: {e}")
        progress_bar.progress((i + 1) / len(uploaded_files))
    status_text.text("Done!")

    if results:
        # Flatten Office Number list for display
        for r in results:
            if isinstance(r.get("Office Number"), list):
                r["Office Number"] = ", ".join(r["Office Number"])
        df = pd.DataFrame(results)
        st.subheader("Extracted Contacts")
        st.dataframe(df, use_container_width=True)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download as CSV",
            data=csv,
            file_name="contacts.csv",
            mime="text/csv",
        )
    else:
        st.warning("No valid contacts extracted.")