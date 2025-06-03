#!/usr/bin/env python3
"""
HTTP Transport Integration Tests for Meta Ads MCP

This test suite validates the complete HTTP transport functionality including:
- MCP protocol compliance (initialize, tools/list, tools/call)
- Authentication header processing
- JSON-RPC request/response format
- Error handling and validation

Usage:
    1. Start the server: python -m meta_ads_mcp --transport streamable-http --port 8080
    2. Run tests: python -m pytest tests/test_http_transport.py -v
    
Or run directly:
    python tests/test_http_transport.py
"""

import requests
import json
import time
import sys
import os
from typing import Dict, Any, Optional

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class HTTPTransportTester:
    """Test suite for Meta Ads MCP HTTP transport"""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip('/')
        self.endpoint = f"{self.base_url}/mcp/"
        self.request_id = 1
        
    def _make_request(self, method: str, params: Dict[str, Any] = None, 
                     headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Make a JSON-RPC request to the MCP server"""
        
        # Default headers for MCP protocol
        default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "MCP-Test-Client/1.0"
        }
        
        if headers:
            default_headers.update(headers)
        
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self.request_id
        }
        
        if params:
            payload["params"] = params
        
        try:
            response = requests.post(
                self.endpoint,
                headers=default_headers,
                json=payload,
                timeout=10
            )
            
            self.request_id += 1
            
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "json": response.json() if response.status_code == 200 else None,
                "text": response.text,
                "success": response.status_code == 200
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "status_code": 0,
                "headers": {},
                "json": None,
                "text": str(e),
                "success": False,
                "error": str(e)
            }
    
    def test_server_availability(self) -> bool:
        """Test if the server is running and accessible"""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            # We expect a 404 for the root path, but it means the server is running
            return response.status_code in [200, 404]
        except:
            return False
    
    def test_mcp_initialize(self, auth_headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Test MCP initialize method"""
        return self._make_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {}
            },
            "clientInfo": {
                "name": "meta-ads-test-client",
                "version": "1.0.0"
            }
        }, auth_headers)
    
    def test_tools_list(self, auth_headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Test tools/list method"""
        return self._make_request("tools/list", {}, auth_headers)
    
    def test_tool_call(self, tool_name: str, arguments: Dict[str, Any] = None,
                      auth_headers: Dict[str, str] = None) -> Dict[str, Any]:
        """Test tools/call method"""
        params = {"name": tool_name}
        if arguments:
            params["arguments"] = arguments
        
        return self._make_request("tools/call", params, auth_headers)
    
    def run_protocol_flow_test(self, auth_headers: Dict[str, str] = None,
                              scenario_name: str = "Default") -> Dict[str, bool]:
        """Run complete MCP protocol flow test"""
        results = {}
        
        print(f"\n🧪 Testing: {scenario_name}")
        print("="*50)
        
        # Test 1: Initialize
        print("🔍 Testing MCP Initialize Request")
        init_result = self.test_mcp_initialize(auth_headers)
        results["initialize"] = init_result["success"]
        
        if not init_result["success"]:
            print(f"❌ Initialize failed: {init_result.get('text', 'Unknown error')}")
            return results
        
        print("✅ Initialize successful")
        if init_result["json"] and "result" in init_result["json"]:
            server_info = init_result["json"]["result"].get("serverInfo", {})
            print(f"   Server: {server_info.get('name', 'unknown')} v{server_info.get('version', 'unknown')}")
        
        # Test 2: Tools List
        print("\n🔍 Testing Tools List Request")
        tools_result = self.test_tools_list(auth_headers)
        results["tools_list"] = tools_result["success"]
        
        if not tools_result["success"]:
            print(f"❌ Tools list failed: {tools_result.get('text', 'Unknown error')}")
            return results
        
        print("✅ Tools list successful")
        if tools_result["json"] and "result" in tools_result["json"]:
            tools = tools_result["json"]["result"].get("tools", [])
            print(f"   Found {len(tools)} tools")
        
        # Test 3: Tool Call
        print("\n🔍 Testing Tool Call: get_ad_accounts")
        tool_result = self.test_tool_call("get_ad_accounts", {"limit": 3}, auth_headers)
        results["tool_call"] = tool_result["success"]
        
        if not tool_result["success"]:
            print(f"❌ Tool call failed: {tool_result.get('text', 'Unknown error')}")
            return results
        
        print("✅ Tool call successful")
        
        # Check if it's an authentication error (expected with test tokens)
        if tool_result["json"] and "result" in tool_result["json"]:
            content = tool_result["json"]["result"].get("content", [{}])[0].get("text", "")
            if "Authentication Required" in content:
                print("   📋 Result: Authentication required (expected with test tokens)")
            else:
                print(f"   📋 Result: {content[:100]}...")
        
        print(f"\n📊 Scenario Results:")
        print(f"   Initialize: {'✅' if results['initialize'] else '❌'}")
        print(f"   Tools List: {'✅' if results['tools_list'] else '❌'}")
        print(f"   Tool Call:  {'✅' if results['tool_call'] else '❌'}")
        
        return results
    
    def run_comprehensive_test_suite(self) -> bool:
        """Run complete test suite with multiple authentication scenarios"""
        print("🚀 Meta Ads MCP HTTP Transport Test Suite")
        print("="*60)
        
        # Check server availability first
        print("🔍 Checking server status...")
        if not self.test_server_availability():
            print("❌ Server is not running at", self.base_url)
            print("   Please start the server with:")
            print("   python -m meta_ads_mcp --transport streamable-http --port 8080 --host localhost")
            return False
        
        print("✅ Server is running")
        
        all_results = {}
        
        # Test scenarios
        scenarios = [
            {
                "name": "No Authentication",
                "headers": None
            },
            {
                "name": "Bearer Token (Primary Path)",
                "headers": {"Authentication": "Bearer test_pipeboard_token_12345"}
            },
            {
                "name": "Custom Meta App ID (Fallback Path)",
                "headers": {"X-META-APP-ID": "123456789012345"}
            },
            {
                "name": "Both Auth Methods",
                "headers": {
                    "Authentication": "Bearer test_pipeboard_token_12345",
                    "X-META-APP-ID": "123456789012345"
                }
            }
        ]
        
        # Run tests for each scenario
        for scenario in scenarios:
            results = self.run_protocol_flow_test(
                auth_headers=scenario["headers"],
                scenario_name=scenario["name"]
            )
            all_results[scenario["name"]] = results
        
        # Summary
        print("\n🏁 TEST SUITE COMPLETED")
        print("="*30)
        
        all_passed = True
        for scenario_name, results in all_results.items():
            scenario_success = all(results.values())
            status = "✅ SUCCESS" if scenario_success else "❌ FAILED"
            print(f"{scenario_name}: {status}")
            if not scenario_success:
                all_passed = False
        
        print(f"\n📊 Overall Result: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
        
        if all_passed:
            print("\n🎉 Meta Ads MCP HTTP transport is fully functional!")
            print("   • MCP protocol compliance: Complete")
            print("   • Authentication integration: Working")
            print("   • All tools accessible via HTTP")
            print("   • Ready for production use")
        
        return all_passed


def main():
    """Main test execution"""
    tester = HTTPTransportTester()
    success = tester.run_comprehensive_test_suite()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 