"""
Firebase Authentication Service

Handles Firebase Admin SDK initialization and token verification.
"""
import os
import json
import logging
from typing import Optional
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, auth
from firebase_admin.auth import InvalidIdTokenError, ExpiredIdTokenError

logger = logging.getLogger(__name__)


class FirebaseService:
    """
    Firebase Admin SDK wrapper for token verification.
    """
    
    _initialized: bool = False
    
    @classmethod
    def initialize(cls) -> bool:
        """
        Initialize Firebase Admin SDK.
        
        Looks for credentials in:
        1. FIREBASE_CREDENTIALS_PATH environment variable
        2. firebase-adminsdk.json in backend root
        3. GOOGLE_APPLICATION_CREDENTIALS environment variable
        
        Returns:
            True if initialized successfully, False otherwise.
        """
        if cls._initialized:
            return True
        
        try:
            # 1. Try JSON content from environment variable (Best for Render/Heroku)
            json_creds = os.getenv("FIREBASE_CREDENTIALS_JSON")
            if json_creds:
                try:
                    cred_dict = json.loads(json_creds)
                    cred = credentials.Certificate(cred_dict)
                    firebase_admin.initialize_app(cred)
                    cls._initialized = True
                    logger.info("Firebase initialized from FIREBASE_CREDENTIALS_JSON env var")
                    return True
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse FIREBASE_CREDENTIALS_JSON: {e}")
            
            # 2. Try explicit path
            cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
            if cred_path and Path(cred_path).exists():
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                cls._initialized = True
                logger.info(f"Firebase initialized from {cred_path}")
                return True
            
            # Try default location
            default_path = Path(__file__).parent.parent.parent / "firebase-adminsdk.json"
            if default_path.exists():
                cred = credentials.Certificate(str(default_path))
                firebase_admin.initialize_app(cred)
                cls._initialized = True
                logger.info(f"Firebase initialized from {default_path}")
                return True
            
            # Try GOOGLE_APPLICATION_CREDENTIALS (for cloud deployments)
            if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                firebase_admin.initialize_app()
                cls._initialized = True
                logger.info("Firebase initialized from GOOGLE_APPLICATION_CREDENTIALS")
                return True
            
            logger.warning("No Firebase credentials found. Auth will fail.")
            return False
            
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            return False
    
    @classmethod
    def verify_token(cls, id_token: str) -> Optional[dict]:
        """
        Verify a Firebase ID token.
        
        Args:
            id_token: The Firebase ID token from the client.
            
        Returns:
            Decoded token dict with user info, or None if invalid.
        """
        if not cls._initialized:
            cls.initialize()
        
        if not cls._initialized:
            logger.error("Firebase not initialized, cannot verify token")
            return None
        
        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token
            
        except InvalidIdTokenError as e:
            logger.warning(f"Invalid Firebase token: {e}")
            return None
            
        except ExpiredIdTokenError as e:
            logger.warning(f"Expired Firebase token: {e}")
            return None
            
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return None
    
    @classmethod
    def get_user_info(cls, id_token: str) -> Optional[dict]:
        """
        Get user info from a Firebase ID token.
        
        Args:
            id_token: The Firebase ID token.
            
        Returns:
            Dict with uid, email, display_name, or None if invalid.
        """
        decoded = cls.verify_token(id_token)
        if not decoded:
            return None
        
        return {
            "uid": decoded.get("uid"),
            "email": decoded.get("email"),
            "display_name": decoded.get("name"),
            "email_verified": decoded.get("email_verified", False),
        }


# Singleton instance for convenience
firebase_service = FirebaseService()
