import httpx
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

LAMONFOX_API_KEY = os.getenv("LAMONFOX_API_KEY")
LAMONFOX_BASE_URL = "https://api.lemonfox.ai/v1"

# Log API key source and status at module level
logger.info("=" * 80)
logger.info("[LAMONFOX] Loading API key from environment...")
if LAMONFOX_API_KEY:
    key_length = len(LAMONFOX_API_KEY)
    key_preview = f"{LAMONFOX_API_KEY[:10]}...{LAMONFOX_API_KEY[-5:]}" if key_length > 15 else f"{LAMONFOX_API_KEY[:5]}***"
    key_first_4 = LAMONFOX_API_KEY[:4] if key_length >= 4 else "N/A"
    key_last_4 = LAMONFOX_API_KEY[-4:] if key_length >= 4 else "N/A"
    logger.info(f"[LAMONFOX] ✅ API key found in environment variable LAMONFOX_API_KEY")
    logger.info(f"[LAMONFOX] API Key Details:")
    logger.info(f"  - Length: {key_length} characters")
    logger.info(f"  - Preview: {key_preview}")
    logger.info(f"  - First 4 chars: {key_first_4}")
    logger.info(f"  - Last 4 chars: {key_last_4}")
    logger.info(f"  - Full preview: {key_preview}")
else:
    logger.warning("[LAMONFOX] ⚠️ LAMONFOX_API_KEY environment variable is NOT SET")
    logger.warning("[LAMONFOX] ⚠️ TTS service will not work without API key")
logger.info("=" * 80)

