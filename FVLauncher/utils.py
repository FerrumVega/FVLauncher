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
import random
import string
import hashlib
from faker import Faker
from typing import Dict, Union, Callable, Any, Optional, Tuple, Iterable
from pypresence.presence import Presence
from multiprocessing.queues import Queue
from PySide6 import QtWidgets, QtGui
from defusedxml import ElementTree as ET

logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


class Constants:
    DISCORD_CLIENT_ID = "1399428342117175497"
    START_LAUNCHER_TIME = int(time.time())

    REDIRECT_URI = "http://localhost:3000"
    MICROSOFT_CLIENT_ID = "63a59a89-2d0f-4bb9-a743-1e944c2cfd3e"

    ELY_PROXY_URL = "https://fvlauncher.ferrumthevega.workers.dev"
    ELY_CLIENT_ID = "fvlauncherapp"

    LAUNCHER_VERSION = "v8.1"
    USER_AGENT = Faker().user_agent()


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


def search_projects(minecraft_directory: str, instance_name: str, queue: Queue):
    queue.put(("status", "Вычиление хэшей"))
    hashes_and_paths = {}
    instance_path = os.path.join(minecraft_directory, "instances", instance_name)
    for project_type_folder in [
        "mods",
        "resourcepacks",
        "datapacks",
        "shaderpacks",
    ]:
        try:
            for filename in os.listdir(
                os.path.join(instance_path, project_type_folder)
            ):
                path = os.path.join(instance_path, project_type_folder, filename)
                hashes_and_paths[
                    hashlib.sha512(open(path, "rb").read()).hexdigest()
                ] = path
        except FileNotFoundError:
            pass
    queue.put(("status", "Поиск файлов версий"))
    with requests.post(
        "https://api.modrinth.com/v2/version_files",
        json={
            "hashes": list(hashes_and_paths.keys()),
            "algorithm": "sha512",
        },
    ) as r:
        r.raise_for_status()
        projects = {}
        for project_hash, project_info in r.json().items():
            projects[project_info["project_id"]] = project_info
            projects[project_info["project_id"]]["path"] = hashes_and_paths[
                project_hash
            ]
            del hashes_and_paths[project_hash]
    with requests.get(
        "https://api.modrinth.com/v2/projects",
        params={"ids": json.dumps(list(projects.keys()))},
    ) as r:
        r.raise_for_status()
        full_projects = r.json()
        projects_len = len(full_projects)
        for index, project_info in enumerate(full_projects, 1):
            project_name = project_info["title"]
            project_id = project_info["id"]
            projects[project_id]["title"] = project_name
            projects[project_id]["disabled"] = projects[project_id]["path"].endswith(
                ".disabled"
            )
            if (icon_url := project_info.get("icon_url")) is not None:
                with requests.get(icon_url, timeout=10) as r:
                    r.raise_for_status()
                    projects[project_id]["icon_bytes"] = r.content
            else:
                projects[project_id]["icon_bytes"] = None
            logging.debug(f"Doing smth with {project_name} ({index}/{projects_len})")
            queue.put(("progressbar", index / projects_len * 100))
            queue.put(("status", f"Работа с {project_name}"))
    queue.put(("projects", projects, list(hashes_and_paths.values())))


def track_progress_factory(queue: Queue):
    progress: int = 0
    max_progress: int = 100

    def track_progress(value: Union[str, int], progress_type: str):
        nonlocal progress, max_progress
        if progress_type != "progress_info":
            if progress_type == "progress":
                progress = value
            elif progress_type == "max":
                max_progress = value
            try:
                percents = min(100.0, progress / max_progress * 100)
            except ZeroDivisionError:
                percents = 0
            queue.put(("progressbar", percents))
        else:
            queue.put(("status", value))

    return track_progress


def hide_security_data(data: str):
    return "[HIDDEN]" if data else "[NULL]"


def generate_folder_name(
    separator: str, random_symbols_len: int, strings: Iterable[str]
):
    return separator.join(
        (
            *strings,
            "".join(
                random.choices(
                    string.ascii_letters + string.digits, k=random_symbols_len
                )
            ),
        )
    )


