# test_telegram.py
# Run this cell after setup_colab.py to test Telegram

import importlib.util
import sys

DRIVE_BASE = '/content/drive/MyDrive/Colab Notebooks/MyOptionScanner'

# Load notifier module from Drive
spec = importlib.util.spec_from_file_location(
    'notifier',
    DRIVE_BASE + '/notifier.py'
)
notifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notifier)

# Run test
notifier.test_connection(DRIVE_BASE + '/config/config.json')
