# Using a Custom Meta Developer App

This guide explains how to use Meta Ads MCP with your own Meta Developer App. Note that this is an alternative method - we recommend using [Pipeboard authentication](README.md) for a simpler setup.

## Create a Meta Developer App

Before using direct Meta authentication, you'll need to set up a Meta Developer App:

1. Go to [Meta for Developers](https://developers.facebook.com/) and create a new app
2. Choose the "Business" app type
3. In your app settings, add the "Marketing API" product
4. Configure your app's OAuth redirect URI to include `http://localhost:8888/callback`
5. Note your App ID (Client ID) for use with the MCP

## Installation & Usage

When using your own Meta app, you'll need to provide the App ID:

```bash
# Using uvx
uvx meta-ads-mcp --app-id YOUR_META_ADS_APP_ID

# Using pip installation
python -m meta_ads_mcp --app-id YOUR_META_ADS_APP_ID
```

## Configuration

### Cursor or Claude Desktop Integration

Add this to your `claude_desktop_config.json` or `~/.cursor/mcp.json`:

```json
"mcpServers": {
  "meta-ads": {
    "command": "uvx",
    "args": ["meta-ads-mcp", "--app-id", "YOUR_META_ADS_APP_ID"]
  }
}
```

## Authentication Flow

When using direct Meta OAuth, the MCP uses Meta's OAuth 2.0 authentication flow:

1. Starts a local callback server on your machine
2. Opens a browser window to authenticate with Meta
3. Asks you to authorize the app
4. Redirects back to the local server to extract and store the token securely

## Environment Variables

You can use these environment variables instead of command-line arguments:

```bash
# Your Meta App ID
export META_APP_ID=your_app_id
uvx meta-ads-mcp

# Or provide a direct access token (bypasses local cache)
export META_ACCESS_TOKEN=your_access_token
uvx meta-ads-mcp
```

## Testing

### CLI Testing

Run the test script to verify authentication:

```bash
# Basic test
python test_meta_ads_auth.py --app-id YOUR_APP_ID

# Force new login
python test_meta_ads_auth.py --app-id YOUR_APP_ID --force-login
```

### LLM Interface Testing

When using direct Meta authentication:
1. Test authentication by calling the `mcp_meta_ads_get_login_link` tool
2. Verify account access by calling `mcp_meta_ads_get_ad_accounts`
3. Check specific account details with `mcp_meta_ads_get_account_info`

## Troubleshooting

### Authentication Issues

1. App ID Issues
   - If you encounter errors like `(#200) Provide valid app ID`, verify your App ID is correct
   - Make sure you've completed the app setup steps above
   - Check that your app has the Marketing API product added

2. OAuth Flow
   - Run with `--force-login` to get a fresh token: `uvx meta-ads-mcp --login --app-id YOUR_APP_ID --force-login`
   - Make sure the terminal has permissions to open a browser window
   - Check that the callback server can run on port 8888

3. Direct Token Usage
   - If you have a valid access token, you can bypass the OAuth flow:
   - `export META_ACCESS_TOKEN=your_access_token`
   - This will ignore the local token cache

### API Errors

If you receive errors from the Meta API:
1. Verify your app has the Marketing API product added
2. Ensure the user has appropriate permissions on the ad accounts
3. Check if there are rate limits or other restrictions on your app 