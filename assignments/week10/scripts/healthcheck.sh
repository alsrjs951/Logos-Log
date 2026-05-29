#!/usr/bin/env bash

# This script verifies the health of the deployed live URL by polling the endpoint.
# Usage: ./healthcheck.sh <target-url> [max-retries] [sleep-seconds]

TARGET_URL=${1:-"http://localhost:3000/health"}
MAX_RETRIES=${2:-15}
SLEEP_SECS=${3:-5}

echo "=================================================="
echo "🛡️ Starting Deployment Health Check"
echo "Target URL  : $TARGET_URL"
echo "Max Retries : $MAX_RETRIES"
echo "Interval    : $SLEEP_SECS seconds"
echo "=================================================="

for ((i=1; i<=MAX_RETRIES; i++)); do
  echo "Attempt $i/$MAX_RETRIES: Fetching $TARGET_URL..."
  
  # Fetch HTTP status code and body
  RESPONSE=$(curl -s -w "\n%{http_code}" --max-time 10 "$TARGET_URL")
  CURL_EXIT_CODE=$?
  
  if [ $CURL_EXIT_CODE -ne 0 ]; then
    echo "⚠️ Network error occurred (curl exit code: $CURL_EXIT_CODE). Server might be booting up."
  else
    # Extract status code (last line) and body (all lines except last)
    HTTP_STATUS=$(echo "$RESPONSE" | tail -n1)
    HTTP_BODY=$(echo "$RESPONSE" | sed '$d')
    
    echo "Response Code: $HTTP_STATUS"
    
    if [ "$HTTP_STATUS" -eq 200 ]; then
      echo "✅ Server responded with HTTP 200 OK!"
      echo "Response Body: $HTTP_BODY"
      
      # Additional validation (check if JSON contains 'healthy' or 'ok')
      if echo "$HTTP_BODY" | grep -qE "healthy|ok|status"; then
        echo "🎉 Health check PASSED successfully!"
        echo "=================================================="
        exit 0
      else
        echo "⚠️ Warning: Response body did not contain expected keywords."
      fi
    else
      echo "❌ Server responded with HTTP status $HTTP_STATUS."
    fi
  fi
  
  echo "Waiting $SLEEP_SECS seconds before next attempt..."
  sleep "$SLEEP_SECS"
done

echo "=================================================="
echo "❌ Health check TIMEOUT. Server failed to become healthy."
echo "=================================================="
exit 1
