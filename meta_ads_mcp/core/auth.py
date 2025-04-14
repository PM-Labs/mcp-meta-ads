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
                # Generate confirmation URL with properly encoded parameters
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
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                
                html = """
                <html>
                <head>
                    <title>Confirm Ad Set Update</title>
                    <meta charset="utf-8">
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
                        <p><strong>Warning:</strong> This action will directly update your ad set in Meta Ads. Please review the changes carefully before approving.</p>
                    </div>
                    
                    <div class="changes">
                        <h3>Changes to apply:</h3>
                        <table class="diff-table">
                            <tr class="header">
                                <td>Field</td>
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
                
                    # Special handling for targeting_automation
                    elif k == "targeting" and isinstance(v, dict) and "targeting_automation" in v:
                        targeting_auto = v.get("targeting_automation", {})
                        if "advantage_audience" in targeting_auto:
                            audience_value = targeting_auto["advantage_audience"]
                            description = f"Set Advantage+ audience to {'ON' if audience_value == 1 else 'OFF'}"
                            if audience_value == 1:
                                description += " (may be restricted for Special Ad Categories)"
                
                    # Format the value for display
                    display_value = json.dumps(v, indent=2) if isinstance(v, (dict, list)) else str(v)
                    
                    html += f"""
                            <tr>
                                <td>{k}</td>
                                <td><pre>{display_value}</pre></td>
                                <td>{description}</td>
                            </tr>
                            """
                
                # Create a properly escaped JSON string for JavaScript
                escaped_changes = json.dumps(changes).replace("'", "\\'").replace('"', '\\"')
                
                html += """
                        </table>
                    </div>
                    
                    <div class="buttons">
                        <button class="approve" onclick="approveChanges()">Approve Changes</button>
                        <button class="cancel" onclick="cancelChanges()">Cancel</button>
                    </div>
                    
                    <div id="status" class="status"></div>

                    <script>
                        // Enable debug logging
                        const DEBUG = true;
                        function debugLog(message, data) {
                            if (DEBUG) {
                                if (data) {
                                    console.log(`[DEBUG-CONFIRM] ${message}:`, data);
                                } else {
                                    console.log(`[DEBUG-CONFIRM] ${message}`);
                                }
                            }
                        }
                        
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
                            debugLog("Approving changes");
                            
                            const buttons = document.querySelectorAll('button');
                            buttons.forEach(button => button.disabled = true);
                            
                            const params = new URLSearchParams({
                                adset_id: '""" + adset_id + """',
                                token: '""" + token + """',
                                changes: '""" + escaped_changes + """',
                                action: 'approve'
                            });
                            
                            debugLog("Sending update request with params", {
                                adset_id: '""" + adset_id + """',
                                changes: JSON.parse('""" + escaped_changes + """')
                            });
                            
                            fetch('/update-confirm?' + params)
                            .then(response => {
                                debugLog("Received response", { status: response.status });
                                return response.text().then(text => {
                                    debugLog("Raw response text", text);
                                    try {
                                        return JSON.parse(text);
                                    } catch (e) {
                                        debugLog("Error parsing JSON response", e);
                                        return { status: "error", error: "Invalid response format from server" };
                                    }
                                });
                            })
                            .then(data => {
                                debugLog("Parsed response data", data);
                                
                                if (data.status === "error") {
                                    // Build a properly encoded and detailed error message
                                    let errorMessage = data.error || "Unknown error";
                                    
                                    // Extract the most appropriate error message for display
                                    const extractBestErrorMessage = (errorData) => {
                                        // Try to find the most user-friendly message in the error data
                                        if (!errorData) return null;
                                        
                                        // Meta often puts the most user-friendly message in error_user_msg
                                        if (errorData.apiError && errorData.apiError.error_user_msg) {
                                            return errorData.apiError.error_user_msg;
                                        }
                                        
                                        // Look for detailed error messages in blame_field_specs
                                        try {
                                            if (errorData.apiError && errorData.apiError.error_data) {
                                                const errorDataObj = typeof errorData.apiError.error_data === 'string' 
                                                    ? JSON.parse(errorData.apiError.error_data) 
                                                    : errorData.apiError.error_data;
                                                
                                                if (errorDataObj.blame_field_specs && errorDataObj.blame_field_specs.length > 0) {
                                                    // Handle nested array structure
                                                    const specs = errorDataObj.blame_field_specs[0];
                                                    if (Array.isArray(specs)) {
                                                        return specs.filter(Boolean).join("; ");
                                                    } else if (typeof specs === 'string') {
                                                        return specs;
                                                    }
                                                }
                                            }
                                        } catch (e) {
                                            debugLog("Error extracting blame_field_specs", e);
                                        }
                                        
                                        // Fall back to standard error message if available
                                        if (errorData.apiError && errorData.apiError.message) {
                                            return errorData.apiError.message;
                                        }
                                        
                                        // If we have error details as an array, join them
                                        if (errorData.details && Array.isArray(errorData.details) && errorData.details.length > 0) {
                                            return errorData.details.join("; ");
                                        }
                                        
                                        // No better message found
                                        return null;
                                    };
                                    
                                    // Find the best error message
                                    const bestMessage = extractBestErrorMessage(data);
                                    if (bestMessage) {
                                        errorMessage = bestMessage;
                                    }
                                    
                                    debugLog("Selected error message", errorMessage);
                                    
                                    // Get the original error from the nested structure if possible
                                    const originalErrorDetails = data.apiError?.details?.error || data.apiError;
                                    
                                    // Create a detailed error object for the verification page
                                    const fullErrorData = {
                                        message: errorMessage,
                                        details: data.errorDetails || [],
                                        apiError: originalErrorDetails || data.apiError || {},
                                        fullResponse: data.fullResponse || {}
                                    };
                                    
                                    debugLog("Redirecting with error message", errorMessage);
                                    debugLog("Full error data", fullErrorData);
                                    
                                    // Encode the stringified error object
                                    const encodedErrorData = encodeURIComponent(JSON.stringify(fullErrorData));
                                    
                                    // Redirect to verification page with detailed error information
                                    const errorParams = new URLSearchParams({
                                        adset_id: '""" + adset_id + """',
                                        token: '""" + token + """',
                                        error: errorMessage,
                                        errorData: encodedErrorData
                                    });
                                    window.location.href = '/verify-update?' + errorParams;
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
                                debugLog("Fetch error", error);
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
                self.wfile.write(html.encode('utf-8'))
                return
            
            elif self.path.startswith("/verify-update"):
                # Parse query parameters
                query = parse_qs(urlparse(self.path).query)
                adset_id = query.get("adset_id", [""])[0]
                token = query.get("token", [""])[0]
                
                # Check if there was an error in the update process
                error_message = query.get("error", [""])[0]
                error_data_encoded = query.get("errorData", [""])[0]
                
                # Try to decode detailed error data if available
                error_data = {}
                if error_data_encoded:
                    try:
                        error_data = json.loads(urllib.parse.unquote(error_data_encoded))
                    except:
                        logger.error("Failed to parse errorData parameter")
                
                # Respond with a verification page
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                
                html = """
                <html>
                <head>
                    <title>Verifying Ad Set Update</title>
                    <meta charset="utf-8">
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
                        .fix-suggestion { background-color: #e6f6ff; border: 1px solid #79b8ff; padding: 15px; border-radius: 6px; margin-top: 10px; }
                        .code-block { background-color: #f6f8fa; padding: 8px; border-radius: 4px; font-family: monospace; }
                        .error-list { margin-top: 10px; }
                        .error-list li { margin-bottom: 8px; }
                        .debug-section { background-color: #f0f0f0; margin-top: 30px; padding: 15px; border: 1px dashed #666; }
                        .debug-section h3 { color: #333; }
                        .raw-response { font-family: monospace; font-size: 12px; max-height: 300px; overflow: auto; }
                        .error-details { margin-top: 15px; background-color: #fff5f5; padding: 15px; border-left: 3px solid #d73a49; }
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
                    
                    <div id="debug-section" class="debug-section" style="display: none;">
                        <h3>Debug Information</h3>
                        <div>
                            <h4>URL Parameters:</h4>
                            <pre id="url-params">Loading...</pre>
                        </div>
                        <div>
                            <h4>Error Data:</h4>
                            <pre id="error-data-debug">""" + json.dumps(error_data, indent=2) + """</pre>
                        </div>
                        <div>
                            <h4>Raw API Response:</h4>
                            <pre id="raw-response" class="raw-response">Loading...</pre>
                        </div>
                    </div>

                    <script>
                        // Enable debug mode
                        const DEBUG = true;
                        
                        // Debug logging helper
                        function debugLog(message, data) {
                            if (DEBUG) {
                                if (data) {
                                    console.log(`[DEBUG] ${message}:`, data);
                                } else {
                                    console.log(`[DEBUG] ${message}`);
                                }
                            }
                        }
                        
                        // Show debug section
                        if (DEBUG) {
                            document.getElementById('debug-section').style.display = 'block';
                        }
                        
                        // Parse and display URL parameters
                        const urlParams = new URLSearchParams(window.location.search);
                        const urlParamsObj = {};
                        for (const [key, value] of urlParams.entries()) {
                            urlParamsObj[key] = value;
                        }
                        
                        debugLog('URL parameters', urlParamsObj);
                        document.getElementById('url-params').textContent = JSON.stringify(urlParamsObj, null, 2);
                        
                        // Try to parse error data if available
                        let errorData = null;
                        const errorDataParam = urlParams.get('errorData');
                        if (errorDataParam) {
                            try {
                                errorData = JSON.parse(decodeURIComponent(errorDataParam));
                                debugLog('Parsed error data', errorData);
                            } catch (e) {
                                debugLog('Failed to parse errorData', e);
                            }
                        }
                        
                        // Check if there was an error passed in the URL
                        const errorParam = urlParams.get('error');
                        debugLog('Error parameter found', errorParam);
                        
                        if (errorParam) {
                            // If there's an error, show it immediately
                            const errorMessage = decodeURIComponent(errorParam);
                            debugLog('Decoded error message', errorMessage);
                            
                            const statusElement = document.getElementById('status');
                            statusElement.classList.remove('loading');
                            statusElement.classList.add('error');
                            
                            // Check if this is a Special Ad Category error
                            const isSpecialAdCategoryError = 
                                errorMessage.includes("Special Ad Category") || 
                                errorMessage.includes("Advantage+") || 
                                errorMessage.includes("advantage_audience");
                            
                            debugLog('Is Special Ad Category error', isSpecialAdCategoryError);
                            
                            if (isSpecialAdCategoryError) {
                                // Format special ad category errors with better explanation
                                debugLog('Displaying Special Ad Category error');
                                statusElement.innerHTML = `
                                    <h3>❌ Special Ad Category Restriction</h3>
                                    <p>${errorMessage}</p>
                                    <div class="note" style="margin-top:10px">
                                        <strong>What does this mean?</strong><br>
                                        Meta restricts certain targeting features like Advantage+ audience for ads in Special Ad Categories 
                                        (housing, employment, credit, social issues, etc.). You need to use standard targeting options instead.
                                    </div>
                                    <div class="fix-suggestion">
                                        <strong>How to fix:</strong><br>
                                        To update this ad set, try setting <span class="code-block">targeting.targeting_automation.advantage_audience</span> to <span class="code-block">0</span> instead of <span class="code-block">1</span>.
                                    </div>
                                `;
                            } else {
                                // Standard error display with more details
                                debugLog('Displaying standard error');
                                
                                // Start with basic error display
                                let errorHtml = `
                                    <h3>❌ Error updating ad set</h3>
                                    <p>${errorMessage}</p>
                                `;
                                
                                // Add detailed error information if available
                                if (errorData) {
                                    errorHtml += `<div class="error-details">`;
                                    
                                    // If we have a nice error title from Meta, display it
                                    if (errorData.apiError && errorData.apiError.error_user_title) {
                                        errorHtml += `<strong>Error Type:</strong> ${errorData.apiError.error_user_title}<br>`;
                                    }
                                    
                                    // Add error codes if available
                                    if (errorData.apiError) {
                                        const apiError = errorData.apiError;
                                        if (apiError.code) {
                                            errorHtml += `<strong>Error Code:</strong> ${apiError.code}`;
                                            if (apiError.error_subcode) {
                                                errorHtml += ` (Subcode: ${apiError.error_subcode})`;
                                            }
                                            errorHtml += `<br>`;
                                        }
                                    }
                                    
                                    // Add detailed error list
                                    if (errorData.details && errorData.details.length > 0) {
                                        errorHtml += `
                                            <strong>Error Details:</strong>
                                            <ul class="error-list">
                                                ${errorData.details.map(detail => `<li>${detail}</li>`).join('')}
                                            </ul>
                                        `;
                                    }
                                    
                                    // Try to extract and display blame_field_specs
                                    try {
                                        if (errorData.apiError && errorData.apiError.error_data) {
                                            const error_data = typeof errorData.apiError.error_data === 'string' 
                                                ? JSON.parse(errorData.apiError.error_data) 
                                                : errorData.apiError.error_data;
                                                
                                            if (error_data.blame_field_specs && error_data.blame_field_specs.length > 0) {
                                                errorHtml += `<strong>Field-Specific Errors:</strong><ul class="error-list">`;
                                                
                                                // Handle different formats of blame_field_specs
                                                if (Array.isArray(error_data.blame_field_specs[0])) {
                                                    // Format: [[error1, error2, ...]]
                                                    error_data.blame_field_specs[0].forEach(spec => {
                                                        if (spec) errorHtml += `<li>${spec}</li>`;
                                                    });
                                                } else {
                                                    // Format: [error1, error2, ...]
                                                    error_data.blame_field_specs.forEach(spec => {
                                                        if (spec) errorHtml += `<li>${spec}</li>`;
                                                    });
                                                }
                                                
                                                errorHtml += `</ul>`;
                                            }
                                        }
                                    } catch (e) {
                                        debugLog('Error parsing blame_field_specs', e);
                                    }
                                    
                                    errorHtml += `</div>`;
                                }
                                
                                statusElement.innerHTML = errorHtml;
                            }
                            
                            // Just display current state, don't try to verify the update since it failed
                            document.getElementById('details').innerHTML = `
                                <h3>Current Ad Set Details (Changes Not Applied):</h3>
                                <p>Fetching current state...</p>
                                <pre id="adset-details">Loading...</pre>
                            `;
                            document.getElementById('details').style.display = 'block';
                            
                            // Fetch the current ad set details to show what wasn't changed
                            fetchAdSetDetails();
                        } else {
                            // Otherwise proceed with normal verification
                            debugLog('No error parameter found, proceeding with verification');
                            setTimeout(verifyUpdate, 3000);
                        }
                        
                        // Function to just fetch the ad set details
                        async function fetchAdSetDetails() {
                            try {
                                debugLog('Fetching ad set details');
                                const apiUrl = '/api/adset?' + new URLSearchParams({
                                    adset_id: '""" + adset_id + """',
                                    token: '""" + token + """'
                                });
                                
                                debugLog('Fetching from URL', apiUrl);
                                const response = await fetch(apiUrl);
                                
                                // Log raw response
                                const responseText = await response.text();
                                debugLog('Raw API response text', responseText);
                                document.getElementById('raw-response').textContent = responseText;
                                
                                // Parse JSON
                                let data;
                                try {
                                    data = JSON.parse(responseText);
                                    debugLog('Parsed API response', data);
                                } catch (parseError) {
                                    debugLog('Error parsing JSON response', parseError);
                                    throw new Error(`Failed to parse API response: ${parseError.message}`);
                                }
                                
                                const detailsElement = document.getElementById('details');
                                const adsetDetailsElement = document.getElementById('adset-details');
                                
                                // Check if there's an error in the response
                                if (data.error) {
                                    debugLog('Error in API response', data.error);
                                    adsetDetailsElement.textContent = JSON.stringify({
                                        error: "Error fetching ad set details", 
                                        details: typeof data.error === 'object' ? 
                                            data.error.message || JSON.stringify(data.error) : 
                                            data.error
                                    }, null, 2);
                                } else {
                                    // No errors, display the ad set details
                                    debugLog('Successfully fetched ad set details');
                                    detailsElement.style.display = 'block';
                                    adsetDetailsElement.textContent = JSON.stringify(data, null, 2);
                                }
                            } catch (error) {
                                debugLog('Error in fetchAdSetDetails', error);
                                console.error('Error fetching ad set details:', error);
                                const adsetDetailsElement = document.getElementById('adset-details');
                                if (adsetDetailsElement) {
                                    adsetDetailsElement.textContent = "Error fetching ad set details: " + error.message;
                                }
                            }
                        }
                        
                        // Function to fetch the ad set details and check if frequency_control_specs was updated
                        async function verifyUpdate() {
                            try {
                                debugLog('Starting verification of update');
                                const apiUrl = '/api/adset?' + new URLSearchParams({
                                    adset_id: '""" + adset_id + """',
                                    token: '""" + token + """'
                                });
                                
                                debugLog('Verifying update from URL', apiUrl);
                                const response = await fetch(apiUrl);
                                
                                // Log raw response
                                const responseText = await response.text();
                                debugLog('Raw verification response text', responseText);
                                document.getElementById('raw-response').textContent = responseText;
                                
                                // Parse JSON
                                let data;
                                try {
                                    data = JSON.parse(responseText);
                                    debugLog('Parsed verification response', data);
                                } catch (parseError) {
                                    debugLog('Error parsing JSON verification response', parseError);
                                    throw new Error(`Failed to parse verification response: ${parseError.message}`);
                                }
                                
                                const statusElement = document.getElementById('status');
                                const detailsElement = document.getElementById('details');
                                const adsetDetailsElement = document.getElementById('adset-details');
                                
                                detailsElement.style.display = 'block';
                                adsetDetailsElement.textContent = JSON.stringify(data, null, 2);
                                
                                // Check if there's an error in the response
                                if (data.error) {
                                    debugLog('Error in verification response', data.error);
                                    statusElement.classList.remove('loading');
                                    statusElement.classList.add('error');
                                    
                                    // Extract error message from various possible formats
                                    let errorMessage = "Unknown error occurred";
                                    
                                    if (typeof data.error === 'string') {
                                        errorMessage = data.error;
                                        debugLog('Error is string', errorMessage);
                                    } else if (data.error.message) {
                                        errorMessage = data.error.message;
                                        debugLog('Error has message property', errorMessage);
                                    } else if (data.error.error_message) {
                                        errorMessage = data.error.error_message;
                                        debugLog('Error has error_message property', errorMessage);
                                    } else {
                                        debugLog('Error format unknown', data.error);
                                    }
                                    
                                    // Check if this is a Special Ad Category error
                                    if (errorMessage.includes("Special Ad Category") || 
                                        errorMessage.includes("Advantage+") || 
                                        errorMessage.includes("advantage_audience")) {
                                        
                                        // Format special ad category errors with better explanation
                                        debugLog('Displaying Special Ad Category verification error');
                                        statusElement.innerHTML = `
                                            <h3>❌ Special Ad Category Restriction</h3>
                                            <p>${errorMessage}</p>
                                            <div class="note" style="margin-top:10px">
                                                <strong>What does this mean?</strong><br>
                                                Meta restricts certain targeting features like Advantage+ audience for ads in Special Ad Categories 
                                                (housing, employment, credit, social issues, etc.). You need to use standard targeting options instead.
                                            </div>
                                            <div class="fix-suggestion">
                                                <strong>How to fix:</strong><br>
                                                To update this ad set, try setting <span class="code-block">targeting.targeting_automation.advantage_audience</span> to <span class="code-block">0</span> instead of <span class="code-block">1</span>.
                                            </div>
                                        `;
                                    } else {
                                        debugLog('Displaying standard verification error');
                                        statusElement.innerHTML = `
                                            <h3>❌ Error retrieving ad set details</h3>
                                            <p>${errorMessage}</p>
                                            <div class="raw-error" style="margin-top: 10px;">
                                                <strong>Raw Error:</strong>
                                                <pre>${JSON.stringify(data.error, null, 2)}</pre>
                                            </div>
                                        `;
                                    }
                                } else {
                                    // Update success message to reflect API visibility limitations
                                    debugLog('Verification successful');
                                    statusElement.classList.remove('loading');
                                    statusElement.classList.add('success');
                                    statusElement.innerHTML = '✅ Update request was processed successfully. Please verify the changes in Meta Ads Manager UI or monitor ad performance metrics.';
                                }
                            } catch (error) {
                                debugLog('Error in verifyUpdate', error);
                                const statusElement = document.getElementById('status');
                                statusElement.classList.remove('loading');
                                statusElement.classList.add('error');
                                statusElement.innerHTML = `
                                    <h3>❌ Error verifying update</h3>
                                    <p>${error.message}</p>
                                    <pre>${error.stack}</pre>
                                `;
                            }
                        }
                    </script>
                </body>
                </html>
                """
                self.wfile.write(html.encode('utf-8'))
                return
            
            elif self.path.startswith("/api/adset"):
                # Parse query parameters
                query = parse_qs(urlparse(self.path).query)
                adset_id = query.get("adset_id", [""])[0]
                token = query.get("token", [""])[0]
                
                from .api import make_api_request
                
                # Call the Graph API directly
                async def get_adset_data():
                    try:
                        endpoint = f"{adset_id}"
                        params = {
                            "fields": "id,name,campaign_id,status,daily_budget,lifetime_budget,targeting,bid_amount,bid_strategy,optimization_goal,billing_event,start_time,end_time,created_time,updated_time,attribution_spec,destination_type,promoted_object,pacing_type,budget_remaining,frequency_control_specs"
                        }
                        
                        result = await make_api_request(endpoint, token, params)
                        
                        # Check if result is a string (possibly an error message)
                        if isinstance(result, str):
                            try:
                                # Try to parse as JSON
                                parsed_result = json.loads(result)
                                return parsed_result
                            except json.JSONDecodeError:
                                # Return error object if can't parse as JSON
                                return {"error": {"message": result}}
                                
                        # If the result is None, return an error object
                        if result is None:
                            return {"error": {"message": "Empty response from API"}}
                            
                        return result
                    except Exception as e:
                        logger.error(f"Error in get_adset_data: {str(e)}")
                        return {"error": {"message": f"Error fetching ad set data: {str(e)}"}}
                
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
                            # Handle potential multiple encoding of JSON
                            decoded_changes = changes
                            # Try multiple decode attempts to handle various encoding scenarios
                            for _ in range(3):  # Try up to 3 levels of decoding
                                try:
                                    # Try to parse as JSON
                                    changes_obj = json.loads(decoded_changes)
                                    # If we got a string back, we need to decode again
                                    if isinstance(changes_obj, str):
                                        decoded_changes = changes_obj
                                        continue
                                    else:
                                        # We have a dictionary, break the loop
                                        changes_dict = changes_obj
                                        break
                                except json.JSONDecodeError:
                                    # Try unescaping first
                                    import html
                                    decoded_changes = html.unescape(decoded_changes)
                                    try:
                                        changes_dict = json.loads(decoded_changes)
                                        break
                                    except:
                                        # Failed to parse, will try again in the next iteration
                                        pass
                            else:
                                # If we got here, we couldn't parse the JSON
                                return {"status": "error", "error": f"Failed to decode changes JSON: {changes}"}
                            
                            endpoint = f"{adset_id}"
                            
                            # Create API parameters properly
                            api_params = {}
                            
                            # Add each change parameter
                            for key, value in changes_dict.items():
                                api_params[key] = value
                                
                            # Add the access token
                            api_params["access_token"] = token
                            
                            # Log what we're about to send
                            logger.info(f"Sending update to Meta API for ad set {adset_id}")
                            logger.info(f"Parameters: {json.dumps(api_params)}")
                            
                            # Make the API request to update the ad set
                            result = await make_api_request(endpoint, token, api_params, method="POST")
                            
                            # Log the result
                            logger.info(f"Meta API update result: {json.dumps(result) if isinstance(result, dict) else result}")
                            
                            # Handle various result formats
                            if result is None:
                                logger.error("Empty response from Meta API")
                                return {"status": "error", "error": "Empty response from Meta API"}
                                
                            # Check if the result contains an error
                            if isinstance(result, dict) and 'error' in result:
                                # Extract detailed error message from Meta API
                                error_obj = result['error']
                                error_msg = error_obj.get('message', 'Unknown API error')
                                detailed_error = ""
                                
                                # Check for more detailed error messages
                                if 'error_user_msg' in error_obj and error_obj['error_user_msg']:
                                    detailed_error = error_obj['error_user_msg']
                                    logger.error(f"Meta API user-facing error message: {detailed_error}")
                                
                                # Extract error data if available
                                error_specs = []
                                if 'error_data' in error_obj and isinstance(error_obj['error_data'], str):
                                    try:
                                        error_data = json.loads(error_obj['error_data'])
                                        if 'blame_field_specs' in error_data and error_data['blame_field_specs']:
                                            blame_specs = error_data['blame_field_specs']
                                            if isinstance(blame_specs, list) and blame_specs:
                                                if isinstance(blame_specs[0], list):
                                                    error_specs = [msg for msg in blame_specs[0] if msg]
                                                else:
                                                    error_specs = [str(spec) for spec in blame_specs if spec]
                                            
                                            if error_specs:
                                                logger.error(f"Meta API blame field specs: {'; '.join(error_specs)}")
                                    except Exception as e:
                                        logger.error(f"Error parsing error_data: {e}")
                                
                                # Construct most descriptive error message
                                if detailed_error:
                                    error_msg = detailed_error
                                elif error_specs:
                                    error_msg = "; ".join(error_specs)
                                
                                # Log the detailed error information
                                logger.error(f"Meta API error: {error_msg}")
                                logger.error(f"Full error object: {json.dumps(error_obj)}")
                                
                                return {
                                    "status": "error", 
                                    "error": error_msg, 
                                    "api_error": result['error'],
                                    "detailed_errors": error_specs,
                                    "full_response": result
                                }
                            
                            # Handle string results (which might be error messages)
                            if isinstance(result, str):
                                try:
                                    # Try to parse as JSON
                                    result_obj = json.loads(result)
                                    if isinstance(result_obj, dict) and 'error' in result_obj:
                                        return {"status": "error", "error": result_obj['error'].get('message', 'Unknown API error')}
                                except:
                                    # If not parseable as JSON, return as error message
                                    return {"status": "error", "error": result}
                            
                            # If we got here, assume success
                            return {"status": "approved", "api_result": result}
                        except Exception as e:
                            # Log the exception for debugging
                            logger.error(f"Error in perform_update: {str(e)}")
                            import traceback
                            logger.error(traceback.format_exc())
                            return {"status": "error", "error": str(e)}
                    
                    # Run the async function
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        result = loop.run_until_complete(perform_update())
                        loop.close()
                        
                        # Ensure result is a dictionary
                        if not isinstance(result, dict):
                            logger.error(f"Unexpected result type: {type(result)}")
                            self.wfile.write(json.dumps({"status": "error", "error": str(result)}).encode())
                            return
                        
                        # Check if the API call returned an error
                        if result.get("status") == "error":
                            error_message = result.get("error", "Unknown error")
                            detailed_errors = result.get("detailed_errors", [])
                            
                            # Log the detailed error
                            logger.error(f"Meta API error during ad set update: {error_message}")
                            if "api_error" in result:
                                logger.error(f"Detailed API error: {json.dumps(result['api_error'])}")
                            
                            # Prepare error response with all available details
                            error_response = {
                                "status": "error",
                                "error": error_message,
                                "errorDetails": detailed_errors
                            }
                            
                            # Include the full API error object for complete details
                            if "api_error" in result:
                                error_response["apiError"] = result["api_error"]
                            
                            # Include the full response if available
                            if "full_response" in result:
                                error_response["fullResponse"] = result["full_response"]
                            
                            logger.info(f"Returning error response: {json.dumps(error_response)}")
                            self.wfile.write(json.dumps(error_response).encode())
                        else:
                            logger.info("Update successful, returning result")
                            self.wfile.write(json.dumps(result).encode())
                    except Exception as e:
                        logger.error(f"Exception in update-confirm handler: {str(e)}")
                        import traceback
                        logger.error(traceback.format_exc())
                        self.wfile.write(json.dumps({
                            "status": "error", 
                            "error": str(e),
                            "traceback": traceback.format_exc()
                        }).encode())
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