class LamonfoxService:
    def __init__(self):
        logger.info("[LAMONFOX INIT] Initializing LamonfoxService")
        logger.info("[LAMONFOX INIT] Checking API key configuration...")
        self.api_key = LAMONFOX_API_KEY
        self.base_url = LAMONFOX_BASE_URL
        
        # Validate API key on initialization with detailed logging
        if not self.api_key:
            logger.warning("[LAMONFOX INIT] ⚠️ LAMONFOX_API_KEY is not set in environment variables")
            logger.warning("[LAMONFOX INIT] ⚠️ Source: Environment variable 'LAMONFOX_API_KEY' is None or empty")
        else:
            key_length = len(self.api_key)
            key_preview = f"{self.api_key[:10]}...{self.api_key[-5:]}" if key_length > 15 else f"{self.api_key[:5]}***"
            key_fingerprint = f"{self.api_key[:6]}...{self.api_key[-6:]}" if key_length > 12 else self.api_key
            logger.info(f"[LAMONFOX INIT] ✅ API key configured successfully")
            logger.info(f"[LAMONFOX INIT] API Key Details:")
            logger.info(f"  - Source: Environment variable 'LAMONFOX_API_KEY'")
            logger.info(f"  - Length: {key_length} characters")
            logger.info(f"  - Preview: {key_preview}")
            logger.info(f"  - Fingerprint: {key_fingerprint}")
            logger.info(f"[LAMONFOX INIT] ✅ This API key will be used for all TTS requests")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key or ''}",
            "Content-Type": "application/json",
            "User-Agent": "MyAIStudio/1.0",
            "Accept": "audio/mpeg"
        }
        logger.info(f"[LAMONFOX INIT] Base URL: {self.base_url}")
        logger.info(f"[LAMONFOX INIT] Headers configured: {list(self.headers.keys())}")
        if self.api_key:
            auth_preview = f"Bearer {self.api_key[:10]}...{self.api_key[-5:]}" if len(self.api_key) > 15 else "Bearer ***"
            logger.info(f"[LAMONFOX INIT] Authorization header preview: {auth_preview}")
    
    async def generate_voice(self, text: str, voice: str = "sarah", response_format: str = "mp3") -> bytes:
        """
        Generate voice using Lamonfox (Lemonfox.ai) API
        """
        logger.info("-" * 80)
        logger.info("[LAMONFOX] Starting voice generation")
        logger.info(f"[LAMONFOX] Text length: {len(text)} chars, Voice: {voice}, Format: {response_format}")
        
        # Detailed API key logging before validation
        logger.info("[LAMONFOX] Checking API key before generation...")
        if self.api_key:
            key_length = len(self.api_key)
            key_preview = f"{self.api_key[:10]}...{self.api_key[-5:]}" if key_length > 15 else f"{self.api_key[:5]}***"
            logger.info(f"[LAMONFOX] API Key Status: ✅ PRESENT")
            logger.info(f"[LAMONFOX] API Key Being Used:")
            logger.info(f"  - Length: {key_length} characters")
            logger.info(f"  - Preview: {key_preview}")
            logger.info(f"  - First 6 chars: {self.api_key[:6]}")
            logger.info(f"  - Last 6 chars: {self.api_key[-6:]}")
            logger.info(f"  - Source: Environment variable 'LAMONFOX_API_KEY'")
        else:
            logger.error("[LAMONFOX] API Key Status: ❌ MISSING")
            logger.error("[LAMONFOX] API Key Source: Environment variable 'LAMONFOX_API_KEY' is not set")
        
        # Validate API key before making request
        if not self.api_key:
            logger.error("[LAMONFOX] ❌ API key validation failed: API key is not configured")
            raise Exception("Lamonfox API key is not configured. Please set LAMONFOX_API_KEY environment variable.")
        
        logger.info("[LAMONFOX] ✅ API key validation passed - proceeding with API request")
        
        # Validate text input
        if not text or not text.strip():
            logger.error("[LAMONFOX] ❌ Text validation failed: Text is empty or whitespace")
            raise Exception("Text input is required for voice generation")
        
        logger.info(f"[LAMONFOX] ✅ Text validation passed: {len(text.strip())} characters")
        
        url = f"{self.base_url}/audio/speech"
        
        data = {
            "input": text,
            "voice": voice,
            "response_format": response_format
        }
        
        logger.info(f"[LAMONFOX] Request URL: {url}")
        logger.info(f"[LAMONFOX] Request data keys: {list(data.keys())}")
        logger.info(f"[LAMONFOX] Voice: {voice}, Format: {response_format}")
        
        # Log API key info (safely)
        if self.api_key:
            key_preview = f"{self.api_key[:10]}...{self.api_key[-5:]}" if len(self.api_key) > 15 else f"{self.api_key[:5]}***"
            logger.info(f"[LAMONFOX] API key used in request:")
            logger.info(f"  - Preview: {key_preview}")
            logger.info(f"  - First 6 chars: {self.api_key[:6]}")
            logger.info(f"  - Last 6 chars: {self.api_key[-6:]}")
        else:
            logger.error("[LAMONFOX] API key: NOT SET")
        
        # Make request directly (no proxy)
        logger.info("[LAMONFOX] Creating HTTP client with 60s timeout")
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                logger.info("[LAMONFOX] Sending POST request to Lamonfox API...")
                
                response = await client.post(url, json=data, headers=self.headers)
                
                logger.info(f"[LAMONFOX] Response received: Status {response.status_code}")
                logger.info(f"[LAMONFOX] Response headers: {dict(response.headers)}")
                logger.info(f"[LAMONFOX] Response content length: {len(response.content)} bytes")
                
                response.raise_for_status()
                
                logger.info(f"[LAMONFOX] ✅ Voice generated successfully")
                logger.info(f"[LAMONFOX] Audio data size: {len(response.content)} bytes")
                logger.info("-" * 80)
                
                return response.content
                
            except httpx.HTTPStatusError as e:
                # Handle HTTP errors from the API
                error_text = e.response.text if e.response else "Unknown error"
                status_code = e.response.status_code if e.response else 0
                
                logger.error("-" * 80)
                logger.error(f"[LAMONFOX ERROR] HTTP Status Error: {status_code}")
                logger.error(f"[LAMONFOX ERROR] Response text: {error_text[:500]}")
                
                # Try to parse JSON error response
                parsed_error = None
                try:
                    if e.response:
                        error_json = e.response.json()
                        logger.error(f"[LAMONFOX ERROR] Parsed JSON: {error_json}")
                        parsed_error = error_json
                        if isinstance(error_json, dict):
                            if "detail" in error_json:
                                detail = error_json["detail"]
                                if isinstance(detail, dict):
                                    message = detail.get("message", error_text)
                                    status_msg = detail.get("status", "")
                                    error_text = f"{status_msg}: {message}" if status_msg else message
                                else:
                                    error_text = str(detail)
                except Exception as parse_error:
                    logger.warning(f"[LAMONFOX ERROR] Could not parse error JSON: {parse_error}")
                
                logger.error(f"[LAMONFOX ERROR] Final error text: {error_text}")
                
                if self.api_key:
                    key_preview = f"{self.api_key[:10]}...{self.api_key[-5:]}" if len(self.api_key) > 15 else f"{self.api_key[:5]}***"
                    logger.error(f"[LAMONFOX ERROR] API Key used: {key_preview}")
                else:
                    logger.error("[LAMONFOX ERROR] API Key: NOT SET")
                
                # Create detailed error message
                error_message = error_text
                
                # Handle specific error cases
                if status_code == 401:
                    logger.error("[LAMONFOX ERROR] 401 Unauthorized - API key invalid or expired")
                    error_message = "Lamonfox API key is invalid or expired. Please check your API key configuration."
                elif status_code == 402:
                    logger.error("[LAMONFOX ERROR] 402 Payment Required - Free tier disabled or payment needed")
                    error_message = "Payment required. Your API key may be on a free tier that has been disabled. Please upgrade to a paid plan or contact Lamonfox support."
                elif status_code == 429:
                    logger.error("[LAMONFOX ERROR] 429 Rate Limit Exceeded")
                    error_message = "Lamonfox API rate limit exceeded. Please try again later."
                elif status_code == 400:
                    logger.error("[LAMONFOX ERROR] 400 Bad Request")
                    # Check for unusual activity error
                    if "unusual_activity" in error_text.lower() or "free tier" in error_text.lower():
                        logger.error("[LAMONFOX ERROR] Detected unusual activity or free tier flag")
                        error_message = (
                            "Lamonfox API Error: Your account is being treated as Free Tier and has been flagged for unusual activity. "
                            "This can happen if:\n"
                            "1. Your API key is from a free account (even if you purchased credits)\n"
                            "2. Railway's IP address is flagged as a proxy/VPN\n"
                            "3. Your paid account needs to be activated\n\n"
                            "SOLUTION: Please contact Lamonfox support at https://lemonfox.ai with:\n"
                            "- Your API key (they can verify if it's paid)\n"
                            "- Request to whitelist Railway's IP addresses\n"
                            "- Ask them to activate your paid subscription\n\n"
                            f"Original error: {error_text}"
                        )
                    else:
                        error_message = f"Invalid request: {error_text}"
                else:
                    logger.error(f"[LAMONFOX ERROR] Unhandled HTTP status: {status_code}")
                    error_message = f"Voice generation failed (HTTP {status_code}): {error_text}"
                
                # Raise exception with detailed error
                exception = Exception(error_message)
                exception.status_code = status_code
                exception.parsed_error = parsed_error
                exception.raw_error = error_text
                raise exception
                    
            except httpx.TimeoutException as e:
                logger.error("-" * 80)
                logger.error(f"[LAMONFOX ERROR] TimeoutException: Request timed out after 60 seconds")
                logger.error(f"[LAMONFOX ERROR] Exception details: {str(e)}")
                logger.error("-" * 80)
                exception = Exception("Voice generation request timed out. Please try again.")
                exception.error_type = "TIMEOUT"
                raise exception
            except Exception as e:
                logger.error("-" * 80)
                logger.error(f"[LAMONFOX ERROR] Unexpected error type: {type(e).__name__}")
                logger.error(f"[LAMONFOX ERROR] Error message: {str(e)}")
                import traceback
                logger.error(f"[LAMONFOX ERROR] Traceback:\n{traceback.format_exc()}")
                logger.error("-" * 80)
                raise Exception(f"Voice generation failed: {str(e)}")
    
    async def get_voices(self):
        """
        Get available voices from Lamonfox API
        Note: This endpoint may vary - check Lamonfox documentation
        """
        # If Lamonfox provides a voices endpoint, implement it here
        # For now, return common voices
        return [
            {"id": "sarah", "name": "Sarah"},
            {"id": "james", "name": "James"},
            {"id": "emma", "name": "Emma"},
            {"id": "william", "name": "William"},
        ]

