"""Explicit download of local small.en weights; listening never downloads."""
from pathlib import Path
from huggingface_hub import snapshot_download
import urllib.request

if __name__ == '__main__':
    destination = Path(__file__).resolve().parents[1] / 'models' / 'faster-whisper-small.en'
    snapshot_download('Systran/faster-whisper-small.en', local_dir=destination,
                      allow_patterns=['*.json', '*.txt', 'model.bin', 'LICENSE*', 'README*'])
    if not (destination / 'LICENSE').is_file():
        urllib.request.urlretrieve('https://raw.githubusercontent.com/openai/whisper/main/LICENSE', destination / 'LICENSE')
    print('Speech model provisioned:', destination)
