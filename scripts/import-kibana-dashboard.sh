#!/bin/bash
# Kibana 대시보드 자동 임포트 스크립트
# 사용법: ./scripts/import-kibana-dashboard.sh <dashboard_file.ndjson> [kibana_url]

set -euo pipefail

KIBANA_URL="${2:-http://localhost:5601}"

if [ ! -f "$1" ]; then
    echo "Error: Dashboard file not found: $1"
    exit 1
fi

echo "Importing dashboard from: $1"
response=$(curl -s -w "%{http_code}" -o /tmp/kibana_response.json \
    -X POST "${KIBANA_URL}/api/saved_objects/_import" \
    -H "kbn-xsrf: true" \
    --form file=@"$1")

if [ "$response" -eq 200 ]; then
    echo "Import successful"
    exit 0
else
    echo "Import failed (HTTP $response)"
    cat /tmp/kibana_response.json
    exit 1
fi