# 📇 Contact Card Recognition

Extract contact information from business card images using OCR and an LLM.
Upload one or more card images and the app returns structured fields (Name, Company, Phone, Email, Address and more) in a table you can copy into Excel or download as CSV.

---

## ✨ Features

- **Batch upload** – process multiple images at once (JPG, JPEG, PNG, BMP, TIFF).
- **OCR** – uses [OCR.space](https://ocr.space/OCRAPI) (free tier available) with orientation detection and auto-scaling.
- **Smart parsing** – uses a [Groq](https://groq.com/) LLM (`openai/gpt-oss-120b`) to turn raw OCR text into structured JSON.
- **Field extraction** – Name, Company Name, Position, Department, Phone Number, Office Number, Extension, Email, Company Address, Country.
- **Automatic country detection** – taken from the LLM's `Country` field, falling back to keyword matching on the address, then to Malaysia.
- **Name and company formatting** – whitespace trimmed and converted to Title Case.
- **Phone number formatting** – strips non-digits, removes the leading `0`, and adds the country code with a `+` prefix (e.g. `012-345 6789` → `+60123456789`).
- **Multiple office numbers** – all are formatted and kept as a list.
- **Extension detection** – if no extension is printed and there are several office numbers, it is computed from the differing suffix.
- **Table view and CSV export** – results shown in an interactive table with a download button.

Supported country codes: Malaysia (60), Singapore (65), Indonesia (62), Thailand (66), United States (1), United Kingdom (44), Australia (61), China (86), Hong Kong (852), Japan (81), South Korea (82). Unknown countries default to Malaysia (60).

---

## 🏗️ How It Works

```
┌────────────┐    ┌────────────┐    ┌────────────┐
│  Business  │───▶│ OCR.space  │───▶│    Groq    │
│ Card Image │    │   (OCR)    │    │   (LLM)    │
└────────────┘    └────────────┘    └─────┬──────┘
                                          │ JSON
                                          ▼
                                    ┌────────────┐
                                    │ Validation │
                                    │ + Format   │
                                    └─────┬──────┘
                                          ▼
                                    ┌────────────┐
                                    │ Streamlit  │
                                    │ Table + CSV│
                                    └────────────┘
```

1. **OCR** – each image is uploaded to OCR.space, which returns raw text.
2. **LLM extraction** – the text is sent to Groq with a prompt asking for a JSON object with the fields above. Markdown fences and extra text in the response are stripped before parsing.
3. **Post-processing** – names and companies are title-cased, phone and office numbers are formatted with the country code, and extensions are computed where needed.
4. **Display** – results appear in a Streamlit table with a CSV download button.

---

## 🚀 Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/your-username/contact-card-recognition.git
cd contact-card-recognition
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

The app needs `streamlit`, `groq`, `requests`, `pandas`, `python-dotenv` and `Pillow`.

### 3. Set up API keys

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your-groq-api-key
OCRSPACE_API_KEY=your-ocr-space-api-key
```

- **Groq API key** – get one free at [console.groq.com](https://console.groq.com/).
- **OCR.space API key** – get one free at [ocr.space/OCRAPI](https://ocr.space/OCRAPI).

The app stops with an error message if either key is missing. Do not commit `.env` to git.

### 4. Run the app

```bash
streamlit run app_g.py
```

Open your browser at <http://localhost:8501>, upload your card images, and download the results as `contacts.csv`.

---

## 📄 Output Fields

| Field | Notes |
|-------|-------|
| Name | Title Case |
| Company Name | Title Case |
| Position | As printed |
| Department | As printed |
| Phone Number | International format, e.g. `+60123456789` |
| Office Number | One or more numbers, comma-separated in the table |
| Extension | Printed value, or computed from multiple office numbers |
| Email | As printed |
| Company Address | Full address string |
| Country | Full country name |

Fields not found on the card are left empty.

---

## ⚠️ Notes and Limitations

- OCR quality depends on image clarity. Use well-lit, straight-on photos.
- The OCR.space free tier has file-size and request limits.
- Only the first phone number is kept if the LLM returns several for the Phone Number field.
- Extracted data is sent to OCR.space and Groq. Do not upload cards you are not permitted to share with third-party services.
