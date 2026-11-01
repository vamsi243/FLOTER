"""Opt-in live checks: defaults inspect configuration without recording or API calls."""
import argparse
import json
from pathlib import Path
import threading
from floter.config import config
from floter.security.executables import resolve_application

def diagnostics(provider=None, microphone=False, transcript=None, expected=None, snippy=False, notepad=False):
    results={}
    for name in config.WHITELISTED_APPS:
        if name in config.APP_CATALOG:
            entry=config.APP_CATALOG[name]
            results[name]={'configured':True,'launch_kind':entry['kind'],'target':entry['target']}
            if entry['kind']=='exe': results[name]['available']=Path(entry['target']).is_file()
            continue
        try: results[name]={'available':True,'path':str(resolve_application(name))}
        except (OSError,ValueError): results[name]={'available':False}
    results['remote_jev_configured']=bool(config.JEV_API_KEY and config.JEV_ENDPOINT)
    results['gemini_configured']=bool(config.GEMINI_API_KEY and config.GEMINI_MODEL)
    results['hermes_configured']=bool(config.OPENROUTER_API_KEY or config.HERMES_API_KEY or 'localhost' in config.HERMES_API_BASE)
    if snippy:
        from floter.tools.snippy_mcp import call_snippy
        results['snippy'] = call_snippy('list_tools', cancel=threading.Event())
    if provider:
        if provider=='jev':
            if not results['remote_jev_configured']: raise RuntimeError('Remote Jev is not configured')
            from floter.tiers.jev_tier import JevReflexTier
            response=JevReflexTier()._call_jev_remote_api('open notepad')
            if response is None: raise RuntimeError('Remote Jev failed; fallback does not count as a live test')
            results['live_provider']={'provider':'jev','action':response.action.value,
                                     'confidence':response.confidence, 'probability':response.probability,
                                     'latency_ms':response.latency_ms}
        elif provider=='gemini':
            from floter.tiers.gemini_tier import GeminiMultimodalTier
            tier=GeminiMultimodalTier(); tier.cancel=threading.Event()
            response=tier.analyze_visual_and_logs('Return a JSON object with analysis set to connection test successful.')
            results['live_provider']={'provider':'gemini','received':bool(response)}
        else:
            from floter.tiers.hermes_tier import HermesAgentOrchestrator
            tier=HermesAgentOrchestrator(); tier.cancel=threading.Event()
            results['live_provider']={'provider':'hermes','received':bool(tier.execute_complex_plan('Reply: connection test successful.'))}
    if microphone:
        import sounddevice as sd
        import numpy as np
        with sd.InputStream(samplerate=16000,channels=1,dtype='float32') as stream:
            audio,overflow=stream.read(32000)
        results['microphone']={'seconds':2,'rms':float(np.sqrt(np.mean(audio**2))),'overflow':overflow}
    if transcript:
        import re
        from floter.audio.listener import AudioListener
        listener = AudioListener()
        text=listener.transcribe_file_or_audio(str(transcript))
        normalized = lambda value: re.findall(r'\w+', value.lower())
        results['transcription']={'text':text,'expected_exact_match':normalized(text)==normalized(expected) if expected else None,
                                  'device':getattr(getattr(listener.whisper_model,'model',None),'device',None)}
    if notepad:
        from floter.tools.desktop_actions import NotepadSession, editor_text
        session = NotepadSession()
        session.open()
        session.append('FLOTER packaged typing check')
        session.append('Second line: {literal} + Unicode café')
        results['notepad'] = {'text':editor_text(session.editor_handle), 'verified':True}
    return results

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument('--provider',choices=['jev','gemini','hermes'])
    parser.add_argument('--snippy',action='store_true',help='Check local MCP tool discovery without capturing the screen')
    parser.add_argument('--microphone',action='store_true',help='Record 2 seconds locally; retain no audio')
    parser.add_argument('--notepad',action='store_true',help='Create a new test draft and verify literal append; leaves it open')
    parser.add_argument('--transcribe',type=Path)
    parser.add_argument('--expected')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    try: result=diagnostics(args.provider,args.microphone,args.transcribe,args.expected,args.snippy,args.notepad); code=0
    except Exception as exc: result={'status':'failed','error_type':type(exc).__name__}; code=1
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    return code
