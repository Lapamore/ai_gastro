import uvicorn
import os
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()
    port = int(os.getenv("BACKEND_PORT", 8000))
    
    uvicorn.run("src.services.app:app", host="localhost", port=port, reload=True, log_level="info")