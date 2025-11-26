from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User, VoiceHistory
from schemas import VoiceGenerateRequest, VoiceGenerateResponse
from services.lamonfox_service import LamonfoxService
from utils.audio_utils import add_watermark_to_audio, audio_to_base64
from routes.auth import get_current_user
import os
import logging
from datetime import datetime, date

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()
lamonfox_service = LamonfoxService()

@router.post("/generate-voice", response_model=VoiceGenerateResponse)
async def generate_voice(
    request: VoiceGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # ========== REQUEST START LOGGING ==========
    request_id = f"{current_user.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info("=" * 80)
    logger.info(f"[REQUEST START] ID: {request_id}")
    logger.info(f"[USER] ID: {current_user.id}, Email: {current_user.email}, Plan: {current_user.plan}")
    logger.info(f"[TEXT] Length: {len(request.text)} chars, Words: {len(request.text.split())}")
    logger.info(f"[TEXT PREVIEW] {request.text[:100]}{'...' if len(request.text) > 100 else ''}")
    
    try:
        # Reset daily counters if needed
        today = date.today()
        if current_user.last_reset_date != today:
            logger.info(f"[COUNTER RESET] Resetting daily counters for user {current_user.id}")
            current_user.daily_voice_count = 0
            current_user.daily_video_count = 0
            # Note: total_tokens_used is NOT reset daily - it's a lifetime limit
            current_user.last_reset_date = today
            db.commit()
            logger.info(f"[COUNTER RESET] Daily counters reset successfully")

        # Ensure daily_voice_count is initialized
        if current_user.daily_voice_count is None:
            current_user.daily_voice_count = 0

        # Check daily voice generation limits
        MAX_DAILY_VOICES = 2 if current_user.plan == "Free" else 5
        logger.info(f"[DAILY VOICE LIMIT] Plan: {current_user.plan}, Max daily voices: {MAX_DAILY_VOICES}, Current count: {current_user.daily_voice_count}")
        
        if current_user.daily_voice_count >= MAX_DAILY_VOICES:
            logger.warning(f"[LIMIT EXCEEDED] Daily voice limit reached: {current_user.daily_voice_count}/{MAX_DAILY_VOICES}")
            error_detail = {
                "message": f"Daily voice generation limit reached. You can generate up to {MAX_DAILY_VOICES} voices per day. You have already generated {current_user.daily_voice_count} voices today.",
                "error_type": "DAILY_VOICE_LIMIT_EXCEEDED",
                "status_code": 429,
                "details": f"You have reached your daily limit of {MAX_DAILY_VOICES} voice generations. Please try again tomorrow.",
                "timestamp": datetime.now().isoformat(),
                "daily_count": current_user.daily_voice_count,
                "max_daily_voices": MAX_DAILY_VOICES
            }
            return VoiceGenerateResponse(
                success=False,
                message=error_detail["message"],
                error=error_detail,
                daily_count=current_user.daily_voice_count,
                limit_reached=True,
                tokens_used=current_user.total_tokens_used or 0,
                tokens_remaining=0
            )

        # Count words in the text (treat each word as 1 token)
        word_count = len(request.text.split())
        logger.info(f"[TOKEN COUNT] Word count: {word_count}")
        
        # Enforce plan limits based on tokens/words
        if current_user.plan == "Free":
            # Free users: 150 words max per generation, 300 total tokens max
            MAX_WORDS_PER_GENERATION = 150
            MAX_TOTAL_TOKENS = 300
            
            logger.info(f"[LIMIT CHECK] Plan: Free, Max words/generation: {MAX_WORDS_PER_GENERATION}, Max total tokens: {MAX_TOTAL_TOKENS}")
            
            # Check word limit per generation
            if word_count > MAX_WORDS_PER_GENERATION:
                logger.warning(f"[LIMIT EXCEEDED] Word limit exceeded: {word_count} > {MAX_WORDS_PER_GENERATION}")
                error_detail = {
                    "message": f"Text exceeds maximum word limit. Maximum {MAX_WORDS_PER_GENERATION} words allowed for free plan. Your text has {word_count} words.",
                    "error_type": "WORD_LIMIT_EXCEEDED",
                    "status_code": 400,
                    "details": f"Your text has {word_count} words, but the maximum allowed is {MAX_WORDS_PER_GENERATION} words per generation.",
                    "timestamp": datetime.now().isoformat()
                }
                return VoiceGenerateResponse(
                    success=False,
                    message=error_detail["message"],
                    error=error_detail,
                    daily_count=current_user.daily_voice_count,
                    limit_reached=False,
                    tokens_used=current_user.total_tokens_used or 0,
                    tokens_remaining=0
                )
            
            # Check total tokens used
            if current_user.total_tokens_used is None:
                current_user.total_tokens_used = 0
            
            logger.info(f"[TOKEN USAGE] Current: {current_user.total_tokens_used}, Requested: {word_count}, Total after: {current_user.total_tokens_used + word_count}")
            
            if current_user.total_tokens_used + word_count > MAX_TOTAL_TOKENS:
                remaining = MAX_TOTAL_TOKENS - current_user.total_tokens_used
                logger.warning(f"[LIMIT EXCEEDED] Token limit reached: {current_user.total_tokens_used}/{MAX_TOTAL_TOKENS}, Remaining: {remaining}")
                error_detail = {
                    "message": f"Token limit reached. You have used {current_user.total_tokens_used}/{MAX_TOTAL_TOKENS} tokens. You can generate up to {remaining} more words.",
                    "error_type": "TOKEN_LIMIT_EXCEEDED",
                    "status_code": 429,
                    "details": f"You have used {current_user.total_tokens_used} out of {MAX_TOTAL_TOKENS} total tokens. Remaining: {remaining} words.",
                    "timestamp": datetime.now().isoformat()
                }
                return VoiceGenerateResponse(
                    success=False,
                    message=error_detail["message"],
                    error=error_detail,
                    daily_count=current_user.daily_voice_count,
                    limit_reached=True,
                    tokens_used=current_user.total_tokens_used,
                    tokens_remaining=remaining
                )
        else:
            # Paid users: unlimited generations but max 800 tokens per person
            MAX_TOTAL_TOKENS = 800
            logger.info(f"[LIMIT CHECK] Plan: Paid, Max total tokens: {MAX_TOTAL_TOKENS}")
            
            # Check total tokens used
            if current_user.total_tokens_used is None:
                current_user.total_tokens_used = 0
            
            logger.info(f"[TOKEN USAGE] Current: {current_user.total_tokens_used}, Requested: {word_count}, Total after: {current_user.total_tokens_used + word_count}")
            
            if current_user.total_tokens_used + word_count > MAX_TOTAL_TOKENS:
                remaining = MAX_TOTAL_TOKENS - current_user.total_tokens_used
                logger.warning(f"[LIMIT EXCEEDED] Token limit reached: {current_user.total_tokens_used}/{MAX_TOTAL_TOKENS}, Remaining: {remaining}")
                error_detail = {
                    "message": f"Token limit reached. You have used {current_user.total_tokens_used}/{MAX_TOTAL_TOKENS} tokens. You can generate up to {remaining} more words.",
                    "error_type": "TOKEN_LIMIT_EXCEEDED",
                    "status_code": 429,
                    "details": f"You have used {current_user.total_tokens_used} out of {MAX_TOTAL_TOKENS} total tokens. Remaining: {remaining} words.",
                    "timestamp": datetime.now().isoformat()
                }
                return VoiceGenerateResponse(
                    success=False,
                    message=error_detail["message"],
                    error=error_detail,
                    daily_count=current_user.daily_voice_count,
                    limit_reached=True,
                    tokens_used=current_user.total_tokens_used,
                    tokens_remaining=remaining
                )
        
        logger.info(f"[LIMIT CHECK] ✅ All limits passed")
    
        # Detailed API key validation and logging before attempting generation
        logger.info("[API KEY CHECK] Validating Lamonfox API key configuration...")
        logger.info(f"[API KEY CHECK] Service instance: {type(lamonfox_service).__name__}")
        
        if not lamonfox_service.api_key:
            logger.error(f"[API KEY] ❌ Lamonfox API key is not configured")
            logger.error(f"[API KEY] Source checked: Environment variable 'LAMONFOX_API_KEY'")
            logger.error(f"[API KEY] Status: Missing or empty")
            error_detail = {
                "message": "Voice generation service is not configured. Please contact support.",
                "error_type": "SERVICE_NOT_CONFIGURED",
                "status_code": 500,
                "details": "The TTS service API key is missing. This is a server configuration issue.",
                "timestamp": datetime.now().isoformat()
            }
            return VoiceGenerateResponse(
                success=False,
                message=error_detail["message"],
                error=error_detail,
                daily_count=current_user.daily_voice_count,
                limit_reached=False,
                tokens_used=current_user.total_tokens_used or 0,
                tokens_remaining=0
            )
        
        # Log detailed API key information
        api_key = lamonfox_service.api_key
        key_length = len(api_key)
        key_preview = f"{api_key[:10]}...{api_key[-5:]}" if key_length > 15 else f"{api_key[:5]}***"
        logger.info(f"[API KEY] ✅ API key is configured")
        logger.info(f"[API KEY] API Key Details:")
        logger.info(f"  - Source: Environment variable 'LAMONFOX_API_KEY'")
        logger.info(f"  - Length: {key_length} characters")
        logger.info(f"  - Preview: {key_preview}")
        logger.info(f"  - First 6 chars: {api_key[:6]}")
        logger.info(f"  - Last 6 chars: {api_key[-6:]}")
        logger.info(f"  - Service: Lamonfox (Lemonfox.ai)")
        logger.info(f"  - Base URL: {lamonfox_service.base_url}")
        logger.info(f"[VOICE GENERATION] Starting voice generation with Lamonfox API using above API key")
        
        # Generate voice using Lamonfox
        audio_data = await lamonfox_service.generate_voice(request.text)
        
        logger.info(f"[AUDIO RECEIVED] Audio data size: {len(audio_data)} bytes")
        
        # Handle trial vs paid users
        if current_user.plan == "Free":
            logger.info(f"[WATERMARK] Adding watermark for Free user")
            watermarked_audio = add_watermark_to_audio(audio_data)
            logger.info(f"[WATERMARK] ✅ Watermark added, Base64 length: {len(watermarked_audio)}")
            
            # Save to voice history (no permanent URL for trial)
            logger.info(f"[DATABASE] Saving voice history entry")
            voice_entry = VoiceHistory(
                user_id=current_user.id,
                text=request.text,
                audio_url=None
            )
            db.add(voice_entry)
            
            # Update token usage
            if current_user.total_tokens_used is None:
                current_user.total_tokens_used = 0
            current_user.total_tokens_used += word_count
            
            # Increment daily count
            current_user.daily_voice_count += 1
            db.commit()
            logger.info(f"[DATABASE] ✅ Voice history saved, ID: {voice_entry.id}")
            logger.info(f"[TOKEN UPDATE] Total tokens: {current_user.total_tokens_used}, Daily count: {current_user.daily_voice_count}")
            
            remaining_tokens = 300 - current_user.total_tokens_used
            logger.info(f"[REQUEST SUCCESS] Voice generated successfully for Free user")
            logger.info(f"[TOKEN STATUS] Used: {current_user.total_tokens_used}, Remaining: {remaining_tokens}, Limit reached: {current_user.total_tokens_used >= 300}")
            logger.info("=" * 80)
            
            return VoiceGenerateResponse(
                success=True,
                message="Voice generated successfully (Trial version with watermark)",
                audio_data=watermarked_audio,
                audio_url=None,
                daily_count=current_user.daily_voice_count,
                limit_reached=current_user.total_tokens_used >= 300,
                tokens_used=current_user.total_tokens_used,
                tokens_remaining=remaining_tokens
            )
        else:
            logger.info(f"[AUDIO PROCESSING] Converting audio to base64 for Paid user")
            audio_base64 = audio_to_base64(audio_data)
            logger.info(f"[AUDIO PROCESSING] ✅ Base64 conversion complete, Length: {len(audio_base64)}")
            
            # Save to voice history with URL
            logger.info(f"[DATABASE] Saving voice history entry")
            voice_entry = VoiceHistory(
                user_id=current_user.id,
                text=request.text,
                audio_url=None
            )
            db.add(voice_entry)
            
            # Update token usage
            if current_user.total_tokens_used is None:
                current_user.total_tokens_used = 0
            current_user.total_tokens_used += word_count
            
            # Increment daily voice count
            current_user.daily_voice_count += 1
            
            db.commit()
            db.refresh(voice_entry)
            
            # Update with actual URL
            voice_entry.audio_url = f"generated_audio_{voice_entry.id}.mp3"
            db.commit()
            logger.info(f"[DATABASE] ✅ Voice history saved, ID: {voice_entry.id}, URL: {voice_entry.audio_url}")
            logger.info(f"[TOKEN UPDATE] Total tokens: {current_user.total_tokens_used}, Daily voice count: {current_user.daily_voice_count}")
            
            remaining_tokens = 800 - current_user.total_tokens_used
            logger.info(f"[REQUEST SUCCESS] Voice generated successfully for Paid user")
            logger.info(f"[TOKEN STATUS] Used: {current_user.total_tokens_used}, Remaining: {remaining_tokens}, Limit reached: {current_user.total_tokens_used >= 800}")
            logger.info("=" * 80)
            
            return VoiceGenerateResponse(
                success=True,
                message="Voice generated successfully",
                audio_data=audio_base64,
                audio_url=voice_entry.audio_url,
                daily_count=current_user.daily_voice_count,
                limit_reached=current_user.total_tokens_used >= 800,
                tokens_used=current_user.total_tokens_used,
                tokens_remaining=remaining_tokens
            )
            
    except HTTPException as e:
        # Re-raise HTTP exceptions but add error details
        logger.error(f"[HTTP EXCEPTION] Status: {e.status_code}, Detail: {e.detail}")
        
        # If detail is already a dict, use it; otherwise create error detail
        if isinstance(e.detail, dict):
            error_detail = e.detail
        else:
            error_detail = {
                "message": str(e.detail),
                "error_type": "HTTP_ERROR",
                "status_code": e.status_code,
                "details": str(e.detail),
                "timestamp": datetime.now().isoformat()
            }
        
        # Return error response instead of raising HTTPException
        return VoiceGenerateResponse(
            success=False,
            message=error_detail.get("message", "An error occurred"),
            error=error_detail,
            daily_count=current_user.daily_voice_count if current_user else 0,
            limit_reached=False,
            tokens_used=current_user.total_tokens_used if current_user else 0,
            tokens_remaining=0
        )
        
    except Exception as e:
        # Log detailed error information for debugging
        import traceback
        error_detail_str = str(e)
        traceback_str = traceback.format_exc()
        
        logger.error("=" * 80)
        logger.error(f"[ERROR] Request ID: {request_id}")
        logger.error(f"[ERROR] Type: {type(e).__name__}")
        logger.error(f"[ERROR] Message: {error_detail_str}")
        logger.error(f"[ERROR] Traceback:")
        logger.error(traceback_str)
        logger.error("=" * 80)
        
        # Determine appropriate status code and error message
        status_code = 500
        error_type = "UNKNOWN_ERROR"
        error_message = error_detail_str
        
        # Map specific errors to appropriate types and messages
        if "API key" in error_detail_str or "api_key" in error_detail_str.lower() or "not configured" in error_detail_str.lower():
            status_code = 500
            error_type = "API_KEY_ERROR"
            error_message = "Voice generation service configuration error. Please contact support."
        elif "Payment required" in error_detail_str or "free tier" in error_detail_str.lower() or "unusual activity" in error_detail_str.lower():
            status_code = 402
            error_type = "PAYMENT_REQUIRED"
            error_message = error_detail_str
        elif "quota" in error_detail_str.lower() or "limit" in error_detail_str.lower():
            status_code = 429
            error_type = "QUOTA_EXCEEDED"
            error_message = "Voice generation quota exceeded. Please try again later."
        elif "rate limit" in error_detail_str.lower():
            status_code = 429
            error_type = "RATE_LIMIT_EXCEEDED"
            error_message = error_detail_str
        elif "network" in error_detail_str.lower() or "connection" in error_detail_str.lower() or "timeout" in error_detail_str.lower():
            status_code = 503
            error_type = "NETWORK_ERROR"
            error_message = "Network error. Please check your connection and try again."
        elif "invalid" in error_detail_str.lower() and "request" in error_detail_str.lower():
            status_code = 400
            error_type = "INVALID_REQUEST"
            error_message = error_detail_str
        
        error_detail = {
            "message": error_message,
            "error_type": error_type,
            "status_code": status_code,
            "details": error_detail_str,
            "timestamp": datetime.now().isoformat(),
            "traceback": traceback_str  # Include traceback for debugging
        }
        
        # Return error response
        return VoiceGenerateResponse(
            success=False,
            message=error_message,
            error=error_detail,
            daily_count=current_user.daily_voice_count if current_user else 0,
            limit_reached=False,
            tokens_used=current_user.total_tokens_used if current_user else 0,
            tokens_remaining=0
        )

@router.get("/history")
async def get_voice_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's voice generation history"""
    history = db.query(VoiceHistory).filter(VoiceHistory.user_id == current_user.id).all()
    
    return [
        {
            "id": entry.id,
            "text": entry.text,
            "audio_url": entry.audio_url,
            "created_at": entry.created_at
        }
        for entry in history
    ]

@router.get("/debug")
async def debug_tts_service(current_user: User = Depends(get_current_user)):
    """Debug endpoint to check TTS service configuration"""
    api_key_set = bool(lamonfox_service.api_key)
    api_key_preview = f"{lamonfox_service.api_key[:10]}...{lamonfox_service.api_key[-5:]}" if lamonfox_service.api_key and len(lamonfox_service.api_key) > 15 else ("Set" if api_key_set else "Not Set")
    
    return {
        "service": "Lamonfox",
        "api_key_configured": api_key_set,
        "api_key_preview": api_key_preview,
        "base_url": lamonfox_service.base_url,
        "status": "ready" if api_key_set else "missing_api_key"
    }

@router.get("/plan")
async def get_plan_info(current_user: User = Depends(get_current_user)):
    """Get user's current plan information"""
    if current_user.total_tokens_used is None:
        current_user.total_tokens_used = 0
    
    if current_user.plan == "Free":
        tokens_remaining = max(0, 300 - current_user.total_tokens_used)
        features = [
            "150 words max per generation",
            "300 tokens total limit",
            "Watermarked audio",
            "No download option"
        ]
        return {
            "plan": current_user.plan,
            "max_words_per_generation": 150,
            "max_total_tokens": 300,
            "tokens_used": current_user.total_tokens_used,
            "tokens_remaining": tokens_remaining,
            "features": features
        }
    else:  # Paid
        tokens_remaining = max(0, 800 - current_user.total_tokens_used)
        features = [
            "Unlimited generations",
            "800 tokens total limit per person",
            "High-quality audio",
            "Download enabled",
            "No watermarks",
            "Priority processing"
        ]
        return {
            "plan": current_user.plan,
            "max_total_tokens": 800,
            "tokens_used": current_user.total_tokens_used,
            "tokens_remaining": tokens_remaining,
            "features": features
        }
