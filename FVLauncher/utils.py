import os
import minecraft_launcher_lib
import requests
import json
import logging
import uuid
import subprocess
import optipy
import time
import sys
import traceback
from PySide6.QtCore import QObject, Signal
from PySide6 import QtWidgets, QtGui
from xml.etree import ElementTree as ET

app = QtWidgets.QApplication(sys.argv)
app.setStyle(QtWidgets.QStyleFactory.create("windows11"))

window_icon = QtGui.QIcon(
    (
        os.path.join(
            "assets",
            "minecraft_title.png",
        )
    )
)


def log_exception(*args):
    logging.critical(
        f"There was an error:\n{''.join(traceback.format_exception(*args))}"
    )
    gui_messenger.critical.emit(
        "Ошибка",
        f"Произошла непредвиденная ошибка:\n{''.join(traceback.format_exception(*args))}",
    )


sys.excepthook = log_exception


def run_in_process_with_exceptions_logging(
    func, *args, queue, is_game_launch_process=False, **kwargs
):
    try:
        func(*args, queue, **kwargs)
    except Exception as e:
        log_exception(type(e), e, e.__traceback__)
        if is_game_launch_process:
            queue.put(("start_button", True))


class GuiMessenger(QObject):
    warning = Signal(str, str)
    critical = Signal(str, str)
    info = Signal(str, str)
    log = Signal(str, str, str)

    def emit_msg(self, t, m, type, directory=None):
        global window_icon
        msg = QtWidgets.QMessageBox()
        msg.setWindowTitle(t)
        msg.setText(m)
        msg.setWindowIcon(window_icon)
        msg.setIcon(type)
        if directory is not None:
            msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if msg.exec() == QtWidgets.QMessageBox.Yes:
                os.startfile(os.path.join(directory, "logs", "latest.log"))
        else:
            msg.exec()

    def __init__(self):
        super().__init__()
        self.warning.connect(
            lambda t, m: self.emit_msg(t, m, QtWidgets.QMessageBox.Warning)
        )
        self.critical.connect(
            lambda t, m: self.emit_msg(t, m, QtWidgets.QMessageBox.Critical)
        )
        self.info.connect(
            lambda t, m: self.emit_msg(t, m, QtWidgets.QMessageBox.Information)
        )
        self.log.connect(
            lambda t, m, d: self.emit_msg(t, m, QtWidgets.QMessageBox.Critical, d)
        )


gui_messenger = GuiMessenger()


def download_profile_from_mrpack(
    minecraft_directory, mrpack_path, no_internet_connection, queue
):
    if mrpack_path:
        profile_name = minecraft_launcher_lib.mrpack.get_mrpack_information(
            mrpack_path
        )["name"]
        profile_path = os.path.join(
            minecraft_directory,
            "profiles",
            profile_name,
        )
        minecraft_launcher_lib.mrpack.install_mrpack(
            mrpack_path,
            minecraft_directory,
            profile_path,
            callback={"setStatus": lambda value: queue.put(("status", value))},
        )
        with open(
            os.path.join(profile_path, "profile_info.json"), "w", encoding="utf-8"
        ) as profile_info_file:
            json.dump(
                [
                    {
                        "mc_version": minecraft_launcher_lib.mrpack.get_mrpack_launch_version(
                            mrpack_path
                        )
                    },
                    [],
                ],
                profile_info_file,
                indent=4,
            )
        open(
            os.path.join(
                minecraft_directory,
                "versions",
                minecraft_launcher_lib.mrpack.get_mrpack_launch_version(mrpack_path),
                "installed.FVL",
            ),
            "w",
            encoding="utf-8",
        ).close()
        if (
            download_injector(
                minecraft_launcher_lib.mrpack.get_mrpack_information(mrpack_path)[
                    "minecraftVersion"
                ],
                minecraft_directory,
                no_internet_connection,
            )
            == "InjectorNotDownloaded"
        ):
            open(
                os.path.join(
                    minecraft_directory,
                    "versions",
                    minecraft_launcher_lib.mrpack.get_mrpack_launch_version(
                        mrpack_path
                    ),
                    "injector_not_downloaded.FVL",
                ),
                "w",
                encoding="utf-8",
            ).close()
        queue.put(("show_versions", None))
        gui_messenger.info.emit(
            "Сборка установлена", f"Сборка {profile_name} была успешно установлена!"
        )


