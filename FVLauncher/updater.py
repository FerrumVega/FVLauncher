import subprocess
import requests
import json
import tempfile


def is_new_version_released(current_version):
    current_version_tuple = tuple(int(t) for t in current_version[1:].split("."))
    with requests.get(
        "https://api.github.com/repos/FerrumVega/FVLauncher/releases/latest", timeout=10
    ) as r:
        r.raise_for_status()
        last_version = json.loads(r.content)["tag_name"]
    last_version_tuple = tuple(int(t) for t in last_version[1:].split("."))
    return True if last_version_tuple > current_version_tuple else False


def update():
    with tempfile.NamedTemporaryFile(
        prefix="FVLInstaller_", suffix=".exe", delete=False
    ) as launcher_installer_file:
        with requests.get(
            "https://github.com/FerrumVega/FVLauncher/releases/latest/download/FVLauncher_Installer.exe",
            timeout=10,
        ) as r:
            r.raise_for_status()
            launcher_installer_file.write(r.content)

    subprocess.Popen(
        [launcher_installer_file.name],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
