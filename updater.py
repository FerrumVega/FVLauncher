import subprocess
import os
import requests
import json


def is_new_version_released(current_version):
    current_version_tuple = tuple(int(t) for t in current_version[1:].split("."))
    last_version = json.loads(
        requests.get(
            "https://api.github.com/repos/FerrumVega/FVLauncher/releases/latest"
        ).content
    )["tag_name"]
    last_version_tuple = tuple(int(t) for t in last_version[1:].split("."))
    return True if last_version_tuple > current_version_tuple else False


def update(launcher_file_path):
    with open("FVLauncher_Installer.exe", "wb") as launcher_installer_file:
        launcher_installer_file.write(
            requests.get(
                "https://github.com/FerrumVega/FVLauncher/releases/latest/download/FVLauncher_Installer.exe",
            ).content
        )

    process = subprocess.run(
        ["FVLauncher_Installer.exe", "/SILENT"],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    os.remove("FVLauncher_Installer.exe")
    subprocess.run(
        [launcher_file_path],
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
