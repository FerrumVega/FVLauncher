import minecraft_launcher_lib
from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import QObject, Signal, Qt, QTimer
from xml.etree import ElementTree as ET
import subprocess
import os
import sys
import requests
import configparser
import uuid
import json
import pypresence
import time
import logging
import optipy
import multiprocessing
import traceback

logging.basicConfig(
    level=logging.DEBUG,
    filename="FVLauncher.log",
    filemode="w",
    format="%(asctime)s %(levelname)s %(message)s",
)
logging.debug("Program started its work")

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


class GuiMessenger(QObject):
    warning = Signal(str, str)
    critical = Signal(str, str)
    info = Signal(str, str)

    def emit_msg(self, t, m, type):
        global window_icon
        msg = QtWidgets.QMessageBox()
        msg.setWindowTitle(t)
        msg.setText(m)
        msg.setWindowIcon(window_icon)
        msg.setIcon(type)
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


gui_messenger = GuiMessenger()


def log_exception(*args):
    logging.critical(
        f"There was an error:\n{''.join(traceback.format_exception(*args))}"
    )
    gui_messenger.critical.emit(
        "Ошибка",
        f"Произошла непредвиденная ошибка:\n{''.join(traceback.format_exception(*args))}",
    )


sys.excepthook = log_exception


