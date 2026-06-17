import json
import os
import sys
import tempfile
import urllib.parse
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

# Ensure project root is in sys.path for Streamlit execution
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.pipeline import run_pipeline


APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACTS_DIR = os.path.join(APP_DIR, "artifacts")
SUBMISSIONS_PATH = os.path.join(ARTIFACTS_DIR, "submitted_reports.json")
DEMO_LOCATION = "Gulberg Main Boulevard, Lahore"
DEMO_IMAGE_PATH = "demo_assets/test_scene.jpg"
DEMO_DESCRIPTION = "There is a severe sewage spill and a massive open hole on the road."

NEARBY_REPORTS_MAP_HTML = """
<style>
  body { margin: 0; background: transparent; font-family: Outfit, Arial, sans-serif; }
  .map-card {
    position: relative;
    height: 240px;
    border-radius: 14px;
    overflow: hidden;
    border: 1px solid #D1D5DB;
    background: linear-gradient(180deg, #F9FAFB 0%, #EEF6F3 100%);
  }
  .map-grid {
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(rgba(203, 213, 225, 0.7) 1px, transparent 1px),
      linear-gradient(90deg, rgba(203, 213, 225, 0.7) 1px, transparent 1px);
    background-size: 40px 40px;
  }
  .map-road {
    position: absolute;
    background: rgba(255, 255, 255, 0.82);
    border: 1px solid rgba(203, 213, 225, 0.95);
  }
  .road-h { left: 18px; right: 18px; top: 108px; height: 24px; }
  .road-v { top: 18px; bottom: 18px; left: 156px; width: 22px; }
  .road-d { width: 180px; height: 20px; right: 36px; top: 52px; transform: rotate(25deg); transform-origin: center; }
  .map-label {
    position: absolute;
    font-size: 11px;
    font-weight: 700;
    color: #475569;
    background: rgba(255, 255, 255, 0.8);
    padding: 2px 6px;
    border-radius: 999px;
  }
  .map-marker {
    position: absolute;
    width: 14px;
    height: 14px;
    border-radius: 999px;
    border: 3px solid #ffffff;
    box-shadow: 0 4px 10px rgba(15, 23, 42, 0.18);
  }
  .map-marker span {
    position: absolute;
    top: -28px;
    left: 12px;
    white-space: nowrap;
    font-size: 10px;
    font-weight: 700;
    color: #111827;
    background: rgba(255, 255, 255, 0.92);
    padding: 3px 7px;
    border-radius: 999px;
  }
  .map-marker-blue { background: #3B82F6; box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.18); }
  .map-marker-red { background: #DC2626; }
  .map-marker-amber { background: #D97706; }
  .map-marker-green { background: #059669; }
</style>
<div class="map-card">
  <div class="map-grid"></div>
  <div class="map-road road-h"></div>
  <div class="map-road road-v"></div>
  <div class="map-road road-d"></div>

  <span class="map-label" style="top:18px; left:28px;">DHA</span>
  <span class="map-label" style="top:76px; left:162px;">Gulberg</span>
  <span class="map-label" style="top:150px; left:44px;">Faisal Town</span>
  <span class="map-label" style="top:46px; left:276px;">Johar Town</span>
  <span class="map-label" style="top:188px; left:230px;">Model Town</span>

  <div class="map-marker map-marker-blue" style="top:104px; left:126px;"><span>User</span></div>
  <div class="map-marker map-marker-red" style="top:42px; left:66px;"><span>Open manhole</span></div>
  <div class="map-marker map-marker-amber" style="top:126px; left:222px;"><span>Sewage spill</span></div>
  <div class="map-marker map-marker-green" style="top:182px; left:84px;"><span>Resolved light</span></div>
</div>
"""


st.set_page_config(page_title="CrisisLens AI", page_icon="◉", layout="wide")


