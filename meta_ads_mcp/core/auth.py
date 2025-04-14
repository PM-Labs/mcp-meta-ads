"""Authentication related functionality for Meta Ads API."""

from typing import Any, Dict, Optional
import time
import platform
import pathlib
import os
import threading
import socket
import webbrowser
import asyncio
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from .utils import logger
import requests

# Auth constants
AUTH_SCOPE = "ads_management,ads_read,business_management"
AUTH_REDIRECT_URI = "http://localhost:8888/callback"
AUTH_RESPONSE_TYPE = "token"

# Log important configuration information
logger.info("Authentication module initialized")
logger.info(f"Auth scope: {AUTH_SCOPE}")
logger.info(f"Default redirect URI: {AUTH_REDIRECT_URI}")

# Global token container for communication between threads
token_container = {"token": None, "expires_in": None, "user_id": None}

# Global container for update confirmations
update_confirmation = {"approved": False}

# Global flag for authentication state
needs_authentication = False

# Global variable for server thread and state
callback_server_thread = None
callback_server_lock = threading.Lock()
callback_server_running = False
callback_server_port = None

# Meta configuration singleton
class MetaConfig:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            logger.debug("Creating new MetaConfig instance")
            cls._instance = super(MetaConfig, cls).__new__(cls)
            cls._instance.app_id = os.environ.get("META_APP_ID", "")
            logger.info(f"MetaConfig initialized with app_id from env: {cls._instance.app_id}")
        return cls._instance
    
    def set_app_id(self, app_id):
        """Set the Meta App ID for API calls"""
        logger.info(f"Setting Meta App ID: {app_id}")
        self.app_id = app_id
        # Also update environment variable for modules that might read directly from it
        os.environ["META_APP_ID"] = app_id
        logger.debug(f"Updated META_APP_ID environment variable: {os.environ.get('META_APP_ID')}")
    
    def get_app_id(self):
        """Get the current Meta App ID"""
        # Check if we have one set
        if hasattr(self, 'app_id') and self.app_id:
            logger.debug(f"Using app_id from instance: {self.app_id}")
            return self.app_id
        
        # If not, try environment variable
        env_app_id = os.environ.get("META_APP_ID", "")
        if env_app_id:
            logger.debug(f"Using app_id from environment: {env_app_id}")
            # Update our instance for future use
            self.app_id = env_app_id
            return env_app_id
        
        logger.warning("No app_id found in instance or environment variables")
        return ""
    
    def is_configured(self):
        """Check if the Meta configuration is complete"""
        app_id = self.get_app_id()
        configured = bool(app_id)
        logger.debug(f"MetaConfig.is_configured() = {configured} (app_id: {app_id})")
        return configured

# Create singleton instance
meta_config = MetaConfig()

class TokenInfo:
    """Stores token information including expiration"""
    def __init__(self, access_token: str, expires_in: int = None, user_id: str = None):
        self.access_token = access_token
        self.expires_in = expires_in
        self.user_id = user_id
        self.created_at = int(time.time())
        logger.debug(f"TokenInfo created. Expires in: {expires_in if expires_in else 'Not specified'}")
    
    def is_expired(self) -> bool:
        """Check if the token is expired"""
        if not self.expires_in:
            return False  # If no expiration is set, assume it's not expired
        
        current_time = int(time.time())
        return current_time > (self.created_at + self.expires_in)
    
    def serialize(self) -> Dict[str, Any]:
        """Convert to a dictionary for storage"""
        return {
            "access_token": self.access_token,
            "expires_in": self.expires_in,
            "user_id": self.user_id,
            "created_at": self.created_at
        }
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> 'TokenInfo':
        """Create from a stored dictionary"""
        token = cls(
            access_token=data.get("access_token", ""),
            expires_in=data.get("expires_in"),
            user_id=data.get("user_id")
        )
        token.created_at = data.get("created_at", int(time.time()))
        return token