def prepare_installation_parameters(
    mod_loader, nickname, ely_uuid, access_token, java_arguments
):
    if mod_loader != "vanilla":
        install_type = minecraft_launcher_lib.mod_loader.get_mod_loader(
            mod_loader
        ).install
    else:
        install_type = minecraft_launcher_lib.install.install_minecraft_version
    options = {
        "username": nickname,
        "uuid": ely_uuid if ely_uuid else str(uuid.uuid4().hex),
        "token": access_token,
        "jvmArguments": java_arguments,
    }
    return install_type, options


def download_injector(raw_version, minecraft_directory, no_internet_connection):
    json_path = os.path.join(
        minecraft_directory,
        "versions",
        raw_version,
        f"{raw_version}.json",
    )
    if not minecraft_launcher_lib.utils.is_vanilla_version(raw_version):
        with open(json_path, encoding="utf-8") as file_with_downloads:
            raw_version = json.load(file_with_downloads)["inheritsFrom"]
    json_path = os.path.join(
        minecraft_directory,
        "versions",
        raw_version,
        f"{raw_version}.json",
    )
    if not no_internet_connection:
        authlib_version = None
        with open(json_path, encoding="utf-8") as file_with_downloads:
            for lib in json.load(file_with_downloads)["libraries"]:
                if lib["name"].startswith("com.mojang:authlib:"):
                    authlib_version = lib["name"].split(":")[-1]
                    break
        if authlib_version is not None:
            base_url = "https://maven.ely.by/releases/by/ely/authlib"
            with requests.get(f"{base_url}/maven-metadata.xml") as r:
                r.raise_for_status()
                maven_metadata = r.text
            for maven_version in ET.fromstring(maven_metadata).findall(
                "./versioning/versions/version"
            )[::-1]:
                if authlib_version in maven_version.text:
                    with open(
                        os.path.join(
                            minecraft_directory,
                            "libraries",
                            "com",
                            "mojang",
                            "authlib",
                            authlib_version,
                            f"authlib-{authlib_version}.jar",
                        ),
                        "wb",
                    ) as jar:
                        with requests.get(
                            f"{base_url}/{maven_version.text}/authlib-{maven_version.text}.jar"
                        ) as r:
                            r.raise_for_status()
                            authlib_jar = r.content
                        jar.write(authlib_jar)
                        logging.debug(f"Installed patched authlib {maven_version.text}")
                    break
            else:
                gui_messenger.warning.emit(
                    "Ошибка скина",
                    "Для данной версии ещё не вышла патченая authlib, обычна она выходит в течении пяти дней после выхода версии.",
                )
                logging.warning(
                    f"Warning message showed in download_injector: skin error, there is not patched authlib for {raw_version} version"
                )
                return "InjectorNotDownloaded"
        else:
            gui_messenger.warning.emit(
                "Ошибка скина",
                "На данной версии нет authlib, скины не поддерживаются.",
            )
            logging.warning(
                f"Warning message showed in download_injector: skins not supported on {raw_version} version"
            )
    else:
        gui_messenger.warning.emit(
            "Ошибка скина", "Отсутсвует подключение к интернету."
        )
        logging.warning(
            "Warning message showed in download_injector: skin error, no internet connection"
        )


