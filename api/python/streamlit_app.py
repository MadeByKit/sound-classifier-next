import streamlit as st
import torch
import os
import tempfile
import requests
from pathlib import Path
import logging
from clapcap import CLAPCap
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure page
st.set_page_config(
    page_title="Toun Audio Classifier API",
    page_icon="🎵",
    layout="wide"
)

# Initialize session state for model
if 'model' not in st.session_state:
    st.session_state.model = None

@st.cache_resource
def download_model():
    """Download the model if it doesn't exist"""
    model_path = Path('clapcap_weights_2023.pth')
    if not model_path.exists():
        try:
            with st.status("Downloading model...", expanded=True) as status:
                model_url = "https://github.com/MadeByKit/sound-classifier-next/releases/download/v1.0.0/clapcap_weights_2023.pth"
                response = requests.get(model_url, stream=True)
                response.raise_for_status()
                
                total_size = int(response.headers.get('content-length', 0))
                block_size = 1024
                progress_bar = st.progress(0)
                
                with open(model_path, 'wb') as f:
                    for i, chunk in enumerate(response.iter_content(chunk_size=block_size)):
                        if chunk:
                            f.write(chunk)
                            if total_size:
                                progress = min((i * block_size) / total_size, 1.0)
                                progress_bar.progress(progress)
                
                status.update(label="Model downloaded successfully!", state="complete")
                return True
        except Exception as e:
            st.error(f"Error downloading model: {str(e)}")
            return False
    return True

@st.cache_resource
def load_model():
    """Load the CLAP model"""
    try:
        if download_model():
            with st.status("Loading model...", expanded=True) as status:
                # Use CPU for Streamlit Cloud
                device = torch.device('cpu')
                model = CLAPCap()
                model.load_state_dict(torch.load('clapcap_weights_2023.pth', map_location=device))
                model.eval()
                status.update(label="Model loaded successfully!", state="complete")
                return model
    except Exception as e:
        st.error(f"Error loading model: {str(e)}")
        logger.error(traceback.format_exc())
    return None

def process_audio(audio_file):
    """Process audio file and return caption"""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(audio_file.read())
            temp_path = temp_file.name

        caption = st.session_state.model.predict(temp_path)
        os.unlink(temp_path)
        return caption
    except Exception as e:
        st.error(f"Error processing audio: {str(e)}")
        logger.error(traceback.format_exc())
        return None

# Main app
st.title("🎵 Toun Audio Classifier API")
st.markdown("""
This is the backend service for the Toun Audio Classifier application.
Upload an audio file to test the captioning functionality.
""")

# Load model on startup
if st.session_state.model is None:
    st.session_state.model = load_model()

# Display model status
st.subheader("Model Status")
if st.session_state.model:
    st.success("✅ Model is loaded and ready")
else:
    st.error("❌ Model failed to load")

# API Documentation
st.subheader("API Documentation")
st.code("""
Endpoint: https://your-streamlit-app-url
Method: POST
Content-Type: multipart/form-data
Body: audio file (wav, mp3, ogg)
Response: JSON with caption field
""")

# Test Interface
st.subheader("Test Interface")
uploaded_file = st.file_uploader("Upload an audio file to test", type=['wav', 'mp3', 'ogg'])

if uploaded_file is not None:
    if st.session_state.model:
        with st.spinner("Processing audio..."):
            caption = process_audio(uploaded_file)
            if caption:
                st.success("Caption generated successfully!")
                st.json({"caption": caption})
    else:
        st.error("Model not loaded. Please try again.") 