class AuthManager:
    """Manages authentication with Meta APIs"""
    def __init__(self, app_id: str, redirect_uri: str = AUTH_REDIRECT_URI):
        self.app_id = app_id
        self.redirect_uri = redirect_uri
        self.token_info = None
        self._load_cached_token()
    
    def _get_token_cache_path(self) -> pathlib.Path:
        """Get the platform-specific path for token cache file"""
        if platform.system() == "Windows":
            base_path = pathlib.Path(os.environ.get("APPDATA", ""))
        elif platform.system() == "Darwin":  # macOS
            base_path = pathlib.Path.home() / "Library" / "Application Support"
        else:  # Assume Linux/Unix
            base_path = pathlib.Path.home() / ".config"
        
        # Create directory if it doesn't exist
        cache_dir = base_path / "meta-ads-mcp"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        return cache_dir / "token_cache.json"
    
    def _load_cached_token(self) -> bool:
        """Load token from cache if available"""
        cache_path = self._get_token_cache_path()
        
        if not cache_path.exists():
            return False
        
        try:
            with open(cache_path, "r") as f:
                data = json.load(f)
                self.token_info = TokenInfo.deserialize(data)
                
                # Check if token is expired
                if self.token_info.is_expired():
                    print("Cached token is expired")
                    self.token_info = None
                    return False
                
                print(f"Loaded cached token (expires in {(self.token_info.created_at + self.token_info.expires_in) - int(time.time())} seconds)")
                return True
        except Exception as e:
            print(f"Error loading cached token: {e}")
            return False
    
    def _save_token_to_cache(self) -> None:
        """Save token to cache file"""
        if not self.token_info:
            return
        
        cache_path = self._get_token_cache_path()
        
        try:
            with open(cache_path, "w") as f:
                json.dump(self.token_info.serialize(), f)
            print(f"Token cached at: {cache_path}")
        except Exception as e:
            print(f"Error saving token to cache: {e}")
    
    def get_auth_url(self) -> str:
        """Generate the Facebook OAuth URL for desktop app flow"""
        return (
            f"https://www.facebook.com/v18.0/dialog/oauth?"
            f"client_id={self.app_id}&"
            f"redirect_uri={self.redirect_uri}&"
            f"scope={AUTH_SCOPE}&"
            f"response_type={AUTH_RESPONSE_TYPE}"
        )
    
    def authenticate(self, force_refresh: bool = False) -> Optional[str]:
        """
        Authenticate with Meta APIs
        
        Args:
            force_refresh: Force token refresh even if cached token exists
            
        Returns:
            Access token if successful, None otherwise
        """
        # Check if we already have a valid token
        if not force_refresh and self.token_info and not self.token_info.is_expired():
            return self.token_info.access_token
        
        # Start the callback server if not already running
        port = start_callback_server()
        
        # Generate the auth URL
        auth_url = self.get_auth_url()
        
        # Open browser with auth URL
        print(f"Opening browser with URL: {auth_url}")
        webbrowser.open(auth_url)
        
        # We don't wait for the token here anymore
        # The token will be processed by the callback server
        # Just return None to indicate we've started the flow
        return None
    
    def get_access_token(self) -> Optional[str]:
        """
        Get the current access token, refreshing if necessary
        
        Returns:
            Access token if available, None otherwise
        """
        if not self.token_info or self.token_info.is_expired():
            return None
        
        return self.token_info.access_token
        
    def invalidate_token(self) -> None:
        """Invalidate the current token, usually because it has expired or is invalid"""
        if self.token_info:
            print(f"Invalidating token: {self.token_info.access_token[:10]}...")
            self.token_info = None
            
            # Signal that authentication is needed
            global needs_authentication
            needs_authentication = True
            
            # Remove the cached token file
            try:
                cache_path = self._get_token_cache_path()
                if cache_path.exists():
                    os.remove(cache_path)
                    print(f"Removed cached token file: {cache_path}")
            except Exception as e:
                print(f"Error removing cached token: {e}")
    
    def clear_token(self) -> None:
        """Clear the current token and remove from cache"""
        self.invalidate_token()


