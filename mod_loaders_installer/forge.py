from minecraft_launcher_lib._helper import download_file, extract_file_from_zip
from minecraft_launcher_lib.install import install_minecraft_version, install_libraries
from minecraft_launcher_lib.forge import forge_processors
from minecraft_launcher_lib._internal_types.forge_types import ForgeInstallProfile
from minecraft_launcher_lib.types import CallbackDict
from minecraft_launcher_lib.exceptions import VersionNotFound
import shutil
import tempfile
import zipfile
import json
import os


def install_forge_version(
    versionid: str,
    path: str | os.PathLike,
    raw_version: str,
    callback: CallbackDict | None = None,
    java: str | os.PathLike | None = None,
) -> None:
    """
    Installs the given Forge version

    :param versionid: A Forge Version. You can get a List of Forge versions using :func:`list_forge_versions`
    :param path: The path to your Minecraft directory
    :param callback: The same dict as for :func:`~minecraft_launcher_lib.install.install_minecraft_version`
    :param java: A Path to a custom Java executable

    Raises a :class:`~minecraft_launcher_lib.exceptions.VersionNotFound` exception when the given forge version is not found
    """
    if callback is None:
        callback = {}

    FORGE_DOWNLOAD_URL = "https://maven.minecraftforge.net/net/minecraftforge/forge/{version}/forge-{version}-installer.jar"

    with tempfile.TemporaryDirectory(
        prefix="minecraft-launcher-lib-forge-install-"
    ) as tempdir:
        installer_path = os.path.join(tempdir, "installer.jar")

        if not download_file(
            FORGE_DOWNLOAD_URL.format(version=versionid), installer_path, callback
        ):
            raise VersionNotFound(versionid)
        zf = zipfile.ZipFile(installer_path, "r")

        # Read the install_profile.json
        with zf.open("install_profile.json", "r") as f:
            version_content = f.read()
            json_content = json.loads(version_content)

        zf.close()
        zf = zipfile.ZipFile(installer_path, "a")

        # Кастомное название папки
        if "version" in json_content:
            old_folder = json_content["version"]
            new_type = True
            json_content["version"] = f"Forge {raw_version}"
        else:
            new_type = False
            json_content["versionInfo"]["id"] = f"Forge {raw_version}"
            json_content["install"]["version"] = f"Forge {raw_version}"
            json_content["install"]["target"] = f"Forge {raw_version}"

        version_data: ForgeInstallProfile = json_content
        forge_version_id = (
            version_data["version"]
            if "version" in version_data
            else version_data["install"]["version"]
        )
        minecraft_version = (
            version_data["minecraft"]
            if "minecraft" in version_data
            else version_data["install"]["minecraft"]
        )

        # Make sure, the base version is installed
        install_minecraft_version(minecraft_version, path, callback=callback)

        # Install all needed libs from install_profile.json
        if "libraries" in version_data:
            install_libraries(
                minecraft_version, version_data["libraries"], str(path), callback
            )

        # Extract the client.json
        version_json_path = os.path.join(
            path, "versions", forge_version_id, forge_version_id + ".json"
        )
        try:
            extract_file_from_zip(
                zf, "version.json", version_json_path, minecraft_directory=path
            )
        except KeyError:
            if "versionInfo" in version_data:
                with open(version_json_path, "w", encoding="utf-8") as f:
                    json.dump(
                        version_data["versionInfo"], f, ensure_ascii=False, indent=4
                    )

        # Extract forge libs from the installer
        forge_lib_path = os.path.join(
            path, "libraries", "net", "minecraftforge", "forge", versionid
        )
        try:
            extract_file_from_zip(
                zf,
                "maven/net/minecraftforge/forge/{version}/forge-{version}-universal.jar".format(
                    version=versionid
                ),
                os.path.join(forge_lib_path, "forge-" + versionid + "-universal.jar"),
                minecraft_directory=path,
            )
        except KeyError:
            pass

        try:
            extract_file_from_zip(
                zf,
                "forge-{version}-universal.jar".format(version=versionid),
                os.path.join(forge_lib_path, f"forge-{versionid}.jar"),
                minecraft_directory=path,
            )
        except KeyError:
            pass

        try:
            extract_file_from_zip(
                zf,
                f"maven/net/minecraftforge/forge/{versionid}/forge-{versionid}.jar",
                os.path.join(forge_lib_path, f"forge-{versionid}.jar"),
                minecraft_directory=path,
            )
        except KeyError:
            pass

        # Extract the client.lzma
        lzma_path = os.path.join(tempdir, "client.lzma")
        try:
            extract_file_from_zip(zf, "data/client.lzma", lzma_path)
        except KeyError:
            pass

        zf.close()

        # Install the rest with the vanilla function
        install_minecraft_version(forge_version_id, str(path), callback=callback)

        # Run the processors
        if "processors" in version_data:
            forge_processors(
                version_data,
                str(path),
                lzma_path,
                installer_path,
                callback,
                "java" if java is None else str(java),
            )
        if new_type:
            versions_dir = os.path.join(path, "versions")
            dst_folder = os.path.join(versions_dir, f"Forge {raw_version}")
            src_folder = os.path.join(versions_dir, old_folder)

            for root, dirs, files in os.walk(src_folder):
                for file in files:
                    src_path = os.path.join(root, file)
                    relative_path = os.path.relpath(src_path, src_folder)
                    dst_path = os.path.join(dst_folder, relative_path)

                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    try:
                        shutil.move(src_path, dst_path)
                    except Exception:
                        pass
            try:
                shutil.rmtree(src_folder)
            except Exception:
                pass
