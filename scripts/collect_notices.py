"""Collect installed runtime dependencies' licenses, retaining original text."""
import importlib.metadata as metadata
import json
from pathlib import Path
import re
import sys
from packaging.requirements import Requirement
ROOT=Path(__file__).resolve().parents[1]

def main():
    out=ROOT/'THIRD_PARTY_NOTICES'; out.mkdir(exist_ok=True)
    pending=['PySide6','Pillow','python-dotenv','jsonschema','mcp','sounddevice','numpy','certifi','faster-whisper','langchain-core','pywinauto','psutil','nvidia-cublas-cu12','nvidia-cudnn-cu12','nvidia-cuda-nvrtc-cu12','playwright']
    inventory=[]; seen=set()
    while pending:
        name=pending.pop(); canonical=re.sub(r'[-_.]+','-',name).lower()
        if canonical in seen: continue
        seen.add(canonical)
        try: dist=metadata.distribution(name)
        except metadata.PackageNotFoundError: continue
        for dependency in dist.requires or []:
            req=Requirement(dependency)
            if req.marker is None or req.marker.evaluate(): pending.append(req.name)
        copied=[]
        for file in dist.files or []:
            if any(part.lower().startswith(('license','copying','notice','copyright')) for part in file.parts) and dist.locate_file(file).is_file():
                target=out/canonical/str(file).replace('..','_')
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(dist.locate_file(file).read_bytes()); copied.append(str(target.relative_to(out)))
        inventory.append({'name':dist.metadata['Name'],'version':dist.version,'license':dist.metadata.get('License-Expression') or dist.metadata.get('License') or 'See upstream','files':copied})
    (out/'inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    (out/'README.txt').write_text('Collected dependency notices for FLOTER. Qt/PySide6 is dynamically linked. Qt source: https://code.qt.io/ and https://download.qt.io/official_releases/QtForPython/. Snippy is separately installed. Bundled Faster Whisper small.en weights: https://huggingface.co/Systran/faster-whisper-small.en (MIT). NVIDIA libraries retain their vendor licenses; the NVIDIA display driver is not bundled.\n',encoding='utf-8')
    license=Path(sys.base_prefix)/'LICENSE.txt'
    if license.exists(): (out/'PYTHON-LICENSE.txt').write_bytes(license.read_bytes())
    print(f'Collected notices for {len(inventory)} dependencies')

if __name__=='__main__': main()
