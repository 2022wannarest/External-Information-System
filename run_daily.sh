#!/bin/bash

# 取得目前腳本所在的目錄
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "Starting Daily Research Task on Mac..."

# 進入 Mac 的虛擬環境 (Mac 的路徑是 bin 而不是 Scripts)
if [ -d "./venv" ]; then
    source ./venv/bin/activate
    python3 main.py
else
    echo "Error: Virtual environment (venv) not found."
fi

echo "Task Completed."
