"""DWG → DXF conversion with the external LibreDWG `dwg2dxf` program.

LibreDWG is GPL: we only run it as a separate process and never link or bundle it
(docs/adr/0001-dwg-conversion.md).
"""
import subprocess
from functools import lru_cache
from pathlib import Path

from app.config import get_settings
from app.importers import FileContentError


class ConverterNotConfigured(FileContentError):
    pass


def _converter() -> Path:
    path = get_settings().dwg2dxf_path
    if path is None or not path.is_file():
        raise ConverterNotConfigured(
            "DWG files need the LibreDWG converter, which is not configured on the server "
            "(set OPTICORE_DWG2DXF_PATH). Alternatively, save the drawing as DXF and upload that.")
    return path


def build_argv(exe: Path, src: Path, dst: Path) -> list[str]:
    # -y: overwrite; -o: output file. Arguments are passed as a list (no shell).
    return [str(exe), "-y", "-o", str(dst), str(src)]


@lru_cache
def _version(exe: Path) -> str:
    try:
        out = subprocess.run([str(exe), "--version"], capture_output=True, text=True, timeout=30,
                             encoding="utf-8", errors="replace")
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return "dwg2dxf (version unknown)"


def convert(src: Path, dst: Path) -> str:
    """Convert `src` (.dwg) to `dst` (.dxf). Returns the converter name/version for the file note."""
    exe = _converter()
    timeout = get_settings().dwg_convert_timeout_s
    try:
        result = subprocess.run(build_argv(exe, src, dst), capture_output=True, text=True, timeout=timeout,
                                encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        raise FileContentError(f"DWG conversion took longer than {timeout} s and was stopped") from None
    if result.returncode != 0 or not dst.is_file() or dst.stat().st_size == 0:
        errors = [line for line in result.stderr.splitlines() if "ERROR" in line][-3:]
        detail = f": {' | '.join(errors)}" if errors else ""
        raise FileContentError(f"DWG conversion failed (exit code {result.returncode}){detail}")
    return _version(exe)
