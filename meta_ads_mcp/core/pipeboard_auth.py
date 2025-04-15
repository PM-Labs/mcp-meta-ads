"""Authentication with Meta Ads API via pipeboard.co."""

import os
import json
import time
import requests
from pathlib import Path
import platform
from typing import Optional, Dict, Any
from .utils import logger

# Enable more detailed logging
import logging
logger.setLevel(logging.DEBUG)

# Base URL for pipeboard API
#PIPEBOARD_API_BASE = "https://pipeboard.co/api"
PIPEBOARD_API_BASE = "http://localhost:3000/api"

class TokenInfo:
    """Stores token information including expiration"""
    def __init__(self, access_token: str, expires_at: str = None, token_type: str = None):
        self.access_token = access_token
        self.expires_at = expires_at
        self.token_type = token_type
        self.created_at = int(time.time())
        logger.debug(f"TokenInfo created. Expires at: {expires_at if expires_at else 'Not specified'}")
    
    def is_expired(self) -> bool:
        """Check if the token is expired"""
        if not self.expires_at:
            logger.debug("No expiration date set for token, assuming not expired")
            return False  # If no expiration is set, assume it's not expired
        
        # Parse ISO 8601 date format to timestamp
        try:
            # Convert the expires_at string to a timestamp
            # Format is like "2023-12-31T23:59:59.999Z" or "2023-12-31T23:59:59.999+00:00"
            from datetime import datetime
            
            # Remove the Z suffix if present and handle +00:00 format
            expires_at_str = self.expires_at
            if expires_at_str.endswith('Z'):
                expires_at_str = expires_at_str[:-1]  # Remove Z
                
            # Handle microseconds if present
            if '.' in expires_at_str:
                datetime_format = "%Y-%m-%dT%H:%M:%S.%f"
            else:
                datetime_format = "%Y-%m-%dT%H:%M:%S"
                
            # Handle timezone offset
            timezone_offset = "+00:00"
            if "+" in expires_at_str:
                expires_at_str, timezone_offset = expires_at_str.split("+")
                timezone_offset = "+" + timezone_offset
            
            # Parse the datetime without timezone info
            expires_datetime = datetime.strptime(expires_at_str, datetime_format)
            
            # Convert to timestamp (assume UTC)
            expires_timestamp = expires_datetime.timestamp()
            current_time = time.time()
            
            # Check if token is expired and log result
            is_expired = current_time > expires_timestamp
            time_diff = expires_timestamp - current_time
            if is_expired:
                logger.debug(f"Token is expired! Current time: {datetime.fromtimestamp(current_time)}, " 
                             f"Expires at: {datetime.fromtimestamp(expires_timestamp)}, "
                             f"Expired {abs(time_diff):.0f} seconds ago")
            else:
                logger.debug(f"Token is still valid. Expires at: {datetime.fromtimestamp(expires_timestamp)}, "
                             f"Time remaining: {time_diff:.0f} seconds")
            
            return is_expired
        except Exception as e:
            logger.error(f"Error parsing expiration date: {e}")
            # Log the actual value to help diagnose format issues
            logger.error(f"Invalid expires_at value: '{self.expires_at}'")
            # Log detailed error information
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return False  # If we can't parse the date, assume it's not expired
    
    def serialize(self) -> Dict[str, Any]:
        """Convert to a dictionary for storage"""
        return {
            "access_token": self.access_token,
            "expires_at": self.expires_at,
            "token_type": self.token_type,
            "created_at": self.created_at
        }
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> 'TokenInfo':
        """Create from a stored dictionary"""
        logger.debug(f"Deserializing token data with keys: {', '.join(data.keys())}")
        if 'expires_at' in data:
            logger.debug(f"Token expires_at from cache: {data['expires_at']}")
        
        token = cls(
            access_token=data.get("access_token", ""),
            expires_at=data.get("expires_at"),
            token_type=data.get("token_type")
        )
        token.created_at = data.get("created_at", int(time.time()))
        return token