def init_session_state():
    defaults = {
        "report": None,
        "error": None,
        "running": False,
        "copy_message": None,
        "copy_payload": None,
        "submit_message": None,
        "submitted_report_id": None,
        "report_input_signature": None,
        "report_is_stale": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def load_css():
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Outfit', sans-serif;
            color: #111827;
        }

        div[data-testid="stAppViewContainer"] {
            background: #F8FAF9;
        }

        [data-testid="stHeader"], footer, #MainMenu {
            visibility: hidden;
            height: 0%;
            display: none !important;
        }

        .reportview-container .main .block-container {
            padding-top: 1rem;
        }

        .card {
            background: #ffffff;
            border: 1px solid #E5E7EB;
            border-radius: 18px;
            padding: 24px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04);
            margin-bottom: 20px;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            background: #ffffff !important;
            border: 1px solid #E5E7EB !important;
            border-radius: 18px !important;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04) !important;
            margin-bottom: 20px !important;
            padding: 0 !important;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] > div {
            padding: 20px !important;
        }

        .stMarkdown, .stMarkdown p, .stMarkdown li, .stCaption, label,
        [data-testid="stWidgetLabel"], .st-emotion-cache-16idsys p {
            color: #111827 !important;
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="base-input"] > div,
        textarea,
        input,
        div[data-baseweb="select"] > div,
        div[data-testid="stFileUploaderDropzone"] {
            background: #ffffff !important;
            color: #111827 !important;
            border: 1px solid #D1D5DB !important;
        }

        textarea::placeholder,
        input::placeholder {
            color: #9CA3AF !important;
        }

        div[data-baseweb="select"] *,
        div[data-baseweb="input"] *,
        div[data-baseweb="base-input"] * {
            color: #111827 !important;
        }

        div[data-testid="stFileUploader"] section,
        div[data-testid="stFileUploader"] section div,
        div[data-testid="stFileUploader"] button,
        div[data-testid="stFileUploaderDropzone"] small,
        div[data-testid="stFileUploaderDropzone"] span,
        div[data-testid="stFileUploaderDropzone"] p {
            color: #374151 !important;
            background: transparent !important;
        }

        [data-testid="stExpander"] {
            border: 1px solid #E5E7EB !important;
            border-radius: 12px !important;
            background: #FAFAFA !important;
        }

        .metric-card {
            background: #FAFAFA;
            border: 1px solid #E5E7EB;
            border-radius: 12px;
            padding: 16px;
            text-align: center;
        }

        .chip {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .chip-high { background: #FEE2E2; color: #DC2626; }
        .chip-medium { background: #FEF3C7; color: #D97706; }
        .chip-low { background: #E0F2FE; color: #0369A1; }
        .chip-success { background: #DCFCE7; color: #166534; }
        .chip-neutral { background: #F3F4F6; color: #4B5563; }

        div.stButton > button,
        div[data-testid="stDownloadButton"] > button {
            background: #007A5A !important;
            color: #ffffff !important;
            border-radius: 12px !important;
            padding: 0.75rem 1.25rem !important;
            font-weight: 650 !important;
            border: none !important;
            transition: background-color 0.2s ease, box-shadow 0.2s ease !important;
            width: 100% !important;
        }

        div.stButton > button:hover,
        div[data-testid="stDownloadButton"] > button:hover {
            background: #006B4F !important;
            box-shadow: 0 4px 12px rgba(0, 122, 90, 0.25) !important;
        }

        div.stButton > button:disabled,
        div[data-testid="stDownloadButton"] > button:disabled {
            background: #B7D9CF !important;
            color: #F8FAF9 !important;
            box-shadow: none !important;
            cursor: not-allowed !important;
        }

        .whatsapp-btn {
            background: #25D366;
            color: #ffffff;
            font-weight: 600;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            text-decoration: none;
            display: inline-block;
            text-align: center;
            transition: all 0.2s ease;
            width: 100%;
            box-sizing: border-box;
        }

        .whatsapp-btn:hover {
            background: #20BA5A;
            box-shadow: 0 4px 10px rgba(37, 211, 102, 0.3);
            color: #ffffff !important;
        }

        .map-card {
            position: relative;
            height: 240px;
            border-radius: 14px;
            overflow: hidden;
            border: 1px solid #D1D5DB;
            background: linear-gradient(180deg, #F9FAFB 0%, #EEF6F3 100%);
        }

        .map-grid {
            position: absolute;
            inset: 0;
            background-image:
                linear-gradient(rgba(203, 213, 225, 0.7) 1px, transparent 1px),
                linear-gradient(90deg, rgba(203, 213, 225, 0.7) 1px, transparent 1px);
            background-size: 40px 40px;
        }

        .map-road {
            position: absolute;
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid rgba(203, 213, 225, 0.95);
        }

        .road-h {
            left: 18px;
            right: 18px;
            top: 108px;
            height: 24px;
        }

        .road-v {
            top: 18px;
            bottom: 18px;
            left: 156px;
            width: 22px;
        }

        .road-d {
            width: 180px;
            height: 20px;
            right: 36px;
            top: 52px;
            transform: rotate(25deg);
            transform-origin: center;
        }

        .map-label {
            position: absolute;
            font-size: 11px;
            font-weight: 700;
            color: #475569;
            background: rgba(255, 255, 255, 0.8);
            padding: 2px 6px;
            border-radius: 999px;
        }

        .map-marker {
            position: absolute;
            width: 14px;
            height: 14px;
            border-radius: 999px;
            border: 3px solid #ffffff;
            box-shadow: 0 4px 10px rgba(15, 23, 42, 0.18);
        }

        .map-marker span {
            position: absolute;
            top: -28px;
            left: 12px;
            white-space: nowrap;
            font-size: 10px;
            font-weight: 700;
            color: #111827;
            background: rgba(255, 255, 255, 0.92);
            padding: 3px 7px;
            border-radius: 999px;
        }

        .map-marker-blue { background: #3B82F6; box-shadow: 0 0 0 6px rgba(59, 130, 246, 0.18); }
        .map-marker-red { background: #DC2626; }
        .map-marker-amber { background: #D97706; }
        .map-marker-green { background: #059669; }

        .timeline {
            display: flex;
            justify-content: space-between;
            position: relative;
            margin: 20px 0;
        }

        .timeline::before {
            content: '';
            position: absolute;
            top: 15px;
            left: 5%;
            right: 5%;
            height: 4px;
            background-color: #E5E7EB;
            z-index: 1;
        }

        .timeline-step {
            display: flex;
            flex-direction: column;
            align-items: center;
            position: relative;
            z-index: 2;
            width: 20%;
        }

        .step-circle {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            background-color: #E5E7EB;
            color: #9CA3AF;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            border: 3px solid #ffffff;
        }

        .step-circle.active { background-color: #007A5A; color: #ffffff; }
        .step-circle.complete { background-color: #10B981; color: #ffffff; }

        .step-text {
            font-size: 12px;
            font-weight: 600;
            margin-top: 8px;
            color: #6B7280;
            text-align: center;
        }

        .step-text.active { color: #111827; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def save_submission(report):
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    payload = {
        "id": datetime.utcnow().strftime("report-%Y%m%d-%H%M%S"),
        "submitted_at_utc": datetime.utcnow().isoformat() + "Z",
        "report": report,
    }

    existing = []
    if os.path.exists(SUBMISSIONS_PATH):
        try:
            with open(SUBMISSIONS_PATH, "r", encoding="utf-8") as file:
                existing = json.load(file)
        except Exception:
            existing = []

    existing.append(payload)

    with open(SUBMISSIONS_PATH, "w", encoding="utf-8") as file:
        json.dump(existing, file, indent=2, ensure_ascii=False)

    return payload["id"]


def safe_remove_temp_file(path):
    if not path or not os.path.exists(path):
        return
    try:
        os.unlink(path)
    except PermissionError:
        pass
    except OSError:
        pass


def trigger_copy_to_clipboard(text):
    payload = json.dumps(text)
    components.html(
        f"""
        <script>
        navigator.clipboard.writeText({payload});
        </script>
        """,
        height=0,
    )


def build_input_signature(
    uploaded_image,
    test_image_path,
    location,
    description,
    category,
    language,
):
    uploaded_marker = None
    if uploaded_image is not None:
        uploaded_marker = f"{uploaded_image.name}:{uploaded_image.size}"
    return json.dumps(
        {
            "uploaded_image": uploaded_marker,
            "test_image_path": (test_image_path or "").strip(),
            "location": (location or "").strip(),
            "description": (description or "").strip(),
            "category": category,
            "language": language,
        },
        sort_keys=True,
    )


def render_header():
    st.markdown(
        """
        <div style="display:flex; justify-content:space-between; align-items:center; padding:12px 0; border-bottom:1px solid #E5E7EB; margin-bottom:20px;">
            <div>
                <span style="font-size:22px; font-weight:700; color:#111827;"><span style="color:#007A5A; margin-right:6px;">◉</span>CrisisLens AI</span>
                <span style="color:#6B7280; font-size:13px; margin-left:12px; border-left:1px solid #E5E7EB; padding-left:12px;">Pakistan civic action agent</span>
            </div>
            <div style="display:flex; align-items:center; gap:16px;">
                <span style="font-size:13px; font-weight:600; color:#111827;">EN | اردو</span>
                <span style="background-color:#F3F4F6; color:#374151; font-size:11px; font-weight:600; padding:4px 10px; border-radius:9999px; border:1px solid #E5E7EB;">Powered by Gemini</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero():
    st.markdown(
        """
        <div class="card">
            <h1 style="color:#111827; font-size:32px; font-weight:700; margin-bottom:8px;">See it. Report it. Fix it.</h1>
            <p style="color:#6B7280; font-size:15px; margin-bottom:20px;">Upload a photo, voice note, and location. Our AI agents turn civic hazards into authority-ready reports.</p>
            <div style="display:flex; gap:10px; flex-wrap:wrap;">
                <span style="background-color:#ECFDF5; color:#047857; padding:6px 14px; border-radius:9999px; font-size:13px; font-weight:600;">✦ Image understanding</span>
                <span style="background-color:#ECFDF5; color:#047857; padding:6px 14px; border-radius:9999px; font-size:13px; font-weight:600;">✦ Risk scoring</span>
                <span style="background-color:#ECFDF5; color:#047857; padding:6px 14px; border-radius:9999px; font-size:13px; font-weight:600;">✦ Authority routing</span>
                <span style="background-color:#ECFDF5; color:#047857; padding:6px 14px; border-radius:9999px; font-size:13px; font-weight:600;">✦ Official complaint generation</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_report_form():
    st.markdown("### New Hazard Report")

    if st.button("Run Demo Case", key="run_demo_case", use_container_width=True):
        with st.spinner("Running demo analysis..."):
            try:
                report = run_pipeline(
                    image_path=DEMO_IMAGE_PATH,
                    location=DEMO_LOCATION,
                    description=DEMO_DESCRIPTION,
                    audio_path=None,
                )
                st.session_state.report = report
                st.session_state.error = None
                st.session_state.copy_message = None
                st.session_state.copy_payload = None
                st.session_state.submit_message = None
                st.session_state.submitted_report_id = None
            except Exception as exc:
                st.session_state.error = str(exc)
        st.rerun()

    st.caption("For quick verification, run the built-in demo case or use the form below.")

    uploaded_image = st.file_uploader(
        "Upload hazard photo",
        type=["jpg", "jpeg", "png"],
        help="Take or choose a photo of the incident scene",
    )

    if uploaded_image is not None:
        st.image(uploaded_image, use_container_width=True, caption="Scene Preview")

    test_image_path = st.text_input(
        "Or enter local image path (for testing/automation)",
        placeholder="e.g. demo_assets/test_scene.jpg",
        help="Type local path for automated execution",
    )

    location = st.text_input("Location", placeholder="15th Lane, Phase 2, DHA Lahore")

    description = st.text_area(
        "Voice note or description",
        placeholder="Example: Yahan road pe khula manhole hai...",
    )

    with st.expander("Add optional voice recording (Urdu / English)"):
        uploaded_audio = st.file_uploader("Upload audio clip", type=["mp3", "wav", "m4a", "ogg"])

    category = st.selectbox(
        "Issue category",
        [
            "Open Manhole",
            "Sewage Overflow",
            "Broken Streetlight",
            "Flooding",
            "Unsafe Electric Wire",
            "Fire",
            "Road Accident",
            "Other",
        ],
    )

    language = st.selectbox("Language", ["English", "Urdu", "Roman Urdu"])

    current_signature = build_input_signature(
        uploaded_image,
        test_image_path,
        location,
        description,
        category,
        language,
    )

    if (
        st.session_state.report is not None
        and st.session_state.report_input_signature
        and st.session_state.report_input_signature != current_signature
    ):
        st.session_state.report_is_stale = True
        st.info("Inputs changed since the last analysis. Run Analyze with AI again to refresh the report.")
    else:
        st.session_state.report_is_stale = False

    button_disabled = (uploaded_image is None and test_image_path.strip() == "") or location.strip() == ""

    if button_disabled:
        st.caption("Upload a photo or enter a test path and enter a location to continue")

    if st.button("Analyze with AI", disabled=button_disabled):
        image_path = None
        if uploaded_image is not None:
            image_bytes = uploaded_image.getvalue()
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp_img:
                tmp_img.write(image_bytes)
                tmp_img.flush()
                image_path = tmp_img.name
        else:
            image_path = test_image_path.strip()

        audio_path = None
        if uploaded_audio is not None:
            suffix = "." + uploaded_audio.name.split(".")[-1]
            audio_bytes = uploaded_audio.getvalue()
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_audio:
                tmp_audio.write(audio_bytes)
                tmp_audio.flush()
                audio_path = tmp_audio.name

        pipeline_description = description.strip()
        if category and category != "Other":
            prefix = f"Issue category: {category}."
            pipeline_description = f"{prefix} {pipeline_description}".strip()
        if language:
            pipeline_description = f"{pipeline_description} Preferred language: {language}.".strip()

        with st.spinner("Analyzing hazard with AI agents..."):
            try:
                report = run_pipeline(
                    image_path=image_path,
                    location=location,
                    description=pipeline_description,
                    audio_path=audio_path,
                )
                st.session_state.report = report
                st.session_state.error = None
                st.session_state.copy_message = None
                st.session_state.copy_payload = None
                st.session_state.submit_message = None
                st.session_state.submitted_report_id = None
                st.session_state.report_input_signature = build_input_signature(
                    uploaded_image,
                    test_image_path,
                    location,
                    description,
                    category,
                    language,
                )
                st.session_state.report_is_stale = False
            except Exception as exc:
                st.session_state.error = str(exc)
            finally:
                safe_remove_temp_file(image_path)
                safe_remove_temp_file(audio_path)

        st.rerun()

    st.markdown(
        "<p style='color:#6B7280; font-size:13px; margin-top:12px;'>Tip: Clear photos and precise locations improve routing accuracy.</p>",
        unsafe_allow_html=True,
    )


def render_nearby_reports():
    st.markdown("### Nearby Reports")
    components.html(NEARBY_REPORTS_MAP_HTML, height=245)

    st.markdown(
        """
        <div style="background-color:#FAFAFA; border:1px solid #E5E7EB; border-radius:12px; padding:16px; margin-top:16px;">
            <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:6px;">
                <span style="font-weight:700; font-size:15px; color:#111827;">Open Manhole</span>
                <span class="chip chip-high" style="font-size:10px; padding:2px 8px;">High Risk</span>
            </div>
            <p style="color:#4B5563; font-size:13px; margin-bottom:8px; font-weight:550;">📍 15th Lane, Phase 2, DHA Lahore</p>
            <p style="color:#6B7280; font-size:12px; margin-bottom:12px;">Reported by 12 citizens nearby</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption("Nearby reports are illustrative examples and do not overwrite your current draft.")


def render_agent_pipeline():
    st.markdown("### Multi-Agent Analysis Pipeline")

    col1, col2, col3, col4, col5 = st.columns(5)
    is_complete = st.session_state.report is not None
    status_text = "Complete" if is_complete else "Ready"
    status_class = "chip-success" if is_complete else "chip-neutral"

    cards = [
        ("👁️", "Vision Agent", "Detects hazard from image"),
        ("🗣️", "Language Agent", "Understands voice and Urdu inputs"),
        ("⚡", "Risk Agent", "Scores urgency and danger group"),
        ("🗺️", "Routing Agent", "Matches issue to relevant authority"),
        ("📝", "Report Agent", "Generates official complaint text"),
    ]

    for column, (icon, title, body) in zip([col1, col2, col3, col4, col5], cards):
        with column:
            st.markdown(
                f"""
                <div style="background-color:#FAFAFA; border:1px solid #E5E7EB; border-radius:12px; padding:14px; height:160px;">
                    <div style="font-size:20px; margin-bottom:8px;">{icon}</div>
                    <div style="font-weight:700; font-size:14px; margin-bottom:4px;">{title}</div>
                    <div style="color:#6B7280; font-size:11px; margin-bottom:12px; height:36px;">{body}</div>
                    <span class="chip {status_class}" style="font-size:9px; padding:2px 6px;">{status_text}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_analysis_results(report):
    st.markdown("### AI Analysis Result")

    full = report.get("full_report", {})
    dispatch = report.get("dispatch", {})
    risk = full.get("risk_level", "High")
    suggested_authority = dispatch.get("authority_name") or full.get("authority_to_contact", "WASA Lahore")
    verified_label = "Google verified" if dispatch.get("google_search_succeeded") else "Resolver fallback"
    verified_class = "chip-success" if dispatch.get("google_search_succeeded") else "chip-neutral"
    chip_class = "chip-high" if risk in ["High", "Critical"] else ("chip-medium" if risk == "Medium" else "chip-low")
    affected = full.get("who_is_at_risk", ["pedestrians", "drivers"])
    if not isinstance(affected, list):
        affected = [str(affected)]

    advice_steps = full.get("immediate_steps", [])
    if not isinstance(advice_steps, list) or not advice_steps:
        advice_steps = [
            "Avoid the area if possible",
            "Keep children away",
            "Use an alternative route",
            "Do not attempt repair yourself unless safe",
        ]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f"""
            <div style="display:flex; flex-direction:column; gap:12px; padding:8px 0;">
                <div>
                    <span style="color:#6B7280; font-size:13px;">Hazard Detected</span><br>
                    <span style="font-weight:700; font-size:17px;">{full.get('incident_type', 'Open Manhole')}</span>
                </div>
                <div>
                    <span style="color:#6B7280; font-size:13px;">Risk Level</span><br>
                    <span class="chip {chip_class}" style="margin-top:4px;">{risk}</span>
                </div>
                <div>
                    <span style="color:#6B7280; font-size:13px;">Suggested Authority</span><br>
                    <span style="font-weight:700; font-size:17px; color:#007A5A;">{suggested_authority}</span><br>
                    <span class="chip {verified_class}" style="margin-top:8px; font-size:10px; padding:3px 8px;">{verified_label}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div style="display:flex; flex-direction:column; gap:12px; padding:8px 0;">
                <div>
                    <span style="color:#6B7280; font-size:13px;">Confidence</span><br>
                    <span style="font-weight:700; font-size:17px;">{full.get('confidence', 95)}%</span>
                </div>
                <div>
                    <span style="color:#6B7280; font-size:13px;">Estimated Resolution</span><br>
                    <span style="font-weight:700; font-size:17px;">24-48 hours</span>
                </div>
                <div>
                    <span style="color:#6B7280; font-size:13px;">Affected People</span><br>
                    <span style="font-weight:700; font-size:17px;">{", ".join(affected)}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    items = "".join(f"<li>{step}</li>" for step in advice_steps[:4])
    st.markdown(
        f"""
        <div style="background-color:#FFFBEB; border:1px solid #FDE68A; border-radius:12px; padding:16px; margin-top:16px;">
            <span style="font-weight:700; font-size:14px; color:#B45309; display:block; margin-bottom:8px;">⚠️ Public Safety Guidance</span>
            <ul style="margin:0; padding-left:20px; font-size:13px; color:#78350F; display:flex; flex-direction:column; gap:4px;">
                {items}
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_official_report(report):
    st.markdown("### Generated Official Complaint")

    full = report.get("full_report", {})
    dispatch = report.get("dispatch", {})
    complaint_text = report.get(
        "report_summary",
        "This is to bring to your attention that a public hazard has been identified at the above location. The hazard poses a serious risk to pedestrians, cyclists, and motorists. Immediate inspection, barricading, and repair are requested to ensure public safety.",
    )
    suggested_authority = dispatch.get("authority_name") or full.get("authority_to_contact", "Lahore Municipal Authority / WASA")
    source_note = dispatch.get("source_found", "Dispatch agent has not attached a source note.")

    st.markdown(
        f"""
        <div style="background-color:#FAFAFA; border:1px solid #E5E7EB; border-radius:12px; padding:20px; font-size:14px;">
            <div style="margin-bottom:12px;">
                <span style="color:#6B7280; font-size:12px; font-weight:600; text-transform:uppercase;">Subject</span><br>
                <span style="font-weight:700; font-size:16px;">Urgent Public Safety Hazard: {full.get('incident_type', 'Open Manhole')}</span>
            </div>
            <div style="margin-bottom:12px;">
                <span style="color:#6B7280; font-size:12px; font-weight:600; text-transform:uppercase;">Location</span><br>
                <span style="font-weight:600;">{full.get('location', '15th Lane, Phase 2, DHA Lahore')}</span>
            </div>
            <div style="margin-bottom:12px;">
                <span style="color:#6B7280; font-size:12px; font-weight:600; text-transform:uppercase;">Complaint Text</span><br>
                <p style="margin-top:4px; line-height:1.5; color:#374151;">{complaint_text}</p>
            </div>
            <div style="margin-bottom:12px;">
                <span style="color:#6B7280; font-size:12px; font-weight:600; text-transform:uppercase;">Evidence</span><br>
                <span style="font-weight:600;">1 photo, user description, GPS location</span>
            </div>
            <div>
                <span style="color:#6B7280; font-size:12px; font-weight:600; text-transform:uppercase;">Suggested Authority</span><br>
                <span style="font-weight:700; color:#007A5A;">{suggested_authority}</span>
            </div>
            <div style="margin-top:12px;">
                <span style="color:#6B7280; font-size:12px; font-weight:600; text-transform:uppercase;">Dispatch Source</span><br>
                <span style="color:#374151;">{source_note}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)
    bcol1, bcol2, bcol3, bcol4 = st.columns(4)

    with bcol1:
        if st.button("Submit Report", key="submit_official"):
            report_id = save_submission(report)
            st.session_state.submitted_report_id = report_id
            st.session_state.submit_message = "Submitted to Authority!"

    with bcol2:
        if st.button("Copy Complaint", key="copy_official"):
            st.session_state.copy_payload = complaint_text
            st.session_state.copy_message = "Copied to Clipboard!"

    with bcol3:
        st.download_button(
            "Download Report",
            data=complaint_text,
            file_name="crisislens_report.txt",
            mime="text/plain",
            key="download_report",
        )

    with bcol4:
        whatsapp_text = (
            f"🚨 EMERGENCY ALERT: {full.get('incident_type')} at {full.get('location')}. "
            f"Risk: {full.get('risk_level')}. Action: {suggested_authority}"
        )
        whatsapp_url = "https://wa.me/?text=" + urllib.parse.quote(whatsapp_text)
        st.markdown(
            f'<a href="{whatsapp_url}" target="_blank" class="whatsapp-btn">Share Alert</a>',
            unsafe_allow_html=True,
        )

    if st.session_state.submit_message:
        st.success(st.session_state.submit_message)
        if st.session_state.submitted_report_id:
            st.caption(f"Local submission record: {st.session_state.submitted_report_id}")

    if st.session_state.copy_payload:
        trigger_copy_to_clipboard(st.session_state.copy_payload)
        st.success(st.session_state.copy_message or "Copied to Clipboard!")
        st.session_state.copy_payload = None


def render_tracking_dashboard():
    st.markdown("### Report Tracking")
    st.markdown(
        """
        <div class="timeline">
            <div class="timeline-step">
                <div class="step-circle complete">✓</div>
                <div class="step-text">Submitted</div>
            </div>
            <div class="timeline-step">
                <div class="step-circle complete">✓</div>
                <div class="step-text">Routed</div>
            </div>
            <div class="timeline-step">
                <div class="step-circle active">•</div>
                <div class="step-text active">Under Review</div>
            </div>
            <div class="timeline-step">
                <div class="step-circle">4</div>
                <div class="step-text">Resolved</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    mcol1, mcol2, mcol3 = st.columns(3)
    metrics = [
        ("58", "Active Reports", "#111827"),
        ("34", "Resolved Today", "#166534"),
        ("2.4 hrs", "Avg Response", "#007A5A"),
    ]
    for col, (value, label, color) in zip([mcol1, mcol2, mcol3], metrics):
        with col:
            st.markdown(
                f"""
                <div class="metric-card">
                    <span style="font-size:26px; font-weight:700; color:{color};">{value}</span><br>
                    <span style="font-size:12px; font-weight:600; color:#6B7280; text-transform:uppercase;">{label}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_dispatch_status(report):
    dispatch = report.get("dispatch")
    if not dispatch:
        return

    st.markdown("### Dispatch Status")
    authority = dispatch.get("authority_name", "Not resolved")
    channel = dispatch.get("dispatch_channel", "unknown")
    confidence = dispatch.get("search_confidence", 0)
    phone = dispatch.get("authority_phone", "Not found")
    email = dispatch.get("authority_email") or "Not found"
    city = dispatch.get("resolved_city", "unknown").title()
    hazard_class = dispatch.get("resolved_hazard_class", "unknown")
    source_found = dispatch.get("source_found", "No source note")
    verified_label = "Google search verified" if dispatch.get("google_search_succeeded") else "Google search fallback"

    st.markdown(
        f"""
        <div style="background-color:#F8FAFC; border:1px solid #E5E7EB; border-radius:12px; padding:20px;">
            <div style="display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap:14px;">
                <div><span style="color:#6B7280; font-size:12px; font-weight:600; text-transform:uppercase;">Authority</span><br><span style="font-weight:700; font-size:16px;">{authority}</span></div>
                <div><span style="color:#6B7280; font-size:12px; font-weight:600; text-transform:uppercase;">Channel</span><br><span style="font-weight:700; font-size:16px;">{channel}</span></div>
                <div><span style="color:#6B7280; font-size:12px; font-weight:600; text-transform:uppercase;">Resolved Jurisdiction</span><br><span style="font-weight:700; font-size:16px;">{city} / {hazard_class}</span></div>
                <div><span style="color:#6B7280; font-size:12px; font-weight:600; text-transform:uppercase;">Confidence</span><br><span style="font-weight:700; font-size:16px;">{confidence}%</span></div>
                <div><span style="color:#6B7280; font-size:12px; font-weight:600; text-transform:uppercase;">Phone</span><br><span style="font-weight:700; font-size:16px;">{phone}</span></div>
                <div><span style="color:#6B7280; font-size:12px; font-weight:600; text-transform:uppercase;">Email</span><br><span style="font-weight:700; font-size:16px;">{email}</span></div>
            </div>
            <div style="margin-top:14px;">
                <span class="chip {'chip-success' if dispatch.get('google_search_succeeded') else 'chip-neutral'}" style="font-size:10px; padding:3px 8px;">{verified_label}</span>
            </div>
            <div style="margin-top:14px;">
                <span style="color:#6B7280; font-size:12px; font-weight:600; text-transform:uppercase;">Source Note</span><br>
                <span style="color:#374151; font-size:14px;">{source_found}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    whatsapp_link = dispatch.get("whatsapp_link")
    if whatsapp_link:
        st.markdown(
            f'<a href="{whatsapp_link}" target="_blank" class="whatsapp-btn" style="margin-top:12px;">Open Verified WhatsApp Draft</a>',
            unsafe_allow_html=True,
        )


def render_recent_reports():
    st.markdown("### Recent Reports")
    st.markdown(
        """
        <div style="background-color:white; border:1px solid #E5E7EB; border-radius:12px; padding:12px; overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse; font-size:13px;">
                <thead>
                    <tr style="border-bottom:2px solid #F3F4F6; text-align:left;">
                        <th style="padding:10px; color:#4B5563; font-weight:600;">Hazard</th>
                        <th style="padding:10px; color:#4B5563; font-weight:600;">Location</th>
                        <th style="padding:10px; color:#4B5563; font-weight:600;">Risk</th>
                        <th style="padding:10px; color:#4B5563; font-weight:600;">Status</th>
                        <th style="padding:10px; color:#4B5563; font-weight:600;">Time</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom:1px solid #F3F4F6;">
                        <td style="padding:10px; font-weight:600;">Open Manhole</td>
                        <td style="padding:10px; color:#4B5563;">DHA Lahore</td>
                        <td style="padding:10px;"><span class="chip chip-high" style="font-size:10px; padding:2px 8px;">High</span></td>
                        <td style="padding:10px;"><span class="chip chip-neutral" style="font-size:10px; padding:2px 8px;">Under Review</span></td>
                        <td style="padding:10px; color:#6B7280;">10 min ago</td>
                    </tr>
                    <tr style="border-bottom:1px solid #F3F4F6;">
                        <td style="padding:10px; font-weight:600;">Sewage Overflow</td>
                        <td style="padding:10px; color:#4B5563;">Johar Town</td>
                        <td style="padding:10px;"><span class="chip chip-medium" style="font-size:10px; padding:2px 8px;">Medium</span></td>
                        <td style="padding:10px;"><span class="chip chip-medium" style="font-size:10px; padding:2px 8px;">Escalated</span></td>
                        <td style="padding:10px; color:#6B7280;">1 hr ago</td>
                    </tr>
                    <tr style="border-bottom:1px solid #F3F4F6;">
                        <td style="padding:10px; font-weight:600;">Broken Streetlight</td>
                        <td style="padding:10px; color:#4B5563;">Gulberg</td>
                        <td style="padding:10px;"><span class="chip chip-low" style="font-size:10px; padding:2px 8px;">Low</span></td>
                        <td style="padding:10px;"><span class="chip chip-success" style="font-size:10px; padding:2px 8px;">Submitted</span></td>
                        <td style="padding:10px; color:#6B7280;">25 min ago</td>
                    </tr>
                    <tr style="border-bottom:1px solid #F3F4F6;">
                        <td style="padding:10px; font-weight:600;">Unsafe Electric Wire</td>
                        <td style="padding:10px; color:#4B5563;">Faisal Town</td>
                        <td style="padding:10px;"><span class="chip chip-high" style="font-size:10px; padding:2px 8px;">High</span></td>
                        <td style="padding:10px;"><span class="chip chip-success" style="font-size:10px; padding:2px 8px;">Routed</span></td>
                        <td style="padding:10px; color:#6B7280;">40 min ago</td>
                    </tr>
                </tbody>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


init_session_state()
load_css()
render_header()
render_hero()

col_form, col_map = st.columns([1.05, 0.95])

with col_form:
    with st.container(border=True):
        render_report_form()

with col_map:
    with st.container(border=True):
        render_nearby_reports()

with st.container(border=True):
    render_agent_pipeline()

show_report = st.session_state.report is not None and not st.session_state.report_is_stale
if show_report:
    st.markdown(
        "<h2 style='font-size:26px; font-weight:700; margin-top:30px; margin-bottom:16px;'>🚨 Analysis Results & Routing Dashboard</h2>",
        unsafe_allow_html=True,
    )

    col_results, col_official = st.columns(2)
    with col_results:
        with st.container(border=True):
            render_analysis_results(st.session_state.report)

    with col_official:
        with st.container(border=True):
            render_official_report(st.session_state.report)

    with st.container(border=True):
        render_tracking_dashboard()

    with st.container(border=True):
        render_dispatch_status(st.session_state.report)

    routing_result = st.session_state.report.get("dispatch", {}).get("routing_result")
    if routing_result:
        st.expander("Authority Discovery Debug").json(routing_result)

    if st.button("Start Over - Report a New Incident", key="reset_app_state", use_container_width=True):
        for key in [
            "report",
            "error",
            "running",
            "copy_message",
            "copy_payload",
            "submit_message",
            "submitted_report_id",
            "report_input_signature",
            "report_is_stale",
        ]:
            st.session_state[key] = None if key not in {"running"} else False
        st.rerun()

if st.session_state.error:
    st.error(f"Something went wrong: {st.session_state.error}")
    if st.button("Try Again", key="clear_error"):
        st.session_state.error = None
        st.rerun()

with st.container(border=True):
    render_recent_reports()
