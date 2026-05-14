# Imports

# > Standard Library
import os
import sys
from pathlib import Path
from typing import Iterable


def _get_windows_documents_dirs() -> Iterable[Path]:
    """Return Windows Documents directories resolved from known-folder settings."""
    seen: set[str] = set()

    def add(path: Path | None):
        if not path:
            return
        normalized = str(path)
        if normalized in seen:
            return
        seen.add(normalized)
        yield_path.append(path)

    yield_path: list[Path] = []

    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        ) as key:
            docs, _ = winreg.QueryValueEx(key, "Personal")
            add(Path(os.path.expandvars(docs)))
    except Exception:
        pass

    return yield_path


def detect_script_log_path() -> str:
    """Resolve the LOTRO Script.log path for the current platform."""
    lotro_rel = Path("The Lord of the Rings Online") / "Script.log"

    if sys.platform != "win32":
        return str(Path.home() / "Documents" / lotro_rel)

    doc_dirs = list(_get_windows_documents_dirs())
    for docs in doc_dirs:
        candidate = docs / lotro_rel
        if candidate.exists():
            return str(candidate)

    if doc_dirs:
        return str(doc_dirs[0] / lotro_rel)

    return str(Path.home() / "Documents" / lotro_rel)
