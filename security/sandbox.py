import os
from pathlib import Path

class GuardrailViolationError(PermissionError):
    """Raised when an operation violates the Read & Create Only sandbox."""
    pass

def validate_file_creation_path(target_path: Path | str) -> Path:
    """Ensure target path does NOT exist already (Strict Read & Create Only)."""
    p = Path(target_path).expanduser().resolve()
    if p.exists():
        raise GuardrailViolationError(
            f"Security Sandbox Violation: In-place overwrite or modification denied for existing file: '{p}'"
        )
    return p

def validate_file_read_path(target_path: Path | str) -> Path:
    """Ensure target path exists and is readable."""
    p = Path(target_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"File not found for reading: '{p}'")
    return p

class SafeFileSystem:
    """Safe wrapper around filesystem operations ensuring Read & Create Only policy."""

    @staticmethod
    def read_text(file_path: Path | str, max_chars: int = 50000) -> str:
        p = validate_file_read_path(file_path)
        with p.open(encoding="utf-8", errors="replace") as stream:
            content = stream.read(max_chars + 1)
        if len(content) > max_chars:
            return content[:max_chars] + f"\n... [Truncated: File exceeded {max_chars} characters]"
        return content

    @staticmethod
    def write_new_text(file_path: Path | str, content: str) -> Path:
        p = validate_file_creation_path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("x", encoding="utf-8") as stream:
            stream.write(content)
        return p

    @staticmethod
    def write_new_bytes(file_path: Path | str, content: bytes) -> Path:
        p = validate_file_creation_path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("xb") as stream:
            stream.write(content)
        return p
