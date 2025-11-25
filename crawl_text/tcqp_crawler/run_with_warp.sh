#!/bin/bash

# Script to run VBPL Crawler with Warp IP rotation
# Runs for 60 seconds, then rotates IP.

while true; do
    echo "=================================="
    echo "Starting Crawler..."
    echo "=================================="
    
    # Run python script in background
    python crawl_all.py &
    CRAWLER_PID=$!
    
    echo "Crawler started with PID: $CRAWLER_PID"
    echo "Running for 60 seconds..."
    
    # Wait for 60 seconds
    sleep 60
    
    echo "Stopping Crawler..."
    kill $CRAWLER_PID
    wait $CRAWLER_PID 2>/dev/null
    
    echo "=================================="
    echo "Rotating IP with Warp..."
    echo "=================================="
    
    echo "Disconnecting Warp..."
    warp-cli disconnect
    
    echo "Waiting 5 seconds..."
    sleep 5
    
    echo "Connecting Warp..."
    warp-cli connect
    
    echo "Waiting 5 seconds for connection..."
    sleep 5
    
    echo "Ready for next cycle."
    echo ""
done
