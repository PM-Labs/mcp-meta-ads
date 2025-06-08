#!/usr/bin/env python3
"""
Example HTTP client for Meta Ads MCP Streamable HTTP transport

This demonstrates how to use the completed HTTP transport implementation
to access Meta Ads tools via HTTP API calls.

Usage:
    1. Start the server: python -m meta_ads_mcp --transport streamable-http
    2. Run this example: python example_http_client.py
"""

import requests
import json
import os
from typing import Dict, Any, Optional

class MetaAdsMCPClient:
    """Simple HTTP client for Meta Ads MCP server"""
    
    def __init__(self, base_url: str = "http://localhost:8080", 
                 pipeboard_token: Optional[str] = None,
                 meta_access_token: Optional[str] = None):
        """Initialize the client
        
        Args:
            base_url: Base URL of the MCP server
            pipeboard_token: Pipeboard API token (recommended)
            meta_access_token: Direct Meta access token (fallback)
        """
        self.base_url = base_url.rstrip('/')
        self.endpoint = f"{self.base_url}/mcp/"
        self.session_id = 1
        
        # Setup authentication headers
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "MetaAdsMCP-Example-Client/1.0"
        }
        
        # Add authentication
        if pipeboard_token:
            self.headers["Authorization"] = f"Bearer {pipeboard_token}"
            print(f"✅ Using Pipeboard authentication")
        elif meta_access_token:
            self.headers["X-META-ACCESS-TOKEN"] = meta_access_token
            print(f"✅ Using direct Meta token authentication")
        else:
            print(f"⚠️  No authentication provided - tools will require auth")
    
    def _make_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make a JSON-RPC request to the server"""
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self.session_id
        }
        
        if params:
            payload["params"] = params
        
        print(f"\n🔄 Making request: {method}")
        print(f"   URL: {self.endpoint}")
        print(f"   Headers: {json.dumps(dict(self.headers), indent=2)}")
        print(f"   Payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = requests.post(
                self.endpoint,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            print(f"   Status: {response.status_code} {response.reason}")
            print(f"   Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Request successful")
                return result
            else:
                print(f"❌ Request failed: {response.status_code}")
                print(f"   Response: {response.text}")
                return {"error": {"code": response.status_code, "message": response.text}}
                
        except Exception as e:
            print(f"❌ Request exception: {e}")
            return {"error": {"code": -1, "message": str(e)}}
        finally:
            self.session_id += 1
    
    def initialize(self) -> Dict[str, Any]:
        """Initialize MCP session"""
        return self._make_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {}
            },
            "clientInfo": {
                "name": "meta-ads-example-client",
                "version": "1.0.0"
            }
        })
    
    def list_tools(self) -> Dict[str, Any]:
        """Get list of available tools"""
        return self._make_request("tools/list")
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call a specific tool"""
        params = {"name": tool_name}
        if arguments:
            params["arguments"] = arguments
        
        return self._make_request("tools/call", params)

def main():
    """Example usage of the Meta Ads MCP HTTP client"""
    print("🚀 Meta Ads MCP HTTP Client Example")
    print("="*60)
    
    # Check for authentication
    pipeboard_token = os.environ.get("PIPEBOARD_API_TOKEN")
    meta_token = os.environ.get("META_ACCESS_TOKEN")
    
    if not pipeboard_token and not meta_token:
        print("⚠️  No authentication tokens found in environment")
        print("   Set PIPEBOARD_API_TOKEN or META_ACCESS_TOKEN for full functionality")
        print("   Using test token for demonstration...")
        pipeboard_token = "demo_token_12345"
    
    # Create client
    client = MetaAdsMCPClient(
        pipeboard_token=pipeboard_token,
        meta_access_token=meta_token
    )
    
    # Test the MCP protocol flow
    print("\n🔄 Testing MCP Protocol Flow")
    print("="*50)
    
    # 1. Initialize
    print("\n" + "="*60)
    print("🔍 Step 1: Initialize MCP Session")
    print("="*60)
    init_result = client.initialize()
    
    if "error" in init_result:
        print(f"❌ Initialize failed: {init_result['error']}")
        return
    
    print(f"✅ Initialize successful")
    print(f"   Server info: {init_result['result']['serverInfo']}")
    print(f"   Protocol version: {init_result['result']['protocolVersion']}")
    
    # 2. List tools
    print("\n" + "="*60)
    print("🔍 Step 2: List Available Tools")
    print("="*60)
    tools_result = client.list_tools()
    
    if "error" in tools_result:
        print(f"❌ Tools list failed: {tools_result['error']}")
        return
    
    tools = tools_result["result"]["tools"]
    print(f"✅ Found {len(tools)} tools:")
    
    # Show first few tools
    for i, tool in enumerate(tools[:5]):
        print(f"   {i+1}. {tool['name']}: {tool['description'][:100]}...")
    
    if len(tools) > 5:
        print(f"   ... and {len(tools) - 5} more tools")
    
    # 3. Test a simple tool call
    print("\n" + "="*60)
    print("🔍 Step 3: Test Tool Call - get_ad_accounts")
    print("="*60)
    
    tool_result = client.call_tool("get_ad_accounts", {"limit": 3})
    
    if "error" in tool_result:
        print(f"❌ Tool call failed: {tool_result['error']}")
        return
    
    print(f"✅ Tool call successful")
    content = tool_result["result"]["content"][0]["text"]
    
    # Parse the response to see if it's authentication or actual data
    try:
        parsed_content = json.loads(content)
        if "error" in parsed_content and "Authentication Required" in parsed_content["error"]["message"]:
            print(f"📋 Result: Authentication required (expected with demo token)")
            print(f"   This confirms the HTTP transport is working!")
            print(f"   Use a real Pipeboard token for actual data access.")
        else:
            print(f"📋 Result: {content[:200]}...")
    except:
        print(f"📋 Raw result: {content[:200]}...")
    
    # Summary
    print("\n" + "🎯" * 30)
    print("EXAMPLE COMPLETE")
    print("🎯" * 30)
    print("\n📊 Results:")
    print("   Initialize: ✅ SUCCESS")
    print("   Tools List: ✅ SUCCESS")
    print("   Tool Call:  ✅ SUCCESS")
    print("\n🎉 Meta Ads MCP HTTP transport is fully functional!")
    print("\n💡 Next steps:")
    print("   1. Set PIPEBOARD_API_TOKEN environment variable")
    print("   2. Call any of the 26 available Meta Ads tools")
    print("   3. Build your web application or automation scripts")

if __name__ == "__main__":
    main() 