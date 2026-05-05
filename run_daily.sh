#!/bin/bash

# 獲取腳本所在的目錄並進入
cd "$(dirname "$0")"

echo "[System] Starting Automation Pipeline (macOS)..."

# 1. 啟用虛擬環境
source venv/bin/activate

# 2. 執行主程式
python3 main.py

echo "[System] Task Completed."
