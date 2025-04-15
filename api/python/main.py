import os
import sys
import logging
import torch
import gc
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import tempfile
import traceback
from typing import Dict, Any
from pydantic import BaseModel
import requests
from pathlib import Path

def download_model():
       model_path = Path('clapcap_weights_2023.pth')
       if not model_path.exists():
           print("Downloading model...")
           model_url = os.getenv('https://github.com/MadeByKit/sound-classifier-next/releases/download/v1.0.0/clapcap_weights_2023.pth')
           response = requests.get(model_url)
           with open(model_path, 'wb') as f:
               f.write(response.content)
           print("Model downloaded successfully")

   # Call this before loading the model
   download_model()

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

def load_model():
    global clap_model
    try:
        logger.info("Starting up the application...")
        
        # Clear any existing model and free memory
        if clap_model is not None:
            del clap_model
            gc.collect()
            torch.cuda.empty_cache()
        
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
            model_fp='./clapcap_weights_2023.pth'
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
    title="Toun Audio Classifier API",
    description="API for audio classification and captioning using CLAP model",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AudioResponse(BaseModel):
    caption: str

@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "message": "Welcome to Toun Audio Classifier API",
        "endpoints": {
            "/api/health": "Check API and model status",
            "/api/process-audio": "Process audio file for classification"
        },
        "status": "operational" if clap_model is not None else "model_not_loaded"
    }

@app.get("/api/health")
async def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "model_loaded": clap_model is not None,
        "cuda_available": torch.cuda.is_available()
    }

@app.post("/api/process-audio", response_model=AudioResponse)
async def process_audio(file: UploadFile = File(...)) -> Dict[str, str]:
    if not clap_model:
        raise HTTPException(
            status_code=503,
            detail="Model not initialized. Please try again later."
        )
    
    try:
        logger.info(f"Processing audio file: {file.filename}")
        
        # Validate file type
        if not file.content_type.startswith('audio/'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Please upload an audio file."
            )
        
        # Create a temporary file to store the uploaded audio
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        logger.info("Generating caption...")
        # Generate caption using CLAP model
        captions = clap_model.generate_caption(
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Error processing audio: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        logger.error(traceback.format_exc())
        raise 
