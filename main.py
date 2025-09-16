import minecraft_launcher_lib
from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Qt, QObject, Signal
import threading
import subprocess
import os
import sys
import requests
import configparser
import uuid
import json
import pypresence
import time
import base64
import datetime
import logging
import hashlib
import optipy


def catch_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.critical(f"Exception in {func.__name__}: {repr(e)}")
            try:
                gui_messenger.critical.emit(
                    args[0], "Ошибка", f"Произошла ошибка в {func.__name__}:\n{e}"
                )
            except:
                gui_messenger.critical.emit(
                    None, "Ошибка", f"Произошла ошибка в {func.__name__}:\n{e}"
                )
            if args:
                self = args[0]
                if hasattr(self, "start_button"):
                    self.set_start_button_status.emit(True)

    return wrapper


logging.basicConfig(
    level=logging.DEBUG,
    filename="FVLauncher.log",
    filemode="w",
    format="%(asctime)s %(levelname)s %(message)s",
)
logging.debug("Program started its work")


class GuiMessenger(QObject):
    warning = Signal(QtWidgets.QWidget, str, str)
    critical = Signal(QtWidgets.QWidget, str, str)
    info = Signal(QtWidgets.QWidget, str, str)

    @catch_errors
    def __init__(self):
        super().__init__()
        self.warning.connect(lambda p, t, m: QtWidgets.QMessageBox.warning(p, t, m))
        self.critical.connect(lambda p, t, m: QtWidgets.QMessageBox.critical(p, t, m))
        self.info.connect(lambda p, t, m: QtWidgets.QMessageBox.information(p, t, m))


