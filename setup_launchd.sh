#!/bin/bash
# Setup script for launchd automatic execution
# This script helps you install and configure the launchd job

echo "=== YouTube Newsletter Launchd Setup ==="
echo ""

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "Error: This script is designed for macOS only."
    exit 1
fi

# Get the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Project directory: $PROJECT_DIR"

# Create logs directory
echo "Creating logs directory..."
mkdir -p "$PROJECT_DIR/logs"

# Make the run script executable
echo "Making run_newsletter.sh executable..."
chmod +x "$PROJECT_DIR/run_newsletter.sh"

# Check if plist file exists
PLIST_FILE="$PROJECT_DIR/com.youtube.newsletter.plist"
if [[ ! -f "$PLIST_FILE" ]]; then
    echo "Error: plist file not found at $PLIST_FILE"
    exit 1
fi

# Copy plist to LaunchAgents
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$LAUNCH_AGENTS_DIR/com.youtube.newsletter.plist"

echo "Copying plist to LaunchAgents..."
cp "$PLIST_FILE" "$TARGET_PLIST"

# Unload any existing job (ignore errors)
echo "Unloading any existing job..."
launchctl unload "$TARGET_PLIST" 2>/dev/null || true

# Load the job
echo "Loading the job..."
launchctl load "$TARGET_PLIST"

# Check if job is loaded
if launchctl list | grep -q "com.youtube.newsletter"; then
    echo "✓ Job successfully loaded!"
    echo ""
    echo "The job will run every day at 7:00 AM"
    echo "Your Mac will wake from sleep to execute the task"
    echo ""
    echo "To check the status:"
    echo "  launchctl list | grep com.youtube.newsletter"
    echo ""
    echo "To view logs:"
    echo "  tail -f $PROJECT_DIR/logs/newsletter.log"
    echo "  tail -f $PROJECT_DIR/logs/launchd.log"
    echo ""
    echo "To stop the job:"
    echo "  launchctl unload $TARGET_PLIST"
    echo ""
    echo "To restart the job:"
    echo "  launchctl unload $TARGET_PLIST"
    echo "  launchctl load $TARGET_PLIST"
else
    echo "✗ Failed to load job. Check the logs for errors."
    echo "Try running manually: $PROJECT_DIR/run_newsletter.sh"
fi