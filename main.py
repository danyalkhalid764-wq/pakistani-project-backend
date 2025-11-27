import sys
import os
import shutil

# Force output immediately
sys.stdout.flush()
sys.stderr.flush()

# Configure ffmpeg PATH before any imports that might use it (pydub, moviepy)
# This ensures ffmpeg is available when pydub/moviepy check for it at import time
try:
    import imageio_ffmpeg
    ffmpeg_binary = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_dir = os.path.dirname(ffmpeg_binary)
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
    print(f"✅ Configured ffmpeg from imageio-ffmpeg: {ffmpeg_binary}", flush=True)
except Exception:
    # Fallback to system ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        ffmpeg_dir = os.path.dirname(ffmpeg_path)
        if ffmpeg_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")
        print(f"✅ Configured system ffmpeg: {ffmpeg_path}", flush=True)
    else:
        print("⚠️ ffmpeg not found in PATH - video/audio features may not work", flush=True)

print("=" * 50, flush=True)
print("Starting FastAPI application...", flush=True)
print("=" * 50, flush=True)

try:
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    print("✅ FastAPI imported", flush=True)
    
    from database import engine, Base, SessionLocal
    print("✅ Database imported", flush=True)
    
    from models import User, VoiceHistory, Payment, GeneratedVideo, Admin
    from utils.jwt_handler import get_password_hash
    print("✅ Models imported", flush=True)
    
    from routes import auth, tts, payments, video
    print("✅ Routes imported", flush=True)
    
    # Check TTS service configuration on startup
    print("=" * 50, flush=True)
    print("[STARTUP] Checking TTS Service Configuration...", flush=True)
    from services.lamonfox_service import LamonfoxService, LAMONFOX_API_KEY
    tts_service_check = LamonfoxService()
    if tts_service_check.api_key:
        key_length = len(tts_service_check.api_key)
        key_preview = f"{tts_service_check.api_key[:10]}...{tts_service_check.api_key[-5:]}" if key_length > 15 else f"{tts_service_check.api_key[:5]}***"
        print(f"[STARTUP] ✅ TTS Service Ready", flush=True)
        print(f"[STARTUP] API Key Preview: {key_preview}", flush=True)
        print(f"[STARTUP] API Key Length: {key_length} characters", flush=True)
        print(f"[STARTUP] API Key First 6 chars: {tts_service_check.api_key[:6]}", flush=True)
        print(f"[STARTUP] API Key Last 6 chars: {tts_service_check.api_key[-6:]}", flush=True)
    else:
        print(f"[STARTUP] ❌ TTS Service NOT Ready - API key missing", flush=True)
        print(f"[STARTUP] ⚠️  Set LAMONFOX_API_KEY environment variable to enable TTS", flush=True)
    print("=" * 50, flush=True)
    
    # Admin credentials are hardcoded (not in database)
    print("[STARTUP] Admin login configured with hardcoded credentials", flush=True)
    print("[STARTUP]   - Admin Name: Sohaib", flush=True)
    print("[STARTUP]   - Admin Password: 123456", flush=True)
    print("[STARTUP]   - Admin Email: admin@myaistudio.com", flush=True)
    print("[STARTUP] ✅ Admin login ready (no database user required)", flush=True)
    
    print("DEBUG_DATABASE_URL:", os.getenv("DATABASE_URL"), flush=True)
    print("=" * 50, flush=True)
