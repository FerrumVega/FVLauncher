import minecraft_launcher_lib
from PySide6 import QtWidgets, QtGui
from PySide6.QtCore import Signal, Qt, QTimer
import os
import sys
import requests
import configparser
import uuid
import json
import pypresence
import logging
import multiprocessing
from faker import Faker

import utils
import updater


logging.basicConfig(
    level=logging.DEBUG,
    filename="FVLauncher.log",
    filemode="w",
    format="%(asctime)s %(levelname)s %(message)s",
)
logging.debug("Program started its work")


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

    def _update_ui_from_queue(self):
        while not self.queue.empty():
            self.progressbar.setValue(self.queue.get_nowait())

    def download_project_process(self, project_version, project, profile, mc_version):
        if profile:
            with open(
                os.path.join(
                    self.minecraft_directory, "profiles", profile, "profile_info.json"
                ),
                encoding="utf-8",
            ) as profile_info_file:
                profile_info = json.load(profile_info_file)
            with open(
                os.path.join(
                    self.minecraft_directory,
                    "versions",
                    profile_info[0]["mc_version"],
                    f"{profile_info[0]['mc_version']}.json",
                ),
                encoding="utf-8",
            ) as mc_version_file:
                try:
                    inherits_from = json.load(mc_version_file).get(
                        "inheritsFrom", profile_info[0]["mc_version"]
                    )
                    if inherits_from != mc_version:
                        if (
                            QtWidgets.QMessageBox.warning(
                                self.profiles_window,
                                "Ошибка скачивания проекта",
                                f"Версия игры профиля не совпадает с версией игры проекта, который вы выбрали\nВерсия игры проекта: {mc_version}\nВерсия игры сборки: {inherits_from}.\nВы уверены, что хотите установить проект на этот профиль?",
                                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                            )
                            != QtWidgets.QMessageBox.Yes
                        ):
                            return
                except KeyError:
                    if project["project_type"] == "mod" and (
                        QtWidgets.QMessageBox.warning(
                            self.profiles_window,
                            "Ошибка скачивания мода",
                            "Вероятнее всего, вы пытаетесь установить мод на ванильный профиль. Вы уверены, что хотите установить мод на этот профиль?",
                            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        )
                        != QtWidgets.QMessageBox.Yes
                    ):
                        return

        type_to_dir = {
            "mod": "mods",
            "resourcepack": "resourcepacks",
            "datapack": "datapacks",
            "shader": "shaderpacks",
        }
        if profile:
            project_file_path = os.path.join(
                self.minecraft_directory,
                "profiles",
                profile,
                type_to_dir[project["project_type"]],
                project_version["filename"],
            )
            profile_info_path = os.path.join(
                self.minecraft_directory,
                "profiles",
                profile,
                "profile_info.json",
            )
        else:
            project_file_path = os.path.join(
                self.minecraft_directory,
                type_to_dir[project["project_type"]],
                project_version["filename"],
            )
            profile_info_path = os.path.join(
                self.minecraft_directory, "profile_info.json"
            )
            if not os.path.isfile(profile_info_path):
                with open(
                    profile_info_path, "w", encoding="utf-8"
                ) as profile_info_file:
                    json.dump([{"mc_version": "any"}, []], profile_info_file, indent=4)

        os.makedirs(os.path.dirname(project_file_path), exist_ok=True)

        if __name__ == "__main__":
            self.queue = multiprocessing.Queue()
            self.download_project_file_process = multiprocessing.Process(
                target=utils.run_in_process_with_exceptions_logging,
                args=(
                    utils.only_project_install,
                    project_version,
                    project,
                    project_file_path,
                    profile_info_path,
                ),
                kwargs={"queue": self.queue},
                daemon=True,
            )
            self.download_project_file_process.start()
            self.timer = QTimer()
            self.timer.timeout.connect(self._update_ui_from_queue)
            self.timer.start(200)

    def install_project(self, project, mc_version, loader):
        with requests.get(
            f'https://api.modrinth.com/v2/project/{project["id"]}/version?game_versions=["{mc_version}"]&loaders=["{loader}"]'
        ) as r:
            r.raise_for_status()
            project_version = json.loads(r.text)[0]["files"][0]
        profiles = []
        if project["project_type"] not in ["mod", "shader", "datapack", "resourcepack"]:
            QtWidgets.QMessageBox.critical(
                self.install_project_window,
                "Ошибка",
                "Вы не можете скачать плагин/модпак в профиль",
            )
            return
        for v in os.listdir(os.path.join(self.minecraft_directory, "profiles")):
            profiles.append(v)
        self.profiles_window = QtWidgets.QDialog(self.install_project_window)
        self.profiles_window.setModal(True)
        self.profiles_window.setWindowTitle(f"Выбор профиля для загрузки проекта")
        self.profiles_window.setFixedSize(300, 500)

        start_y_coord = 30
        buttons = []

        self.progressbar = QtWidgets.QProgressBar(
            self.profiles_window, textVisible=False
        )
        self.progressbar.setFixedWidth(260)
        self.progressbar.move(20, 430)

        for profile in profiles:
            download_button = QtWidgets.QPushButton(self.profiles_window)
            download_button.setText(profile)
            download_button.setFixedWidth(240)
            download_button.move(30, start_y_coord)
            buttons.append(download_button)
            start_y_coord += 30
            download_button.clicked.connect(
                lambda *args, cur_profile=profile: self.download_project_process(
                    project_version, project, cur_profile, mc_version
                )
            )
        download_button = QtWidgets.QPushButton(self.profiles_window)
        download_button.setText("В корень (без сборки)")
        download_button.setFixedWidth(240)
        download_button.move(30, start_y_coord)
        buttons.append(download_button)
        start_y_coord += 30
        download_button.clicked.connect(
            lambda *args, cur_profile="": self.download_project_process(
                project_version, project, cur_profile, mc_version
            )
        )

        self.profiles_window.show()

    def show_version_info(self, project, mc_version):
        self.install_project_window = QtWidgets.QDialog(self.project_info_window)
        self.install_project_window.setModal(True)
        self.install_project_window.setWindowTitle(f"Загрузка {project['title']}")
        self.install_project_window.setFixedSize(300, 500)

        start_y_coord = 30

        for loader in project["loaders"]:
            download_button = QtWidgets.QPushButton(self.install_project_window)
            download_button.setText(loader)
            download_button.setFixedWidth(240)
            download_button.move(30, start_y_coord)
            start_y_coord += 30
            download_button.clicked.connect(
                lambda *args, current_loader=loader: self.install_project(
                    project, mc_version, current_loader
                )
            )

        self.install_project_window.show()

    def show_versions(self, project):
        mc_versions = project["game_versions"]
        for mc_version in mc_versions[::-1]:
            w = ClickableLabel(text=mc_version)
            w.clicked.connect(
                lambda current_mc_version=mc_version: self.show_version_info(
                    project, current_mc_version
                )
            )
            w.setStyleSheet("QLabel::hover {color: #03D3FC}")
            w.setCursor(Qt.PointingHandCursor)
            w.setToolTip("Кликните для просмотра")
            self.versions_layout.addWidget(w)

    def show_project(self, id):
        with requests.get(f"https://api.modrinth.com/v2/project/{id}") as r:
            r.raise_for_status()
            project = json.loads(r.text)

        type_to_russian_name = {
            "mod": "мод",
            "resourcepack": "ресурспак",
            "datapack": "датапак",
            "shader": "шейдер",
        }

        self.project_info_window = QtWidgets.QDialog(self)
        self.project_info_window.setModal(True)
        self.project_info_window.setWindowTitle(project["title"])
        self.project_info_window.setFixedSize(300, 500)

        self.project_title = QtWidgets.QLabel(self.project_info_window)
        self.project_title.move(20, 20)
        self.downloads = f"{project['downloads']:_}".replace("_", " ")
        self.project_title.setText(
            f"{project['title']} ({type_to_russian_name.get(project['project_type'], 'проект').capitalize()} с {self.downloads} скачиваниями)"
        )
        self.project_title.setAlignment(Qt.AlignCenter)
        self.project_title.setFixedWidth(260)

        self.icon = QtGui.QPixmap()
        with requests.get(project["icon_url"]) as r:
            r.raise_for_status()
            self.icon.loadFromData(r.content)
        self.project_icon = QtWidgets.QLabel(self.project_info_window)
        self.icon = self.icon.scaled(100, 100)
        self.project_icon.setPixmap(self.icon)
        self.project_icon.move(100, 40)

        self.project_description = QtWidgets.QLabel(self.project_info_window)
        self.project_description.move(20, 140)
        self.project_description.setText(
            project["description"][:130]
            + ("..." if len(project["description"]) > 130 else "")
        )
        self.project_description.setAlignment(Qt.AlignCenter)
        self.project_description.setFixedWidth(260)
        self.project_description.setWordWrap(True)

        self.versions_container = QtWidgets.QWidget()
        self.versions_layout = QtWidgets.QVBoxLayout(self.versions_container)

        self.scroll_area = QtWidgets.QScrollArea(self.project_info_window)
        self.scroll_area.move(0, 200)
        self.scroll_area.setFixedSize(300, 300)
        self.scroll_area.setWidget(self.versions_container)
        self.scroll_area.setWidgetResizable(True)
        self.show_versions(project)

        self.project_info_window.show()

    def search(self, query):
        while self.p_layout.count():
            self.p_layout.takeAt(0).widget().deleteLater()
        with requests.get(f"https://api.modrinth.com/v2/search?query={query}") as r:
            r.raise_for_status()
            info = json.loads(r.text)
        for project in info["hits"]:
            w = ClickableLabel(text=project["title"])
            w.clicked.connect(
                lambda current_project_id=project["project_id"]: self.show_project(
                    current_project_id
                )
            )
            w.setStyleSheet("QLabel::hover {color: #03D3FC}")
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

    def __init__(self, window):
        super().__init__(window)
        self._make_ui()

    def set_game_directory(self, directory):
        if directory != "":
            window.minecraft_directory = directory.replace("/", "\\")
            self.current_minecraft_directory.setText(
                f"Текущая папка с игрой:\n{window.minecraft_directory}"
            )

    def closeEvent(self, event):
        os.makedirs(os.path.join(window.minecraft_directory, "profiles"), exist_ok=True)
        window.java_arguments = self.java_arguments_entry.text()
        window.show_console = self.show_console_checkbox.isChecked()
        window.show_old_alphas = self.old_alphas_checkbox.isChecked()
        window.show_old_betas = self.old_betas_checkbox.isChecked()
        window.show_snapshots = self.snapshots_checkbox.isChecked()
        window.show_releases = self.releases_checkbox.isChecked()
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
        self.java_arguments_entry.setText(window.java_arguments)
        self.java_arguments_entry.move(25, 45)
        self.java_arguments_entry.setFixedWidth(250)

        self.show_console_checkbox = QtWidgets.QCheckBox(self)
        self.show_console_checkbox.setChecked(window.show_console)
        self.show_console_checkbox.setText("Запуск с консолью")
        checkbox_width = self.show_console_checkbox.sizeHint().width()
        self.m_window_width = self.width()
        self.show_console_checkbox.move((self.m_window_width - checkbox_width) // 2, 85)

        self.versions_filter_label = QtWidgets.QLabel(self, text="Фильтр версий")
        self.versions_filter_label.move(25, 125)
        self.versions_filter_label.setFixedWidth(250)
        self.versions_filter_label.setAlignment(Qt.AlignCenter)

        self.old_alphas_checkbox = QtWidgets.QCheckBox(self)
        self.old_alphas_checkbox.setChecked(window.show_old_alphas)
        self.old_alphas_checkbox.setText("Старые альфы")
        self.old_alphas_checkbox.stateChanged.connect(
            lambda: window.show_versions(
                window,
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
        self.old_betas_checkbox.setChecked(window.show_old_betas)
        self.old_betas_checkbox.setText("Старые беты")
        self.old_betas_checkbox.stateChanged.connect(
            lambda: window.show_versions(
                window,
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
        self.snapshots_checkbox.setChecked(window.show_snapshots)
        self.snapshots_checkbox.setText("Снапшоты")
        self.snapshots_checkbox.stateChanged.connect(
            lambda: window.show_versions(
                window,
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
        self.releases_checkbox.setChecked(window.show_releases)
        self.releases_checkbox.setText("Релизы")
        self.releases_checkbox.stateChanged.connect(
            lambda: window.show_versions(
                window,
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
            lambda: self.set_game_directory(
                QtWidgets.QFileDialog.getExistingDirectory(
                    self, "Выбор папки для файлов игры"
                )
            )
        )
        self.minecraft_directory_button.setText("Выбор папки для файов игры")

        self.current_minecraft_directory = QtWidgets.QLabel(self)
        self.current_minecraft_directory.move(25, 310)
        self.current_minecraft_directory.setFixedWidth(250)
        self.current_minecraft_directory.setText(
            f"Текущая папка с игрой:\n{window.minecraft_directory}"
        )
        self.current_minecraft_directory.setWordWrap(True)
        self.current_minecraft_directory.setAlignment(Qt.AlignCenter)

        self.launcher_version_label = QtWidgets.QLabel(self)
        self.launcher_version_label.setText(
            f"Версия лаунчера: {utils.LAUNCHER_VERSION}"
        )
        self.launcher_version_label.move(25, 450)
        self.launcher_version_label.setFixedWidth(250)
        self.launcher_version_label.setAlignment(Qt.AlignCenter)

        self.show()


class AccountWindow(QtWidgets.QDialog):

    def __init__(self, window):
        super().__init__(window)
        self._make_ui()

    def _make_ui(self):

        def login():
            with requests.post(
                "https://authserver.ely.by/auth/authenticate",
                json={
                    "username": self.ely_username_entry.text(),
                    "password": self.ely_password_entry.text(),
                    "clientToken": window.client_token,
                    "requestUser": True,
                },
            ) as r:
                self.data = r
            if self.sign_status_label.text() == "Статус: вы вошли в аккаунт":
                QtWidgets.QMessageBox.critical(
                    self, "Ошибка входа", "Сначала выйдите из аккаунта"
                )
                logging.error(
                    f"Error message showed in login: login error, sign out before login"
                )
            elif self.data.status_code == 200:
                window.access_token = self.data.json()["accessToken"]
                window.ely_uuid = self.data.json()["user"]["id"]
                QtWidgets.QMessageBox.information(
                    self, "Поздравляем!", "Теперь вы будете видеть свой скин в игре."
                )
                logging.info(
                    f"Info message showed in login: ely skin will be shown in game"
                )
                window.sign_status = "Статус: вы вошли в аккаунт"
                self.sign_status_label.setText(window.sign_status)
                window.nickname_entry.setText(self.data.json()["user"]["username"])
                window.nickname_entry.setReadOnly(True)
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Ошибка входа",
                    f"Текст ошибки: {self.data.json()['errorMessage']}",
                )
                logging.error(
                    f"Error message showed in login: login error, {self.data.json()['errorMessage']}"
                )

        def signout():
            with requests.post(
                "https://authserver.ely.by/auth/invalidate",
                json={
                    "accessToken": window.access_token,
                    "clientToken": window.client_token,
                },
            ) as r:
                self.data = r
            window.access_token = ""
            window.ely_uuid = ""
            if self.data.status_code == 200:
                QtWidgets.QMessageBox.information(
                    self, "Выход из аккаунта", "Вы вышли из аккаунта"
                )
                logging.info(f"Info message showed in signout: successfully signed out")
                window.nickname_entry.setReadOnly(False)
                window.sign_status = "Статус: вы вышли из аккаунта"
                self.sign_status_label.setText(window.sign_status)
            else:
                QtWidgets.QMessageBox.critical(
                    self, "Ошибка выхода", self.data.json()["errorMessage"]
                )
                logging.error(
                    f"Error message showed in signout: sign out error, {self.data.json()['errorMessage']}"
                )

        self.setWindowTitle("Настройки")
        self.setFixedSize(300, 500)
        self.setModal(True)

        self.ely_username_entry = QtWidgets.QLineEdit(self)
        self.ely_username_entry.setPlaceholderText("Никнейм аккаунта ely.by")
        self.m_window_width = self.width()
        self.entry_width = self.ely_username_entry.sizeHint().width()
        self.ely_username_entry.move((self.m_window_width - self.entry_width) // 2, 40)

        self.ely_password_entry = QtWidgets.QLineEdit(self)
        self.ely_password_entry.setPlaceholderText("Пароль аккаунта ely.by")
        self.ely_password_entry.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.entry_width = self.ely_password_entry.sizeHint().width()
        self.ely_password_entry.move((self.m_window_width - self.entry_width) // 2, 70)

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

        self.sign_status_label = QtWidgets.QLabel(self, text=window.sign_status)
        self.label_width = self.sign_status_label.sizeHint().width()
        self.sign_status_label.move((self.m_window_width - self.label_width) // 2, 180)

        self.show()


class ProfilesWindow(QtWidgets.QDialog):

    def __init__(self, window):
        super().__init__(window)
        self._make_ui()

    def closeEvent(self, event):
        if hasattr(self, "import_mrpack_process"):
            self.import_mrpack_process.terminate()
        return super().closeEvent(event)

    def _update_ui_from_queue(self):
        while not self.queue.empty():
            var, value = self.queue.get_nowait()
            if var == "status":
                self.mrpack_import_status.setText(value)
            elif "show_versions":
                window.show_versions(
                    window,
                    window.show_old_alphas,
                    window.show_old_betas,
                    window.show_snapshots,
                    window.show_releases,
                )

    def _handle_open_mrpack_choosing_window(self):
        mrpack_path = QtWidgets.QFileDialog.getOpenFileName(
            self, "Выберите файл сборки", "", "*.mrpack"
        )[0].replace("/", "\\")

        if __name__ == "__main__":
            self.queue = multiprocessing.Queue()
            self.import_mrpack_process = multiprocessing.Process(
                target=utils.run_in_process_with_exceptions_logging,
                args=(
                    utils.download_profile_from_mrpack,
                    window.minecraft_directory,
                    mrpack_path,
                    window.no_internet_connection,
                ),
                kwargs={"queue": self.queue},
                daemon=True,
            )
            self.import_mrpack_process.start()
            self.timer = QTimer()
            self.timer.timeout.connect(self._update_ui_from_queue)
            self.timer.start(200)

    def create_own_profile(self):

        def create_folder():
            version_folder_name = os.path.basename(self.profile_version_entry.text())
            profile_name = self.profile_name_entry.text()
            version_installed = os.path.isfile(
                os.path.join(
                    window.minecraft_directory,
                    "versions",
                    version_folder_name,
                    "installed.FVL",
                )
            )
            if profile_name and version_folder_name and version_installed:
                profile_path = os.path.join(
                    window.minecraft_directory,
                    "profiles",
                    profile_name,
                )
                os.makedirs(profile_path, exist_ok=True)
                with open(
                    os.path.join(profile_path, "profile_info.json"),
                    "w",
                    encoding="utf-8",
                ) as profile_info_file:
                    json.dump(
                        [
                            {"mc_version": version_folder_name},
                            [],
                        ],
                        profile_info_file,
                        indent=4,
                    )
                window.show_versions(
                    window,
                    window.show_old_alphas,
                    window.show_old_betas,
                    window.show_snapshots,
                    window.show_releases,
                )
                QtWidgets.QMessageBox.information(
                    self,
                    "Создание папки профиля",
                    f"Папка профиль успешно создана по пути {profile_path}",
                )
            elif not version_installed:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Ошибка создания профиля",
                    "Выбранная вами версия некорректно устанолена",
                )
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Ошибка создания профиля",
                    "Укажите название профиля и выберите папку версии",
                )

        self.create_own_profile_window = QtWidgets.QDialog(self)
        self.create_own_profile_window.setModal(True)
        self.create_own_profile_window.setWindowTitle("Создание папки профиля")
        self.create_own_profile_window.setFixedSize(300, 150)

        self.profile_name_entry = QtWidgets.QLineEdit(self.create_own_profile_window)
        self.profile_name_entry.setFixedWidth(240)
        self.profile_name_entry.setPlaceholderText("Название профиля")
        self.profile_name_entry.move(10, 20)

        self.random_profile_name_button = QtWidgets.QPushButton(
            self.create_own_profile_window
        )
        self.random_profile_name_button.setFixedWidth(30)
        self.random_profile_name_button.setText("🎲")
        self.random_profile_name_button.move(260, 20)
        self.random_profile_name_button.clicked.connect(
            lambda: self.profile_name_entry.setText(
                Faker().word(part_of_speech="adjective").capitalize()
                + Faker().word(part_of_speech="noun").capitalize()
            )
        )

        self.profile_version_entry = QtWidgets.QLineEdit(self.create_own_profile_window)
        self.profile_version_entry.setFixedWidth(240)
        self.profile_version_entry.setPlaceholderText("Путь к папке версии")
        self.profile_version_entry.move(10, 50)

        self.choose_version_folder_button = QtWidgets.QPushButton(
            self.create_own_profile_window
        )
        self.choose_version_folder_button.setFixedWidth(30)
        self.choose_version_folder_button.setText("📂")
        self.choose_version_folder_button.move(260, 50)
        self.choose_version_folder_button.clicked.connect(
            lambda: self.profile_version_entry.setText(
                QtWidgets.QFileDialog.getExistingDirectory(
                    self.create_own_profile_window,
                    "Выбор папки версии",
                    os.path.join(window.minecraft_directory, "versions"),
                ).replace("/", "\\")
            )
        )

        self.create_own_profile_button = QtWidgets.QPushButton(
            self.create_own_profile_window
        )
        self.create_own_profile_button.setFixedWidth(120)
        self.create_own_profile_button.move(90, 80)
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
            utils.gui_messenger.critical.emit(
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
        if self.check_java():
            self.save_config_on_close = True
            self._make_ui()
        else:
            self.save_config_on_close = False
            self.close()

    def closeEvent(self, event):
        self.optifine = self.optifine_checkbox.isChecked()
        self.mod_loader = self.loaders_combobox.currentText()
        self.raw_version = self.versions_combobox.currentText()
        self.nickname = self.nickname_entry.text()
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
        if __name__ == "__main__":
            self.optifine = self.optifine_checkbox.isChecked()
            self.mod_loader = self.loaders_combobox.currentText()
            self.raw_version = self.versions_combobox.currentText()
            self.nickname = self.nickname_entry.text()

            self.start_button.setEnabled(False)

            self.queue = multiprocessing.Queue()
            self.minecraft_download_process = multiprocessing.Process(
                target=utils.run_in_process_with_exceptions_logging,
                args=(
                    utils.launch,
                    self.minecraft_directory,
                    self.mod_loader,
                    self.raw_version,
                    self.optifine,
                    self.show_console,
                    self.nickname,
                    self.ely_uuid,
                    self.access_token,
                    self.java_arguments,
                    self.no_internet_connection,
                ),
                kwargs={"queue": self.queue, "is_game_launch_process": True},
                daemon=True,
            )
            self.minecraft_download_process.start()
            self.timer = QTimer()
            self.timer.timeout.connect(self._update_ui_from_queue)
            self.timer.start(200)

    def auto_login(self):
        if not self.no_internet_connection:
            if self.saved_ely_uuid and self.saved_access_token:
                with requests.post(
                    "https://authserver.ely.by/auth/validate",
                    json={"accessToken": self.saved_access_token},
                ) as r:
                    valid_token_info = r
                if valid_token_info.status_code != 200:
                    with requests.post(
                        "https://authserver.ely.by/auth/refresh",
                        json={
                            "accessToken": self.saved_access_token,
                            "clientToken": self.client_token,
                            "requestUser": True,
                        },
                    ) as r:
                        refreshed_token_info = r
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
        else:
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
        self.setWindowIcon(utils.window_icon)

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
        ).replace("/", "\\")
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
        self.versions_combobox.setFixedHeight(30)
        self.versions_combobox.setEditable(True)

        self.nickname_entry = QtWidgets.QLineEdit(self)
        self.nickname_entry.move(20, 60)
        self.nickname_entry.setFixedWidth(260)
        self.nickname_entry.setPlaceholderText("Никнейм")
        self.nickname_entry.setText(self.nickname)

        self.optifine_checkbox = QtWidgets.QCheckBox(self)
        self.optifine_checkbox.setText("Optifine")
        self.optifine_checkbox.move(20, 100)
        self.optifine_checkbox.setFixedWidth(260)
        self.optifine_checkbox.setChecked(self.optifine)

        mod_loaders = ["fabric", "forge", "quilt", "neoforge", "vanilla"]
        self.loaders_combobox = QtWidgets.QComboBox(self)
        self.loaders_combobox.addItems(mod_loaders)
        self.loaders_combobox.move(160, 20)
        self.loaders_combobox.setFixedWidth(120)
        self.loaders_combobox.setCurrentText(self.mod_loader)
        self.block_optifine_checkbox()
        self.loaders_combobox.currentIndexChanged.connect(self.block_optifine_checkbox)
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
        self.settings_button.setText("Настройки")
        self.settings_button.clicked.connect(lambda: SettingsWindow(self))
        self.settings_button.move(5, 465)
        self.settings_button.setFixedWidth(80)

        self.account_button = QtWidgets.QPushButton(self)
        self.account_button.setText("Аккаунт")
        self.account_button.clicked.connect(lambda: AccountWindow(self))
        self.account_button.move(215, 465)
        self.account_button.setFixedWidth(80)

        self.show()

        try:
            requests.get("https://google.com").raise_for_status()
            self.no_internet_connection = False
        except requests.exceptions.ConnectionError:
            self.no_internet_connection = True

        self.client_token = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(uuid.getnode())))
        rpc = pypresence.Presence(utils.CLIENT_ID)
        if not self.no_internet_connection:
            try:
                rpc.connect()
            except:
                pass
        utils.start_rich_presence()

        self.access_token, self.ely_uuid = self.auto_login()

        if (
            getattr(sys, "frozen", False)
            and not self.no_internet_connection
            and updater.is_new_version_released(utils.LAUNCHER_VERSION)
        ):
            if (
                QtWidgets.QMessageBox.information(
                    self,
                    "Новое обновление!",
                    "Вышло новое обновление лаунчера.<br>"
                    "Нажмите ОК для обновления.<br>"
                    "После загрузки инсталлера, согласитесь на внесение изменений на устройстве.<br>"
                    'Нажимая "OK", вы соглашаетесь с текстами лицензий, расположенных по адресам:<br>'
                    '<a href="https://raw.githubusercontent.com/FerrumVega/FVLauncher/refs/heads/main/LICENSE">https://raw.githubusercontent.com/FerrumVega/FVLauncher/refs/heads/main/LICENSE</a><br>'
                    '<a href="https://raw.githubusercontent.com/FerrumVega/FVLauncher/refs/heads/main/THIRD_PARTY_LICENSES">https://raw.githubusercontent.com/FerrumVega/FVLauncher/refs/heads/main/THIRD_PARTY_LICENSES</a>',
                    QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel,
                )
                == QtWidgets.QMessageBox.Ok
            ):
                self.save_config_on_close = False
                self.close()
                multiprocessing.Process(
                    target=updater.update,
                    daemon=False,
                ).start()
                sys.exit()


if __name__ == "__main__":
    multiprocessing.freeze_support()
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
    sys.exit(utils.app.exec())
