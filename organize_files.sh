#!/bin/bash

# Error Handling + Logging

set -euo pipefail
trap 'echo "[ERROR] Script failed at line $LINENO" | tee -a "$LOG_FILE"' ERR


# Input Args

SOURCE_DIR="$1"
ORGANIZED_DIR="$2"

if [ -z "$SOURCE_DIR" ] || [ -z "$ORGANIZED_DIR" ]; then
    echo "Usage: $0 <source_directory> <organized_directory>"
    exit 1
fi

# Validate source directory
if [ ! -d "$SOURCE_DIR" ]; then
    echo "[ERROR] Source directory does not exist: $SOURCE_DIR"
    exit 1
fi

# Ensure target directory exists
mkdir -p "$ORGANIZED_DIR"

# Paths
CHECKSUM_LOG="$ORGANIZED_DIR/organized_files_checksum.log"
LOG_FILE="$ORGANIZED_DIR/organizer.log"


# Logger Function

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "[INFO] Script started"
log "[INFO] Source: $SOURCE_DIR"
log "[INFO] Output: $ORGANIZED_DIR"


# BACKUP FEATURE 

BACKUP_DIR="$ORGANIZED_DIR/backups"
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.zip"

log "[INFO] Creating backup before processing..."

if zip -r "$BACKUP_FILE" "$SOURCE_DIR" &>/dev/null; then
    log "[INFO] Backup created successfully: $BACKUP_FILE"
else
    log "[ERROR] Backup failed — aborting for safety."
    exit 1
fi


# Create Category Folders

mkdir -p "$ORGANIZED_DIR/finance_sheets"
mkdir -p "$ORGANIZED_DIR/supplier_bills"
mkdir -p "$ORGANIZED_DIR/images"
mkdir -p "$ORGANIZED_DIR/pdf_documents"
mkdir -p "$ORGANIZED_DIR/spreadsheets"
mkdir -p "$ORGANIZED_DIR/text_files"
mkdir -p "$ORGANIZED_DIR/data_files"
mkdir -p "$ORGANIZED_DIR/log_files"
mkdir -p "$ORGANIZED_DIR/other"


# Process Files

for file in "$SOURCE_DIR"/*; do
    [ -e "$file" ] || continue

    filename=$(basename "$file")
    extension="${filename##*.}"

    # Classification
    if [[ "$filename" == *"finance"* ]]; then
        dest="finance_sheets"
    elif [[ "$filename" == *"supplier"* ]]; then
        dest="supplier_bills"
    elif [[ "$extension" =~ ^(jpg|jpeg|png|gif)$ ]]; then
        dest="images"
    elif [[ "$extension" =~ ^(pdf)$ ]]; then
        dest="pdf_documents"
    elif [[ "$extension" =~ ^(csv|xlsx)$ ]]; then
        dest="spreadsheets"
    elif [[ "$extension" =~ ^(txt|md)$ ]]; then
        dest="text_files"
    elif [[ "$extension" =~ ^(json|xml|yaml|yml)$ ]]; then
        dest="data_files"
    elif [[ "$extension" =~ ^(log)$ ]]; then
        dest="log_files"
    else
        dest="other"
    fi

    destination="$ORGANIZED_DIR/$dest/$filename"
    mkdir -p "$ORGANIZED_DIR/$dest"

    # Move file
    if mv "$file" "$destination"; then
        log "[INFO] Moved $filename to $dest"
    else
        log "[ERROR] Failed to move $filename"
        continue
    fi

    # Checksum
    if sha256sum "$destination" >> "$CHECKSUM_LOG"; then
        log "[INFO] Logged checksum for $filename"
    else
        log "[ERROR] Failed to checksum $filename"
        continue
    fi
done


# Apply Permissions (Option A)

log "[INFO] Applying category-based file permissions..."

# Sensitive — only you
chmod -R 600 "$ORGANIZED_DIR/finance_sheets"
chmod -R 600 "$ORGANIZED_DIR/data_files"
chmod -R 600 "$ORGANIZED_DIR/log_files"

# Moderately sensitive
chmod -R 640 "$ORGANIZED_DIR/supplier_bills"
chmod -R 640 "$ORGANIZED_DIR/pdf_documents"
chmod -R 640 "$ORGANIZED_DIR/spreadsheets"

# Public-readable (non-sensitive)
chmod -R 644 "$ORGANIZED_DIR/images"
chmod -R 644 "$ORGANIZED_DIR/text_files"
chmod -R 644 "$ORGANIZED_DIR/other"

log "[INFO] Permissions applied successfully."
log "[INFO] File organization completed successfully."
