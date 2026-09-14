import io
import os
from google import genai
from PIL import Image
import streamlit as st

# 1. Page Setup & Mobile Styling
st.set_page_config(
    page_title="Book Scanner to Gemini UI", page_icon="📚", layout="centered"
)

# Custom CSS to lock camera height and gallery styling
st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 2rem !important;
            max-width: 500px !important;
        }
        iframe {
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
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

# 3. Custom HTML5 Rear Camera Feed Component
# Forces facingMode: "environment" (rear camera) and fills portrait view
camera_html = """
<div style="width: 100%; display: flex; flex-direction: column; align-items: center; gap: 8px;">
    <video id="webcam" autoplay playsinline style="width: 100%; height: 50vh; object-fit: cover; border-radius: 12px; background: #000;"></video>
    <button id="snap-btn" style="width: 100%; height: 48px; background-color: #0B57D0; color: white; border: none; border-radius: 24px; font-weight: 600; font-size: 16px; cursor: pointer;">
        📷 Snap Page Photo
    </button>
    <canvas id="canvas" style="display:none;"></canvas>
</div>

<script>
    const video = document.getElementById('webcam');
    const canvas = document.getElementById('canvas');
    const snapBtn = document.getElementById('snap-btn');

    // Request rear camera with portrait resolution parameters
    navigator.mediaDevices.getUserMedia({
        video: {
            facingMode: { exact: "environment" },
            width: { ideal: 1920 },
            height: { ideal: 1080 }
        }
    }).then(stream => {
        video.srcObject = stream;
    }).catch(err => {
        // Fallback for desktop browsers without rear camera
        navigator.mediaDevices.getUserMedia({ video: true }).then(stream => {
            video.srcObject = stream;
        });
    });

    snapBtn.addEventListener('click', () => {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
        
        // Send image data to Streamlit backend via window communication
        window.parent.postMessage({
            type: "streamlit:setComponentValue",
            value: dataUrl
        }, "*");
    });
</script>
"""

# Render Camera HTML inside high-priority container
captured_data_url = st.components.v1.html(camera_html, height=440)

# Process snap payload
if captured_data_url:
  import base64

  # Decode base64 image data from HTML JS component
  header, encoded = captured_data_url.split(",", 1)
  img_bytes = base64.b64decode(encoded)

  if (
      not st.session_state["page_images"]
      or st.session_state["page_images"][-1]["bytes"] != img_bytes
  ):
    pil_img = Image.open(io.BytesIO(img_bytes))
    pil_img.thumbnail((1500, 1500))
    st.session_state["page_images"].append(
        {"bytes": img_bytes, "pil": pil_img}
    )
    st.success(f"Added Page {len(st.session_state['page_images'])} to queue!")
    st.rerun()

# 4. Scanned Page Gallery & Selective Delete Controls
if st.session_state["page_images"]:
  st.divider()
  st.subheader(
      f"🖼️ Scanned Queue ({len(st.session_state['page_images'])} Pages)"
  )

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

# 5. AI Processing Engine
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

# 6. Reader View Controls & Offline Export
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
