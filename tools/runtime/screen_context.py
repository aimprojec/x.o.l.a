"""On-demand screenshot -> local OCR -> grounded model context. 🦋
Requires Tesseract on PATH for OCR. Never reports invented screen text.
"""
import os
import shutil
import subprocess


def observe_screen(image_path=None):
    if image_path is None:
        from jarvis.hands import capture_screenshot
        capture = capture_screenshot()
        if capture.get('status') != 'SUCCESS':
            return capture
        image_path = capture['path']
    if not os.path.isfile(image_path):
        return {'status': 'ERROR', 'error': 'Screen image does not exist'}
    binary = os.environ.get('XOLA_TESSERACT_BIN') or shutil.which('tesseract')
    if not binary:
        return {'status': 'UNSUPPORTED', 'path': image_path,
                'error': 'Install Tesseract or set XOLA_TESSERACT_BIN to enable screen OCR'}
    try:
        result = subprocess.run([binary, image_path, 'stdout'], capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=20)
        if result.returncode:
            return {'status': 'ERROR', 'error': result.stderr[-1000:], 'path': image_path}
        return {'status': 'SUCCESS', 'path': image_path, 'text': result.stdout[:12000],
                'source': 'local_ocr', 'untrusted_content': True}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'status': 'ERROR', 'error': str(exc), 'path': image_path}
