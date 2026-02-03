"""
HabitCity Backend - Main Application

FastAPI application with PPO model loading at startup.
Designed for free-tier deployment (CPU-only, stateless).
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api.routes import router
from app.models.model_loader import model_loader
from app.database import init_db
from app.services.firebase import firebase_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan: load model, init database, setup Firebase on startup.
    """
    # Startup
    logger.info("Starting HabitCity Backend...")
    
    # Initialize database
    logger.info("Initializing database...")
    try:
        init_db()
        logger.info("Database initialized successfully")
        app.state.db_initialized = True
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        app.state.db_initialized = False
    
    # Initialize Firebase
    logger.info("Initializing Firebase...")
    firebase_initialized = firebase_service.initialize()
    app.state.firebase_initialized = firebase_initialized
    if firebase_initialized:
        logger.info("Firebase initialized successfully")
    else:
        logger.warning("Firebase not initialized - auth may not work")
    
    # Load PPO model and VecNormalize
    model_path = settings.full_model_path
    vecnorm_path = settings.full_vecnorm_path
    
    if model_path.exists() and vecnorm_path.exists():
        success = model_loader.load(model_path, vecnorm_path)
        if success:
            logger.info("Model loaded successfully at startup")
        else:
            logger.warning("Model loading failed, running in fallback mode")
    else:
        logger.warning(f"Model files not found at {model_path} and {vecnorm_path}")
        logger.warning("Running in fallback mode (NEUTRAL_WAIT only)")
    
    yield
    
    # Shutdown
    logger.info("Shutting down HabitCity Backend...")


# Create FastAPI app
app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="AI-driven motivation adaptation backend for HabitCity",
    lifespan=lifespan,
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://*.vercel.app",  # Vercel deployments
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "running",
        "model_loaded": model_loader.is_loaded,
        "db_initialized": getattr(app.state, "db_initialized", False),
        "firebase_initialized": getattr(app.state, "firebase_initialized", False),
    }