class PipeboardAuthManager:
    """Manages authentication with Meta APIs via pipeboard.co"""
    def __init__(self):
        self.api_token = os.environ.get("PIPEBOARD_API_TOKEN", "")
        logger.debug(f"PipeboardAuthManager initialized with API token: {self.api_token[:5]}..." if self.api_token else "No API token")
        self.token_info = None
        self._load_cached_token()
    
    def _get_token_cache_path(self) -> Path:
        """Get the platform-specific path for token cache file"""
        if platform.system() == "Windows":
            base_path = Path(os.environ.get("APPDATA", ""))
        elif platform.system() == "Darwin":  # macOS
            base_path = Path.home() / "Library" / "Application Support"
        else:  # Assume Linux/Unix
            base_path = Path.home() / ".config"
        
        # Create directory if it doesn't exist
        cache_dir = base_path / "meta-ads-mcp"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        cache_path = cache_dir / "pipeboard_token_cache.json"
        logger.debug(f"Token cache path: {cache_path}")
        return cache_path
    
    def _load_cached_token(self) -> bool:
        """Load token from cache if available"""
        cache_path = self._get_token_cache_path()
        
        if not cache_path.exists():
            logger.debug(f"Token cache file not found at {cache_path}")
            return False
        
        try:
            with open(cache_path, "r") as f:
                logger.debug(f"Reading token cache from {cache_path}")
                data = json.load(f)
                self.token_info = TokenInfo.deserialize(data)
                
                # Log token details (partial token for security)
                masked_token = self.token_info.access_token[:10] + "..." + self.token_info.access_token[-5:] if self.token_info.access_token else "None"
                logger.debug(f"Loaded token: {masked_token}")
                
                # Check if token is expired
                if self.token_info.is_expired():
                    logger.info("Cached token is expired")
                    self.token_info = None
                    return False
                
                logger.info(f"Loaded cached token (expires at {self.token_info.expires_at})")
                return True
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing token cache file: {e}")
            logger.debug("Token cache file might be corrupted, trying to read raw content")
            try:
                with open(cache_path, "r") as f:
                    raw_content = f.read()
                logger.debug(f"Raw cache file content (first 100 chars): {raw_content[:100]}")
            except Exception as e2:
                logger.error(f"Could not read raw cache file: {e2}")
            return False
        except Exception as e:
            logger.error(f"Error loading cached token: {e}")
            return False
    
    def _save_token_to_cache(self) -> None:
        """Save token to cache file"""
        if not self.token_info:
            logger.debug("No token to save to cache")
            return
        
        cache_path = self._get_token_cache_path()
        
        try:
            token_data = self.token_info.serialize()
            logger.debug(f"Saving token to cache. Expires at: {token_data.get('expires_at')}")
            
            with open(cache_path, "w") as f:
                json.dump(token_data, f)
            logger.info(f"Token cached at: {cache_path}")
        except Exception as e:
            logger.error(f"Error saving token to cache: {e}")
    
    def initiate_auth_flow(self) -> Dict[str, str]:
        """
        Initiate the Meta OAuth flow via pipeboard.co
        
        Returns:
            Dict with loginUrl and status info
        """
        if not self.api_token:
            logger.error("No PIPEBOARD_API_TOKEN environment variable set")
            raise ValueError("No PIPEBOARD_API_TOKEN environment variable set")
            
        url = f"{PIPEBOARD_API_BASE}/meta/auth"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        logger.debug(f"Initiating auth flow with POST request to {url}")
        
        try:
            response = requests.post(url, headers=headers)
            logger.debug(f"Auth flow response status: {response.status_code}")
            
            # Better error handling
            if response.status_code != 200:
                logger.error(f"Auth flow error: HTTP {response.status_code}")
                logger.error(f"Response content: {response.text}")
                response.raise_for_status()
                
            data = response.json()
            
            # Log auth flow response (without sensitive information)
            if 'loginUrl' in data:
                logger.debug(f"Auth flow initiated successfully with login URL: {data['loginUrl'][:30]}...")
            else:
                logger.warning(f"Auth flow response missing loginUrl field. Response keys: {', '.join(data.keys())}")
            
            return data
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error to Pipeboard: {e}")
            logger.debug(f"Attempting to connect to: {PIPEBOARD_API_BASE}")
            raise
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout connecting to Pipeboard: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Error initiating auth flow: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error initiating auth flow: {e}")
            raise
    
    def get_access_token(self, force_refresh: bool = False) -> Optional[str]:
        """
        Get the current access token, refreshing if necessary or if forced
        
        Args:
            force_refresh: Force token refresh even if cached token exists
            
        Returns:
            Access token if available, None otherwise
        """
        # Check if we already have a valid token
        if not force_refresh and self.token_info and not self.token_info.is_expired():
            logger.debug("Using existing valid token")
            return self.token_info.access_token
        
        logger.debug(f"Getting new token (force_refresh={force_refresh})")
        
        # If force refresh or no token/expired token, get a new one from Pipeboard
        try:
            # Make a request to get the token
            url = f"{PIPEBOARD_API_BASE}/meta/token"
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
            
            logger.debug(f"Requesting token from {url}")
            
            response = requests.get(url, headers=headers)
            logger.debug(f"Token request response status: {response.status_code}")
            
            # Better error handling with response content
            if response.status_code != 200:
                logger.error(f"Token request error: HTTP {response.status_code}")
                logger.error(f"Response content: {response.text}")
                response.raise_for_status()
                
            data = response.json()
            
            # Validate response data
            if "access_token" not in data:
                logger.error(f"No access_token in response. Response keys: {', '.join(data.keys())}")
                if "error" in data:
                    logger.error(f"Error in response: {data['error']}")
                return None
                
            # Create new token info
            self.token_info = TokenInfo(
                access_token=data.get("access_token"),
                expires_at=data.get("expires_at"),
                token_type=data.get("token_type", "bearer")
            )
            
            # Save to cache
            self._save_token_to_cache()
            
            masked_token = self.token_info.access_token[:10] + "..." + self.token_info.access_token[-5:] if self.token_info.access_token else "None"
            logger.info(f"Successfully retrieved access token from pipeboard.co: {masked_token}")
            return self.token_info.access_token
        except requests.RequestException as e:
            status_code = e.response.status_code if hasattr(e, 'response') and e.response else None
            response_text = e.response.text if hasattr(e, 'response') and e.response else "No response"
            
            if status_code == 401:
                logger.error(f"Unauthorized: Check your PIPEBOARD_API_TOKEN. Response: {response_text}")
            elif status_code == 404:
                logger.error(f"No token available: You might need to complete authorization first. Response: {response_text}")
                # Provide the login URL
                try:
                    auth_data = self.initiate_auth_flow()
                    logger.info(f"Please visit this URL to authorize: {auth_data.get('loginUrl', 'No URL available')}")
                except Exception as auth_error:
                    logger.error(f"Error initiating auth flow after 404: {auth_error}")
            else:
                logger.error(f"Error getting access token (status {status_code}): {e}")
                logger.error(f"Response content: {response_text}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting access token: {e}")
            return None
        
    def invalidate_token(self) -> None:
        """Invalidate the current token, usually because it has expired or is invalid"""
        if self.token_info:
            logger.info(f"Invalidating token: {self.token_info.access_token[:10]}...")
            self.token_info = None
            
            # Remove the cached token file
            try:
                cache_path = self._get_token_cache_path()
                if cache_path.exists():
                    os.remove(cache_path)
                    logger.info(f"Removed cached token file: {cache_path}")
                else:
                    logger.debug(f"No token cache file to remove: {cache_path}")
            except Exception as e:
                logger.error(f"Error removing cached token file: {e}")
        else:
            logger.debug("No token to invalidate")

    def test_token_validity(self) -> bool:
        """
        Test if the current token is valid with the Meta Graph API
        
        Returns:
            True if valid, False otherwise
        """
        if not self.token_info or not self.token_info.access_token:
            logger.debug("No token to test")
            return False
            
        try:
            # Make a simple request to the /me endpoint to test the token
            META_GRAPH_API_VERSION = "v20.0"
            url = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/me"
            headers = {"Authorization": f"Bearer {self.token_info.access_token}"}
            
            logger.debug(f"Testing token validity with request to {url}")
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"Token is valid. User ID: {data.get('id')}")
                return True
            else:
                logger.error(f"Token validation failed with status {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error testing token validity: {e}")
            return False


# Create singleton instance
pipeboard_auth_manager = PipeboardAuthManager() 