def run_in_process_with_exceptions_logging(func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except Exception as e:
        log_exception(type(e), e, e.__traceback__)


def load_config():
    default_config = {
        "version": "1.16.5",
        "mod_loader": "forge",
        "nickname": "Player",
        "java_arguments": "",
        "optifine": "1",
        "access_token": "",
        "ely_uuid": "",
        "show_console": "0",
        "show_old_alphas": "0",
        "show_old_betas": "0",
        "show_snapshots": "0",
        "show_releases": "1",
        "minecraft_directory": "",
    }

    config_path = "FVLauncher.ini"
    parser = configparser.ConfigParser()

    if not os.path.isfile(config_path):
        parser.add_section("Settings")
        parser["Settings"] = default_config
        with open(config_path, "w", encoding="utf-8") as config_file:
            parser.write(config_file)
    else:
        updated = False
        parser.read(config_path, encoding="utf-8")
        for key, value in default_config.items():
            if key not in parser["Settings"]:
                parser["Settings"][key] = value
                updated = True
        if updated:
            with open(config_path, "w", encoding="utf-8") as config_file:
                parser.write(config_file)

    return {key: parser["Settings"][key] for key in parser.options("Settings")}


def download_profile_from_mrpack(minecraft_directory, mrpack_path, queue):
    if mrpack_path:
        profile_path = os.path.join(
            minecraft_directory,
            "profiles",
            minecraft_launcher_lib.mrpack.get_mrpack_information(mrpack_path)["name"],
        )
        minecraft_launcher_lib.mrpack.install_mrpack(
            mrpack_path,
            minecraft_directory,
            profile_path,
            callback={"setStatus": queue.put},
        )
        with open(
            os.path.join(profile_path, "profile_info.json"), "w"
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
    if not no_internet_connection:
        if not minecraft_launcher_lib.utils.is_vanilla_version(raw_version):
            with open(json_path) as file_with_downloads:
                raw_version = json.load(file_with_downloads)["inheritsFrom"]
        json_path = os.path.join(
            minecraft_directory,
            "versions",
            raw_version,
            f"{raw_version}.json",
        )
        authlib_version = None
        with open(json_path) as file_with_downloads:
            for lib in json.load(file_with_downloads)["libraries"]:
                if lib["name"].startswith("com.mojang:authlib:"):
                    authlib_version = lib["name"].split(":")[-1]
                    break
        if authlib_version is not None:
            base_url = "https://maven.ely.by/releases/by/ely/authlib"
            for maven_version in ET.fromstring(
                requests.get(f"{base_url}/maven-metadata.xml").text
            ).findall("./versioning/versions/version")[::-1]:
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
                        jar.write(
                            requests.get(
                                f"{base_url}/{maven_version.text}/authlib-{maven_version.text}.jar"
                            ).content
                        )
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
        else:
            gui_messenger.warning.emit(
                "Ошибка скина",
                "На данной версии нет authlib, скины не поддерживаются.",
            )
            logging.warning(
                f"Warning message showed in download_injector: skins not supported on {raw_version} version"
            )
            return False
    else:
        gui_messenger.warning.emit(
            "Ошибка скина", "Отсутсвует подключение к интернету."
        )
        logging.warning(
            "Warning message showed in download_injector: skin error, no internet connection"
        )
        return False


def resolve_version_name(
    version, mod_loader, minecraft_directory, ignore_installed_file=False
):
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
            elif mod_loader != "vanilla":
                with open(
                    os.path.join(
                        minecraft_directory,
                        "versions",
                        folder_name,
                        f"{folder_name}.json",
                    )
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
                with open(profile_info_path) as profile_info_file:
                    vanilla_version = json.load(profile_info_file)[0]["mc_version"]

                    if resolve_version_name(version, mod_loader, minecraft_directory)[
                        0
                    ]:
                        return vanilla_version, {
                            "gameDir": os.path.join(minecraft_directory, "profiles", v)
                        }
                    else:
                        return None, {}
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
                    percents = progress / max_progress * 100
                except ZeroDivisionError:
                    percents = 0
                if percents > 100.0:
                    percents = 100.0
                queue.put(("progressbar", percents))
                last_track_progress_call_time = time.time()
            else:
                last_progress_info = value
                queue.put(("status", value))

    name_of_folder_with_version, game_dir = resolve_version_name(
        raw_version, mod_loader, minecraft_directory
    )
    if game_dir:
        options["gameDirectory"] = game_dir["gameDir"]

    if name_of_folder_with_version is not None:
        return name_of_folder_with_version, minecraft_directory, options
    elif not no_internet_connection and mod_loader_is_supported(
        raw_version, mod_loader
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
            ).close()
            queue.put(("status", "Загрузка injector..."))
            logging.debug("Installing injector in launch")
            download_injector(
                raw_version,
                minecraft_directory,
                no_internet_connection,
            )
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
    else:
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
            queue.put(("start_button", "Загрузка optifine..."))
            logging.debug("Installing optifine in download_optifine")
            with open(optifine_path, "wb") as optifine_jar:
                optifine_jar.write(requests.get(url).content)
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
    queue,
    no_internet_connection,
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
        **({"creationflags": subprocess.CREATE_NO_WINDOW} if not show_console else {}),
    )
    queue.put(("status", "Игра запущена"))
    logging.debug(f"Minecraft process started on {version} version")
    queue.put(("start_button", True))
    start_rich_presence(raw_version, True, minecraft_process)


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


class ClickableLabel(QtWidgets.QLabel):
    clicked = Signal()

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)

        self.clicked.emit()


class ProjectsSearch(QtWidgets.QDialog):

    def __init__(self, window, minecraft_directory):
        super().__init__(window)
        self.minecraft_directory = minecraft_directory
        self._make_ui()

    def download_project_process(self, project_version, project, profile):
        type_to_dir = {
            "mod": "mods",
            "resourcepack": "resourcepacks",
            "datapack": "datapacks",
            "shader": "shaderpacks",
        }
        project_file_path = os.path.join(
            self.minecraft_directory.replace("/", "\\"),
            "profiles",
            profile,
            type_to_dir[project["project_type"]],
            project_version["filename"],
        )
        profile_info_path = os.path.join(
            self.minecraft_directory.replace("/", "\\"),
            "profiles",
            profile,
            "profile_info.json",
        )
        os.makedirs(os.path.dirname(project_file_path), exist_ok=True)
        with open(
            project_file_path,
            "wb",
        ) as project_file:
            project_file.write(requests.get(project_version["url"]).content)
        with open(profile_info_path, "r", encoding="utf-8") as profile_info_file:
            profile_info = json.load(profile_info_file)
        profile_info[1].append([project_version, project])
        with open(profile_info_path, "w", encoding="utf-8") as profile_info_file:
            json.dump(profile_info, profile_info_file, indent=4)

    def install_project(self, current_loader, mc_version, project_version, project):
        found = False
        profiles = []
        if project["project_type"] in ["plugin", "modpack"]:
            QtWidgets.QMessageBox.critical(
                self.install_project_window,
                "Ошибка",
                "Вы не можете скачать плагин/модпак в профиль",
            )
            return
        if project["project_type"] == "mod":
            for v in os.listdir(os.path.join(self.minecraft_directory, "profiles")):
                profile_info_path = os.path.join(
                    self.minecraft_directory,
                    "profiles",
                    v,
                    "profile_info.json",
                )
                if os.path.isfile(profile_info_path):
                    with open(profile_info_path) as profile_info_file:
                        vanilla_version = json.load(profile_info_file)[0]["mc_version"]
                        version_name = resolve_version_name(
                            mc_version, current_loader, self.minecraft_directory
                        )[0]
                        if version_name is not None and vanilla_version == version_name:
                            profiles.append(v)
                            found = True
        if not found and project["project_type"] == "mod":
            QtWidgets.QMessageBox.critical(
                self.install_project_window,
                "Ошибка",
                "Нет установленных версий, подходящих для этого проекта",
            )
            return
        elif project["project_type"] != "mod":
            for v in os.listdir(os.path.join(self.minecraft_directory, "profiles")):
                profiles.append(v)
        self.profiles_window = QtWidgets.QDialog(self.install_project_window)
        self.profiles_window.setModal(True)
        self.profiles_window.setWindowTitle(f"Выбор профиля для загрузки проекта")
        self.profiles_window.setFixedSize(300, 500)

        start_y_coord = 30
        buttons = []

        for profile in profiles:
            download_button = QtWidgets.QPushButton(self.profiles_window)
            download_button.setText(profile)
            download_button.setFixedWidth(240)
            download_button.move(30, start_y_coord)
            buttons.append(download_button)
            start_y_coord += 30
            download_button.clicked.connect(
                lambda *args, cur_profile=profile: self.download_project_process(
                    project_version, project, cur_profile
                )
            )

        self.profiles_window.show()

    def show_version_info(self, project, mc_version):
        supported_mc_versions = json.loads(
            requests.get(
                f"https://api.modrinth.com/v2/project/{project['id']}/version?game_versions={list(mc_version)}"
            ).text
        )
        self.install_project_window = QtWidgets.QDialog(self.project_info_window)
        self.install_project_window.setModal(True)
        self.install_project_window.setWindowTitle(f"Загрузка {project['title']}")
        self.install_project_window.setFixedSize(300, 500)

        start_y_coord = 30
        buttons = []
        loaders = []

        for version in supported_mc_versions:
            for loader in version["loaders"]:
                if not loader in loaders:
                    loaders.append(loader)
                    download_button = QtWidgets.QPushButton(self.install_project_window)
                    download_button.setText(loader)
                    download_button.setFixedWidth(240)
                    download_button.move(30, start_y_coord)
                    buttons.append(download_button)
                    start_y_coord += 30
                    download_button.clicked.connect(
                        lambda *args, current_loader=loader, cur_version=version[
                            "files"
                        ][0]: self.install_project(
                            current_loader,
                            mc_version,
                            cur_version,
                            project,
                        )
                    )

        self.install_project_window.show()

    def show_versions(self, project):
        mc_versions = project["game_versions"]
        while self.versions_layout.count():
            self.versions_layout.takeAt(0).widget().deleteLater()
        for mc_version in sorted(mc_versions, reverse=True):
            w = ClickableLabel(text=mc_version)
            w.clicked.connect(
                lambda current_mc_version=mc_version: self.show_version_info(
                    project, current_mc_version
                )
            )
            w.setStyleSheet(r"QLabel::hover {color: #03D3FC}")
            w.setCursor(Qt.PointingHandCursor)
            w.setToolTip("Кликните для просмотра")
            self.versions_layout.addWidget(w)

    def show_project(self, id):
        project = json.loads(
            requests.get(f"https://api.modrinth.com/v2/project/{id}").text
        )

        self.project_info_window = QtWidgets.QDialog(self)
        self.project_info_window.setModal(True)
        self.project_info_window.setWindowTitle(project["title"])
        self.project_info_window.setFixedSize(300, 500)

        self.project_title = QtWidgets.QLabel(self.project_info_window)
        self.project_title.move(20, 20)
        self.project_title.setText(project["title"])
        self.project_title.setAlignment(Qt.AlignCenter)
        self.project_title.setFixedWidth(260)

        self.project_description = QtWidgets.QLabel(self.project_info_window)
        self.project_description.move(20, 40)
        self.project_description.setText(project["description"])
        self.project_description.setAlignment(Qt.AlignCenter)
        self.project_description.setFixedWidth(260)
        self.project_description.setWordWrap(True)

        self.versions_container = QtWidgets.QWidget()
        self.versions_layout = QtWidgets.QVBoxLayout(self.versions_container)

        self.scroll_area = QtWidgets.QScrollArea(self.project_info_window)
        self.scroll_area.move(0, 100)
        self.scroll_area.setFixedSize(300, 200)
        self.scroll_area.setWidget(self.versions_container)
        self.scroll_area.setWidgetResizable(True)
        self.show_versions(project)

        self.project_info_window.show()

    def search(self, query):
        while self.p_layout.count():
            self.p_layout.takeAt(0).widget().deleteLater()
        info = json.loads(
            requests.get(f"https://api.modrinth.com/v2/search?query={query}").text
        )
        for project in info["hits"]:
            w = ClickableLabel(text=project["title"])
            w.clicked.connect(
                lambda current_project_id=project["project_id"]: self.show_project(
                    current_project_id
                )
            )
            w.setStyleSheet(r"QLabel::hover {color: #03D3FC}")
            w.setCursor(Qt.PointingHandCursor)
            w.setToolTip("Кликните для просмотра")
            self.p_layout.addWidget(w)

    def _make_ui(self):
        self.setWindowTitle("Поиск проектов на Modrinth")
        self.setFixedSize(300, 500)
        self.setModal(True)

        self.search_string = QtWidgets.QLineEdit(self)
        self.search_string.move(20, 20)
        self.search_string.setFixedWidth(200)

        self.search_button = QtWidgets.QPushButton(self)
        self.search_button.move(240, 20)
        self.search_button.setFixedWidth(40)
        self.search_button.setText("Поиск")
        self.search_button.clicked.connect(
            lambda: self.search(self.search_string.text())
        )

        self.container = QtWidgets.QWidget()
        self.p_layout = QtWidgets.QVBoxLayout(self.container)

        self.scroll_area = QtWidgets.QScrollArea(self)
        self.scroll_area.move(0, 60)
        self.scroll_area.setFixedSize(300, 400)
        self.scroll_area.setWidget(self.container)
        self.scroll_area.setWidgetResizable(True)

        self.show()


class SettingsWindow(QtWidgets.QDialog):

    def __init__(
        self,
        window,
        java_arguments,
        show_console,
        show_old_alphas,
        show_old_betas,
        show_snapshots,
        show_releases,
    ):
        super().__init__(window)
        self.m_window = window
        self.m_window.java_arguments = java_arguments
        self.m_window.show_console = show_console
        self.m_window.show_old_alphas = show_old_alphas
        self.m_window.show_old_betas = show_old_betas
        self.m_window.show_snapshots = show_snapshots
        self.m_window.show_releases = show_releases
        self._make_ui()

    def set_var(self, pos, var):
        if var == "java_arguments":
            self.m_window.java_arguments = pos
        elif var == "show_console":
            self.m_window.show_console = pos
        elif var == "alphas":
            self.m_window.show_old_alphas = pos
        elif var == "betas":
            self.m_window.show_old_betas = pos
        elif var == "snapshots":
            self.m_window.show_snapshots = pos
        elif var == "releases":
            self.m_window.show_releases = pos
        elif var == "directory" and pos != "":
            self.m_window.minecraft_directory = pos
            self.current_minecraft_directory.setText(
                f"Текущая папка с игрой:\n{self.m_window.minecraft_directory}"
            )

    def closeEvent(self, event):
        os.makedirs(
            os.path.join(self.m_window.minecraft_directory, "profiles"), exist_ok=True
        )
        return super().closeEvent(event)

    def _make_ui(self):
        self.setWindowTitle("Настройки")
        self.setFixedSize(300, 500)
        self.setModal(True)

        self.java_arguments_label = QtWidgets.QLabel(self, text="java-аргументы")
        self.java_arguments_label.move(25, 25)
        self.java_arguments_label.setFixedWidth(250)
        self.java_arguments_label.setAlignment(Qt.AlignCenter)

        self.java_arguments_entry = QtWidgets.QLineEdit(self)
        self.java_arguments_entry.setText(self.m_window.java_arguments)
        self.java_arguments_entry.textChanged.connect(
            lambda pos: self.set_var(pos, "java_arguments")
        )
        self.java_arguments_entry.move(25, 45)
        self.java_arguments_entry.setFixedWidth(250)

        self.show_console_checkbox = QtWidgets.QCheckBox(self)
        self.show_console_checkbox.setChecked(self.m_window.show_console)
        self.show_console_checkbox.stateChanged.connect(
            lambda pos: self.set_var(pos, "show_console")
        )
        self.show_console_checkbox.setText("Запуск с консолью")
        checkbox_width = self.show_console_checkbox.sizeHint().width()
        self.m_window_width = self.width()
        self.show_console_checkbox.move((self.m_window_width - checkbox_width) // 2, 85)

        self.versions_filter_label = QtWidgets.QLabel(self, text="Фильтр версий")
        self.versions_filter_label.move(25, 125)
        self.versions_filter_label.setFixedWidth(250)
        self.versions_filter_label.setAlignment(Qt.AlignCenter)

        self.old_alphas_checkbox = QtWidgets.QCheckBox(self)
        self.old_alphas_checkbox.setChecked(self.m_window.show_old_alphas)
        self.old_alphas_checkbox.stateChanged.connect(
            lambda pos: self.set_var(pos, "alphas")
        )
        self.old_alphas_checkbox.setText("Старые альфы")
        self.old_alphas_checkbox.stateChanged.connect(
            lambda: self.m_window.show_versions(
                self.m_window,
                self.old_alphas_checkbox.isChecked(),
                self.old_betas_checkbox.isChecked(),
                self.snapshots_checkbox.isChecked(),
                self.releases_checkbox.isChecked(),
            )
        )
        self.checkbox_width = self.old_alphas_checkbox.sizeHint().width()
        self.old_alphas_checkbox.move(
            (self.m_window_width - self.checkbox_width) // 2, 145
        )

        self.old_betas_checkbox = QtWidgets.QCheckBox(self)
        self.old_betas_checkbox.setChecked(self.m_window.show_old_betas)
        self.old_betas_checkbox.stateChanged.connect(
            lambda pos: self.set_var(pos, "betas")
        )
        self.old_betas_checkbox.setText("Старые беты")
        self.old_betas_checkbox.stateChanged.connect(
            lambda: self.m_window.show_versions(
                self.m_window,
                self.old_alphas_checkbox.isChecked(),
                self.old_betas_checkbox.isChecked(),
                self.snapshots_checkbox.isChecked(),
                self.releases_checkbox.isChecked(),
            )
        )
        self.checkbox_width = self.old_betas_checkbox.sizeHint().width()
        self.old_betas_checkbox.move(
            (self.m_window_width - self.checkbox_width) // 2, 165
        )

        self.snapshots_checkbox = QtWidgets.QCheckBox(self)
        self.snapshots_checkbox.setChecked(self.m_window.show_snapshots)
        self.snapshots_checkbox.stateChanged.connect(
            lambda pos: self.set_var(pos, "snapshots")
        )
        self.snapshots_checkbox.setText("Снапшоты")
        self.snapshots_checkbox.stateChanged.connect(
            lambda: self.m_window.show_versions(
                self.m_window,
                self.old_alphas_checkbox.isChecked(),
                self.old_betas_checkbox.isChecked(),
                self.snapshots_checkbox.isChecked(),
                self.releases_checkbox.isChecked(),
            )
        )
        self.checkbox_width = self.snapshots_checkbox.sizeHint().width()
        self.snapshots_checkbox.move(
            (self.m_window_width - self.checkbox_width) // 2, 185
        )

        self.releases_checkbox = QtWidgets.QCheckBox(self)
        self.releases_checkbox.setChecked(self.m_window.show_releases)
        self.releases_checkbox.stateChanged.connect(
            lambda pos: self.set_var(pos, "releases")
        )
        self.releases_checkbox.setText("Релизы")
        self.releases_checkbox.stateChanged.connect(
            lambda: self.m_window.show_versions(
                self.m_window,
                self.old_alphas_checkbox.isChecked(),
                self.old_betas_checkbox.isChecked(),
                self.snapshots_checkbox.isChecked(),
                self.releases_checkbox.isChecked(),
            )
        )
        self.checkbox_width = self.releases_checkbox.sizeHint().width()
        self.releases_checkbox.move(
            (self.m_window_width - self.checkbox_width) // 2, 205
        )

        self.minecraft_directory_button = QtWidgets.QPushButton(self)
        self.minecraft_directory_button.move(25, 280)
        self.minecraft_directory_button.setFixedWidth(250)
        self.minecraft_directory_button.clicked.connect(
            lambda: self.set_var(
                QtWidgets.QFileDialog.getExistingDirectory(
                    self, "Выбор папки для файлов игры"
                ),
                "directory",
            )
        )
        self.minecraft_directory_button.setText("Выбор папки для файов игры")

        self.current_minecraft_directory = QtWidgets.QLabel(self)
        self.current_minecraft_directory.move(25, 300)
        self.current_minecraft_directory.setFixedWidth(250)
        self.current_minecraft_directory.setText(
            f"Текущая папка с игрой:\n{self.m_window.minecraft_directory}"
        )
        self.current_minecraft_directory.setWordWrap(True)
        self.current_minecraft_directory.setAlignment(Qt.AlignCenter)

        self.launcher_version_label = QtWidgets.QLabel(self)
        self.launcher_version_label.setText(f"Версия лаунчера: {LAUNCHER_VERSION}")
        self.launcher_version_label.move(25, 450)
        self.launcher_version_label.setFixedWidth(250)
        self.launcher_version_label.setAlignment(Qt.AlignCenter)

        self.show()


class AccountWindow(QtWidgets.QDialog):

    def __init__(self, window):
        super().__init__(window)
        self.m_window = window
        self._make_ui()

    def _make_ui(self):

        def login():
            self.data = requests.post(
                "https://authserver.ely.by/auth/authenticate",
                json={
                    "username": self.ely_username.text(),
                    "password": self.ely_password.text(),
                    "clientToken": self.m_window.client_token,
                    "requestUser": True,
                },
            )
            if self.sign_status_label.text() == "Статус: вы вошли в аккаунт":
                gui_messenger.critical.emit(
                    "Ошибка входа", "Сначала выйдите из аккаунта"
                )
                logging.error(
                    f"Error message showed in login: login error, sign out before login"
                )
            elif self.data.status_code == 200:
                self.m_window.access_token = self.data.json()["accessToken"]
                self.m_window.ely_uuid = self.data.json()["user"]["id"]
                gui_messenger.info.emit(
                    "Поздравляем!", "Теперь вы будете видеть свой скин в игре."
                )
                logging.info(
                    f"Info message showed in login: ely skin will be shown in game"
                )
                self.m_window.sign_status = "Статус: вы вошли в аккаунт"
                self.sign_status_label.setText(self.m_window.sign_status)
                self.m_window.nickname_entry.setText(
                    self.data.json()["user"]["username"]
                )
                self.m_window.nickname_entry.setReadOnly(True)
            else:
                gui_messenger.critical.emit(
                    "Ошибка входа",
                    f"Текст ошибки: {self.data.json()['errorMessage']}",
                )
                logging.error(
                    f"Error message showed in login: login error, {self.data.json()['errorMessage']}"
                )

        def signout():
            self.data = requests.post(
                "https://authserver.ely.by/auth/invalidate",
                json={
                    "accessToken": self.m_window.access_token,
                    "clientToken": self.m_window.client_token,
                },
            )
            self.m_window.access_token = ""
            self.m_window.ely_uuid = ""
            if self.data.status_code == 200:
                gui_messenger.info.emit("Выход из аккаунта", "Вы вышли из аккаунта")
                logging.info(f"Info message showed in signout: successfully signed out")
                self.m_window.nickname_entry.setReadOnly(False)
                self.m_window.sign_status = "Статус: вы вышли из аккаунта"
                self.sign_status_label.setText(self.m_window.sign_status)
            else:
                gui_messenger.critical.emit(
                    "Ошибка выхода", self.data.json()["errorMessage"]
                )
                logging.error(
                    f"Error message showed in signout: sign out error, {self.data.json()['errorMessage']}"
                )

        self.setWindowTitle("Настройки")
        self.setFixedSize(300, 500)
        self.setModal(True)

        self.ely_username = QtWidgets.QLineEdit(self)
        self.ely_username.setPlaceholderText("Никнейм аккаунта ely.by")
        self.m_window_width = self.width()
        self.entry_width = self.ely_username.sizeHint().width()
        self.ely_username.move((self.m_window_width - self.entry_width) // 2, 40)

        self.ely_password = QtWidgets.QLineEdit(self)
        self.ely_password.setPlaceholderText("Пароль аккаунта ely.by")
        self.ely_password.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.entry_width = self.ely_password.sizeHint().width()
        self.ely_password.move((self.m_window_width - self.entry_width) // 2, 70)

        self.login_button = QtWidgets.QPushButton(self)
        self.login_button.setText("Войти в аккаунт")
        self.login_button.clicked.connect(login)
        self.button_width = self.login_button.sizeHint().width()
        self.login_button.move((self.m_window_width - self.button_width) // 2, 120)

        self.signout_button = QtWidgets.QPushButton(self)
        self.signout_button.setText("Выйти из аккаунта")
        self.signout_button.clicked.connect(signout)
        self.button_width = self.signout_button.sizeHint().width()
        self.signout_button.move((self.m_window_width - self.button_width) // 2, 150)

        self.sign_status_label = QtWidgets.QLabel(self, text=self.m_window.sign_status)
        self.label_width = self.sign_status_label.sizeHint().width()
        self.sign_status_label.move((self.m_window_width - self.label_width) // 2, 180)

        self.show()


class ProfilesWindow(QtWidgets.QDialog):

    def __init__(self, window):
        super().__init__(window)
        self.m_window = window
        self._make_ui()

    def closeEvent(self, event):
        if hasattr(self, "import_mrpack_process"):
            self.import_mrpack_process.terminate()
        return super().closeEvent(event)

    def _update_ui_from_queue(self):
        while not self.queue.empty():
            self.mrpack_import_status.setText(self.queue.get_nowait())

    def _handle_open_mrpack_choosing_window(self):
        mrpack_path = QtWidgets.QFileDialog.getOpenFileName(
            self, "Выберите файл сборки", "", "*.mrpack"
        )[0].replace("/", "\\")

        self.queue = multiprocessing.Queue()
        self.import_mrpack_process = multiprocessing.Process(
            target=download_profile_from_mrpack,
            args=(self.m_window.minecraft_directory, mrpack_path, self.queue),
            daemon=True,
        )
        self.import_mrpack_process.start()
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_ui_from_queue)
        self.timer.start(200)

    def create_own_profile(self):

        def create_folder():
            profile_path = os.path.join(
                self.m_window.minecraft_directory,
                "profiles",
                self.profile_name_entry.text(),
            )
            os.makedirs(profile_path, exist_ok=True)
            with open(
                os.path.join(profile_path, "profile_info.json"), "w"
            ) as profile_info_file:
                json.dump(
                    [
                        {"mc_version": self.profile_version_entry.text()},
                        [],
                    ],
                    profile_info_file,
                )
            gui_messenger.info.emit(
                "Создание папки профиля",
                f"Папка профиль успешно создана по пути {profile_path}",
            )
            self.m_window.show_versions(
                self.m_window,
                self.m_window.show_old_alphas,
                self.m_window.show_old_betas,
                self.m_window.show_snapshots,
                self.m_window.show_releases,
            )

        self.create_own_profile_window = QtWidgets.QDialog(self)
        self.create_own_profile_window.setModal(True)
        self.create_own_profile_window.setWindowTitle("Создание папки профиля")
        self.create_own_profile_window.setFixedSize(200, 150)

        self.profile_name_entry = QtWidgets.QLineEdit(self.create_own_profile_window)
        self.profile_name_entry.setFixedWidth(180)
        self.profile_name_entry.setPlaceholderText("Название профиля")
        self.profile_name_entry.move(10, 20)

        self.profile_version_entry = QtWidgets.QLineEdit(self.create_own_profile_window)
        self.profile_version_entry.setFixedWidth(180)
        self.profile_version_entry.setPlaceholderText("Название папки версии")
        self.profile_version_entry.move(10, 50)

        self.create_own_profile_button = QtWidgets.QPushButton(
            self.create_own_profile_window
        )
        self.create_own_profile_button.setFixedWidth(90)
        self.create_own_profile_button.move(55, 80)
        self.create_own_profile_button.setText("Создать профиль")
        self.create_own_profile_button.clicked.connect(create_folder)

        self.create_own_profile_window.show()

    def _make_ui(self):
        self.setModal(True)
        self.setWindowTitle("Создание/импорт профиля/сборки")
        self.setFixedSize(300, 500)

        self.choose_mrpack_file_button = QtWidgets.QPushButton(self)
        self.choose_mrpack_file_button.setFixedWidth(120)
        self.choose_mrpack_file_button.move(90, 90)
        self.choose_mrpack_file_button.setText("Выбрать файл")
        self.choose_mrpack_file_button.clicked.connect(
            self._handle_open_mrpack_choosing_window
        )

        self.mrpack_import_status = QtWidgets.QLabel(self)
        self.mrpack_import_status.setFixedWidth(290)
        self.mrpack_import_status.setAlignment(Qt.AlignCenter)
        self.mrpack_import_status.move(5, 450)

        self.create_profile_button = QtWidgets.QPushButton(self)
        self.create_profile_button.setFixedWidth(120)
        self.create_profile_button.move(90, 120)
        self.create_profile_button.setText("Создать профиль")
        self.create_profile_button.clicked.connect(self.create_own_profile)

        self.show()


class MainWindow(QtWidgets.QMainWindow):

    def check_java(self):
        self.java_path = minecraft_launcher_lib.utils.get_java_executable()
        if self.java_path == "java" or self.java_path == "javaw":
            gui_messenger.critical.emit(
                "Java не найдена",
                "На вашем компьютере отсутствует java, загрузите её с github лаунчера.",
            )
            logging.error(f"Error message showed while checking java: java not found")
            return False
        else:
            return True

    def _update_ui_from_queue(self):
        while not self.queue.empty():
            var, value = self.queue.get_nowait()
            if var == "progressbar":
                self.progressbar.setValue(value)
            elif var == "status":
                self.download_info_label.setText(value)
            elif var == "start_button":
                self.start_button.setEnabled(value)

    def __init__(
        self,
        chosen_version,
        chosen_mod_loader,
        chosen_nickname,
        chosen_java_arguments,
        optifine_position,
        saved_access_token,
        saved_ely_uuid,
        show_console_position,
        show_old_alphas_position,
        show_old_betas_position,
        show_snapshots_position,
        show_releases_position,
        saved_minecraft_directory,
    ):
        global rpc
        self.chosen_version = chosen_version
        self.chosen_mod_loader = chosen_mod_loader
        self.chosen_nickname = chosen_nickname
        self.chosen_java_arguments = chosen_java_arguments
        self.optifine_position = optifine_position
        self.saved_access_token = saved_access_token
        self.saved_ely_uuid = saved_ely_uuid
        self.show_console_position = show_console_position
        self.show_old_alphas_position = show_old_alphas_position
        self.show_old_betas_position = show_old_betas_position
        self.show_snapshots_position = show_snapshots_position
        self.show_releases_position = show_releases_position
        self.saved_minecraft_directory = saved_minecraft_directory

        super().__init__()
        self.client_token = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(uuid.getnode())))
        rpc = pypresence.Presence(CLIENT_ID)
        try:
            rpc.connect()
        except:
            pass
        start_rich_presence()
        if self.check_java():
            self.save_config_on_close = True
            self._make_ui()
        else:
            self.save_config_on_close = False
            self.close()

    def closeEvent(self, event):
        if self.save_config_on_close:
            self.save_config()
        logging.debug("Launcher was closed")
        return super().closeEvent(event)

    def show_versions(
        self, window, show_old_alphas, show_old_betas, show_snapshots, show_releases
    ):
        window.show_old_alphas = show_old_alphas
        window.show_old_betas = show_old_betas
        window.show_snapshots = show_snapshots
        window.show_releases = show_releases
        versions_names_list = []
        try:
            for version in minecraft_launcher_lib.utils.get_version_list():
                if version["type"] == "old_alpha" and show_old_alphas:
                    versions_names_list.append(version["id"])
                elif version["type"] == "old_beta" and show_old_betas:
                    versions_names_list.append(version["id"])
                elif version["type"] == "snapshot" and show_snapshots:
                    versions_names_list.append(version["id"])
                elif version["type"] == "release" and show_releases:
                    versions_names_list.append(version["id"])
            for item in minecraft_launcher_lib.utils.get_installed_versions(
                window.minecraft_directory
            ):
                if (
                    not "fabric" in item["id"].lower()
                    and not "forge" in item["id"].lower()
                    and not "quilt" in item["id"].lower()
                    and not "neoforge" in item["id"].lower()
                    and not minecraft_launcher_lib.utils.is_vanilla_version(item["id"])
                ):
                    versions_names_list.append(item["id"])
            for item in os.listdir(
                os.path.join(window.minecraft_directory, "profiles")
            ):
                versions_names_list.append(item)
            window.versions_combobox.clear()
            window.versions_combobox.addItems(versions_names_list)
        except requests.exceptions.ConnectionError:
            pass

    def save_config(self):
        settings = {
            "version": self.raw_version,
            "mod_loader": self.mod_loader,
            "nickname": self.nickname,
            "java_arguments": self.java_arguments,
            "optifine": int(self.optifine),
            "access_token": self.access_token,
            "ely_uuid": self.ely_uuid,
            "show_console": int(self.show_console),
            "show_old_alphas": int(self.show_old_alphas),
            "show_old_betas": int(self.show_old_betas),
            "show_snapshots": int(self.show_snapshots),
            "show_releases": int(self.show_releases),
            "minecraft_directory": self.minecraft_directory,
        }
        config_path = "FVLauncher.ini"
        parser = configparser.ConfigParser()

        parser.add_section("Settings")
        parser["Settings"] = settings

        with open(config_path, "w", encoding="utf-8") as config_file:
            parser.write(config_file)

    def block_optifine_checkbox(self, *args):
        if self.loaders_combobox.currentText() == "forge":
            self.optifine_checkbox.setDisabled(False)
        else:
            self.optifine_checkbox.setDisabled(True)

    def on_start_button(self):
        self.queue = multiprocessing.Queue()
        if __name__ == "__main__":
            self.minecraft_download_process = multiprocessing.Process(
                target=run_in_process_with_exceptions_logging,
                args=(
                    launch,
                    self.minecraft_directory,
                    self.mod_loader,
                    self.raw_version,
                    self.optifine,
                    self.show_console,
                    self.nickname,
                    self.ely_uuid,
                    self.access_token,
                    self.java_arguments,
                    self.queue,
                    no_internet_connection,
                ),
                daemon=True,
            )
            self.minecraft_download_process.start()
            self.timer = QTimer()
            self.timer.timeout.connect(self._update_ui_from_queue)
            self.timer.start(200)

    def set_var(self, pos, var):
        if var == "optifine":
            self.optifine = pos
        elif var == "mod_loader":
            self.mod_loader = pos
        elif var == "version":
            self.raw_version = pos
        elif var == "nickname":
            self.nickname = pos

    def auto_login(self):
        try:
            if self.saved_ely_uuid and self.saved_access_token:
                valid_token_info = requests.post(
                    "https://authserver.ely.by/auth/validate",
                    json={"accessToken": self.saved_access_token},
                )
                if valid_token_info.status_code != 200:
                    refreshed_token_info = requests.post(
                        "https://authserver.ely.by/auth/refresh",
                        json={
                            "accessToken": self.saved_access_token,
                            "clientToken": self.client_token,
                            "requestUser": True,
                        },
                    )
                    if refreshed_token_info.status_code != 200:
                        access_token = ""
                        ely_uuid = ""
                        self.sign_status = "Статус: вы не вошли в аккаунт"
                        return access_token, ely_uuid
                    else:
                        access_token = refreshed_token_info.json()["accessToken"]
                        ely_uuid = refreshed_token_info.json()["user"]["id"]
                        username = refreshed_token_info.json()["user"]["username"]
                        self.nickname_entry.setText(username)
                        self.nickname_entry.setReadOnly(True)
                        self.sign_status = "Статус: вы вошли в аккаунт"
                        return access_token, ely_uuid
                else:
                    username = self.chosen_nickname
                    self.nickname_entry.setText(username)
                    self.nickname_entry.setReadOnly(True)
                    self.sign_status = "Статус: вы вошли в аккаунт"
                    return self.saved_access_token, self.saved_ely_uuid
            else:
                self.sign_status = "Статус: вы не вошли в аккаунт"
                return self.saved_access_token, self.saved_ely_uuid
        except requests.exceptions.ConnectionError:
            self.sign_status = "Статус: вы не вошли в аккаунт"
            return self.saved_access_token, self.saved_ely_uuid

    def _make_ui(self):
        # self.setStyleSheet(
        #     f"""
        #     QMainWindow {{
        #         background-image: url("assets/background.png");
        #         background-repeat: no-repeat;
        #         background-position: center;
        #         background-attachment: fixed;
        #     }}
        # """
        # )

        self.setWindowTitle("FVLauncher")
        self.sign_status = ""
        self.setWindowIcon(window_icon)

        self.setFixedSize(300, 500)

        self.raw_version = self.chosen_version
        self.mod_loader = self.chosen_mod_loader
        self.optifine = int(self.optifine_position)
        self.nickname = self.chosen_nickname

        self.java_arguments = self.chosen_java_arguments
        self.show_console = int(self.show_console_position)

        self.show_old_alphas = int(self.show_old_alphas_position)
        self.show_old_betas = int(self.show_old_betas_position)
        self.show_snapshots = int(self.show_snapshots_position)
        self.show_releases = int(self.show_releases_position)

        self.minecraft_directory = (
            self.saved_minecraft_directory
            if self.saved_minecraft_directory
            else minecraft_launcher_lib.utils.get_minecraft_directory()
        )
        os.makedirs(os.path.join(self.minecraft_directory, "profiles"), exist_ok=True)

        self.versions_combobox = QtWidgets.QComboBox(self)
        self.versions_combobox.move(20, 20)
        self.versions_combobox.setFixedWidth(120)
        self.show_versions(
            self,
            self.show_old_alphas,
            self.show_old_betas,
            self.show_snapshots,
            self.show_releases,
        )
        self.versions_combobox.setCurrentText(self.raw_version)
        self.versions_combobox.currentTextChanged.connect(
            lambda pos: self.set_var(pos, "version")
        )
        self.versions_combobox.setFixedHeight(30)
        self.versions_combobox.setEditable(True)

        self.nickname_entry = QtWidgets.QLineEdit(self)
        self.nickname_entry.move(20, 60)
        self.nickname_entry.setFixedWidth(260)
        self.nickname_entry.setPlaceholderText("Никнейм")
        self.nickname_entry.setText(self.nickname)
        self.nickname_entry.textChanged.connect(
            lambda pos: self.set_var(pos, "nickname")
        )

        self.optifine_checkbox = QtWidgets.QCheckBox(self)
        self.optifine_checkbox.setText("Optifine")
        self.optifine_checkbox.move(20, 100)
        self.optifine_checkbox.setFixedWidth(260)
        self.optifine_checkbox.setChecked(self.optifine)
        self.optifine_checkbox.stateChanged.connect(
            lambda pos: self.set_var(pos, "optifine")
        )

        mod_loaders = ["fabric", "forge", "quilt", "neoforge", "vanilla"]
        self.loaders_combobox = QtWidgets.QComboBox(self)
        self.loaders_combobox.addItems(mod_loaders)
        self.loaders_combobox.move(160, 20)
        self.loaders_combobox.setFixedWidth(120)
        self.loaders_combobox.setCurrentText(self.mod_loader)
        self.block_optifine_checkbox()
        self.loaders_combobox.currentIndexChanged.connect(self.block_optifine_checkbox)
        self.loaders_combobox.currentTextChanged.connect(
            lambda pos: self.set_var(pos, "mod_loader")
        )
        self.loaders_combobox.setFixedHeight(30)
        self.loaders_combobox.setEditable(True)

        self.start_button = QtWidgets.QPushButton(self)
        self.start_button.setText("Запуск")
        self.start_button.setFixedWidth(260)
        self.start_button.clicked.connect(self.on_start_button)
        self.start_button.move(20, 140)

        self.download_projects_button = QtWidgets.QPushButton(self)
        self.download_projects_button.setText("Скачать проекты")
        self.download_projects_button.setFixedWidth(220)
        self.download_projects_button.move(40, 360)
        self.download_projects_button.clicked.connect(
            lambda: ProjectsSearch(self, self.minecraft_directory)
        )

        self.create_profile_button = QtWidgets.QPushButton(self)
        self.create_profile_button.setText("Создание/импорт профиля/сборки")
        self.create_profile_button.setFixedWidth(220)
        self.create_profile_button.move(40, 400)
        self.create_profile_button.clicked.connect(lambda: ProfilesWindow(self))

        self.progressbar = QtWidgets.QProgressBar(self, textVisible=False)
        self.progressbar.setFixedWidth(260)
        self.progressbar.move(20, 430)

        self.download_info_label = QtWidgets.QLabel(self)
        self.download_info_label.setFixedWidth(290)
        self.download_info_label.move(5, 450)
        self.download_info_label.setAlignment(Qt.AlignCenter)

        self.settings_button = QtWidgets.QPushButton(self)
        self.settings_button.setText("⚙️")
        self.settings_button.clicked.connect(
            lambda: SettingsWindow(
                self,
                self.java_arguments,
                self.show_console,
                self.show_old_alphas,
                self.show_old_betas,
                self.show_snapshots,
                self.show_releases,
            )
        )
        self.settings_button.move(5, 465)
        self.settings_button.setFixedSize(30, 30)

        self.account_button = QtWidgets.QPushButton(self)
        self.account_button.setText("🩻")
        self.account_button.clicked.connect(lambda: AccountWindow(self))
        self.account_button.move(265, 465)
        self.account_button.setFixedSize(30, 30)

        self.access_token, self.ely_uuid = self.auto_login()

        self.show()


if __name__ == "__main__":
    try:
        requests.get("https://google.com")
        no_internet_connection = False
    except requests.exceptions.ConnectionError:
        no_internet_connection = True

    CLIENT_ID = "1399428342117175497"
    LAUNCHER_VERSION = "v5.3"
    start_launcher_time = int(time.time())
    config = load_config()
    window = MainWindow(
        config["version"],
        config["mod_loader"],
        config["nickname"],
        config["java_arguments"],
        config["optifine"],
        config["access_token"],
        config["ely_uuid"],
        config["show_console"],
        config["show_old_alphas"],
        config["show_old_betas"],
        config["show_snapshots"],
        config["show_releases"],
        config["minecraft_directory"],
    )
    sys.exit(app.exec())