def run_in_process_with_exceptions_logging(
    func: Callable,
    *args: Any,
    queue: Queue,
    is_game_launch_process: bool = False,
    **kwargs: Any,
):
    try:
        func(*args, queue, **kwargs)
    except Exception as e:
        queue.put(
            (
                "log_exception",
                None,
                "".join(traceback.format_exception(type(e), e, e.__traceback__)),
            )
        )
        if is_game_launch_process:
            queue.put(("start_button", True))


def boolean_to_sign_status(auth_info: Tuple[Optional[bool], Optional[str]]):
    sign_text = {
        True: "Вы вошли в аккаунт",
        False: "Вы не вошли в аккаунт",
        None: "Ошибка проверки входа в аккаунт",
    }[auth_info[0]]
    return f"{sign_text} (Аккаунт {auth_info[1]})" if auth_info[0] else sign_text


def download_instance_from_mrpack(
    minecraft_directory: str,
    mrpack_path: str,
    no_internet_connection: bool,
    queue: Queue,
):
    track_progress = track_progress_factory(queue)

    if mrpack_path:
        mrpack_info = minecraft_launcher_lib.mrpack.get_mrpack_information(mrpack_path)
        folder_name = generate_folder_name(
            "_", 5, [mrpack_info["name"], mrpack_info["minecraftVersion"]]
        )
        instance_path = os.path.join(
            minecraft_directory,
            "instances",
            folder_name,
        )
        minecraft_launcher_lib.mrpack.install_mrpack(
            mrpack_path,
            minecraft_directory,
            instance_path,
            callback={
                "setProgress": lambda value: track_progress(value, "progress"),
                "setMax": lambda value: track_progress(value, "max"),
                "setStatus": lambda value: track_progress(value, "progress_info"),
            },
        )
        with open(
            os.path.join(instance_path, "instance_info.json"), "w", encoding="utf-8"
        ) as instance_info_file:
            json.dump(
                {
                    "mc_version": minecraft_launcher_lib.mrpack.get_mrpack_launch_version(
                        mrpack_path
                    )
                },
                instance_info_file,
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
        queue.put(("show_versions", None))
        queue.put(
            (
                "show_message",
                "information",
                "Сборка установлена",
                f"Сборка {mrpack_info['name']} была успешно установлена в папку {folder_name}!",
            )
        )


def prepare_installation_parameters(
    mod_loader: str,
    nickname: str,
    game_uuid: str,
    access_token: str,
    java_arguments: str,
):
    if mod_loader != "vanilla":
        install_type = minecraft_launcher_lib.mod_loader.get_mod_loader(
            mod_loader
        ).install
    else:
        install_type = minecraft_launcher_lib.install.install_minecraft_version
    options = {
        "username": nickname,
        "uuid": game_uuid if game_uuid else str(uuid.uuid4().hex),
        "token": access_token,
        "jvmArguments": java_arguments.split(),
    }
    return install_type, options


def download_authlib(
    raw_version: str,
    minecraft_directory: str,
    no_internet_connection: bool,
    launch_account_type: str,
    queue: Queue,
):
    if not no_internet_connection:
        queue.put(("status", "Загрузка authlib..."))
        logging.debug(
            f"Installing authlib in launch, account type: {launch_account_type}"
        )
        json_path = os.path.join(
            minecraft_directory,
            "versions",
            raw_version,
            f"{raw_version}.json",
        )

        authlib_version = None
        with open(json_path, encoding="utf-8") as file_with_downloads:
            for lib in json.load(file_with_downloads)["libraries"]:
                if lib["name"].startswith("com.mojang:authlib:"):
                    authlib_version = lib["name"].split(":")[-1]
                    lib_artifact = lib["downloads"]["artifact"]
                    break
        if authlib_version is not None:
            if launch_account_type == "Ely.by":
                base_url = "https://maven.ely.by/releases/by/ely/authlib"
                with requests.get(f"{base_url}/maven-metadata.xml", timeout=10) as r:
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
                                lib_artifact["path"].replace("/", "\\"),
                            ),
                            "wb",
                        ) as jar:
                            with requests.get(
                                f"{base_url}/{maven_version.text}/authlib-{maven_version.text}.jar",
                                timeout=10,
                            ) as r:
                                r.raise_for_status()
                                authlib_jar = r.content
                            jar.write(authlib_jar)
                            logging.debug(
                                f"Installed patched authlib {maven_version.text}"
                            )
                        break
                else:
                    queue.put(
                        (
                            "show_message",
                            "warning",
                            "Ошибка authlib",
                            "Для данной версии ещё не вышла патченая authlib, обычна она выходит в течении пяти дней после выхода версии.",
                        )
                    )
                    logging.warning(
                        f"Warning message showed in download_authlib: skin error, there is not patched authlib for {raw_version} version"
                    )
                    return
            elif launch_account_type == "Microsoft":
                with open(
                    os.path.join(
                        minecraft_directory,
                        "libraries",
                        lib_artifact["path"].replace("/", "\\"),
                    ),
                    "wb",
                ) as jar:
                    with requests.get(
                        lib_artifact["url"],
                        timeout=10,
                    ) as r:
                        r.raise_for_status()
                        authlib_jar = r.content
                    jar.write(authlib_jar)
                    logging.debug("Installed original authlib")

        else:
            queue.put(
                (
                    "show_message",
                    "warning",
                    "Ошибка authlib",
                    "На данной версии нет authlib, скины и авторизация не поддерживаются.",
                )
            )
            logging.warning(
                f"Warning message showed in download_authlib: skins not supported on {raw_version} version"
            )
    else:
        queue.put(
            (
                "show_message",
                "warning",
                "Ошибка authlib",
                "Отсутсвует подключение к интернету.",
            )
        )
        logging.warning(
            "Warning message showed in download_authlib: skin error, no internet connection"
        )


