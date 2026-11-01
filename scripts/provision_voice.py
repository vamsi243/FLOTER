"""Explicitly provision the small offline English model for source/frozen builds."""
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip'

def main():
    directory = ROOT / 'models'
    target = directory / 'vosk-model-small-en-us-0.15'
    if (target / 'am' / 'final.mdl').is_file():
        if not (target / 'LICENSE').is_file():
            urllib.request.urlretrieve('https://www.apache.org/licenses/LICENSE-2.0.txt', target / 'LICENSE')
        print('Offline Vosk model already provisioned.')
        return
    directory.mkdir(exist_ok=True)
    archive = directory / 'vosk-model-small-en-us-0.15.zip'
    urllib.request.urlretrieve(URL, archive)
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            resolved = (directory / member.filename).resolve()
            if not resolved.is_relative_to(target.resolve()):
                raise ValueError('Unexpected model archive path')
        package.extractall(directory)
    urllib.request.urlretrieve('https://www.apache.org/licenses/LICENSE-2.0.txt', target / 'LICENSE')
    print('Offline Vosk model provisioned:', target)

if __name__ == '__main__':
    main()
