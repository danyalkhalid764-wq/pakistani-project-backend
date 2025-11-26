from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models import User, Payment, Admin
from schemas import UserCreate, UserLogin, UserResponse, Token, AdminLogin, AdminLoginResponse, AdminUpdateCredentials
from utils.jwt_handler import verify_password, get_password_hash, create_access_token, verify_token
from datetime import timedelta, datetime

router = APIRouter()

# OAuth2PasswordBearer with auto_error=False to allow OPTIONS preflight requests
# This is critical for CORS to work properly
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


# Explicit OPTIONS handlers for CORS preflight requests
# FastAPI's CORS middleware should handle these automatically, but explicit handlers
# ensure compatibility with all browsers and prevent validation errors
from fastapi import Request
from fastapi.responses import Response

@router.options("/register")
@router.options("/login")
@router.options("/me")
async def options_handler(request: Request):
    """Handle CORS preflight OPTIONS requests - no validation, just return 200"""
    # Return empty 200 response - CORS middleware will add headers
    # This handler prevents FastAPI from trying to validate the OPTIONS request
    return Response(status_code=200)


@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    try:
        print(f"📝 Registration attempt for email: {user.email}", flush=True)
        
        # Check if user already exists
        db_user = db.query(User).filter(User.email == user.email).first()
        if db_user:
            print(f"⚠️ Email already registered: {user.email}", flush=True)
            raise HTTPException(status_code=400, detail="Email already registered")

        # Create new user
        print(f"🔐 Hashing password for user: {user.email}", flush=True)
        hashed_password = get_password_hash(user.password)
        
        print(f"👤 Creating user object: {user.name}, {user.email}", flush=True)
        db_user = User(
            name=user.name,
            email=user.email,
            password_hash=hashed_password,
            plan="Free",
            daily_voice_count=0,
        )

        print(f"💾 Adding user to database...", flush=True)
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        print(f"✅ User created successfully: ID={db_user.id}, Email={db_user.email}", flush=True)

        return UserResponse(
            id=db_user.id,
            name=db_user.name,
            email=db_user.email,
            plan=db_user.plan,
            daily_voice_count=db_user.daily_voice_count or 0,
            created_at=db_user.created_at
        )
    except HTTPException:
        # Re-raise HTTP exceptions (they already have proper status codes and CORS headers)
        raise
    except Exception as e:
        # Log the error and re-raise as HTTPException with CORS-friendly response
        import traceback
        error_detail = str(e)
        traceback_str = traceback.format_exc()
        print(f"❌ Registration error: {error_detail}", flush=True)
        print(f"Traceback: {traceback_str}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {error_detail}"
        )


