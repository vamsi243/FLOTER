"""Explicitly download GUI model weights; normal inference is offline."""
from pathlib import Path
import json
from huggingface_hub import snapshot_download
import easyocr

root=Path(__file__).resolve().parents[1]/'models/omniparser'
snapshot_download('microsoft/OmniParser-v2.0',revision='d10c4687d4af8245d67780ae59900f09660aad3a',local_dir=root,
    allow_patterns=['icon_detect_v3/*','icon_caption/*'],max_workers=1)
snapshot_download('microsoft/Florence-2-base',revision='5ca5edf5bd017b9919c05d08aebef5e4c7ac3bac',local_dir=root/'processor',
    allow_patterns=['*.json','*.py','*.txt'])
# Florence's custom model implementation is loaded from the local snapshot.
for name in ('configuration_florence2.py','modeling_florence2.py'):
    (root/'icon_caption'/name).write_bytes((root/'processor'/name).read_bytes())
for directory in (root/'icon_caption', root/'processor'):
    for path in directory.glob('*.json'):
        data=json.loads(path.read_text(encoding='utf-8'))
        if isinstance(data.get('auto_map'),dict):
            data['auto_map']={key:value.split('--')[-1] if isinstance(value,str) else value
                             for key,value in data['auto_map'].items()}
            path.write_text(json.dumps(data,indent=2),encoding='utf-8')
easyocr.Reader(['en'],gpu=False,model_storage_directory=str(root/'ocr'),verbose=False)
print('OmniParser models provisioned:',root)