@catch_errors
def load_config():
    default_config = {
        "version": "1.16.5",
        "mod_loader": "forge",
        "nickname": "Player",
        "java_arguments": "",
        "optifine": "2",
        "access_token": "",
        "ely_uuid": "",
        "show_console": "0",
        "show_old_alphas": "0",
        "show_old_betas": "0",
        "show_snapshots": "0",
        "show_releases": "2",
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


class SettingsWindow(QtWidgets.QDialog):
    @catch_errors
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
        super().__init__()
        self.window = window
        self.window.java_arguments = java_arguments
        self.window.show_console = show_console
        self.window.show_old_alphas = show_old_alphas
        self.window.show_old_betas = show_old_betas
        self.window.show_snapshots = show_snapshots
        self.window.show_releases = show_releases
        self.minecraft_directory = (
            minecraft_launcher_lib.utils.get_minecraft_directory()
        )
        self._make_ui()

    @catch_errors
    def set_var(self, pos, var):
        if var == "java_arguments":
            self.window.java_arguments = pos
        elif var == "show_console":
            self.window.show_console = pos
        elif var == "alphas":
            self.window.show_old_alphas = pos
        elif var == "betas":
            self.window.show_old_betas = pos
        elif var == "snapshots":
            self.window.show_snapshots = pos
        elif var == "releases":
            self.window.show_releases = pos

    @catch_errors
    def _make_ui(self):
        self.setWindowTitle("Настройки")
        self.setFixedSize(300, 500)
        self.setWindowIcon(window_icon)

        self.java_arguments_label = QtWidgets.QLabel(self, text="java-аргументы")
        self.java_arguments_label.move(25, 25)
        self.java_arguments_label.setFixedWidth(250)
        self.java_arguments_label.setAlignment(Qt.AlignCenter)

        self.java_arguments_entry = QtWidgets.QLineEdit(self)
        self.java_arguments_entry.setText(self.window.java_arguments)
        self.java_arguments_entry.textChanged.connect(
            lambda pos: self.set_var(pos, "java_arguments")
        )
        self.java_arguments_entry.move(25, 45)
        self.java_arguments_entry.setFixedWidth(250)

        self.show_console_checkbox = QtWidgets.QCheckBox(self)
        self.show_console_checkbox.setChecked(self.window.show_console)
        self.show_console_checkbox.stateChanged.connect(
            lambda pos: self.set_var(pos, "show_console")
        )
        self.show_console_checkbox.setText("Запуск с консолью")
        checkbox_width = self.show_console_checkbox.sizeHint().width()
        self.window_width = self.width()
        self.show_console_checkbox.move((self.window_width - checkbox_width) // 2, 85)

        self.versions_filter_label = QtWidgets.QLabel(self, text="Фильтр версий")
        self.versions_filter_label.move(25, 125)
        self.versions_filter_label.setFixedWidth(250)
        self.versions_filter_label.setAlignment(Qt.AlignCenter)

        self.old_alphas_checkbox = QtWidgets.QCheckBox(self)
        self.old_alphas_checkbox.setChecked(self.window.show_old_alphas)
        self.old_alphas_checkbox.stateChanged.connect(
            lambda pos: self.set_var(pos, "alphas")
        )
        self.old_alphas_checkbox.setText("Старые альфы")
        self.old_alphas_checkbox.stateChanged.connect(
            lambda: self.window.showversions(
                self.window,
                self.old_alphas_checkbox.isChecked(),
                self.old_betas_checkbox.isChecked(),
                self.snapshots_checkbox.isChecked(),
                self.releases_checkbox.isChecked(),
            )
        )
        self.checkbox_width = self.old_alphas_checkbox.sizeHint().width()
        self.old_alphas_checkbox.move(
            (self.window_width - self.checkbox_width) // 2, 145
        )

        self.old_betas_checkbox = QtWidgets.QCheckBox(self)
        self.old_betas_checkbox.setChecked(self.window.show_old_betas)
        self.old_betas_checkbox.stateChanged.connect(
            lambda pos: self.set_var(pos, "betas")
        )
        self.old_betas_checkbox.setText("Старые беты")
        self.old_betas_checkbox.stateChanged.connect(
            lambda: self.window.showversions(
                self.window,
                self.old_alphas_checkbox.isChecked(),
                self.old_betas_checkbox.isChecked(),
                self.snapshots_checkbox.isChecked(),
                self.releases_checkbox.isChecked(),
            )
        )
        self.checkbox_width = self.old_betas_checkbox.sizeHint().width()
        self.old_betas_checkbox.move(
            (self.window_width - self.checkbox_width) // 2, 165
        )

        self.snapshots_checkbox = QtWidgets.QCheckBox(self)
        self.snapshots_checkbox.setChecked(self.window.show_snapshots)
        self.snapshots_checkbox.stateChanged.connect(
            lambda pos: self.set_var(pos, "snapshots")
        )
        self.snapshots_checkbox.setText("Снапшоты")
        self.snapshots_checkbox.stateChanged.connect(
            lambda: self.window.showversions(
                self.window,
                self.old_alphas_checkbox.isChecked(),
                self.old_betas_checkbox.isChecked(),
                self.snapshots_checkbox.isChecked(),
                self.releases_checkbox.isChecked(),
            )
        )
        self.checkbox_width = self.snapshots_checkbox.sizeHint().width()
        self.snapshots_checkbox.move(
            (self.window_width - self.checkbox_width) // 2, 185
        )

        self.releases_checkbox = QtWidgets.QCheckBox(self)
        self.releases_checkbox.setChecked(self.window.show_releases)
        self.releases_checkbox.stateChanged.connect(
            lambda pos: self.set_var(pos, "releases")
        )
        self.releases_checkbox.setText("Релизы")
        self.releases_checkbox.stateChanged.connect(
            lambda: self.window.showversions(
                self.window,
                self.old_alphas_checkbox.isChecked(),
                self.old_betas_checkbox.isChecked(),
                self.snapshots_checkbox.isChecked(),
                self.releases_checkbox.isChecked(),
            )
        )
        self.checkbox_width = self.releases_checkbox.sizeHint().width()
        self.releases_checkbox.move((self.window_width - self.checkbox_width) // 2, 205)

        self.launcher_version_label = QtWidgets.QLabel(self)
        self.launcher_version_label.setText(f"Версия лаунчера: {LAUNCHER_VERSION}")
        self.launcher_version_label.move(25, 450)
        self.launcher_version_label.setFixedWidth(250)
        self.launcher_version_label.setAlignment(Qt.AlignCenter)

        self.show()


class AccountWindow(QtWidgets.QDialog):
    @catch_errors
    def __init__(self, window):
        super().__init__()
        self.window = window
        self._make_ui()

    @catch_errors
    def _make_ui(self):
        @catch_errors
        def login():
            self.data = requests.post(
                "https://authserver.ely.by/auth/authenticate",
                json={
                    "username": self.ely_username.text(),
                    "password": self.ely_password.text(),
                    "clientToken": self.window.client_token,
                    "requestUser": True,
                },
            )
            if self.sign_status_label.text() == "Статус: вы вошли в аккаунт":
                gui_messenger.critical.emit(
                    self, "Ошибка входа", "Сначала выйдите из аккаунта"
                )
                logging.error(
                    f"Error message showed in login: login error, sign out before login"
                )
            elif self.data.status_code == 200:
                self.window.access_token = self.data.json()["accessToken"]
                self.window.ely_uuid = self.data.json()["user"]["id"]
                gui_messenger.info.emit(
                    self, "Поздравляем!", "Теперь вы будете видеть свой скин в игре."
                )
                logging.info(
                    f"Info message showed in login: ely skin will be shown in game"
                )
                self.window.sign_status = "Статус: вы вошли в аккаунт"
                self.sign_status_label.setText(self.window.sign_status)
                self.window.nickname_entry.setText(self.data.json()["user"]["username"])
                self.window.nickname_entry.setReadOnly(True)
            else:
                gui_messenger.critical.emit(
                    self,
                    "Ошибка входа",
                    f"Текст ошибки: {self.data.json()['errorMessage']}",
                )
                logging.error(
                    f"Error message showed in login: login error, {self.data.json()['errorMessage']}"
                )

        @catch_errors
        def signout():
            self.data = requests.post(
                "https://authserver.ely.by/auth/invalidate",
                json={
                    "accessToken": self.window.access_token,
                    "clientToken": self.window.client_token,
                },
            )
            self.window.access_token = ""
            self.window.ely_uuid = ""
            if self.data.status_code == 200:
                gui_messenger.info.emit(
                    self, "Выход из аккаунта", "Вы вышли из аккаунта"
                )
                logging.info(f"Info message showed in signout: successfully signed out")
                self.window.nickname_entry.setReadOnly(False)
                self.window.sign_status = "Статус: вы вышли из аккаунта"
                self.sign_status_label.setText(self.window.sign_status)
            else:
                gui_messenger.critical.emit(
                    self, "Ошибка выхода", self.data.json()["errorMessage"]
                )
                logging.error(
                    f"Error message showed in signout: sign out error, {self.data.json()['errorMessage']}"
                )

        self.setWindowTitle("Настройки")
        self.setFixedSize(300, 500)
        self.setWindowIcon(window_icon)

        self.ely_username = QtWidgets.QLineEdit(self)
        self.ely_username.setPlaceholderText("Никнейм аккаунта ely.by")
        self.window_width = self.width()
        self.entry_width = self.ely_username.sizeHint().width()
        self.ely_username.move((self.window_width - self.entry_width) // 2, 40)

        self.ely_password = QtWidgets.QLineEdit(self)
        self.ely_password.setPlaceholderText("Пароль аккаунта ely.by")
        self.ely_password.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.entry_width = self.ely_password.sizeHint().width()
        self.ely_password.move((self.window_width - self.entry_width) // 2, 70)

        self.login_button = QtWidgets.QPushButton(self)
        self.login_button.setText("Войти в аккаунт")
        self.login_button.clicked.connect(login)
        self.button_width = self.login_button.sizeHint().width()
        self.login_button.move((self.window_width - self.button_width) // 2, 120)

        self.signout_button = QtWidgets.QPushButton(self)
        self.signout_button.setText("Выйти из аккаунта")
        self.signout_button.clicked.connect(signout)
        self.button_width = self.signout_button.sizeHint().width()
        self.signout_button.move((self.window_width - self.button_width) // 2, 150)

        self.sign_status_label = QtWidgets.QLabel(self, text=self.window.sign_status)
        self.label_width = self.sign_status_label.sizeHint().width()
        self.sign_status_label.move((self.window_width - self.label_width) // 2, 180)

        self.show()


class MainWindow(QtWidgets.QMainWindow):
    set_progressbar = Signal(int)
    set_download_info = Signal(str)
    set_start_button_status = Signal(bool)

    @catch_errors
    def check_java(self):
        self.java_path = minecraft_launcher_lib.utils.get_java_executable()
        if self.java_path == "java" or self.java_path == "javaw":
            gui_messenger.critical.emit(
                self,
                "Java не найдена",
                "На вашем компьютере отсутствует java, загрузите её с github лаунчера.",
            )
            logging.error(f"Error message showed while checking java: java not found")
            return False
        else:
            return True

    @catch_errors
    def start_rich_presence(
        self,
        minecraft=False,
        minecraft_process=None,
    ):
        try:
            if not minecraft:
                self.rpc.update(
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
                self.rpc.update(
                    pid=minecraft_process.pid,
                    state=(f"Играет на версии {self.raw_version}"),
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
                self.start_rich_presence()
        except:
            pass

    @catch_errors
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
    ):
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
        super().__init__()
        self.client_token = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(uuid.getnode())))
        self.rpc = pypresence.Presence(CLIENT_ID)
        try:
            self.rpc.connect()
        except:
            pass
        self.start_rich_presence()
        if self.check_java():
            self.save_config_on_close = True
            self._make_ui()
        else:
            self.save_config_on_close = False
            self.close()

    @catch_errors
    def closeEvent(self, event):
        if self.save_config_on_close:
            self.save_config()
        logging.debug("Launcher was closed")
        return super().closeEvent(event)

    @catch_errors
    def showversions(
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
            window.versions_combobox.clear()
            window.versions_combobox.addItems(versions_names_list)
        except requests.exceptions.ConnectionError:
            pass

    @catch_errors
    def prepare_installation_parameters(self):
        if self.mod_loader != "vanilla":
            install_type = minecraft_launcher_lib.mod_loader.get_mod_loader(
                self.mod_loader
            ).install
        else:
            install_type = minecraft_launcher_lib.install.install_minecraft_version
        options = {
            "username": self.nickname,
            "uuid": self.ely_uuid if self.ely_uuid else str(uuid.uuid4().hex),
            "token": self.access_token,
            "jvmArguments": self.java_arguments,
            "executablePath": self.java_path,
        }
        return install_type, options

    @catch_errors
    def download_injector(self, options, version):
        try:
            with open(
                os.path.join(self.minecraft_directory, "authlib-injector.jar"), "rb"
            ) as injector_jar:
                if (
                    hashlib.md5(injector_jar.read()).hexdigest()
                    == "c60d3899b711537e10be33c680ebd8ae"
                ):
                    logging.debug("Injector alredy installed")
                    return True
        except FileNotFoundError:
            pass
        if not no_internet_connection:
            json_path = os.path.join(
                self.minecraft_directory,
                "versions",
                self.raw_version,
                f"{self.raw_version}.json",
            )
            if not minecraft_launcher_lib.utils.is_vanilla_version(self.raw_version):
                with open(json_path) as file_with_downloads:
                    self.raw_version = json.load(file_with_downloads)["inheritsFrom"]
            json_path = os.path.join(
                self.minecraft_directory,
                "versions",
                self.raw_version,
                f"{self.raw_version}.json",
            )
            authlib_version = None
            with open(json_path) as file_with_downloads:
                for lib in json.load(file_with_downloads)["libraries"]:
                    if lib["name"].startswith("com.mojang:authlib:"):
                        authlib_version = lib["name"].split(":")[-1]
                        break
            if authlib_version is not None:
                textures_info = requests.get(
                    f"http://skinsystem.ely.by/profile/{self.nickname}"
                )
                textures = (
                    json.loads(textures_info.content)
                    if textures_info.status_code == 200
                    else {}
                )
                textures_payload = {
                    "timestamp": int(time.time() * 1000),
                    "profileName": self.nickname,
                    "textures": textures,
                }
                textures_b64 = base64.b64encode(
                    json.dumps(textures_payload).encode()
                ).decode()
                options["user_properties"] = {"textures": [textures_b64]}

                with open(
                    os.path.join(self.minecraft_directory, "authlib-injector.jar"), "wb"
                ) as injector_jar:
                    injector_jar.write(
                        requests.get(
                            "https://github.com/yushijinhun/authlib-injector/releases/download/v1.2.5/authlib-injector-1.2.5.jar"
                        ).content
                    )
                return True
            else:
                gui_messenger.warning.emit(
                    self,
                    "Ошибка скина",
                    "На данной версии нет authlib, скины не поддерживаются.",
                )
                logging.warning(
                    f"Warning message showed in download_injector: skins not supported on {version} version (raw version is {self.raw_version})"
                )
                return False
        else:
            gui_messenger.warning.emit(
                self, "Ошибка скина", "Отсутсвует подключение к интернету."
            )
            logging.warning(
                f"Warning message showed in download_injector: skin error, no internet connection"
            )
            return False

    @catch_errors
    def install_version(
        self,
        install_type,
        options,
        installed_versions_json_path,
    ):
        progress = 0
        max_progress = 100
        percents = 0
        last_track_progress_call_time = time.time()
        last_progress_info = ""

        @catch_errors
        def resolve_version_name(
            installed_versions_json_path, check_after_download=False
        ):
            if not os.path.isfile(installed_versions_json_path):
                with open(
                    installed_versions_json_path, "w", encoding="utf-8"
                ) as installed_versions_json_file:
                    json.dump({"installed_versions": []}, installed_versions_json_file)
            with open(
                installed_versions_json_path, "r", encoding="utf-8"
            ) as installed_versions_json_file:
                installed_versions = json.load(installed_versions_json_file)
            if (
                f"{self.mod_loader}{self.raw_version}"
                in installed_versions["installed_versions"]
                or check_after_download
            ):
                for v in minecraft_launcher_lib.utils.get_installed_versions(
                    self.minecraft_directory
                ):
                    folder_name = v["id"]
                    if self.mod_loader == "vanilla" and folder_name == self.raw_version:
                        return folder_name
                    elif (
                        self.mod_loader == "neoforge" and self.mod_loader in folder_name
                    ):
                        with open(
                            os.path.join(
                                self.minecraft_directory,
                                "versions",
                                folder_name,
                                f"{folder_name}.json",
                            )
                        ) as version_info:
                            if (
                                json.load(version_info)["inheritsFrom"]
                                == self.raw_version
                            ):
                                return folder_name
                    elif (
                        self.mod_loader in folder_name
                        and self.raw_version in folder_name
                    ):
                        return folder_name
                else:
                    return None
            else:
                return None

        @catch_errors
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
                    self.set_progressbar.emit(percents)
                    last_track_progress_call_time = time.time()
                else:
                    last_progress_info = value
                    self.set_download_info.emit(value)

        name_of_folder_with_version = resolve_version_name(installed_versions_json_path)
        if name_of_folder_with_version is not None:
            return name_of_folder_with_version, self.minecraft_directory, options
        elif not no_internet_connection and self.mod_loader_is_supported(
            self.raw_version, self.mod_loader
        ):
            install_type(
                self.raw_version,
                self.minecraft_directory,
                callback={
                    "setProgress": lambda value: track_progress(value, "progress"),
                    "setMax": lambda value: track_progress(value, "max"),
                    "setStatus": lambda value: track_progress(value, "progress_info"),
                },
            )
            name_of_folder_with_version = resolve_version_name(
                installed_versions_json_path, True
            )
            if name_of_folder_with_version is not None:
                return name_of_folder_with_version, self.minecraft_directory, options
            else:
                gui_messenger.critical.emit(
                    self,
                    "Ошибка загрузки",
                    "Произошла непредвиденная ошибка во время загрузки версии.",
                )
                self.set_start_button_status.emit(True)
                logging.error(
                    f"Error message showed in install_version: error after download {self.raw_version} version"
                )
                return None
        elif no_internet_connection:
            gui_messenger.critical.emit(
                self,
                "Ошибка подключения",
                "Вы в оффлайн-режиме. Версия отсутсвует на вашем компьютере, загрузка невозможна. Попробуйте перезапустить лаунчер.",
            )
            self.set_start_button_status.emit(True)
            logging.error(
                f"Error message showed in install_version: cannot download version because there is not internet connection"
            )
        else:
            gui_messenger.critical.emit(
                self,
                "Ошибка",
                "Для данной версии нет выбранного вами загрузчика модов.",
            )
            self.set_start_button_status.emit(True)
            logging.error(
                f"Error message showed in install_version: mod loader {self.mod_loader} is not supported on the {self.raw_version} version"
            )

    @catch_errors
    def download_optifine(self, optifine_path):
        if not no_internet_connection:
            url = None
            optifine_info = optipy.getVersion(self.raw_version)
            if optifine_info is not None:
                url = optifine_info[self.raw_version][0]["url"]
                self.set_download_info.emit("Загрузка Optifine...")
                logging.debug("Installing optifine in download_optifine")
                with open(optifine_path, "wb") as optifine_jar:
                    optifine_jar.write(requests.get(url).content)
            else:
                gui_messenger.warning.emit(
                    self,
                    "Запуск без optifine",
                    "Optifine недоступен на выбранной вами версии.",
                )
                logging.warning(
                    f"Warning message showed in download_optifine: optifine is not support on {self.raw_version} version"
                )
        else:
            gui_messenger.warning.emit(
                self, "Ошибка optifine", "Отсутсвует подключение к интернету."
            )
            logging.warning(
                f"Warning message showed in download_optifine: optifine error, no internet connection"
            )

    @catch_errors
    def launch(self):
        installed_versions_json_path = os.path.join(
            self.minecraft_directory, "installed_versions.json"
        )
        if not os.path.isdir(self.minecraft_directory):
            os.mkdir(self.minecraft_directory)

        install_type, options = self.prepare_installation_parameters()

        launch_info = self.install_version(
            install_type,
            options,
            installed_versions_json_path,
        )

        if launch_info is not None:
            with open(
                installed_versions_json_path, "r", encoding="utf-8"
            ) as installed_versions_json_file:
                installed_versions = json.load(installed_versions_json_file)
            with open(
                installed_versions_json_path, "w", encoding="utf-8"
            ) as installed_versions_json_file:
                if (
                    not f"{self.mod_loader}{self.raw_version}"
                    in installed_versions["installed_versions"]
                ):
                    installed_versions["installed_versions"].append(
                        f"{self.mod_loader}{self.raw_version}"
                    )
                if (
                    self.mod_loader != "vanilla"
                    and not f"vanilla{self.raw_version}"
                    in installed_versions["installed_versions"]
                ):
                    installed_versions["installed_versions"].append(
                        f"vanilla{self.raw_version}"
                    )
                json.dump(installed_versions, installed_versions_json_file)
            version, self.minecraft_directory, options = launch_info
            self.set_download_info.emit("Загрузка injector...")
            logging.debug("Installing injector in launch")
            self.set_progressbar.emit(100)
            options["jvmArguments"] = options["jvmArguments"].split()
            if self.download_injector(options, version):
                options["jvmArguments"].append(
                    f"-javaagent:{os.path.join(self.minecraft_directory, 'authlib-injector.jar')}=ely.by"
                )
            else:
                options.pop("executablePath")

            optifine_path = os.path.join(
                self.minecraft_directory, "mods", "optifine.jar"
            )

            if not os.path.isdir(os.path.join(self.minecraft_directory, "mods")):
                os.mkdir(os.path.join(self.minecraft_directory, "mods"))
            if os.path.isfile(optifine_path):
                os.remove(optifine_path)
            if self.optifine and self.mod_loader == "forge":
                self.download_optifine(optifine_path)
            logging.debug(f"Launching {version} version")
            minecraft_process = subprocess.Popen(
                minecraft_launcher_lib.command.get_minecraft_command(
                    version, self.minecraft_directory, options
                ),
                cwd=self.minecraft_directory,
                **(
                    {"creationflags": subprocess.CREATE_NO_WINDOW}
                    if not self.show_console
                    else {}
                ),
            )
            self.set_download_info.emit("Игра запущена")
            logging.debug(f"Minecraft process started on {version} version")
            self.set_start_button_status.emit(True)
            self.start_rich_presence(True, minecraft_process)

    @catch_errors
    def v1_6_or_higher(self, raw_version):
        for version in minecraft_launcher_lib.utils.get_version_list():
            if raw_version == version["id"]:
                return version["releaseTime"] >= datetime.datetime(
                    2013, 6, 25, 13, 8, 56, tzinfo=datetime.timezone.utc
                )

    @catch_errors
    def mod_loader_is_supported(self, raw_version, mod_loader):
        if mod_loader != "vanilla":
            if minecraft_launcher_lib.mod_loader.get_mod_loader(
                mod_loader
            ).is_minecraft_version_supported(raw_version) and self.v1_6_or_higher(
                raw_version
            ):
                return True
            else:
                return False
        else:
            return True

    @catch_errors
    def save_config(self):
        settings = {
            "version": self.raw_version,
            "mod_loader": self.mod_loader,
            "nickname": self.nickname,
            "java_arguments": self.java_arguments,
            "optifine": self.optifine,
            "access_token": self.access_token,
            "ely_uuid": self.ely_uuid,
            "show_console": self.show_console,
            "show_old_alphas": self.show_old_alphas,
            "show_old_betas": self.show_old_betas,
            "show_snapshots": self.show_snapshots,
            "show_releases": self.show_releases,
        }
        config_path = "FVLauncher.ini"
        parser = configparser.ConfigParser()

        parser.add_section("Settings")
        parser["Settings"] = settings

        with open(config_path, "w", encoding="utf-8") as config_file:
            parser.write(config_file)

    @catch_errors
    def block_optifine_checkbox(self, *args):
        if self.loaders_combobox.currentText() == "forge":
            self.optifine_checkbox.setDisabled(False)
        else:
            self.optifine_checkbox.setDisabled(True)

    @catch_errors
    def on_start_button(self):
        self.set_start_button_status.emit(False)
        threading.Thread(target=self.launch, daemon=True).start()

    @catch_errors
    def set_var(self, pos, var):
        if var == "optifine":
            self.optifine = pos
        elif var == "mod_loader":
            self.mod_loader = pos
        elif var == "version":
            self.raw_version = pos
        elif var == "nickname":
            self.nickname = pos

    @catch_errors
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

    @catch_errors
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
        self.minecraft_directory = (
            minecraft_launcher_lib.utils.get_minecraft_directory()
        )

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

        self.versions_combobox = QtWidgets.QComboBox(self)
        self.versions_combobox.move(20, 20)
        self.versions_combobox.setFixedWidth(120)
        self.showversions(
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
        self.set_start_button_status.connect(self.start_button.setEnabled)

        self.progressbar = QtWidgets.QProgressBar(self, textVisible=False)
        self.progressbar.setFixedWidth(260)
        self.progressbar.move(20, 430)
        self.set_progressbar.connect(self.progressbar.setValue)

        self.download_info_label = QtWidgets.QLabel(self)
        self.download_info_label.setFixedWidth(200)
        self.download_info_label.move(50, 450)
        self.download_info_label.setAlignment(Qt.AlignCenter)
        self.set_download_info.connect(self.download_info_label.setText)

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
        sys.exit(app.exec())


if __name__ == "__main__":
    try:
        requests.get("https://google.com")
        no_internet_connection = False
    except requests.exceptions.ConnectionError:
        no_internet_connection = True

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle(QtWidgets.QStyleFactory.create("windows11"))
    gui_messenger = GuiMessenger()

    CLIENT_ID = "1399428342117175497"
    LAUNCHER_VERSION = "v4.4"
    start_launcher_time = int(time.time())
    window_icon = QtGui.QIcon(
        (
            os.path.join(
                "assets",
                "minecraft_title.png",
            )
        )
    )
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
    )
