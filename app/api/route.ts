import { NextResponse } from 'next/server';

// Helper function to check if Python server is running
async function isPythonServerRunning(): Promise<boolean> {
  try {
    const response = await fetch('http://localhost:8000/health', {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    return response.ok;
  } catch (error) {
    return false;
  }
}

export async function POST(request: Request) {
  try {
    // Check if Python server is running
    const isRunning = await isPythonServerRunning();
    if (!isRunning) {
      return NextResponse.json(
        { error: 'Python server is not running. Please start the Python server.' },
        { status: 503 }
      );
    }

    const formData = await request.formData();
    const audioFile = formData.get('audio_file');
    const industry = formData.get('industry');

    // Forward the request to your Python FastAPI server
    const response = await fetch('http://localhost:8000/process-audio', {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Python API responded with status: ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error processing request:', error);
    return NextResponse.json(
      { error: 'Failed to process audio. Please ensure the Python server is running.' },
      { status: 500 }
    );
  }
}

export async function GET() {
  try {
    // Check if Python server is running
    const isRunning = await isPythonServerRunning();
    if (!isRunning) {
      return NextResponse.json(
        { error: 'Python server is not running. Please start the Python server.' },
        { status: 503 }
      );
    }

    // Forward health check to Python API
    const response = await fetch('http://localhost:8000/health');
    
    if (!response.ok) {
      throw new Error(`Python API health check failed with status: ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Health check failed:', error);
    return NextResponse.json(
      { error: 'Python server is not running. Please start the Python server.' },
      { status: 503 }
    );
  }
} 