import uvicorn
from app.core.config import load_settings

if __name__ == "__main__":
    s = load_settings()
    uvicorn.run("app.main:app", host=s.host, port=s.port, reload=False)