def resolve_version_name(
    version, mod_loader, minecraft_directory, ignore_installed_file=False
):
    other_loaders = ["fabric", "forge", "quilt", "neoforge", "vanilla"]
    other_loaders.remove(mod_loader)
    for v in sorted(
        minecraft_launcher_lib.utils.get_installed_versions(minecraft_directory),
        reverse=True,
        key=lambda s: s["id"],
    ):
        folder_name = v["id"]
        if (
            os.path.isfile(
                os.path.join(
                    minecraft_directory, "versions", folder_name, "installed.FVL"
                )
            )
            or ignore_installed_file
        ):
            if mod_loader == "vanilla" and folder_name == version:
                return folder_name, {}
            elif mod_loader != "vanilla" and all(
                not loader in folder_name for loader in other_loaders
            ):
                with open(
                    os.path.join(
                        minecraft_directory,
                        "versions",
                        folder_name,
                        f"{folder_name}.json",
                    ),
                    encoding="utf-8",
                ) as version_info:
                    if (
                        mod_loader in folder_name
                        and json.load(version_info)["inheritsFrom"] == version
                    ):
                        return folder_name, {}
    else:
        for v in os.listdir(os.path.join(minecraft_directory, "profiles")):
            profile_info_path = os.path.join(
                minecraft_directory,
                "profiles",
                v,
                "profile_info.json",
            )
            if version == v and os.path.isfile(profile_info_path):
                with open(profile_info_path, encoding="utf-8") as profile_info_file:
                    vanilla_version = json.load(profile_info_file)[0]["mc_version"]
                    if resolve_version_name(
                        vanilla_version, mod_loader, minecraft_directory
                    )[0]:
                        return vanilla_version, {
                            "game_directory": os.path.join(
                                minecraft_directory, "profiles", v
                            )
                        }
                    else:
                        gui_messenger.critical.emit(
                            "Ошибка запуска профиля/сборки",
                            "Версия игры, которую требует профиль/сборка некорректно установлена. Запуск невозможен.",
                        )
                        return None, {"do_not_install": True}
        else:
            return None, {}


