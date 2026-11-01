import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict
import sys
from dotenv import load_dotenv
from floter.app_catalog import load_catalog

# Keys and settings come from exactly one file: FLOTER_ENV_FILE if set, else the source
# folder's .env for source runs, else %USERPROFILE%\.floter\.env for the installed EXE.
_DEFAULT_ENV = Path.home() / ".floter" / ".env" if getattr(sys, "frozen", False) else Path(__file__).parent / ".env"
ENV_FILE = Path(os.getenv("FLOTER_ENV_FILE") or _DEFAULT_ENV)
load_dotenv(ENV_FILE, override=False)


DEFAULT_HERMES_API_BASE = "https://openrouter.ai/api/v1"
DEFAULT_JEV_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
# Gemini's OpenAI-compatible endpoint lets one Gemini key drive navigation and advice.
GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
# Invalid user values fall back to defaults; the UI shows these at startup.
CONFIG_WARNINGS: List[str] = []

def _number(name, default, cast, low, high):
    raw = os.getenv(name, "")
    if not raw.strip():
        return default
    try:
        value = cast(raw)
        if not low <= value <= high:
            raise ValueError
        return value
    except ValueError:
        CONFIG_WARNINGS.append(f"{name}={raw!r} is invalid (allowed {low}–{high}); using {default}.")
        return default

def _choice(name, default, allowed):
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    if raw in allowed:
        return raw
    CONFIG_WARNINGS.append(f"{name}={raw!r} is invalid (allowed {', '.join(allowed)}); using {default}.")
    return default

def model_chain(primary, fallbacks):
    """Primary model first, then distinct fallbacks, in order."""
    return list(dict.fromkeys(m for m in (primary, *fallbacks) if m))

def _catalog():
    try:
        return load_catalog()
    except (OSError, ValueError) as exc:
        CONFIG_WARNINGS.append(f"Application catalog could not be read ({type(exc).__name__}); registered apps are unavailable.")
        return {}

