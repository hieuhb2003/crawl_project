#!/bin/bash

URL=""
ARCHIVE_FILE="archive.txt"
OUTPUT_DIR="downloads" 
BATCH_SIZE=10

touch "$ARCHIVE_FILE"
mkdir -p "$OUTPUT_DIR"

while true
do
    echo "----------------------------------------"
    
    SIZE_BEFORE=$(wc -c < "$ARCHIVE_FILE")
    
    echo "[Network] Get new IP..."
    warp-cli disconnect
    sleep 3
    warp-cli connect
    sleep 10 
    
    yt-dlp -x --audio-format mp3 \
    --download-archive "$ARCHIVE_FILE" \
    --max-downloads "$BATCH_SIZE" \
    --sleep-requests 2 \
    -o "$OUTPUT_DIR/%(title)s.%(ext)s" \
    "$URL"
    
    SIZE_AFTER=$(wc -c < "$ARCHIVE_FILE")
    
    if [ "$SIZE_BEFORE" -eq "$SIZE_AFTER" ]; then
        echo "[INFO] Archive file size not changed."
        echo "[STOP] All videos from the channel have been downloaded!"
        break
    else
        echo "[CONTINUE] New videos downloaded, continue loop..."
    fi
    
    sleep 5
done

