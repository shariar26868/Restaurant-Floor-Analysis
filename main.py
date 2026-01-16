from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import connect_db, close_db
from routes import guests, video
import logging

# ---------------------------
# Logging
# ---------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------
# FastAPI app
# ---------------------------
app = FastAPI(title="Restaurant Management API")

# ---------------------------
# CORS Middleware
# ---------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Startup / Shutdown Events
# ---------------------------
@app.on_event("startup")
async def startup():
    await connect_db()
    logger.info("✅ MongoDB connected")

@app.on_event("shutdown")
async def shutdown():
    await close_db()
    logger.info("🔴 MongoDB disconnected")

# ---------------------------
# Routes
# ---------------------------
app.include_router(guests.router, prefix="/api/guests", tags=["Guests"])
app.include_router(video.router, prefix="/api/video", tags=["Video Analysis"])

# ---------------------------
# Health / Root Endpoint
# ---------------------------
@app.get("/", tags=["Root"])
def root():
    return {"message": "Restaurant Management API", "status": "running"}

# ---------------------------
# Optional local development entry
# ---------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        # reload=True  # Only for dev
        reload=True
    )