def install_version(
    install_type,
    options,
    minecraft_directory,
    mod_loader,
    raw_version,
    queue,
    no_internet_connection,
):
    progress = 0
    max_progress = 100
    percents = 0
    last_track_progress_call_time = time.time()
    last_progress_info = ""

    def track_progress(value, type):
        nonlocal progress, max_progress, last_track_progress_call_time, last_progress_info, percents
        if time.time() - last_track_progress_call_time > 1 or (
            type == "progress_info" and value != last_progress_info
        ):
            if type != "progress_info":
                if type == "progress":
                    progress = value
                elif type == "max":
                    max_progress = value
                try:
                    percents = min(100.0, progress / max_progress * 100)
                except ZeroDivisionError:
                    percents = 0
                queue.put(("progressbar", percents))
                last_track_progress_call_time = time.time()
            else:
                last_progress_info = value
                queue.put(("status", value))

    name_of_folder_with_version, other_info = resolve_version_name(
        raw_version, mod_loader, minecraft_directory
    )
    if other_info and other_info.get("game_directory", None) is not None:
        options["gameDirectory"] = other_info["game_directory"]

    if name_of_folder_with_version is not None:
        if os.path.isfile(
            os.path.join(
                minecraft_directory,
                "versions",
                name_of_folder_with_version,
                "injector_not_downloaded.FVL",
            )
        ):
            queue.put(("status", "Загрузка injector..."))
            if (
                download_injector(
                    name_of_folder_with_version,
                    minecraft_directory,
                    no_internet_connection,
                )
                is None
            ):
                os.remove(
                    os.path.join(
                        minecraft_directory,
                        "versions",
                        name_of_folder_with_version,
                        "injector_not_downloaded.FVL",
                    )
                )
                logging.debug(
                    "Inector installed and injector_not_downloaded.FVL deleted"
                )

        return name_of_folder_with_version, minecraft_directory, options
    elif (
        not no_internet_connection
        and mod_loader_is_supported(raw_version, mod_loader)
        and not other_info.get("do_not_install", False)
    ):
        install_type(
            raw_version,
            minecraft_directory,
            callback={
                "setProgress": lambda value: track_progress(value, "progress"),
                "setMax": lambda value: track_progress(value, "max"),
                "setStatus": lambda value: track_progress(value, "progress_info"),
            },
        )
        name_of_folder_with_version = resolve_version_name(
            raw_version, mod_loader, minecraft_directory, ignore_installed_file=True
        )[0]
        if name_of_folder_with_version is not None:
            open(
                os.path.join(
                    minecraft_directory,
                    "versions",
                    name_of_folder_with_version,
                    "installed.FVL",
                ),
                "w",
                encoding="utf-8",
            ).close()
            queue.put(("status", "Загрузка injector..."))
            logging.debug("Installing injector in launch")
            if (
                download_injector(
                    name_of_folder_with_version,
                    minecraft_directory,
                    no_internet_connection,
                )
                == "InjectorNotDownloaded"
            ):
                open(
                    os.path.join(
                        minecraft_directory,
                        "versions",
                        name_of_folder_with_version,
                        "injector_not_downloaded.FVL",
                    ),
                    "w",
                    encoding="utf-8",
                ).close()
            return name_of_folder_with_version, minecraft_directory, options
        else:
            gui_messenger.critical.emit(
                "Ошибка загрузки",
                "Произошла непредвиденная ошибка во время загрузки версии.",
            )
            queue.put(("start_button", True))
            logging.error(
                f"Error message showed in install_version: error after download {raw_version} version"
            )
            return None
    elif no_internet_connection:
        gui_messenger.critical.emit(
            "Ошибка подключения",
            "Вы в оффлайн-режиме. Версия отсутсвует на вашем компьютере, загрузка невозможна. Попробуйте перезапустить лаунчер.",
        )
        queue.put(("start_button", True))
        logging.error(
            f"Error message showed in install_version: cannot download version because there is not internet connection"
        )
    elif not other_info.get("do_not_install", False):
        gui_messenger.critical.emit(
            "Ошибка",
            "Для данной версии нет выбранного вами загрузчика модов.",
        )
        queue.put(("start_button", True))
        logging.error(
            f"Error message showed in install_version: mod loader {mod_loader} is not supported on the {raw_version} version"
        )


def download_optifine(optifine_path, raw_version, queue, no_internet_connection):
    if not no_internet_connection:
        url = None
        optifine_info = optipy.getVersion(raw_version)
        if optifine_info is not None:
            url = optifine_info[raw_version][0]["url"]
            queue.put(("status", "Загрузка optifine..."))
            logging.debug("Installing optifine in download_optifine")
            with open(optifine_path, "wb") as optifine_jar:
                with requests.get(url) as r:
                    r.raise_for_status()
                    optifine_jar.write(r.content)
        else:
            gui_messenger.warning.emit(
                "Запуск без optifine",
                "Optifine недоступен на выбранной вами версии.",
            )
            logging.warning(
                f"Warning message showed in download_optifine: optifine is not support on {raw_version} version"
            )
    else:
        gui_messenger.warning.emit(
            "Ошибка optifine", "Отсутсвует подключение к интернету."
        )
        logging.warning(
            f"Warning message showed in download_optifine: optifine error, no internet connection"
        )