except Exception as e:
    print(f"❌ Import error: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Create all database tables at startup (SQLite will recreate if deleted)
# This ensures the database schema is always up to date with the models
print("🔄 Creating database tables...", flush=True)
try:
    # Import all models to ensure they're registered with Base.metadata
    from models import User, VoiceHistory, Payment, GeneratedVideo, Admin
    
    # Create all tables (only creates if they don't exist, safe for existing databases)
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created/verified successfully!", flush=True)
    
    # Initialize default admin user if it doesn't exist
    db = SessionLocal()
    try:
        default_admin = db.query(Admin).filter(Admin.name == "Sohaib").first()
        if not default_admin:
            print("📝 Creating default admin user...", flush=True)
            admin = Admin(name="Sohaib", password="123456")
            db.add(admin)
            db.commit()
            print("✅ Default admin created: Name='Sohaib', Password='123456'", flush=True)
        
        user_count = db.query(User).count()
        print(f"📊 Database connected! Current users: {user_count}", flush=True)
    finally:
        db.close()
except Exception as e:
    print(f"❌ Error creating database tables: {e}", flush=True)
    import traceback
    traceback.print_exc()
    # Don't exit - let the server start and show the error

# Initialize FastAPI app
app = FastAPI(
    title="MyAIStudio API",
    description="Text-to-Speech API with Lamonfox (Lemonfox.ai) integration",
    version="1.0.0"
)

# Startup event to ensure database tables exist
@app.on_event("startup")
async def startup_db_check():
    """Ensure database tables exist on startup and default admin is created"""
    try:
        from models import Admin
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables verified on startup event!", flush=True)
        
        # Ensure default admin exists
        db = SessionLocal()
        try:
            default_admin = db.query(Admin).filter(Admin.name == "Sohaib").first()
            if not default_admin:
                print("📝 Creating default admin user on startup...", flush=True)
                admin = Admin(name="Sohaib", password="123456")
                db.add(admin)
                db.commit()
                print("✅ Default admin created on startup", flush=True)
        finally:
            db.close()
    except Exception as e:
        print(f"⚠️ Database startup check warning: {e}", flush=True)

# ✅ FIXED: Proper CORS setup for both local + production
# CORS middleware must be added BEFORE routers to handle OPTIONS preflight requests
# CORS configuration - allow Netlify domains and local development
from config import settings
cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",  # Vite dev server
    "https://picvoice3lab.netlify.app",         # NEW: current deployed frontend
    "https://picvoice3labc.netlify.app",         # old deployed frontend
    "https://pakistani-project-frontend.netlify.app",  # backup / test domain
    "https://startling-cobbler-7dd158.netlify.app",  # previous Netlify domain
]
# Add any additional origins from config
if hasattr(settings, 'ALLOWED_ORIGINS'):
    cors_origins.extend([origin for origin in settings.ALLOWED_ORIGINS if origin not in cors_origins])

# CORS middleware configuration
# This MUST be added before routers to handle OPTIONS preflight requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    allow_headers=["*"],  # Allow all headers - "*" is more permissive
    expose_headers=["*"],
    max_age=3600,
)

# Global exception handler to ensure CORS headers are included in error responses
# Note: HTTPException is already handled by FastAPI with CORS headers
# This handler catches unexpected exceptions
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi import Request, status

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to ensure CORS headers are included in all error responses"""
    # Don't handle HTTPException - FastAPI already handles it with CORS
    if isinstance(exc, HTTPException):
        raise exc
    
    import traceback
    error_detail = str(exc)
    traceback_str = traceback.format_exc()
    print(f"❌ Global exception handler: {error_detail}", flush=True)
    print(f"Traceback: {traceback_str}", flush=True)
    
    # Return JSON response with CORS headers (middleware will add them)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "error": error_detail
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with CORS headers"""
    errors = exc.errors()
    # Format validation errors for better readability
    error_messages = []
    for error in errors:
        field = ".".join(str(loc) for loc in error.get("loc", []))
        message = error.get("msg", "Validation error")
        error_messages.append(f"{field}: {message}")
    
    print(f"⚠️ Validation error: {error_messages}", flush=True)
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": error_messages if error_messages else exc.errors(),
            "errors": exc.errors()
        }
    )

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(tts.router, prefix="/api", tags=["text-to-speech"])
app.include_router(payments.router, prefix="/api/payment", tags=["payments"])
app.include_router(video.router, prefix="/api/video", tags=["video"])