@dataclass
class FloterConfig:
    APP_CATALOG: Dict = field(default_factory=_catalog)
    # API Keys
    GEMINI_API_KEY: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    JEV_API_KEY: str = field(default_factory=lambda: os.getenv("Jev_API_Key", ""))
    OPENROUTER_API_KEY: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", ""))
    HERMES_API_KEY: str = field(default_factory=lambda: os.getenv("HERMES_API_KEY", ""))
    
    # Model Configurations
    GEMINI_MODEL: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", ""))
    GEMINI_VISION_MODEL: str = field(default_factory=lambda: os.getenv("GEMINI_VISION_MODEL", ""))
    # Comma-separated models tried in order when a Gemini call is busy or fails.
    GEMINI_FALLBACK_MODELS: List[str] = field(default_factory=lambda: [
        m.strip() for m in os.getenv("GEMINI_FALLBACK_MODELS", "").split(",") if m.strip()])
    HERMES_MODEL: str = field(default_factory=lambda: os.getenv("HERMES_MODEL", "nousresearch/hermes-3-llama-3.1-70b"))
    HERMES_API_BASE: str = field(default_factory=lambda: os.getenv("HERMES_API_BASE") or DEFAULT_HERMES_API_BASE)
    JEV_ENDPOINT: str = field(default_factory=lambda: os.getenv("JEV_ENDPOINT") or DEFAULT_JEV_ENDPOINT)
    JEV_MODEL: str = field(default_factory=lambda: os.getenv("JEV_MODEL", ""))
    
    # Paths
    HOME_DIR: Path = Path.home()
    HERMES_BASE_DIR: Path = Path.home() / ".hermes"
    HERMES_MEMORY_DIR: Path = Path.home() / ".hermes" / "memory"
    HERMES_SKILLS_DIR: Path = Path.home() / ".hermes" / "skills"
    SNIPPY_CACHE_DIR: Path = Path.home() / ".floter" / "cache"
    
    SNIPPY_URL: str = field(default_factory=lambda: os.getenv("SNIPPY_URL", ""))
    SNIPPY_COMMAND: str = field(default_factory=lambda: os.getenv("SNIPPY_COMMAND", ""))
    SNIPPY_ARGS: str = field(default_factory=lambda: os.getenv("SNIPPY_ARGS", '["--mcp-stdio"]'))
    SNIPPY_CWD: str = field(default_factory=lambda: os.getenv("SNIPPY_CWD", ""))
    MICA_ENABLED: bool = field(default_factory=lambda: os.getenv("MICA_ENABLED", "1") == "1")
    CAMERA_DEVICE: str = field(default_factory=lambda: os.getenv('CAMERA_DEVICE', ''))
    CAMERA_SAVE_DIR: str = field(default_factory=lambda: os.getenv('CAMERA_SAVE_DIR') or str(Path.home() / 'Pictures' / 'FLOTER'))
    CAMERA_VIDEO_SECONDS: int = field(default_factory=lambda: _number('CAMERA_VIDEO_SECONDS', 60, int, 1, 300))
    CAMERA_RECORD_AUDIO: bool = field(default_factory=lambda: os.getenv('CAMERA_RECORD_AUDIO', '1') == '1')
    # Experimental: FLOTER-owned browser driven by Playwright (installed Edge/Chrome/Brave, own profile).
    BROWSER_AUTOMATION: bool = field(default_factory=lambda: os.getenv('BROWSER_AUTOMATION', '0') == '1')
    BROWSER_CHANNEL: str = field(default_factory=lambda: _choice('BROWSER_CHANNEL', 'msedge', ('msedge', 'chrome', 'brave')))
    BROWSER_PROFILE_DIR: str = field(default_factory=lambda: os.getenv('BROWSER_PROFILE_DIR') or str(Path.home() / '.floter' / 'browser-profile'))
    # Hosts (and their subdomains) where the browser agent may click or type.
    BROWSER_INPUT_SITES: List[str] = field(default_factory=lambda: [
        s.strip().lower() for s in os.getenv('BROWSER_INPUT_SITES', 'youtube.com,google.com,wikipedia.org').split(',') if s.strip()])

    # Audio / Mic Settings
    WAKE_WORD: str = field(default_factory=lambda: 'hey rex' if os.getenv('WAKE_WORD', 'hey rex').lower() == 'hey floter' else os.getenv('WAKE_WORD', 'hey rex'))
    AUDIO_SAMPLE_RATE: int = 16000
    AUDIO_CHANNELS: int = 1
    AUDIO_CHUNK_SIZE: int = 1024
    STT_ENGINE: str = field(default_factory=lambda: os.getenv("STT_ENGINE", "auto"))
    WHISPER_MODEL_PATH: str = field(default_factory=lambda: os.getenv('WHISPER_MODEL_PATH') or str(Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'models' / 'faster-whisper-small.en'))
    WHISPER_DEVICE: str = field(default_factory=lambda: os.getenv('WHISPER_DEVICE', 'auto'))
    SPEECH_SILENCE_SECONDS: float = field(default_factory=lambda: _number('SPEECH_SILENCE_SECONDS', .7, float, .35, 2.))
    SPEECH_PARTIAL_SECONDS: float = field(default_factory=lambda: _number('SPEECH_PARTIAL_SECONDS', .6, float, .3, 5.))
    VOICE_FOLLOWUP_SECONDS: float = field(default_factory=lambda: _number('VOICE_FOLLOWUP_SECONDS', 20., float, 0., 60.))
    VOSK_MODEL_PATH: str = field(default_factory=lambda: os.getenv("VOSK_MODEL_PATH") or str(
        Path(getattr(sys, '_MEIPASS', Path(__file__).parent)) / 'models' / 'vosk-model-small-en-us-0.15'))
    
    # Security Whitelists
    WHITELISTED_APPS: Dict[str, List[str]] = field(default_factory=lambda: {
        "brave": ["brave", "brave.exe", "brave-browser", r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"],
        "chrome": ["chrome", "chrome.exe", "google-chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"],
        "terminal": ["wt.exe", "powershell.exe", "cmd.exe", "gnome-terminal", "alacritty", "xterm"],
        "vscode": ["code", "code.cmd", "code.exe"],
        "notepad": ["notepad", "notepad.exe", "gedit", "kate", "mousepad"],
        "calculator": ["calc.exe", "gnome-calculator", "kcalc"],
        "edge": ["msedge.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                 r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"],
        "firefox": ["firefox.exe", r"C:\Program Files\Mozilla Firefox\firefox.exe"],
    })
    # Allowlisted apps that can open a URL passed as their first argument.
    BROWSERS: tuple = ("brave", "chrome", "edge", "firefox")

    # Whitelisted URLs for web actions
    WHITELISTED_URL_MAP: Dict[str, str] = field(default_factory=lambda: {
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "gmail": "https://mail.google.com",
        "google-drive": "https://drive.google.com",
        "google-docs": "https://docs.google.com",
        "google-calendar": "https://calendar.google.com",
        "google-maps": "https://maps.google.com",
        "outlook": "https://outlook.live.com/mail/",
        "github": "https://www.github.com",
        "wikipedia": "https://www.wikipedia.org",
        "linkedin": "https://www.linkedin.com",
        "reddit": "https://www.reddit.com",
        "netflix": "https://www.netflix.com",
        "chatgpt": "https://chatgpt.com",
        "gemini": "https://gemini.google.com",
        "claude": "https://claude.ai",
    })

    def __post_init__(self):
        for name in ('claude','gemini'):
            target=os.getenv(name.upper()+'_APP_PATH','')
            if target and Path(target).is_absolute() and Path(target).suffix.lower()=='.exe' and Path(target).is_file():
                self.APP_CATALOG[name]={'name':name.title(),'kind':'exe','target':target,'executable':target}
        for name, entry in self.APP_CATALOG.items():
            self.WHITELISTED_APPS.setdefault(name, [entry['target']] if entry['kind'] == 'exe' else [])
        # Without a separate reasoning provider, reuse the Gemini key and model.
        self.REASONING_PROVIDER = 'hermes'
        self.REASONING_FALLBACK_MODELS: List[str] = []
        if (self.GEMINI_API_KEY and self.GEMINI_MODEL and not os.getenv('HERMES_API_BASE')
                and not (self.HERMES_API_KEY or self.OPENROUTER_API_KEY)):
            self.HERMES_API_BASE = GEMINI_OPENAI_BASE
            self.HERMES_API_KEY = self.GEMINI_API_KEY
            self.HERMES_MODEL = self.GEMINI_MODEL
            self.REASONING_PROVIDER = 'gemini'
            self.REASONING_FALLBACK_MODELS = self.GEMINI_FALLBACK_MODELS

config = FloterConfig()