def launch(
    minecraft_directory,
    mod_loader,
    raw_version,
    optifine,
    show_console,
    nickname,
    ely_uuid,
    access_token,
    java_arguments,
    no_internet_connection,
    queue,
):
    install_type, options = prepare_installation_parameters(
        mod_loader, nickname, ely_uuid, access_token, java_arguments
    )

    launch_info = install_version(
        install_type,
        options,
        minecraft_directory,
        mod_loader,
        raw_version,
        queue,
        no_internet_connection,
    )
    if launch_info is not None:
        version, minecraft_directory, options = launch_info

        options["jvmArguments"] = options["jvmArguments"].split()
        queue.put(("progressbar", 100))

        optifine_path = os.path.join(minecraft_directory, "mods", "optifine.jar")

        if not os.path.isdir(os.path.join(minecraft_directory, "mods")):
            os.mkdir(os.path.join(minecraft_directory, "mods"))
        if os.path.isfile(optifine_path):
            os.remove(optifine_path)
        if optifine and mod_loader == "forge":
            download_optifine(optifine_path, raw_version, queue, no_internet_connection)
        logging.debug(f"Launching {version} version")
        minecraft_process = subprocess.Popen(
            minecraft_launcher_lib.command.get_minecraft_command(
                version, minecraft_directory, options
            ),
            cwd=minecraft_directory,
            **(
                {"creationflags": subprocess.CREATE_NO_WINDOW}
                if not show_console
                else {}
            ),
        )
        queue.put(("status", "Игра запущена"))
        queue.put(("start_button", True))
        logging.debug(f"Minecraft process started on {version} version")
        start_rich_presence(raw_version, True, minecraft_process)
        minecraft_return_code = minecraft_process.wait()
        if minecraft_return_code != 0:
            gui_messenger.log.emit(
                "Игра была закрыта с ошибкой",
                f"Minecraft вернул ошибку (крашнулся). Код ошибки: {minecraft_return_code}<br>"
                "Вы хотите открыть лог?",
                minecraft_directory,
            )
    else:
        queue.put(("start_button", True))


def mod_loader_is_supported(raw_version, mod_loader):
    if mod_loader != "vanilla":
        if minecraft_launcher_lib.mod_loader.get_mod_loader(
            mod_loader
        ).is_minecraft_version_supported(raw_version):
            return True
        else:
            return False
    else:
        return True


def only_project_install(
    project_version, project, project_file_path, profile_info_path, queue
):
    with requests.get(project_version["url"], stream=True) as r:
        r.raise_for_status()
        with open(project_file_path, "wb") as project_file:
            bytes_downloaded = 0
            project_size = project_version["size"]
            chunk_size = int(project_size / 100)
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    bytes_downloaded += chunk_size
                    queue.put(min(100, int(bytes_downloaded / project_size * 100)))
                    project_file.write(chunk)
    with open(profile_info_path, encoding="utf-8") as profile_info_file:
        profile_info = json.load(profile_info_file)
    if not [project_version, project] in profile_info[1]:
        profile_info[1].append([project_version, project])
        with open(profile_info_path, "w", encoding="utf-8") as profile_info_file:
            json.dump(profile_info, profile_info_file, indent=4)
    gui_messenger.info.emit(
        "Проект установлен",
        f"Проект {project['title']} был успешно установлен.",
    )


def start_rich_presence(
    raw_version=None,
    minecraft=False,
    minecraft_process=None,
):
    global rpc
    try:
        if not minecraft:
            rpc.update(
                details="В меню",
                start=start_launcher_time,
                large_image="minecraft_title",
                large_text="FVLauncher",
                buttons=[
                    {
                        "label": "Скачать лаунчер",
                        "url": "https://github.com/FerrumVega/FVLauncher",
                    }
                ],
            )
        else:
            rpc.update(
                pid=minecraft_process.pid,
                state=(f"Играет на версии {raw_version}"),
                details="В Minecraft",
                start=start_launcher_time,
                large_image="minecraft_title",
                large_text="FVLauncher",
                small_image="grass_block",
                small_text="В игре",
                buttons=[
                    {
                        "label": "Скачать лаунчер",
                        "url": "https://github.com/FerrumVega/FVLauncher",
                    }
                ],
            )
            minecraft_process.wait()
            start_rich_presence()
    except:
        pass


CLIENT_ID = "1399428342117175497"
start_launcher_time = int(time.time())
LAUNCHER_VERSION = "v5.5"