# ✅ Static files for generated videos
# Use app directory for generated_videos (writable location on Railway)
# Use absolute path for consistency with video.py
videos_dir = os.path.join(os.path.dirname(__file__), "generated_videos")
videos_dir = os.path.abspath(videos_dir)  # Ensure absolute path
os.makedirs(videos_dir, exist_ok=True)
print(f"📁 Video files directory (main.py): {videos_dir}", flush=True)

# List existing files for debugging
try:
    if os.path.exists(videos_dir):
        existing_files = os.listdir(videos_dir)
        print(f"📹 Existing video files in directory: {len(existing_files)} files", flush=True)
        if existing_files:
            print(f"   Sample files (first 5): {existing_files[:5]}", flush=True)
    else:
        print(f"⚠️ Videos directory created but doesn't exist yet", flush=True)
except Exception as e:
    print(f"⚠️ Could not list video directory: {e}", flush=True)

# Direct route handler to serve video files (more reliable than mount)
from fastapi.responses import FileResponse, Response
from fastapi import HTTPException
# Request is already imported above (line 179)

@app.options("/static/videos/{filename}")
async def serve_video_options(filename: str, request: Request):
    """Handle OPTIONS preflight requests for video files with CORS"""
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    user_agent = request.headers.get("user-agent", "")[:100]  # Truncate for logging
    
    print("=" * 80, flush=True)
    print(f"🔍 [CORS DEBUG] OPTIONS request for video: {filename}", flush=True)
    print(f"   Origin: {origin}", flush=True)
    print(f"   Referer: {referer}", flush=True)
    print(f"   User-Agent: {user_agent}", flush=True)
    print(f"   Allowed origins: {cors_origins}", flush=True)
    print(f"   Origin in allowed list: {origin in cors_origins}", flush=True)
    print(f"   All request headers: {dict(request.headers)}", flush=True)
    
    if origin in cors_origins:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "3600",
        }
        print(f"✅ [CORS DEBUG] Sending CORS headers for OPTIONS:", flush=True)
        for key, value in headers.items():
            print(f"   {key}: {value}", flush=True)
        print("=" * 80, flush=True)
        return Response(status_code=200, headers=headers)
    
    print(f"⚠️ [CORS DEBUG] Origin not in allowed list - returning 200 without CORS headers", flush=True)
    print("=" * 80, flush=True)
    return Response(status_code=200)

