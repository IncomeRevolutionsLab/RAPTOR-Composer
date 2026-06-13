from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# Add subdirectories to sys.path to allow imports
sys.path.append(os.path.join(os.path.dirname(__file__), "1_collection"))
sys.path.append(os.path.join(os.path.dirname(__file__), "2_analysis"))

from web_server import app as collection_app
from analyzer_server import app as analysis_app

app = FastAPI(title="YouTube Insight Engine Unified Gateway")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount sub-applications
app.mount("/analysis", analysis_app)
app.mount("/", collection_app) # Default to collection/frontend

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
