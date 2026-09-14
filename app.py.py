import io
import os
from google import genai
from PIL import Image
import streamlit as st

# 1. Page Config & CSS Scaling Rules
st.set_page_config(
    page_title="Book Scanner to Gemini UI", page_icon="📚", layout="centered"
)

# Responsive mobile CSS to keep camera container locked within screen height
st.markdown(
    """
    <style>
        /* Restrain camera element height so no scrolling is needed */
        div[data-testid="stCameraInput"] {
            max-height: 42vh !important;
            overflow: hidden !important;
            border-radius: 12px;
        }
        div[data-testid="stCameraInput"] video {
            max-height: 40vh !important;
            object-fit: cover !important;
        }
        /* Mobile gallery thumbnail framing */
        .thumb-box {
            border: 1px solid #E3E3E3;
            border-radius: 8px;
            padding: 4px;
            background: #FAFAFA;
        }
    </style>
""",
    unsafe_allow_html=True,
)

# 2. Session State Initialization
if "page_images" not in st.session_state:
  st.session_state["page_images"] = []
if "raw_html" not in st.session_state:
  st.session_state["raw_html"] = None

# Safely extract API Key
api_key = ""
if "GEMINI_API_KEY" in st.secrets:
  api_key = st.secrets["GEMINI_API_KEY"]
elif "GEMINI_API_KEY" in os.environ:
  api_key = os.environ["GEMINI_API_KEY"]

client = genai.Client(api_key=api_key) if api_key else None

st.title("📚 Book Page Scanner")

if not api_key:
  st.error(
      "❌ API Key NOT detected! Check Streamlit Secrets under Manage App."
  )

# 3. Continuous Camera Input (Scales to Mobile Viewport)
camera_image = st.camera_input("Snap Page", label_visibility="collapsed")

if camera_image:
  img_bytes = camera_image.getvalue()
  # Add image if queue is empty or snapshot is not identical to last addition
  if (
      not st.session_state["page_images"]
      or st.session_state["page_images"][-1]["bytes"] != img_bytes
  ):
    pil_img = Image.open(io.BytesIO(img_bytes))
    pil_img.thumbnail((1500, 1500))  # Downscale to preserve memory
    st.session_state["page_images"].append(
        {"bytes": img_bytes, "pil": pil_img}
    )
    st.success(f"Added Page {len(st.session_state['page_images'])} to queue!")
    st.rerun()

# 4. Scanned Page Gallery & Deletion Controls
if st.session_state["page_images"]:
  st.divider()
  st.subheader(
      f"🖼️ Scanned Queue ({len(st.session_state['page_images'])} Pages)"
  )

  # Top-level Global Actions
  col_clear, col_finish = st.columns(2)
  with col_clear:
    if st.button("🗑️ Delete All Pages", use_container_width=True):
      st.session_state["page_images"] = []
      st.session_state["raw_html"] = None
      st.rerun()

  with col_finish:
    finish_clicked = st.button(
        "🚀 Finish & Process Book", type="primary", use_container_width=True
    )

  # Display scrollable page thumbnails with selective deletion
  st.write("Review captured pages below:")
  for idx, page_data in enumerate(st.session_state["page_images"]):
    grid_col1, grid_col2 = st.columns([1, 2])

    with grid_col1:
      st.image(page_data["pil"], caption=f"Page {idx + 1}", width=120)

    with grid_col2:
      st.write(f"**Page {idx + 1}**")
      if st.button(f"❌ Delete Page {idx + 1}", key=f"del_{idx}"):
        st.session_state["page_images"].pop(idx)
        st.rerun()

  st.divider()
else:
  finish_clicked = False

# 5. AI OCR Processing Block
if finish_clicked and client:
  with st.spinner(
      f"Processing {len(st.session_state['page_images'])} pages with AI..."
  ):
    pil_list = [item["pil"] for item in st.session_state["page_images"]]
    prompt = (
        "Extract all text sequentially across all provided page images."
        " Preserve original typographical styling: convert bold text to"
        " <strong>...</strong>, italics to <em>...</em>, and headers to <h1>"
        " or <h2>. Return ONLY valid inner HTML elements without markdown code"
        " block wrappers."
    )

    try:
      response = client.models.generate_content(
          model="gemini-2.0-flash", contents=[*pil_list, prompt]
      )
      st.session_state["raw_html"] = (
          response.text.replace("```html", "").replace("```", "").strip()
      )
    except Exception as e:
      st.error(f"⚠️ Gemini API Error Details: {e}")

# 6. Gemini Reader Display & Offline Export
if st.session_state.get("raw_html"):
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

  size_map = {
      "Small": "14px",
      "Medium": "16px",
      "Large": "19px",
      "Extra Large": "22px",
  }
  selected_size = size_map[font_size]

  if dark_mode:
    bg_body, bg_card, text_color, border_color, h1_color = (
        "#121212",
        "#1E1E1E",
        "#E3E3E3",
        "#333333",
        "#8AB4F8",
    )
  else:
    bg_body, bg_card, text_color, border_color, h1_color = (
        "#F8F9FA",
        "#FFFFFF",
        "#1F1F1F",
        "#E3E3E3",
        "#0B57D0",
    )

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
