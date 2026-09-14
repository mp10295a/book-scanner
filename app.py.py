import io
import os
import streamlit as st
from google import genai
from PIL import Image

# 1. Page Configuration & Initial Layout
st.set_page_config(
    page_title="Book Scanner to Gemini UI", page_icon="📚", layout="centered"
)

# Initialize Session State Variables
if "page_images" not in st.session_state:
  st.session_state["page_images"] = []
if "raw_html" not in st.session_state:
  st.session_state["raw_html"] = None

# Initialize API Client
# Checks Streamlit Secrets first, then environment variables, then empty fallback
api_key = ""
if "GEMINI_API_KEY" in st.secrets:
  api_key = st.secrets["GEMINI_API_KEY"]
elif "GEMINI_API_KEY" in os.environ:
  api_key = os.environ["GEMINI_API_KEY"]

client = genai.Client(api_key=api_key) if api_key else None

st.title("📚 Book Page Scanner")
st.write("Capture book pages sequentially, then compile them into one view.")

# --- 2. CAMERA CAPTURE & QUEUE MANAGEMENT ---
camera_image = st.camera_input("Take a photo of a page")

if camera_image:
  img_bytes = camera_image.getvalue()
  # Prevent duplicate additions of the same snapshot
  if (
      not st.session_state["page_images"]
      or st.session_state["page_images"][-1]["bytes"] != img_bytes
  ):
    pil_img = Image.open(io.BytesIO(img_bytes))
    # Resize image to save memory and ensure high performance
    pil_img.thumbnail((1500, 1500))
    st.session_state["page_images"].append(
        {"bytes": img_bytes, "pil": pil_img}
    )
    st.success(f"Added Page {len(st.session_state['page_images'])} to queue!")

# Display current queue controls
if st.session_state["page_images"]:
  st.info(f"Pages captured so far: **{len(st.session_state['page_images'])}**")
  col_clear, col_finish = st.columns(2)

  with col_clear:
    if st.button("🗑️ Reset Queue", use_container_width=True):
      st.session_state["page_images"] = []
      st.session_state["raw_html"] = None
      st.rerun()

  with col_finish:
    finish_clicked = st.button(
        "🚀 Finish & Process Book", type="primary", use_container_width=True
    )

  # --- 3. AGGREGATED AI OCR PROCESSING ---
  if finish_clicked and client:
    with st.spinner(
        f"Processing {len(st.session_state['page_images'])} pages with AI..."
    ):
      pil_list = [item["pil"] for item in st.session_state["page_images"]]

      prompt = (
          "You are an expert OCR and document formatting engine.\n"
          "1. Extract all text sequentially across all provided page images.\n"
          "2. Preserve original typographical styling: convert bold text to"
          " <strong>...</strong>, italics to <em>...</em>, and headers to <h1>"
          " or <h2>.\n"
          "3. Seamlessly merge sentences and paragraphs that break across page"
          " boundaries.\n"
          "4. Return ONLY valid inner HTML elements without any markdown code"
          " block wrappers."
      )

      response = client.models.generate_content(
          model="gemini-2.5-flash", contents=[*pil_list, prompt]
      )

      # Clean raw response string
      st.session_state["raw_html"] = (
          response.text.replace("```html", "").replace("```", "").strip()
      )

# --- 4. READER CONTROLS & DYNAMIC DISPLAY ---
if st.session_state.get("raw_html"):
  st.divider()
  st.subheader("📖 Reader Controls")

  ctrl_col1, ctrl_col2 = st.columns([1, 1])

  with ctrl_col1:
    dark_mode = st.toggle("🌙 Dark Mode", value=False)

  with ctrl_col2:
    font_size = st.select_slider(
        "🔤 Font Size",
        options=["Small", "Medium", "Large", "Extra Large"],
        value="Medium",
    )

  # Size Map Definitions
  size_map = {
      "Small": "14px",
      "Medium": "16px",
      "Large": "19px",
      "Extra Large": "22px",
  }
  selected_size = size_map[font_size]

  # Theme CSS Variables
  if dark_mode:
    bg_body = "#121212"
    bg_card = "#1E1E1E"
    text_color = "#E3E3E3"
    border_color = "#333333"
    h1_color = "#8AB4F8"
  else:
    bg_body = "#F8F9FA"
    bg_card = "#FFFFFF"
    text_color = "#1F1F1F"
    border_color = "#E3E3E3"
    h1_color = "#0B57D0"

  # Render Interactive HTML Display
  styled_reader_html = f"""
    <div style="
        background-color: {bg_card};
        color: {text_color};
        border: 1px solid {border_color};
        border-radius: 16px;
        padding: 24px 28px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: {selected_size};
        line-height: 1.65;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        margin-top: 10px;
    ">
        <style>
            h1 {{ color: {h1_color}; font-size: 1.6em; border-bottom: 1px solid {border_color}; padding-bottom: 8px; }}
            h2 {{ color: {text_color}; font-size: 1.25em; margin-top: 20px; }}
            p {{ margin-bottom: 14px; word-wrap: break-word; }}
        </style>
        {st.session_state['raw_html']}
    </div>
    """

  st.markdown(styled_reader_html, unsafe_allow_html=True)
  st.divider()

  # Construct Standalone Downloadable HTML Document
  standalone_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Scanned Book</title>
<style>
    body {{
        background-color: {bg_body};
        color: {text_color};
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: {selected_size};
        line-height: 1.65;
        padding: 20px 12px;
        margin: 0;
    }}
    .container {{
        max-width: 680px;
        margin: 0 auto;
        background: {bg_card};
        padding: 24px 28px;
        border-radius: 16px;
        border: 1px solid {border_color};
    }}
    h1 {{ color: {h1_color}; font-size: 1.6em; border-bottom: 1px solid {border_color}; padding-bottom: 8px; }}
    h2 {{ color: {text_color}; font-size: 1.25em; margin-top: 20px; }}
    p {{ margin-bottom: 14px; word-wrap: break-word; }}
</style>
</head>
<body>
    <div class="container">
        {st.session_state['raw_html']}
    </div>
</body>
</html>"""

  st.download_button(
      label="💾 Download Offline HTML Document",
      data=standalone_doc,
      file_name="scanned_book.html",
      mime="text/html",
      use_container_width=True,
  )
