import os
import sys
import subprocess
import time
import io
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
import shutil
import string

from floter.config import config
from floter.security.sandbox import GuardrailViolationError, SafeFileSystem

class FastMCPToolRegistry:
    """Registry of FastMCP tools adhering strictly to Read & Create Only rules."""

    @staticmethod
    def open_website(target: str, browser: Optional[str] = None) -> str:
        from floter.tools.desktop_actions import open_url
        if target not in config.WHITELISTED_URL_MAP:
            raise GuardrailViolationError('Website is not configured')
        used = open_url(config.WHITELISTED_URL_MAP[target], browser)
        return f'Opened website: {target} ({used})'

    @staticmethod
    def launch_application(target: str) -> str:
        """
        Matches whitelisted app targets and launches process immediately via subprocess.Popen.
        """
        target_clean = target.strip().lower()
        if target_clean in config.APP_CATALOG:
            from floter.app_catalog import launch_registered
            return launch_registered(config.APP_CATALOG[target_clean])
        
        # Check if URL or browser search target
        if target_clean in config.WHITELISTED_URL_MAP:
            url = config.WHITELISTED_URL_MAP[target_clean]
            # Try launching with default or whitelisted browser
            if sys.platform.startswith("win"):
                os.startfile(url)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", url])
            else:
                subprocess.Popen(["xdg-open", url])
            return f"Successfully opened whitelisted URL: {url}"

        # Check whitelisted binaries
        if target_clean not in config.WHITELISTED_APPS:
            raise GuardrailViolationError(
                f"Application '{target}' is not in the approved whitelist: {list(config.WHITELISTED_APPS.keys())}"
            )

        from floter.security.executables import resolve_application
        binary_to_run = resolve_application(target_clean)
        subprocess.Popen([str(binary_to_run)], shell=False, cwd=str(binary_to_run.parent))
        return f"Successfully launched application: {target_clean} ({binary_to_run})"

    @staticmethod
    def snippy_capture(region: str = "full_screen") -> str:
        """
        Captures display buffer using screen capture, returns saved file path and base64 preview.
        """
        if region != "full_screen":
            raise ValueError("Only full_screen capture is supported")
        from PIL import ImageGrab
        screenshot = ImageGrab.grab()
        buffer = io.BytesIO()
        screenshot.save(buffer, "PNG")
        output_file = config.SNIPPY_CACHE_DIR / f"capture_{uuid.uuid4().hex}.png"
        SafeFileSystem.write_new_bytes(output_file, buffer.getvalue())
        return str(output_file)

    @staticmethod
    def inspect_storage_all_drives(time_budget: float = 8.0, max_entries_per_drive: int = 1000, cancel=None) -> Dict[str, Any]:
        """Read-only bounded capacity and top-level path inventory for system drives."""
        if not 1 <= time_budget <= 30 or not 1 <= max_entries_per_drive <= 10000:
            raise ValueError("Invalid storage inspection budget")
        deadline = time.monotonic() + time_budget
        roots = []
        if sys.platform.startswith("win"):
            roots = [Path(f"{letter}:\\") for letter in string.ascii_uppercase if Path(f"{letter}:\\").exists()]
        else:
            roots = [Path("/")]
        report = {"status": "success", "read_only": True, "drives": []}
        for root in roots:
            if time.monotonic() >= deadline or (cancel is not None and cancel.is_set()):
                break
            item: Dict[str, Any] = {"drive": str(root), "paths": []}
            try:
                usage = shutil.disk_usage(root)
                item.update({"total_bytes": usage.total, "used_bytes": usage.used, "free_bytes": usage.free})
                with os.scandir(root) as entries:
                    for entry in entries:
                        if len(item["paths"]) >= max_entries_per_drive or time.monotonic() >= deadline or (cancel is not None and cancel.is_set()):
                            break
                        try:
                            if entry.is_symlink() or (getattr(entry.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400):
                                continue
                            item["paths"].append({"path": entry.path, "is_dir": entry.is_dir(follow_symlinks=False), "size_bytes": entry.stat(follow_symlinks=False).st_size if entry.is_file(follow_symlinks=False) else None})
                        except OSError:
                            continue
            except OSError as exc:
                item["error"] = type(exc).__name__
            report["drives"].append(item)
        return report

    @staticmethod
    def generate_notepad_document(file_name: str, content: str) -> str:
        """
        Writes a brand-new .txt or .md file to the Desktop.
        Strictly enforces that the file must not pre-exist.
        """
        desktop_dir = config.HOME_DIR / "Desktop"
        if not desktop_dir.exists():
            desktop_dir = config.HOME_DIR

        if not (file_name.endswith(".txt") or file_name.endswith(".md")):
            file_name += ".txt"

        if not file_name or any(c in file_name for c in ("/", "\\", ":")) or file_name in {".", ".."}:
            raise GuardrailViolationError("Report name must be a plain filename")
        target_path = desktop_dir / file_name
        valid_path = SafeFileSystem.write_new_text(target_path, content)
        return f"Successfully generated document at: {valid_path}"

    @staticmethod
    def write_notepad(file_name: str, content: str) -> str:
        """Create a new document and open only that document in trusted Notepad."""
        if not sys.platform.startswith('win'):
            raise RuntimeError('Notepad requires Windows')
        from floter.security.executables import resolve_application
        executable = resolve_application('notepad')
        message = FastMCPToolRegistry.generate_notepad_document(file_name, content)
        desktop = config.HOME_DIR / 'Desktop'
        directory = desktop if desktop.exists() else config.HOME_DIR
        suffix = '' if file_name.endswith(('.txt','.md')) else '.txt'
        document = (directory / (file_name + suffix)).resolve()
        subprocess.Popen([str(executable), str(document)], shell=False, cwd=str(executable.parent))
        return message + '; opened in Notepad'
