"""Blender detection and subprocess management."""

import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Path to the blender_process.py script bundled with this tool
_SCRIPT_PATH = Path(__file__).parent / "scripts" / "blender_process.py"


def find_blender() -> str | None:
    """Find the Blender executable.

    Search order:
    1. BLENDER_PATH environment variable
    2. Standard Windows install paths (newest version first)
    3. System PATH (shutil.which)
    4. Steam common path
    """
    # 1. Environment variable
    env_path = os.environ.get("BLENDER_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path

    # 2. Standard Windows install paths
    if sys.platform == "win32":
        pattern = r"C:\Program Files\Blender Foundation\Blender *\blender.exe"
        matches = sorted(glob.glob(pattern), reverse=True)  # newest first
        if matches:
            return matches[0]

    # 3. System PATH
    which_result = shutil.which("blender")
    if which_result:
        return which_result

    # 4. Steam path
    if sys.platform == "win32":
        steam_path = r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"
        if os.path.isfile(steam_path):
            return steam_path

    return None


def process_glb(
    glb_path: str,
    decimate_ratio: float,
    output_fbx_path: str,
    timeout: int = 300,
) -> subprocess.CompletedProcess:
    """Run Blender headless to convert GLB to FBX.

    Args:
        glb_path: Path to input .glb file.
        decimate_ratio: Mesh decimation ratio (0.0-1.0).
        output_fbx_path: Path for output .fbx file.
        timeout: Subprocess timeout in seconds (default 5 minutes).

    Returns:
        CompletedProcess with stdout/stderr.

    Raises:
        FileNotFoundError: If Blender not found or GLB file missing.
        subprocess.TimeoutExpired: If Blender takes too long.
        subprocess.CalledProcessError: If Blender exits with error.
    """
    blender = find_blender()
    if not blender:
        raise FileNotFoundError(
            "Blender not found. Install Blender or set BLENDER_PATH environment variable."
        )

    if not os.path.isfile(glb_path):
        raise FileNotFoundError(f"GLB file not found: {glb_path}")

    cmd = [
        blender,
        "--background",
        "--python",
        str(_SCRIPT_PATH),
        "--",
        "--input",
        str(glb_path),
        "--output",
        str(output_fbx_path),
        "--decimate",
        str(decimate_ratio),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    result.check_returncode()
    return result
