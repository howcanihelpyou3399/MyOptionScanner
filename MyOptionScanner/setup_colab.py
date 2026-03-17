# setup_colab.py
# Run this single cell in Google Colab to set up everything
# Usage: exec(open('/content/MyOptionScanner/setup_colab.py').read())

import os
import subprocess
import shutil

print("=" * 50)
print("  MyOptionScanner - Colab Setup")
print("=" * 50)

# Mount Google Drive
print("\n[1/4] Mounting Google Drive...")
from google.colab import drive
drive.mount('/content/drive', force_remount=True)
print("      OK")

# Define paths
REPO = '/content/MyOptionScanner'
DRIVE_BASE = '/content/drive/MyDrive/Colab Notebooks/MyOptionScanner'

# Create Drive directories
print("\n[2/4] Creating directories on Drive...")
for d in ['config', 'input', 'output', 'logs']:
    os.makedirs(DRIVE_BASE + '/' + d, exist_ok=True)
print("      OK - " + DRIVE_BASE)

# Install dependencies
print("\n[3/4] Installing dependencies...")
subprocess.run(['pip', 'install', 'yfinance', 'pytz', 'requests', 'pandas', 'numpy', '-q'])
print("      OK")

# Copy files from repo to Drive
print("\n[4/4] Copying files to Drive...")
files_to_copy = [
    'notifier.py',
    'config/config.example.json',
    'input/watchlist.csv',
]
for f in files_to_copy:
    src = REPO + '/' + f
    dst = DRIVE_BASE + '/' + f
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print("      copied: " + f)
    else:
        print("      SKIP (not found): " + f)

# Check config.json
config_path = DRIVE_BASE + '/config/config.json'
if not os.path.exists(config_path):
    shutil.copy2(DRIVE_BASE + '/config/config.example.json', config_path)
    print("\nWARNING: config.json created from template")
    print("Please edit " + config_path)
    print("Fill in your Telegram token and chat_id")
else:
    print("\nOK - config.json already exists")

print("\n" + "=" * 50)
print("  Setup complete")
print("  Next: run test_telegram.py")
print("=" * 50)
