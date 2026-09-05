"""Read-only installation diagnostics. No model calls or microphone capture. 🦋"""
import os
import platform
import shutil
import sys
from pathlib import Path


def diagnose():
    root = Path(__file__).resolve().parents[2]
    agy = os.environ.get('XOLA_AGY_BIN') or shutil.which('agy')
    tesseract = os.environ.get('XOLA_TESSERACT_BIN') or shutil.which('tesseract')
    return {
        'python': platform.python_version(),
        'python_supported': sys.version_info >= (3, 10),
        'platform': platform.system(),
        'project_directory': str(root),
        'project_writable': os.access(root, os.W_OK),
        'model_cli': agy,
        'model_cli_exists': bool(agy and Path(agy).is_file()),
        'configured_model': os.environ.get('XOLA_MODEL', 'gemini-3.8-flash-high'),
        'model_live_tested': False,
        'powershell': shutil.which('powershell'),
        'windows_voice_available_to_test': sys.platform == 'win32' and bool(shutil.which('powershell')),
        'ocr_binary': tesseract,
        'ocr_available_to_test': bool(tesseract and Path(tesseract).is_file()),
        'notes': ['Model name is inherited from the prototype; set XOLA_MODEL to a model your CLI supports.',
                  'Live model, microphone, speech language and desktop permissions require local verification.'],
    }
