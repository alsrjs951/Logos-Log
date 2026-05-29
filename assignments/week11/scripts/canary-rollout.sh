#!/usr/bin/env bash

# Canary Rollout & Automatic Rollback Simulator
# Usage: ./canary-rollout.sh [healthy|unhealthy]

MODE=${1:-"healthy"}
THRESHOLD_ERROR_RATE=5.0

echo "=================================================="
echo "🚀 Starting Canary Rollout Strategy Simulation"
echo "Rollout Plan : 1% -> 10% -> 50% -> 100%"
echo "Simulation Mode : $MODE"
echo "Rollback Threshold Error Rate : $THRESHOLD_ERROR_RATE%"
echo "=================================================="

# Function to simulate health check
# Args: percentage, simulate_failure (true/false)
perform_health_check() {
  local pct=$1
  local fail=$2
  
  echo "Checking Canary ($pct%) health..."
  sleep 1
  
  if [ "$fail" = "true" ]; then
    # Simulate a high error rate
    local err_rate=$(echo "scale=1; 12.0 + $RANDOM % 50 / 10" | bc)
    echo "⚠️  Canary Uptime Check Failed! Error Rate: $err_rate%"
    echo "Evaluating rollback condition: $err_rate% > $THRESHOLD_ERROR_RATE%"
    return 1
  else
    local err_rate=$(echo "scale=1; 0.1 + $RANDOM % 10 / 10" | bc)
    echo "✅ Canary Uptime Check Passed. Error Rate: $err_rate% (Healthy)"
    return 0
  fi
}

rollback() {
  local failed_pct=$1
  echo "=================================================="
  echo "🚨 [CRITICAL ALERT] Canary health check failed at $failed_pct%!"
  echo "Executing automatic rollback sequence..."
  echo "=================================================="
  
  sleep 1.5
  echo "🔄 Re-routing traffic: 0% Canary / 100% Stable (v1.0.0)"
  echo "🚫 Evicting Canary instances from load balancer..."
  
  sleep 1
  echo "🛡️ Verifying stable service health..."
  echo "✅ Stable Service (v1.0.0) is 100% operational."
  echo "🎉 [SUCCESS] Rollback completed. Stable service successfully restored."
  echo "=================================================="
  exit 1
}

# Step 1: 1% Canary Rollout
echo "🌐 Step 1: Deploying Canary v1.1.0 (Routing 1% traffic, 99% stable)"
if ! perform_health_check 1 "false"; then
  rollback 1
fi
echo ""

# Step 2: 10% Canary Rollout
echo "🌐 Step 2: Increasing Canary scale (Routing 10% traffic, 90% stable)"
if [ "$MODE" = "unhealthy" ]; then
  # Trigger failure at 10% stage
  if ! perform_health_check 10 "true"; then
    rollback 10
  fi
else
  if ! perform_health_check 10 "false"; then
    rollback 10
  fi
fi
echo ""

# Step 3: 50% Canary Rollout
echo "🌐 Step 3: Scaling Canary to half-load (Routing 50% traffic, 50% stable)"
if ! perform_health_check 50 "false"; then
  rollback 50
fi
echo ""

# Step 4: 100% Canary Rollout
echo "🌐 Step 4: Finalizing rollout (Routing 100% traffic to v1.1.0)"
sleep 1
echo "🎉 [SUCCESS] Canary Rollout completed. 100% traffic is now served by v1.1.0."
echo "=================================================="
exit 0
