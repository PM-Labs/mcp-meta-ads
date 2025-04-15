#!/bin/bash
echo "Initiating Meta OAuth authorization flow..."
curl -X POST "http://localhost:3000/api/meta/auth?api_token=pk_8ee8c727644d4d32b646ddcf16f2385e" -H "Content-Type: application/json"
read -p "Press enter after authorizing the app in the browser..."
