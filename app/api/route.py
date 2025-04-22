import os
import sys
import json
import logging
import torch
import gc
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
from typing import Optional, Dict, Any
import tempfile
import shutil
import traceback
from pydub import AudioSegment
from contextlib import asynccontextmanager
import requests
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Global variable for the model
clap_model = None

# Model configuration
MODEL_URL = "https://github.com/MadeByKit/sound-classifier-next/releases/download/v1.0.0/clapcap_weights_2023.pth"
MODEL_PATH = Path("clapcap_weights_2023.pth")

def download_model():
    if not MODEL_PATH.exists():
        logger.info("Downloading model from GitHub releases...")
        try:
            response = requests.get(MODEL_URL, stream=True)
            response.raise_for_status()
            
            # Save the model file
            with open(MODEL_PATH, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logger.info("Model downloaded successfully")
        except Exception as e:
            logger.error(f"Failed to download model: {str(e)}")
            raise RuntimeError(f"Failed to download model: {str(e)}")

def load_model():
    global clap_model
    try:
        logger.info("Starting up the application...")
        
        # Clear any existing model and free memory
        if clap_model is not None:
            del clap_model
            gc.collect()
            torch.cuda.empty_cache()
        
        # Download model if it doesn't exist
        download_model()
        
        # Check if CUDA is available
        use_cuda = torch.cuda.is_available()
        logger.info(f"CUDA available: {use_cuda}")
        
        # Set memory allocation strategy
        if not use_cuda:
            torch.set_num_threads(1)  # Limit CPU threads
            os.environ['OMP_NUM_THREADS'] = '1'
            os.environ['MKL_NUM_THREADS'] = '1'
        
        # Initialize CLAP model
        logger.info("Loading CLAP model...")
        from msclap import CLAP
        clap_model = CLAP(
            version='clapcap',
            use_cuda=use_cuda,
            model_fp=str(MODEL_PATH)
        )
        logger.info("CLAP model loaded successfully")
        return True
    except Exception as e:
        logger.error(f"Error loading model: {str(e)}")
        logger.error(traceback.format_exc())
        return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the model on startup
    if not load_model():
        logger.error("Failed to load model during startup")
        raise Exception("Failed to load model")
    yield
    # Clean up on shutdown
    global clap_model
    if clap_model is not None:
        del clap_model
        gc.collect()
        torch.cuda.empty_cache()

app = FastAPI(
    title="Audio Captioning API",
    description="API for generating captions from audio files",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Audio Captioning API is running", "status": "healthy"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "model_loaded": clap_model is not None,
        "cuda_available": torch.cuda.is_available(),
        "version": "1.0.0"
    }

@app.post("/process-audio")
async def process_audio(
    audio_file: UploadFile = File(...),
    industry: Optional[str] = Form(None)
):
    if not clap_model:
        raise HTTPException(
            status_code=503,
            detail="Model not initialized. Please try again later."
        )
    
    temp_path = None
    wav_path = None
    
    try:
        logger.info(f"Received file: {audio_file.filename}")
        logger.info(f"Content type: {audio_file.content_type}")
        
        # Create temporary file with original extension
        file_extension = os.path.splitext(audio_file.filename)[1].lower()
        with tempfile.NamedTemporaryFile(suffix=file_extension, delete=False) as temp_file:
            temp_path = temp_file.name
            # Save uploaded file to temporary location
            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(audio_file.file, buffer)
        
        # Convert audio to WAV using pydub
        audio = AudioSegment.from_file(temp_path)
        wav_path = temp_path + ".wav"
        audio.export(wav_path, format="wav")
        
        # Clean up the original temp file
        os.unlink(temp_path)
        temp_path = None
        
        # Generate caption using CLAP model
        logger.info("Generating caption...")
        captions = clap_model.generate_caption(
            [wav_path],
            resample=True,
            beam_size=3,
            entry_length=67,
            temperature=0.01
        )
        
        if not captions or not isinstance(captions, list) or not captions[0]:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate caption. Please try again."
            )
        
        caption = str(captions[0])
        logger.info(f"Generated caption: {caption}")
        
        return {
            "caption": caption,
            "industry": industry,
            "status": "success"
        }
            
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing audio: {str(e)}"
        )
    finally:
        # Clean up any remaining temporary files
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
        if wav_path and os.path.exists(wav_path):
            os.unlink(wav_path)

if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        logger.error(traceback.format_exc())
        raise 