# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware
# from database import connect_db, close_db
# from routes import floor_plan, guests
# import logging

# # ---------------------------
# # Logging
# # ---------------------------
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # ---------------------------
# # FastAPI app
# # ---------------------------
# app = FastAPI(
#     title="Restaurant Management API",
#     description="API for restaurant floor plan analysis and guest management",
#     version="1.0.0"
# )

# # ---------------------------
# # CORS Middleware
# # ---------------------------
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Change to specific domains in production
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # ---------------------------
# # Startup / Shutdown Events
# # ---------------------------
# @app.on_event("startup")
# async def startup():
#     await connect_db()
#     logger.info("✅ MongoDB connected")

# @app.on_event("shutdown")
# async def shutdown():
#     await close_db()
#     logger.info("🔴 MongoDB disconnected")

# # ---------------------------
# # Routes
# # ---------------------------
# app.include_router(guests.router, prefix="/api/guests", tags=["Guests"])

# # 🟢 Floor plan router - prefix change করলাম
# app.include_router(floor_plan.router, prefix="/api/floor-plan", tags=["Floor Plan Analysis"])

# # ---------------------------
# # Health / Root Endpoint
# # ---------------------------
# @app.get("/", tags=["Root"])
# def root():
#     return {
#         "message": "Restaurant Management API",
#         "status": "running",
#         "version": "1.0.0",
#         "endpoints": {
#             "guests": "/api/guests",
#             "floor_plan_upload": "POST /api/floor-plan/upload",
#             "floor_plan_analysis": "GET /api/floor-plan/analysis/{analysis_id}",
#             "all_analyses": "GET /api/floor-plan/all"
#         }
#     }

# # ---------------------------
# # Optional local development entry
# # ---------------------------
# if __name__ == "__main__":
#     import uvicorn

#     uvicorn.run(
#         "main:app",
#         host="0.0.0.0",
#         port=8000,
#         reload=True  # Only for dev
#     )




from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import connect_db, close_db
from routes import floor_plan, guests, reservation_extract  # ← ADD reservation_extract
import logging

# ---------------------------
# Logging
# ---------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------
# FastAPI app
# ---------------------------
app = FastAPI(
    title="Restaurant Management API",
    description="API for restaurant floor plan analysis and guest management",
    version="1.0.0"
)

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

# 🟢 Floor plan router - prefix change করলাম
app.include_router(floor_plan.router, prefix="/api/floor-plan", tags=["Floor Plan Analysis"])

# 🟢 NEW: Reservation extract router
app.include_router(reservation_extract.router)  # ← ADD THIS LINE (prefix already in router)

# ---------------------------
# Health / Root Endpoint
# ---------------------------
@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Restaurant Management API",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "guests": "/api/guests",
            "floor_plan_upload": "POST /api/floor-plan/upload",
            "floor_plan_analysis": "GET /api/floor-plan/analysis/{analysis_id}",
            "all_analyses": "GET /api/floor-plan/all",
            "reservation_extract": "POST /api/reservation/extract-details"  # ← ADD THIS LINE
        }
    }

# ---------------------------
# Optional local development entry
# ---------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True  # Only for dev
    )