@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    try:
        print(f"🔐 Login attempt for email: {user_credentials.email}", flush=True)
        
        # Query user from database
        user = db.query(User).filter(User.email == user_credentials.email).first()
        
        if not user:
            print(f"⚠️ User not found: {user_credentials.email}", flush=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Verify password
        if not verify_password(user_credentials.password, user.password_hash):
            print(f"⚠️ Invalid password for user: {user_credentials.email}", flush=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        print(f"✅ Password verified for user: {user_credentials.email}", flush=True)
        
        # Create access token
        access_token_expires = timedelta(minutes=30)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        
        print(f"✅ Login successful for user: {user_credentials.email} (ID: {user.id})", flush=True)
        
        return {"access_token": access_token, "token_type": "bearer"}
        
    except HTTPException:
        # Re-raise HTTP exceptions (they already have proper status codes and CORS headers)
        raise
    except Exception as e:
        # Log the error and re-raise as HTTPException with CORS-friendly response
        import traceback
        error_detail = str(e)
        traceback_str = traceback.format_exc()
        print(f"❌ Login error: {error_detail}", flush=True)
        print(f"Traceback: {traceback_str}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {error_detail}"
        )


def get_current_user(token: Optional[str] = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Get current authenticated user from JWT token.
    Raises exception if token is missing or invalid.
    For admin users, creates a fake user object if not in database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Token is required for authenticated endpoints
    if token is None:
        raise credentials_exception

    email = verify_token(token)
    if email is None:
        raise credentials_exception

    # Check if this is the admin email (hardcoded admin)
    ADMIN_EMAIL = "admin@myaistudio.com"
    if email == ADMIN_EMAIL:
        # Create a fake admin user object (not in database)
        class FakeAdminUser:
            def __init__(self):
                self.id = 0
                self.name = "Sohaib"
                self.email = ADMIN_EMAIL
                self.plan = "Admin"
                self.daily_voice_count = 0
                self.total_tokens_used = 0
                self.requested = False
                self.created_at = None
        
        return FakeAdminUser()

    # For regular users, query the database
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    return user


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        plan=current_user.plan,
        daily_voice_count=(current_user.daily_voice_count or 0) if hasattr(current_user, 'daily_voice_count') else 0,
        created_at=current_user.created_at
    )


# =======================
# Admin Endpoints
# =======================

@router.options("/admin/login")
@router.options("/admin/users")
async def admin_options_handler(request: Request):
    """Handle CORS preflight OPTIONS requests for admin endpoints"""
    return Response(status_code=200)


@router.post("/admin/login", response_model=AdminLoginResponse)
async def admin_login(credentials: AdminLogin, db: Session = Depends(get_db)):
    """Simple admin login - matches name and password from database"""
    try:
        print(f"[ADMIN LOGIN] Admin login attempt for: {credentials.name}", flush=True)
        
        # Query admin from database
        admin = db.query(Admin).filter(Admin.name == credentials.name).first()
        
        if not admin:
            print(f"[ADMIN LOGIN] ❌ Admin not found: {credentials.name}", flush=True)
            return AdminLoginResponse(
                success=False,
                message="Login unsuccessful"
            )
        
        # Check if password matches
        if admin.password != credentials.password:
            print(f"[ADMIN LOGIN] ❌ Password mismatch for admin: {credentials.name}", flush=True)
            return AdminLoginResponse(
                success=False,
                message="Login unsuccessful"
            )
        
        print(f"[ADMIN LOGIN] ✅ Login successful for admin: {credentials.name}", flush=True)
        return AdminLoginResponse(
            success=True,
            message="Login successful"
        )
        
    except Exception as e:
        print(f"[ADMIN LOGIN] ❌ Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return AdminLoginResponse(
            success=False,
            message="Login unsuccessful"
        )


def check_admin(current_user: User = Depends(get_current_user)):
    """Check if current user is admin - checks by email"""
    ADMIN_EMAIL = "admin@myaistudio.com"
    # Check if the user's email matches admin email
    if current_user.email != ADMIN_EMAIL:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.get("/admin/users")
async def get_all_users(
    db: Session = Depends(get_db)
):
    """Get all users - admin only (no authentication required)"""
    try:
        # Exclude admin user from results
        all_users = db.query(User).filter(User.name != "Sohaib").all()
        
        free_users = [u for u in all_users if u.plan == "Free" and (not hasattr(u, 'requested') or not u.requested)]
        paid_users = [u for u in all_users if u.plan == "Paid" and (not hasattr(u, 'requested') or not u.requested)]
        requested_users = [u for u in all_users if hasattr(u, 'requested') and u.requested == True]
        
        def format_user(user):
            return {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "plan": user.plan,
                "requested": getattr(user, 'requested', False),
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "daily_voice_count": user.daily_voice_count or 0,
                "total_tokens_used": user.total_tokens_used or 0,
            }
        
        return {
            "free_users": [format_user(u) for u in free_users],
            "paid_users": [format_user(u) for u in paid_users],
            "requested_users": [format_user(u) for u in requested_users],
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print(f"❌ Error fetching users: {str(e)}", flush=True)
        print(f"Traceback: {traceback.format_exc()}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch users: {str(e)}"
        )


@router.get("/admin/users/{user_id}/payments")
async def get_user_payments(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Get user payments - admin only (no authentication required)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    payments = db.query(Payment).filter(Payment.user_id == user_id).all()
    
    return {
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "plan": user.plan,
            "requested": getattr(user, 'requested', False),
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "daily_voice_count": user.daily_voice_count or 0,
            "total_tokens_used": user.total_tokens_used or 0,
        },
        "payments": [
            {
                "id": p.id,
                "amount": p.amount,
                "status": p.status,
                "transaction_id": p.transaction_id,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in payments
        ]
    }


@router.put("/admin/users/{user_id}/accept")
async def accept_user_request(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Accept user request - admin only (no authentication required)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.requested = False
    user.plan = "Paid"
    db.commit()
    db.refresh(user)
    
    return {"success": True, "message": "User request accepted"}


@router.put("/admin/users/{user_id}/reject")
async def reject_user_request(
    user_id: int,
    db: Session = Depends(get_db)
):
    """Reject user request - admin only (no authentication required)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.requested = False
    db.commit()
    db.refresh(user)
    
    return {"success": True, "message": "User request rejected"}


@router.put("/admin/credentials")
async def update_admin_credentials(
    credentials: AdminUpdateCredentials,
    db: Session = Depends(get_db)
):
    """Update admin credentials - requires current password (no JWT auth)"""
    try:
        # Find admin by name from request (since no JWT, we need to identify admin differently)
        # For simplicity, we'll require the admin to provide their current name in the request
        # Or we can make it so it updates the first admin (since there's only one)
        
        # Get the default admin (Sohaib) - for now, we'll update the first admin
        admin = db.query(Admin).first()
        
        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")
        
        # Verify current password (plain text comparison since we're storing plain passwords)
        if admin.password != credentials.current_password:
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        
        # Update name if provided
        if credentials.name and credentials.name.strip():
            new_name = credentials.name.strip()
            # Check if name already exists
            existing = db.query(Admin).filter(Admin.name == new_name, Admin.id != admin.id).first()
            if existing:
                raise HTTPException(status_code=400, detail="Name already taken")
            admin.name = new_name
        
        # Update password if provided
        if credentials.password:
            admin.password = credentials.password
        
        db.commit()
        db.refresh(admin)
        
        return {"success": True, "message": "Credentials updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error updating admin credentials: {str(e)}", flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update credentials: {str(e)}"
        )
