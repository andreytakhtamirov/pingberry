#!/bin/sh

# Absolute path to the current directory (portable even from symlink)
BASEDIR="$(cd "$(dirname "$0")" && pwd)"

TARGET_PARENT="$HOME/apps"
APP_NAME="$(basename "$BASEDIR")"
TARGET_DIR="$TARGET_PARENT/$APP_NAME"

# Location of the data file we want to preserve
PRESERVED_FILE_REL="app/client_data.json"
PRESERVED_FILE_SRC="$TARGET_DIR/$PRESERVED_FILE_REL"

# Temp location for backup
TMP_BACKUP="/tmp/client_data_backup_$$.json"

if [ "$BASEDIR" != "$TARGET_DIR" ]; then
    echo "Preparing to move '$APP_NAME' to home directory..."

    # If the target already exists, back up encryption keys
    if [ -f "$PRESERVED_FILE_SRC" ]; then
        echo "Backing up existing encryption keys..."
        cp "$PRESERVED_FILE_SRC" "$TMP_BACKUP"
    fi

    # Delete old copy
    if [ -d "$TARGET_DIR" ]; then
        echo "Removing existing PingBerry installation"
        rm -rf "$TARGET_DIR"
    fi

    echo "Moving PingBerry to apps"
    mkdir -p "$TARGET_PARENT"

    mv "$BASEDIR" "$TARGET_PARENT" || {
        echo "Failed to move directory!"
        exit 1
    }

    # Restore preserved client data if backed up
    if [ -f "$TMP_BACKUP" ]; then
        echo "Restoring preserved encryption keys..."
        cp "$TMP_BACKUP" "$TARGET_DIR/$PRESERVED_FILE_REL"
        rm "$TMP_BACKUP"
    fi

    echo "Restarting installer from new location..."
    exec "$TARGET_DIR/$(basename "$0")" "$@"
    # exec replaces current process; no code below runs here
fi

# Now we are running inside the target dir ($HOME/apps/pingberry-env)
echo "Running actual installer from home directory"

SKIP_ROTATION_FLAG=""

# Skip registering if upgrading PingBerry
if [ -f "$TARGET_DIR/$PRESERVED_FILE_REL" ]; then
    SKIP_ROTATION_FLAG="--skip-rotation"
fi

# Run the actual app script using the embedded bash
"$BASEDIR/bin/bash" "$BASEDIR/app/install.sh" $SKIP_ROTATION_FLAG "$@"