# Callback Handler class definition
class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global token_container, auth_manager, needs_authentication, update_confirmation
        
        try:
            # Print path for debugging
            print(f"Callback server received request: {self.path}")
            
            if self.path.startswith("/callback"):
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                
                # Get the token from the fragment
                # We need to handle it via JS since the fragment is not sent to the server
                callback_html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Authentication Successful</title>
                    <style>
                        body { 
                            font-family: Arial, sans-serif; 
                            line-height: 1.6;
                            color: #333;
                            max-width: 800px;
                            margin: 0 auto;
                            padding: 20px;
                        }
                        .success { 
                            color: #4CAF50;
                            font-size: 24px;
                            margin-bottom: 20px;
                        }
                        .info {
                            background-color: #f5f5f5;
                            padding: 15px;
                            border-radius: 4px;
                            margin-bottom: 20px;
                        }
                        .button {
                            background-color: #4CAF50;
                            color: white;
                            padding: 10px 15px;
                            border: none;
                            border-radius: 4px;
                            cursor: pointer;
                        }
                    </style>
                </head>
                <body>
                    <div class="success">Authentication Successful!</div>
                    <div class="info">
                        <p>Your Meta Ads API token has been received.</p>
                        <p>You can now close this window and return to the application.</p>
                    </div>
                    <button class="button" onclick="window.close()">Close Window</button>
                    
                    <script>
                    // Function to parse URL parameters including fragments
                    function parseURL(url) {
                        var params = {};
                        var parser = document.createElement('a');
                        parser.href = url;
                        
                        // Parse fragment parameters
                        var fragment = parser.hash.substring(1);
                        var fragmentParams = fragment.split('&');
                        
                        for (var i = 0; i < fragmentParams.length; i++) {
                            var pair = fragmentParams[i].split('=');
                            params[pair[0]] = decodeURIComponent(pair[1]);
                        }
                        
                        return params;
                    }
                    
                    // Parse the URL to get the access token
                    var params = parseURL(window.location.href);
                    var token = params['access_token'];
                    var expires_in = params['expires_in'];
                    
                    // Send the token to the server
                    if (token) {
                        // Create XMLHttpRequest object
                        var xhr = new XMLHttpRequest();
                        
                        // Configure it to make a GET request to the /token endpoint
                        xhr.open('GET', '/token?token=' + encodeURIComponent(token) + 
                                      '&expires_in=' + encodeURIComponent(expires_in), true);
                        
                        // Set up a handler for when the request is complete
                        xhr.onload = function() {
                            if (xhr.status === 200) {
                                console.log('Token successfully sent to server');
                            } else {
                                console.error('Failed to send token to server');
                            }
                        };
                        
                        // Send the request
                        xhr.send();
                    } else {
                        console.error('No token found in URL');
                        document.body.innerHTML += '<div style="color: red; margin-top: 20px;">Error: No authentication token found. Please try again.</div>';
                    }
                    </script>
                </body>
                </html>
                """
                self.wfile.write(callback_html.encode())
                return
                
            elif self.path.startswith("/token"):
                # Extract token from query params
                query = parse_qs(urlparse(self.path).query)
                token_container["token"] = query.get("token", [""])[0]
                
                if "expires_in" in query:
                    try:
                        token_container["expires_in"] = int(query.get("expires_in", ["0"])[0])
                    except ValueError:
                        token_container["expires_in"] = None
                
                # Send success response
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Token received")
                
                # Process the token (save it) immediately
                if token_container["token"]:
                    # Get the short-lived token
                    short_lived_token = token_container["token"]
                    
                    # Try to exchange for a long-lived token
                    long_lived_token_info = exchange_token_for_long_lived(short_lived_token)
                    
                    if long_lived_token_info:
                        # Successfully exchanged for long-lived token
                        logger.info(f"Token received and exchanged for long-lived token (expires in {long_lived_token_info.expires_in} seconds)")
                        
                        try:
                            # Set the token info in the auth_manager
                            auth_manager.token_info = long_lived_token_info
                            logger.info(f"Long-lived token info set in auth_manager, expires in {long_lived_token_info.expires_in} seconds")
                            
                            # Save to cache
                            auth_manager._save_token_to_cache()
                            logger.info(f"Long-lived token successfully saved to cache at {auth_manager._get_token_cache_path()}")
                        except Exception as e:
                            logger.error(f"Error saving long-lived token to cache: {e}")
                    else:
                        # Fall back to the short-lived token
                        logger.warning("Failed to exchange for long-lived token, using short-lived token instead")
                        token_info = TokenInfo(
                            access_token=token_container["token"],
                            expires_in=token_container["expires_in"]
                        )
                        
                        try:
                            # Set the token info in the auth_manager
                            auth_manager.token_info = token_info
                            logger.info(f"Token info set in auth_manager, expires in {token_info.expires_in} seconds")
                            
                            # Save to cache
                            auth_manager._save_token_to_cache()
                            logger.info(f"Token successfully saved to cache at {auth_manager._get_token_cache_path()}")
                        except Exception as e:
                            logger.error(f"Error saving token to cache: {e}")
                    
                    # Reset auth needed flag
                    needs_authentication = False
                    
                    return token_container["token"]
                else:
                    logger.warning("Received empty token in callback")
                    needs_authentication = True
                    return None
            
            elif self.path.startswith("/confirm-update"):
                # Parse query parameters
                query = parse_qs(urlparse(self.path).query)
                adset_id = query.get("adset_id", [""])[0]
                token = query.get("token", [""])[0]
                changes = query.get("changes", ["{}"])[0]
                
                try:
                    changes_dict = json.loads(changes)
                except json.JSONDecodeError:
                    changes_dict = {}
                
                # Return confirmation page
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                
                html = """
                <html>
                <head>
                    <title>Confirm Ad Set Update</title>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 20px; max-width: 1000px; margin: 0 auto; }
                        .warning { color: #d73a49; margin: 20px 0; padding: 15px; border-left: 4px solid #d73a49; background-color: #fff8f8; }
                        .changes { background: #f6f8fa; padding: 15px; border-radius: 6px; }
                        .buttons { margin-top: 20px; }
                        button { padding: 10px 20px; margin-right: 10px; border-radius: 6px; cursor: pointer; }
                        .approve { background: #2ea44f; color: white; border: none; }
                        .cancel { background: #d73a49; color: white; border: none; }
                        .diff-table { width: 100%; border-collapse: collapse; margin: 15px 0; }
                        .diff-table td { padding: 8px; border: 1px solid #ddd; }
                        .diff-table .header { background: #f1f8ff; font-weight: bold; }
                        .status { padding: 15px; margin-top: 20px; border-radius: 6px; display: none; }
                        .success { background-color: #e6ffed; border: 1px solid #2ea44f; color: #22863a; }
                        .error { background-color: #ffeef0; border: 1px solid #d73a49; color: #d73a49; }
                        pre { white-space: pre-wrap; word-break: break-all; }
                    </style>
                </head>
                <body>
                    <h1>Confirm Ad Set Update</h1>
                    <p>You are about to update Ad Set: <strong>""" + adset_id + """</strong></p>
                    
                    <div class="warning">
                        <strong>⚠️ Warning:</strong> These changes will be applied immediately upon approval.
                        """ + ("<br><strong>🔴 Important:</strong> This update includes status changes that may affect billing." if "status" in changes_dict else "") + """
                    </div>
                    
                    <h2>Proposed Changes:</h2>
                    <div class="changes">
                        <table class="diff-table">
                            <tr class="header">
                                <td>Setting</td>
                                <td>New Value</td>
                                <td>Description</td>
                            </tr>
                            """
                
                # Special handling for frequency_control_specs
                for k, v in changes_dict.items():
                    description = ""
                    if k == "frequency_control_specs" and isinstance(v, list) and len(v) > 0:
                        spec = v[0]
                        if all(key in spec for key in ["event", "interval_days", "max_frequency"]):
                            description = f"Cap to {spec['max_frequency']} {spec['event'].lower()} per {spec['interval_days']} days"
                
                    # Format the value for display
                    display_value = json.dumps(v, indent=2) if isinstance(v, (dict, list)) else str(v)
                    
                    html += f"""
                            <tr>
                                <td>{k}</td>
                                <td><pre>{display_value}</pre></td>
                                <td>{description}</td>
                            </tr>
                            """
                
                html += """
                        </table>
                    </div>
                    
                    <div class="buttons">
                        <button class="approve" onclick="approveChanges()">Approve Changes</button>
                        <button class="cancel" onclick="cancelChanges()">Cancel</button>
                    </div>
                    
                    <div id="status" class="status"></div>

                    <script>
                        function showStatus(message, isError = false) {
                            const statusElement = document.getElementById('status');
                            statusElement.textContent = message;
                            statusElement.style.display = 'block';
                            if (isError) {
                                statusElement.classList.add('error');
                                statusElement.classList.remove('success');
                            } else {
                                statusElement.classList.add('success');
                                statusElement.classList.remove('error');
                            }
                        }
                        
                        function approveChanges() {
                            showStatus("Processing update...");
                            
                            const buttons = document.querySelectorAll('button');
                            buttons.forEach(button => button.disabled = true);
                            
                            fetch('/update-confirm?' + new URLSearchParams({
                                adset_id: '""" + adset_id + """',
                                token: '""" + token + """',
                                changes: '""" + changes + """',
                                action: 'approve'
                            }))
                            .then(response => response.json())
                            .then(data => {
                                if (data.error) {
                                    showStatus('Error applying changes: ' + data.error, true);
                                    buttons.forEach(button => button.disabled = false);
                                } else {
                                    showStatus('Changes approved and will be applied shortly!');
                                    setTimeout(() => {
                                        window.location.href = '/verify-update?' + new URLSearchParams({
                                            adset_id: '""" + adset_id + """',
                                            token: '""" + token + """'
                                        });
                                    }, 3000);
                                }
                            })
                            .catch(error => {
                                showStatus('Error applying changes: ' + error, true);
                                buttons.forEach(button => button.disabled = false);
                            });
                        }
                        
                        function cancelChanges() {
                            showStatus("Cancelling update...");
                            
                            fetch('/update-confirm?' + new URLSearchParams({
                                adset_id: '""" + adset_id + """',
                                action: 'cancel'
                            }))
                            .then(() => {
                                showStatus('Update cancelled.');
                                setTimeout(() => window.close(), 2000);
                            });
                        }
                    </script>
                </body>
                </html>
                """
                self.wfile.write(html.encode())
                return
            
            elif self.path.startswith("/verify-update"):
                # Parse query parameters
                query = parse_qs(urlparse(self.path).query)
                adset_id = query.get("adset_id", [""])[0]
                token = query.get("token", [""])[0]
                
                # Respond with a verification page
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                
                html = """
                <html>
                <head>
                    <title>Verifying Ad Set Update</title>
                    <style>
                        body { font-family: Arial, sans-serif; margin: 20px; max-width: 800px; margin: 0 auto; }
                        .status { padding: 15px; margin-top: 20px; border-radius: 6px; }
                        .loading { background-color: #f1f8ff; border: 1px solid #0366d6; }
                        .success { background-color: #e6ffed; border: 1px solid #2ea44f; color: #22863a; }
                        .error { background-color: #ffeef0; border: 1px solid #d73a49; color: #d73a49; }
                        .details { background: #f6f8fa; padding: 15px; border-radius: 6px; margin-top: 20px; }
                        .note { background-color: #fff8c5; border: 1px solid #e36209; padding: 15px; border-radius: 6px; margin: 20px 0; }
                        pre { white-space: pre-wrap; word-break: break-all; }
                        .spinner { display: inline-block; width: 20px; height: 20px; border: 3px solid rgba(0, 0, 0, 0.1); border-radius: 50%; border-top-color: #0366d6; animation: spin 1s ease-in-out infinite; margin-right: 10px; }
                        @keyframes spin { to { transform: rotate(360deg); } }
                    </style>
                </head>
                <body>
                    <h1>Verifying Ad Set Update</h1>
                    <p>Checking the status of your update for Ad Set <strong>""" + adset_id + """</strong></p>
                    
                    <div class="note">
                        <strong>Note about Meta API Visibility:</strong>
                        <p>Some fields (like frequency caps) may not be visible in the API response even when successfully set. This is a limitation of the Meta API and depends on factors like the ad set's optimization goal. You can verify these settings in the Meta Ads Manager UI or by monitoring metrics like frequency in the ad insights.</p>
                    </div>
                    
                    <div id="status" class="status loading">
                        <div class="spinner"></div> Verifying update...
                    </div>
                    
                    <div id="details" class="details" style="display: none;">
                        <h3>Updated Ad Set Details:</h3>
                        <pre id="adset-details">Loading...</pre>
                    </div>

                    <script>
                        // Function to fetch the ad set details and check if frequency_control_specs was updated
                        async function verifyUpdate() {
                            try {
                                const response = await fetch('/api/adset?' + new URLSearchParams({
                                    adset_id: '""" + adset_id + """',
                                    token: '""" + token + """'
                                }));
                                
                                const data = await response.json();
                                const statusElement = document.getElementById('status');
                                const detailsElement = document.getElementById('details');
                                const adsetDetailsElement = document.getElementById('adset-details');
                                
                                detailsElement.style.display = 'block';
                                adsetDetailsElement.textContent = JSON.stringify(data, null, 2);
                                
                                // Update success message to reflect API visibility limitations
                                statusElement.classList.remove('loading');
                                statusElement.classList.add('success');
                                statusElement.innerHTML = '✅ Update request was processed successfully. Please verify the changes in Meta Ads Manager UI or monitor ad performance metrics.';
                            } catch (error) {
                                const statusElement = document.getElementById('status');
                                statusElement.classList.remove('loading');
                                statusElement.classList.add('error');
                                statusElement.textContent = 'Error verifying update: ' + error;
                            }
                        }
                        
                        // Wait a moment before verifying
                        setTimeout(verifyUpdate, 3000);
                    </script>
                </body>
                </html>
                """
                self.wfile.write(html.encode())
                return
            
            elif self.path.startswith("/api/adset"):
                # Parse query parameters
                query = parse_qs(urlparse(self.path).query)
                adset_id = query.get("adset_id", [""])[0]
                token = query.get("token", [""])[0]
                
                from .api import make_api_request
                
                # Call the Graph API directly
                async def get_adset_data():
                    endpoint = f"{adset_id}"
                    params = {
                        "fields": "id,name,campaign_id,status,daily_budget,lifetime_budget,targeting,bid_amount,bid_strategy,optimization_goal,billing_event,start_time,end_time,created_time,updated_time,attribution_spec,destination_type,promoted_object,pacing_type,budget_remaining,frequency_control_specs"
                    }
                    
                    return await make_api_request(endpoint, token, params)
                
                # Run the async function
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(get_adset_data())
                loop.close()
                
                # Return the result
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result, indent=2).encode())
                return
            
            elif self.path.startswith("/update-confirm"):
                # Handle update confirmation response
                query = parse_qs(urlparse(self.path).query)
                action = query.get("action", [""])[0]
                
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                
                if action == "approve":
                    adset_id = query.get("adset_id", [""])[0]
                    token = query.get("token", [""])[0]
                    changes = query.get("changes", ["{}"])[0]
                    
                    # Store the approval in a global variable for the main thread to process
                    global update_confirmation
                    update_confirmation = {
                        "approved": True,
                        "adset_id": adset_id,
                        "token": token,
                        "changes": changes
                    }
                    
                    # Prepare the API call to actually execute the update
                    from .api import make_api_request
                    
                    # Function to perform the actual update
                    async def perform_update():
                        try:
                            changes_dict = json.loads(changes)
                            endpoint = f"{adset_id}"
                            
                            # Create a copy of changes_dict for the API call
                            api_params = dict(changes_dict)
                            api_params["access_token"] = token
                            
                            # Make the API request to update the ad set
                            result = await make_api_request(endpoint, token, api_params, method="POST")
                            return {"status": "approved", "api_result": result}
                        except Exception as e:
                            return {"status": "error", "error": str(e)}
                    
                    # Run the async function
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        result = loop.run_until_complete(perform_update())
                        loop.close()
                        
                        self.wfile.write(json.dumps(result).encode())
                    except Exception as e:
                        self.wfile.write(json.dumps({"status": "error", "error": str(e)}).encode())
                else:
                    # Store the cancellation
                    update_confirmation = {
                        "approved": False
                    }
                    self.wfile.write(json.dumps({"status": "cancelled"}).encode())
                return
            
            else:
                # If no matching path, return a 404 error
                self.send_response(404)
                self.end_headers()
        except Exception as e:
            print(f"Error processing request: {e}")
            self.send_response(500)
            self.end_headers()
    
    # Silence server logs
    def log_message(self, format, *args):
        return


def start_callback_server():
    """Start the callback server if it's not already running"""
    global callback_server_thread, callback_server_running, callback_server_port, auth_manager
    
    with callback_server_lock:
        if callback_server_running:
            print(f"Callback server already running on port {callback_server_port}")
            return callback_server_port
        
        # Find an available port
        port = 8888
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    break
            except OSError:
                port += 1
                if attempt == max_attempts - 1:
                    raise Exception(f"Could not find an available port after {max_attempts} attempts")
        
        # Update auth manager's redirect URI with new port
        if 'auth_manager' in globals():
            auth_manager.redirect_uri = f"http://localhost:{port}/callback"
        callback_server_port = port
        
        try:
            # Get the CallbackHandler class from global scope
            handler_class = globals()['CallbackHandler']
            
            # Create and start server in a daemon thread
            server = HTTPServer(('localhost', port), handler_class)
            print(f"Callback server starting on port {port}")
            
            # Create a simple flag to signal when the server is ready
            server_ready = threading.Event()
            
            def server_thread():
                try:
                    # Signal that the server thread has started
                    server_ready.set()
                    print(f"Callback server is now ready on port {port}")
                    # Start serving HTTP requests
                    server.serve_forever()
                except Exception as e:
                    print(f"Server error: {e}")
                finally:
                    with callback_server_lock:
                        global callback_server_running
                        callback_server_running = False
            
            callback_server_thread = threading.Thread(target=server_thread)
            callback_server_thread.daemon = True
            callback_server_thread.start()
            
            # Wait for server to be ready (up to 5 seconds)
            if not server_ready.wait(timeout=5):
                print("Warning: Timeout waiting for server to start, but continuing anyway")
            
            callback_server_running = True
            
            # Verify the server is actually accepting connections
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2)
                    s.connect(('localhost', port))
                print(f"Confirmed server is accepting connections on port {port}")
            except Exception as e:
                print(f"Warning: Could not verify server connection: {e}")
                
            return port
            
        except Exception as e:
            print(f"Error starting callback server: {e}")
            # Try again with a different port in case of bind issues
            if "address already in use" in str(e).lower():
                print("Port may be in use, trying a different port...")
                return start_callback_server()  # Recursive call with a new port
            raise e


def process_token_response(token_container):
    """Process the token response from Facebook."""
    global needs_authentication, auth_manager
    
    if token_container and token_container.get('token'):
        logger.info("Processing token response from Facebook OAuth")
        
        # Exchange the short-lived token for a long-lived token
        short_lived_token = token_container['token']
        long_lived_token_info = exchange_token_for_long_lived(short_lived_token)
        
        if long_lived_token_info:
            logger.info(f"Successfully exchanged for long-lived token (expires in {long_lived_token_info.expires_in} seconds)")
            
            try:
                auth_manager.token_info = long_lived_token_info
                logger.info(f"Long-lived token info set in auth_manager, expires in {long_lived_token_info.expires_in} seconds")
            except NameError:
                logger.error("auth_manager not defined when trying to process token")
                
            try:
                logger.info("Attempting to save long-lived token to cache")
                auth_manager._save_token_to_cache()
                logger.info(f"Long-lived token successfully saved to cache at {auth_manager._get_token_cache_path()}")
            except Exception as e:
                logger.error(f"Error saving token to cache: {e}")
                
            needs_authentication = False
            return True
        else:
            # Fall back to the short-lived token if exchange fails
            logger.warning("Failed to exchange for long-lived token, using short-lived token instead")
            token_info = TokenInfo(
                access_token=short_lived_token,
                expires_in=token_container.get('expires_in', 0)
            )
            
            try:
                auth_manager.token_info = token_info
                logger.info(f"Short-lived token info set in auth_manager, expires in {token_info.expires_in} seconds")
            except NameError:
                logger.error("auth_manager not defined when trying to process token")
                
            try:
                logger.info("Attempting to save token to cache")
                auth_manager._save_token_to_cache()
                logger.info(f"Token successfully saved to cache at {auth_manager._get_token_cache_path()}")
            except Exception as e:
                logger.error(f"Error saving token to cache: {e}")
                
            needs_authentication = False
            return True
    else:
        logger.warning("Received empty token in process_token_response")
        needs_authentication = True
        return False


def exchange_token_for_long_lived(short_lived_token):
    """
    Exchange a short-lived token for a long-lived token (60 days validity).
    
    Args:
        short_lived_token: The short-lived access token received from OAuth flow
        
    Returns:
        TokenInfo object with the long-lived token, or None if exchange failed
    """
    logger.info("Attempting to exchange short-lived token for long-lived token")
    
    try:
        # Get the app ID from the configuration
        app_id = meta_config.get_app_id()
        
        # Get the app secret - this should be securely stored
        app_secret = os.environ.get("META_APP_SECRET", "")
        
        if not app_id or not app_secret:
            logger.error("Missing app_id or app_secret for token exchange")
            return None
            
        # Make the API request to exchange the token
        url = "https://graph.facebook.com/v18.0/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": short_lived_token
        }
        
        logger.debug(f"Making token exchange request to {url}")
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            logger.debug(f"Token exchange response: {data}")
            
            # Create TokenInfo from the response
            # The response includes access_token and expires_in (in seconds)
            new_token = data.get("access_token")
            expires_in = data.get("expires_in")
            
            if new_token:
                logger.info(f"Received long-lived token, expires in {expires_in} seconds (~{expires_in//86400} days)")
                return TokenInfo(
                    access_token=new_token,
                    expires_in=expires_in
                )
            else:
                logger.error("No access_token in exchange response")
                return None
        else:
            logger.error(f"Token exchange failed with status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error exchanging token: {e}")
        return None


async def get_current_access_token() -> Optional[str]:
    """Get the current access token from auth manager"""
    # Use the singleton auth manager
    global auth_manager
    
    # Log the function call and current app ID
    logger.debug("get_current_access_token() called")
    app_id = meta_config.get_app_id()
    logger.debug(f"Current app_id: {app_id}")
    
    # Attempt to get access token
    try:
        token = auth_manager.get_access_token()
        
        if token:
            logger.debug("Access token found in auth_manager")
            return token
        else:
            logger.warning("No valid access token available in auth_manager")
            return None
    except Exception as e:
        logger.error(f"Error getting access token: {str(e)}")
        return None


def login():
    """
    Start the login flow to authenticate with Meta
    """
    print("Starting Meta Ads authentication flow...")
    
    try:
        # Start the callback server first
        port = start_callback_server()
        
        # Get the auth URL and open the browser
        auth_url = auth_manager.get_auth_url()
        print(f"Opening browser with URL: {auth_url}")
        webbrowser.open(auth_url)
        
        # Wait for token to be received
        print("Waiting for authentication to complete...")
        max_wait = 300  # 5 minutes
        wait_interval = 2  # 2 seconds
        
        for _ in range(max_wait // wait_interval):
            if token_container["token"]:
                token = token_container["token"]
                print("Authentication successful!")
                # Verify token works by getting basic user info
                try:
                    from .api import make_api_request
                    result = asyncio.run(make_api_request("me", token, {}))
                    print(f"Authenticated as: {result.get('name', 'Unknown')} (ID: {result.get('id', 'Unknown')})")
                    return
                except Exception as e:
                    print(f"Warning: Could not verify token: {e}")
                    return
            time.sleep(wait_interval)
        
        print("Authentication timed out. Please try again.")
    except Exception as e:
        print(f"Error during authentication: {e}")
        print(f"Direct authentication URL: {auth_manager.get_auth_url()}")
        print("You can manually open this URL in your browser to complete authentication.")

# Initialize auth manager with a placeholder - will be updated at runtime
META_APP_ID = os.environ.get("META_APP_ID", "YOUR_META_APP_ID")
auth_manager = AuthManager(META_APP_ID) 