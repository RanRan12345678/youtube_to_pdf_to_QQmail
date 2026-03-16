#!/bin/bash
# Runner script for YouTube Newsletter
# This script is called by launchd on a schedule

# Change to the project directory
cd /Users/dajiu/project_tutor/youtube-to-ebook

# Create logs directory if it doesn't exist
mkdir -p logs

# 添加代理设置（根据你的实际代理配置）
export http_proxy="http://127.0.0.1:15236"
export https_proxy="http://127.0.0.1:15236"

# Prevent system from sleeping during execution
# This requires caffeinate to be available (built-in on macOS)
caffeinate -d -s -w $ &

# Log start time
echo "=== Script started at $(date) ===" >> /Users/dajiu/project_tutor/youtube-to-ebook/logs/newsletter.log

# Run the newsletter generator using virtual environment Python
# Use the Python interpreter from the virtual environment
/Users/dajiu/project_tutor/youtube-to-ebook/venv/bin/python /Users/dajiu/project_tutor/youtube-to-ebook/main.py >> /Users/dajiu/project_tutor/youtube-to-ebook/logs/newsletter.log 2>&1

# Add a timestamp to the log
echo "--- Completed at $(date) ---" >> /Users/dajiu/project_tutor/youtube-to-ebook/logs/newsletter.log
