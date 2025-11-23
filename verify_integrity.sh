#!/bin/bash

# ==============================
# Error Handling
# ==============================
set -euo pipefail
trap 'echo "[ERROR] Integrity script failed at line $LINENO" | tee -a "$LOG_FILE"' ERR

# ==============================
# Input Args
# ==============================
ORGANIZED_DIR="$1"

if [ -z "$ORGANIZED_DIR" ]; then
    echo "Usage: $0 <organized_directory>"
    exit 1
fi

if [ ! -d "$ORGANIZED_DIR" ]; then
    echo "[ERROR] Organized directory does not exist: $ORGANIZED_DIR"
    exit 1
fi

# Correct checksum file path
CHECKSUM_LOG="$ORGANIZED_DIR/organized_files_checksum.log"
LOG_FILE="$ORGANIZED_DIR/integrity_check.log"

if [ ! -f "$CHECKSUM_LOG" ]; then
    echo "[ERROR] Checksum log not found at: $CHECKSUM_LOG"
    exit 1
fi

# ==============================
# Logger
# ==============================
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "[INFO] Verifying file integrity..."
log "[INFO] Using checksum log: $CHECKSUM_LOG"

# ==============================
# Run checksum verification
# ==============================
if sha256sum -c "$CHECKSUM_LOG" 2>&1 | tee -a "$LOG_FILE"; then
    log "[INFO] Integrity OK. All files are unchanged."
else
    log "[WARNING] Integrity check failed! Files missing or modified."
fi

log "[INFO] Verification complete."
