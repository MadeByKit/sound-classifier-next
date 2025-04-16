import streamlit as st
import torch
import os
import tempfile
import requests
from pathlib import Path
import logging
from msclap import CLAP
import traceback
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
                model = CLAP(
                    version='clapcap',
                    use_cuda=False,
                    model_fp='./clapcap_weights_2023.pth'
                )
                status.update(label="Model loaded successfully!", state="complete")
                return model
    except Exception as e:
        st.error(f"Error loading model: {str(e)}")
        logger.error(traceback.format_exc())
    return None

@app.post("/api/process-audio")
async def process_audio(file: UploadFile = File(...)):
    if not st.session_state.model:
        raise HTTPException(status_code=503, detail="Model not initialized")
    
    try:
        logger.info(f"Processing audio file: {file.filename}")
        
        # Create a temporary file to store the uploaded audio
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # Generate caption using CLAP model
        captions = st.session_state.model.generate_caption(
            [temp_path],
            resample=True,
            beam_size=3,
            entry_length=67,
            temperature=0.01
        )

        # Clean up the temporary file
        os.unlink(temp_path)
        logger.info("Caption generated successfully")

        if not captions or not isinstance(captions, list) or not captions[0]:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate caption. Please try again."
            )

        return {"caption": str(captions[0])}

    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error processing audio: {str(e)}"
        )

def process_audio_streamlit(audio_file):
    """Process audio file and return caption"""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_file.write(audio_file.read())
            temp_path = temp_file.name

        captions = st.session_state.model.generate_caption(
            [temp_path],
            resample=True,
            beam_size=3,
            entry_length=67,
            temperature=0.01
        )
        os.unlink(temp_path)
        return captions[0] if captions else None
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
Endpoint: https://sound-classifier-next3.vercel.app//api/process-audio
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
            caption = process_audio_streamlit(uploaded_file)
            if caption:
                st.success("Caption generated successfully!")
                st.json({"caption": caption})
    else:
        st.error("Model not loaded. Please try again.") 