def resolve_version_name(
    version: str,
    mod_loader: str,
    minecraft_directory: str,
    queue: Queue,
    ignore_installed_file: bool = False,
) -> Tuple[Union[None, str], Dict[str, bool | str]]:
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
            elif mod_loader != "vanilla" and (
                "forge" not in folder_name if folder_name == "neoforge" else 1
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
        for v in os.listdir(os.path.join(minecraft_directory, "instances")):
            instance_info_path = os.path.join(
                minecraft_directory,
                "instances",
                v,
                "instance_info.json",
            )
            if version == v and os.path.isfile(instance_info_path):
                with open(instance_info_path, encoding="utf-8") as instance_info_file:
                    vanilla_version = json.load(instance_info_file)["mc_version"]
                    if resolve_version_name(
                        vanilla_version, mod_loader, minecraft_directory, queue
                    )[0]:
                        return vanilla_version, {
                            "game_directory": os.path.join(
                                minecraft_directory, "instances", v
                            )
                        }
                    elif mod_loader == "vanilla":
                        queue.put(
                            (
                                "show_message",
                                "critical",
                                "Ошибка запуска профиля/сборки",
                                "Версия игры, которую требует профиль/сборка некорректно установлена. Запуск невозможен.",
                            )
                        )
                        return None, {"do_not_install": True}
                    else:
                        queue.put(
                            (
                                "show_message",
                                "critical",
                                "Ошибка запуска профиля/сборки",
                                'Для запуска сборки/профиля выберите "vanilla" в списке загрузчиков модов',
                            )
                        )
                        return None, {"do_not_install": True}
        else:
            return None, {}


def install_version(
    install_type,  # TODO
    options,  # TODO
    minecraft_directory: str,
    mod_loader: str,
    version: str,
    queue: Queue,
    no_internet_connection: bool,
):
    track_progress = track_progress_factory(queue)

    name_of_folder_with_version, other_info = resolve_version_name(
        version, mod_loader, minecraft_directory, queue
    )
    if other_info and other_info.get("game_directory", None) is not None:
        options["gameDirectory"] = other_info["game_directory"]
    if name_of_folder_with_version is not None:
        return name_of_folder_with_version, minecraft_directory, options
    elif (
        not no_internet_connection
        and mod_loader_is_supported(version, mod_loader)
        and not other_info.get("do_not_install", False)
    ):
        install_type(
            version,
            minecraft_directory,
            callback={
                "setProgress": lambda value: track_progress(value, "progress"),
                "setMax": lambda value: track_progress(value, "max"),
                "setStatus": lambda value: track_progress(value, "progress_info"),
            },
        )
        name_of_folder_with_version = resolve_version_name(
            version,
            mod_loader,
            minecraft_directory,
            queue,
            ignore_installed_file=True,
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
            return name_of_folder_with_version, minecraft_directory, options
        else:
            queue.put(
                (
                    "show_message",
                    "critical",
                    "Ошибка загрузки",
                    "Произошла непредвиденная ошибка во время загрузки версии.",
                )
            )
            queue.put(("start_button", True))
            logging.error(
                f"Error message showed in install_version: error after download {version} version"
            )
            return None
    elif no_internet_connection:
        queue.put(
            (
                "show_message",
                "critical",
                "Ошибка подключения",
                "Вы в оффлайн-режиме. Версия отсутсвует на вашем компьютере, загрузка невозможна. Попробуйте перезапустить лаунчер.",
            )
        )
        queue.put(("start_button", True))
        logging.error(
            "Error message showed in install_version: cannot download version because there is not internet connection"
        )
    elif not other_info.get("do_not_install", False):
        queue.put(
            (
                "show_message",
                "critical",
                "Ошибка",
                "Для данной версии нет выбранного вами загрузчика модов.",
            )
        )
        queue.put(("start_button", True))
        logging.error(
            f"Error message showed in install_version: mod loader {mod_loader} is not supported on the {version} version"
        )


def download_optifine(
    optifine_path: str,
    raw_version: str,
    queue: Queue,
    no_internet_connection: bool,
):
    if not no_internet_connection:
        url = None
        optifine_info = optipy.getVersion(raw_version)
        if optifine_info is not None:
            url = optifine_info[raw_version][0]["url"]
            queue.put(("status", "Загрузка optifine..."))
            logging.debug("Installing optifine in download_optifine")
            with open(optifine_path, "wb") as optifine_jar:
                with requests.get(url, timeout=10) as r:
                    r.raise_for_status()
                    optifine_jar.write(r.content)
            logging.debug(f"Optifine installed, path: {optifine_path}")
        else:
            queue.put(
                (
                    "show_message",
                    "warning",
                    "Запуск без optifine",
                    "Optifine недоступен на выбранной вами версии.",
                )
            )
            logging.warning(
                f"Warning message showed in download_optifine: optifine is not support on {raw_version} version"
            )
    else:
        queue.put(
            (
                "show_message",
                "warning",
                "Ошибка optifine",
                "Отсутсвует подключение к интернету.",
            )
        )
        logging.warning(
            "Warning message showed in download_optifine: optifine error, no internet connection"
        )


def launch(
    minecraft_directory: str,
    mod_loader: str,
    version: str,
    optifine: bool,
    show_console: bool,
    nickname: str,
    game_uuid: str,
    access_token: str,
    java_arguments: str,
    launch_account_type: str,
    no_internet_connection: bool,
    queue: Queue,
):
    install_type, options = prepare_installation_parameters(
        mod_loader, nickname, game_uuid, access_token, java_arguments
    )

    launch_info = install_version(
        install_type,
        options,
        minecraft_directory,
        mod_loader,
        version,
        queue,
        no_internet_connection,
    )
    if launch_info is not None:
        version_to_launch, minecraft_directory, options = launch_info
        queue.put(("progressbar", 100))

        if not no_internet_connection:
            json_path = os.path.join(
                minecraft_directory, "versions", version, f"{version}.json"
            )
            if not minecraft_launcher_lib.utils.is_vanilla_version(
                version
            ) and os.path.isfile(json_path):
                with open(json_path, encoding="utf-8") as file_with_downloads:
                    raw_version = json.load(file_with_downloads)["inheritsFrom"]
                    optifine_path = os.path.join(
                        minecraft_directory, "mods", "optifine.jar"
                    )
            elif os.path.isfile(
                os.path.join(
                    minecraft_directory, "instances", version, "instance_info.json"
                )
            ):
                with open(
                    os.path.join(
                        minecraft_directory,
                        "instances",
                        version,
                        "instance_info.json",
                    )
                ) as instance_info_file:
                    version_with_loader = json.load(instance_info_file)["mc_version"]
                    with open(
                        os.path.join(
                            minecraft_directory,
                            "versions",
                            version_with_loader,
                            f"{version_with_loader}.json",
                        ),
                        encoding="utf-8",
                    ) as file_with_downloads:
                        raw_version = json.load(file_with_downloads)["inheritsFrom"]
                        optifine_path = os.path.join(
                            minecraft_directory,
                            "instances",
                            version,
                            "mods",
                            "optifine.jar",
                        )
            else:
                raw_version = version
                optifine_path = os.path.join(
                    minecraft_directory, "mods", "optifine.jar"
                )
        else:
            raw_version = version
            optifine_path = os.path.join(minecraft_directory, "mods", "optifine.jar")

        if not os.path.isdir(os.path.join(minecraft_directory, "mods")):
            os.mkdir(os.path.join(minecraft_directory, "mods"))
        if os.path.isfile(optifine_path):
            os.remove(optifine_path)
        if optifine:
            download_optifine(optifine_path, raw_version, queue, no_internet_connection)
        download_authlib(
            raw_version,
            minecraft_directory,
            no_internet_connection,
            launch_account_type,
            queue,
        )
        logging.debug(f"Launching {version} version")
        popen_kwargs = {}
        if not show_console:
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        minecraft_process = subprocess.Popen(
            minecraft_launcher_lib.command.get_minecraft_command(
                version_to_launch, minecraft_directory, options
            ),
            cwd=minecraft_directory,
            **popen_kwargs,
        )
        queue.put(("start_button", True))
        queue.put(("status", "Игра запущена"))
        queue.put(("progressbar", 100))
        logging.debug(f"Minecraft process started on {version} version")
        queue.put(
            (
                "start_rich_presence",
                "minecraft_opened",
                raw_version,
                minecraft_process.pid,
            )
        )
        minecraft_return_code = minecraft_process.wait()
        if minecraft_return_code != 0:
            queue.put(
                (
                    "show_message",
                    "log",
                    "Игра была закрыта с ошибкой",
                    f"Minecraft вернул ошибку (крашнулся). Код ошибки: {minecraft_return_code}<br>"
                    "Вы хотите открыть лог?",
                    os.path.join(minecraft_directory, "logs", "latest.log"),
                )
            )
        queue.put(("start_rich_presence", "minecraft_closed"))
        queue.put(("status", ""))
    else:
        queue.put(("start_button", True))


def mod_loader_is_supported(raw_version: str, mod_loader: str):
    if mod_loader != "vanilla":
        return minecraft_launcher_lib.mod_loader.get_mod_loader(
            mod_loader
        ).is_minecraft_version_supported(raw_version)
    else:
        return True


def only_project_install(
    project_version: Dict[Any, Any],
    project: Dict[Any, Any],
    project_file_path: str,
    queue: Queue,
):
    with requests.get(project_version["url"], stream=True, timeout=10) as r:
        r.raise_for_status()
        with open(project_file_path, "wb") as project_file:
            bytes_downloaded = 0
            project_size = project_version["size"]
            chunk_size = int(project_size / 100)
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    bytes_downloaded += chunk_size
                    queue.put(
                        (
                            "progressbar",
                            min(100, int(bytes_downloaded / project_size * 100)),
                        )
                    )
                    queue.put(("status", f"Загрузка {project['title']}"))
                    project_file.write(chunk)
    queue_info = [
        "show_message",
        "information",
        "Проект установлен",
        f"Проект {project['title']} был успешно установлен.",
    ]
    if project["project_type"] == "modpack":
        queue_info.append(project_file_path)
    queue.put(queue_info)
    logging.info(f"Project {project['title']} installed")


def start_rich_presence(
    rpc: Presence, raw_version: Optional[str] = None, pid: Optional[int] = None
):
    try:
        if pid is None:
            rpc.update(
                details="В меню",
                start=Constants.START_LAUNCHER_TIME,
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
                pid=pid,
                state=(f"Играет на версии {raw_version}"),
                details="В Minecraft",
                start=Constants.START_LAUNCHER_TIME,
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
    except AssertionError:
        pass