@app.get("/static/videos/{filename}")
async def serve_video(filename: str, request: Request):
    """
    Serve video files directly from disk with CORS headers.
    """
    # Remove query parameters if present
    original_filename = filename
    filename = filename.split('?')[0]
    file_path = os.path.join(videos_dir, filename)
    
    # Get all request headers for debugging
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    host = request.headers.get("host", "")
    user_agent = request.headers.get("user-agent", "")[:100]  # Truncate for logging
    all_headers = dict(request.headers)
    
    print("=" * 80, flush=True)
    print(f"🎬 [CORS DEBUG] GET request for video: {original_filename}", flush=True)
    print(f"   Cleaned filename: {filename}", flush=True)
    print(f"   File path: {file_path}", flush=True)
    print(f"   File exists: {os.path.exists(file_path)}", flush=True)
    print(f"   Origin header: '{origin}'", flush=True)
    print(f"   Referer header: '{referer}'", flush=True)
    print(f"   Host header: '{host}'", flush=True)
    print(f"   User-Agent: {user_agent}", flush=True)
    print(f"   Allowed origins: {cors_origins}", flush=True)
    print(f"   Origin in allowed list: {origin in cors_origins}", flush=True)
    print(f"   All request headers:", flush=True)
    for key, value in all_headers.items():
        print(f"      {key}: {value}", flush=True)
    
    if os.path.exists(file_path) and os.path.isfile(file_path):
        file_size = os.path.getsize(file_path)
        print(f"✅ File found - size: {file_size} bytes", flush=True)
        
        # Build headers with CORS support
        headers = {
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600",
        }
        
        # Add CORS headers if origin matches allowed origins
        if origin in cors_origins:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
            headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
            headers["Access-Control-Allow-Headers"] = "*"
            headers["Access-Control-Expose-Headers"] = "*"
            print(f"✅ [CORS DEBUG] Adding CORS headers:", flush=True)
            for key, value in headers.items():
                print(f"   {key}: {value}", flush=True)
        else:
            # Try to extract origin from referer if origin header is missing
            if not origin and referer:
                print(f"⚠️ [CORS DEBUG] No origin header, trying to extract from referer: {referer}", flush=True)
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(referer)
                    extracted_origin = f"{parsed.scheme}://{parsed.netloc}"
                    print(f"   Extracted origin: {extracted_origin}", flush=True)
                    if extracted_origin in cors_origins:
                        headers["Access-Control-Allow-Origin"] = extracted_origin
                        headers["Access-Control-Allow-Credentials"] = "true"
                        headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
                        headers["Access-Control-Allow-Headers"] = "*"
                        headers["Access-Control-Expose-Headers"] = "*"
                        print(f"✅ [CORS DEBUG] Added CORS headers using extracted origin:", flush=True)
                        for key, value in headers.items():
                            if key.startswith("Access-Control"):
                                print(f"   {key}: {value}", flush=True)
                except Exception as e:
                    print(f"❌ [CORS DEBUG] Failed to extract origin from referer: {e}", flush=True)
            else:
                print(f"⚠️ [CORS DEBUG] Origin '{origin}' not in allowed list - NOT adding CORS headers", flush=True)
                print(f"   This may cause CORS errors in the browser", flush=True)
        
        print("=" * 80, flush=True)
        return FileResponse(
            file_path,
            media_type="video/mp4",
            headers=headers
        )
    
    # File not found - but still add CORS headers
    print(f"❌ Video not found: {filename}", flush=True)
    print(f"   Searched path: {file_path}", flush=True)
    print(f"   Videos directory: {videos_dir}", flush=True)
    print(f"   Videos directory absolute: {os.path.abspath(videos_dir)}", flush=True)
    
    # List files in directory for debugging
    try:
        if os.path.exists(videos_dir):
            files_in_dir = os.listdir(videos_dir)
            print(f"   Files in directory ({len(files_in_dir)} files):", flush=True)
            for f in files_in_dir[:10]:  # List first 10 files
                file_full_path = os.path.join(videos_dir, f)
                file_size = os.path.getsize(file_full_path) if os.path.isfile(file_full_path) else 0
                print(f"      - {f} ({file_size} bytes)", flush=True)
        else:
            print(f"   ❌ Videos directory does not exist!", flush=True)
    except Exception as e:
        print(f"   ⚠️ Could not list directory: {e}", flush=True)
    
    # Get origin for CORS headers
    origin = request.headers.get("origin", "")
    referer = request.headers.get("referer", "")
    
    # Build error response with CORS headers
    error_detail = f"Video file not found: {filename}"
    
    # Create response with CORS headers (JSONResponse already imported above)
    headers = {}
    if origin in cors_origins:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    elif referer:
        # Try extracting from referer
        try:
            from urllib.parse import urlparse
            parsed = urlparse(referer)
            extracted_origin = f"{parsed.scheme}://{parsed.netloc}"
            if extracted_origin in cors_origins:
                headers["Access-Control-Allow-Origin"] = extracted_origin
                headers["Access-Control-Allow-Credentials"] = "true"
        except Exception:
            pass
    
    print(f"   CORS headers for 404: {headers}", flush=True)
    print("=" * 80, flush=True)
    
    return JSONResponse(
        status_code=404,
        content={"detail": error_detail},
        headers=headers
    )

@app.get("/")
async def root():
    return {"message": "MyAIStudio API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Print server startup info
print("=" * 50)
print("✅ FastAPI application initialized successfully!")
print("Routes registered:")
print("  - /auth/* (authentication)")
print("  - /api/* (text-to-speech)")
print("  - /api/payment/* (payments)")
print("  - /api/video/* (video generation)")
print("  - /static/videos/* (video files)")
print("=" * 50)
print("🚀 Starting Uvicorn server...")
print("=" * 50)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)