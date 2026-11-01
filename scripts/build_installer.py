"""Build the installer. Optional signing uses a certificate in the Windows user store."""
import argparse
import os
from pathlib import Path
import subprocess
import tomllib
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--compiler',default=str(ROOT/'.tools/Inno/ISCC.exe'))
    parser.add_argument('--publisher',default='FLOTER')
    parser.add_argument('--bundle-dir', type=Path, default=ROOT/'dist/FLOTER')
    parser.add_argument('--sign',action='store_true')
    args=parser.parse_args()
    bundle=args.bundle_dir.resolve()
    if not (bundle/'FLOTER.exe').is_file():
        parser.error('The selected bundle must contain FLOTER.exe')
    version=tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
    command=[args.compiler,f'/DAppVersion={version}',f'/DPublisher={args.publisher}',f'/DBundleDir={bundle}']
    if args.sign:
        tool=os.environ['FLOTER_SIGNTOOL']; thumb=os.environ['FLOTER_CERT_SHA1']; timestamp=os.environ['FLOTER_TIMESTAMP_URL']
        subprocess.run([tool,'sign','/sha1',thumb,'/fd','SHA256','/tr',timestamp,'/td','SHA256',str(bundle/'FLOTER.exe')],check=True)
        subprocess.run([tool,'verify','/pa',str(bundle/'FLOTER.exe')],check=True)
        command += ['/DSignRelease',f'/Sfloter=$q{tool}$q sign /sha1 {thumb} /fd SHA256 /tr $q{timestamp}$q /td SHA256 $f']
    command.append(str(ROOT/'packaging/floter.iss'))
    subprocess.run(command,check=True)
    if args.sign:
        subprocess.run([tool,'verify','/pa',str(ROOT/f'dist/installer/FLOTER-{version}-Setup.exe')],check=True)

if __name__=='__main__': main()
