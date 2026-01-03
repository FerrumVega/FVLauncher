import minecraft_launcher_lib
from PySide6 import QtWidgets, QtGui, QtWebEngineWidgets, QtWebEngineCore
from PySide6.QtCore import Signal, Qt, QTimer, QUrl, QUrlQuery
import os
import sys
import requests
import configparser
import json
from pypresence.presence import Presence
import pypresence.exceptions
import logging
import multiprocessing
from faker import Faker
from typing import Dict, Union, Any, Optional
import traceback
from minecraft_launcher_lib.exceptions import AccountNotOwnMinecraft
import time
import shutil
import hashlib

import utils
import updater

logging.basicConfig(
    level=logging.DEBUG,
    filename="FVLauncher.log",
    filemode="a",
    format="%(asctime)s %(levelname)s %(message)s",
)


def log_exception(exception_info: str):
    logging.critical(f"There was an error:\n{exception_info}")
    QtWidgets.QMessageBox.critical(
        utils.app.activeWindow(),
        "Ошибка",
        f"Произошла непредвиденная ошибка:\n{exception_info}",
    )


sys.excepthook = lambda exception_type, exception, exception_traceback: log_exception(
    "".join(traceback.format_exception(exception_type, exception, exception_traceback))
)


def load_config():
    default_config = {
        "Account": {
            "access_token": "",
            "token_expires_at": "0",
            "game_uuid": "",
            "refresh_token": "",
            "launch_account_type": "Ely.by",
        },
        "Preset": {
            "version": "1.21.10",
            "mod_loader": "fabric",
            "nickname": "Player",
            "optifine": "0",
        },
        "Settings": {
            "java_arguments": "-XX:+UseZGC -XX:+ZGenerational",
            "show_console": "0",
            "show_old_alphas": "0",
            "show_old_betas": "0",
            "show_snapshots": "0",
            "show_releases": "1",
            "show_other_versions": "1",
            "show_instances_and_packs": "1",
            "minecraft_directory": "",
        },
        "Experiments": {
            "allow_experiments": "0",
            "hover_color": "",
        },
    }

    config_path = "FVLauncher.ini"
    parser = configparser.ConfigParser()
    if not os.path.isfile(config_path):
        for section, config_part in default_config.items():
            parser.add_section(section)
            parser[section] = config_part
        with open(config_path, "w", encoding="utf-8") as config_file:
            parser.write(config_file)
    else:
        updated = False
        parser.read(config_path, encoding="utf-8")
        for section, config_part in default_config.items():
            if not parser.has_section(section):
                parser.add_section(section)
            for key, value in config_part.items():
                if key not in parser[section]:
                    parser[section][key] = value
                    updated = True
        if updated:
            with open(config_path, "w", encoding="utf-8") as config_file:
                parser.write(config_file)

    return {section: dict(parser[section]) for section in parser.sections()}


def update_ui_from_queue(self):
    while not self.queue.empty():
        var, value, *other_info = self.queue.get_nowait()
        match var:
            case "show_versions":
                main_window.show_versions(
                    main_window,
                    main_window.show_old_alphas,
                    main_window.show_old_betas,
                    main_window.show_snapshots,
                    main_window.show_releases,
                    main_window.show_other_versions,
                    main_window.show_instances_and_packs,
                    main_window.versions_combobox.currentText(),
                )
            case "status":
                self.download_info_label.setText(value)
            case "progressbar":
                self.progressbar.setValue(value)
            case "log_exception":
                log_exception(*other_info)
                try:
                    self._after_stop_download_process()
                except AttributeError:
                    pass
            case "show_message":
                match value:
                    case "critical":
                        QtWidgets.QMessageBox.critical(
                            self, other_info[1], other_info[2]
                        )
                    case "warning":
                        QtWidgets.QMessageBox.warning(
                            self, other_info[1], other_info[2]
                        )
                    case "information":
                        match other_info:
                            case [title, message, project_file_path]:  # noqa: F841
                                InstancesWindow._handle_open_mrpack_choosing_window(
                                    self, project_file_path
                                )
                            case _:
                                QtWidgets.QMessageBox.information(
                                    self, other_info[0], other_info[1]
                                )
                    case "log":
                        if (
                            QtWidgets.QMessageBox.critical(
                                self,
                                other_info[0],
                                other_info[1],
                                QtWidgets.QMessageBox.StandardButton.Yes
                                | QtWidgets.QMessageBox.StandardButton.No,
                            )
                            == QtWidgets.QMessageBox.StandardButton.Yes
                        ):
                            self.ShowLogWindow(self, other_info[2])
            case "start_button":
                if value:
                    self._after_stop_download_process()
                else:
                    self.start_button_type = "Stop"
                    self.start_button.setText("Отмена")
            case "start_rich_presence":
                match value:
                    case "minecraft_opened":
                        utils.start_rich_presence(self.rpc, *other_info)
                    case "minecraft_closed":
                        utils.start_rich_presence(self.rpc)
            case "projects":
                self.projects = value
                self._make_ui()


class ClickableLabel(QtWidgets.QLabel):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        if main_window.allow_experiments and main_window.hover_color:
            self.setStyleSheet(f"QLabel::hover {{color: {main_window.hover_color}}}")
        else:
            self.setStyleSheet("QLabel::hover {color: #03D3FC}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Кликните для просмотра")

    clicked = Signal()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        super().mouseReleaseEvent(e)
        self.clicked.emit()


class ProjectsSearch(QtWidgets.QDialog):
    class ProjectInfoWindow(QtWidgets.QDialog):
        class ProjectLoadersChooseWindow(QtWidgets.QDialog):
            class ProjectInstallWindow(QtWidgets.QDialog):
                def __init__(
                    self,
                    parent: QtWidgets.QWidget,
                    project: Dict[Any, Any],
                    mc_version: str,
                    loader: str,
                    minecraft_directory: str,
                    loaders_and_files: Dict[str, Dict],
                ):
                    super().__init__(parent)
                    self.project = project
                    self.mc_version = mc_version
                    self.loader = loader
                    self.minecraft_directory = minecraft_directory
                    self.loaders_and_files = loaders_and_files
                    self._make_ui()

                def reject(self):
                    self.close()
                    return super().reject()

                def closeEvent(self, event: QtGui.QCloseEvent):
                    if hasattr(self, "download_project_file_process"):
                        self.download_project_file_process.terminate()
                    return super().closeEvent(event)

                def download_project_process(
                    self,
                    project_file: Dict[Any, Any],
                    project: Dict[Any, Any],
                    instance: Optional[str],
                    mc_version: str,
                    loader: str,
                ):
                    if instance:
                        with open(
                            os.path.join(
                                self.minecraft_directory,
                                "instances",
                                instance,
                                "instance_info.json",
                            ),
                            encoding="utf-8",
                        ) as instance_info_file:
                            instance_info = json.load(instance_info_file)
                        with open(
                            os.path.join(
                                self.minecraft_directory,
                                "versions",
                                instance_info["mc_version"],
                                f"{instance_info['mc_version']}.json",
                            ),
                            encoding="utf-8",
                        ) as mc_version_file:
                            try:
                                inherits_from = json.load(mc_version_file).get(
                                    "inheritsFrom", instance_info["mc_version"]
                                )
                                if inherits_from != mc_version:
                                    if (
                                        QtWidgets.QMessageBox.warning(
                                            self,
                                            "Предупреждение",
                                            f"Версия игры экземпляра не совпадает с версией игры проекта, который вы выбрали\nВерсия игры проекта: {mc_version}\nВерсия игры сборки: {inherits_from}.\nВы уверены, что хотите установить проект на этот экземпляр?",
                                            QtWidgets.QMessageBox.StandardButton.Yes
                                            | QtWidgets.QMessageBox.StandardButton.No,
                                        )
                                        != QtWidgets.QMessageBox.StandardButton.Yes
                                    ):
                                        return
                            except KeyError:
                                if project["project_type"] == "mod" and (
                                    QtWidgets.QMessageBox.warning(
                                        self,
                                        "Предупреждение",
                                        "Вероятнее всего, вы пытаетесь установить мод на ванильный экземпляр. Вы уверены, что хотите установить мод на этот экземпляр?",
                                        QtWidgets.QMessageBox.StandardButton.Yes
                                        | QtWidgets.QMessageBox.StandardButton.No,
                                    )
                                    != QtWidgets.QMessageBox.StandardButton.Yes
                                ):
                                    return
                            if (
                                project["project_type"] == "mod"
                                and loader != "datapack"
                                and loader not in instance_info["mc_version"]
                                and (
                                    QtWidgets.QMessageBox.warning(
                                        self,
                                        "Предупреждение",
                                        f"Вероятнее всего, вы пытаетесь установить мод на неподходящий загрузчик модов.\nНазвание папки версии: {instance_info['mc_version']}\nВыбранный загрузчик модов: {loader}.\nВы уверены, что хотите установить мод на этот экземпляр?",
                                        QtWidgets.QMessageBox.StandardButton.Yes
                                        | QtWidgets.QMessageBox.StandardButton.No,
                                    )
                                    != QtWidgets.QMessageBox.StandardButton.Yes
                                )
                            ):
                                return

                    type_to_dir = {
                        "mod": "mods",
                        "resourcepack": "resourcepacks",
                        "shader": "shaderpacks",
                        "datapack": "datapacks",
                        "modpack": None,
                    }
                    if instance:
                        project_file_path = os.path.join(
                            self.minecraft_directory,
                            "instances",
                            instance,
                            (
                                type_to_dir[project["project_type"]]
                                if loader != "datapack"
                                else type_to_dir["datapack"]
                            ),
                            project_file["filename"],
                        )
                    elif project["project_type"] != "modpack":
                        project_file_path = os.path.join(
                            self.minecraft_directory,
                            (
                                type_to_dir[project["project_type"]]
                                if loader != "datapack"
                                else type_to_dir["datapack"]
                            ),
                            project_file["filename"],
                        )
                    else:
                        project_file_path = os.path.join(
                            self.minecraft_directory, project_file["filename"]
                        )
                    if project["project_type"] != "modpack":
                        os.makedirs(os.path.dirname(project_file_path), exist_ok=True)

                    self.queue = multiprocessing.Queue()
                    self.download_project_file_process = multiprocessing.Process(
                        target=utils.run_in_process_with_exceptions_logging,
                        args=(
                            utils.only_project_install,
                            project_file,
                            project,
                            project_file_path,
                        ),
                        kwargs={"queue": self.queue},
                        daemon=True,
                    )
                    self.download_project_file_process.start()
                    self.timer = QTimer()
                    self.timer.timeout.connect(lambda: update_ui_from_queue(self))
                    self.timer.start(200)

                def _make_ui(self):
                    instances = []
                    for instance in os.listdir(
                        os.path.join(self.minecraft_directory, "instances")
                    ):
                        if os.path.isfile(
                            os.path.join(
                                self.minecraft_directory,
                                "instances",
                                instance,
                                "instance_info.json",
                            )
                        ):
                            instances.append(instance)
                    self.setModal(True)
                    self.setWindowTitle("Выбор экземпляра для загрузки проекта")
                    self.setFixedSize(300, 500)

                    self.progressbar = QtWidgets.QProgressBar(self, textVisible=False)
                    self.progressbar.setFixedWidth(260)
                    self.progressbar.move(20, 430)

                    self.download_info_label = QtWidgets.QLabel(self)
                    self.download_info_label.setFixedWidth(290)
                    self.download_info_label.move(5, 450)
                    self.download_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

                    self.instances_container = QtWidgets.QWidget()
                    self.instances_layout = QtWidgets.QVBoxLayout(
                        self.instances_container
                    )

                    self.scroll_area = QtWidgets.QScrollArea(self)
                    self.scroll_area.setFixedSize(300, 200)
                    self.scroll_area.setWidget(self.instances_container)
                    self.scroll_area.setWidgetResizable(True)

                    for instance in instances:
                        download_button = ClickableLabel(self)
                        download_button.setText(instance)
                        download_button.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        download_button.clicked.connect(
                            lambda *args,
                            cur_instance=instance: self.download_project_process(
                                self.loaders_and_files[self.loader],
                                self.project,
                                cur_instance,
                                self.mc_version,
                                self.loader,
                            )
                        )
                        self.instances_layout.addWidget(download_button)
                    download_button = ClickableLabel(self)
                    download_button.setText("В корень (без сборки)")
                    download_button.clicked.connect(
                        lambda *args, cur_instance="": self.download_project_process(
                            self.loaders_and_files[self.loader],
                            self.project,
                            cur_instance,
                            self.mc_version,
                            self.loader,
                        )
                    )
                    download_button.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.instances_layout.addWidget(download_button)

                    self.show()

            def __init__(
                self,
                parent: QtWidgets.QWidget,
                project: Dict[Any, Any],
                mc_version: str,
                minecraft_directory: str,
            ):
                super().__init__(parent)
                self.project = project
                self.mc_version = mc_version
                self.minecraft_directory = minecraft_directory
                self._make_ui()

            def closeEvent(self, event: QtGui.QCloseEvent):
                if hasattr(self, "import_mrpack_process"):
                    self.import_mrpack_process.terminate()
                if hasattr(self, "download_project_file_process"):
                    self.download_project_file_process.terminate()
                return super().closeEvent(event)

            def _make_ui(self):
                self.setModal(True)
                self.setWindowTitle(f"Загрузка {self.project['title']}")
                self.setFixedSize(300, 500)

                with requests.get(
                    f"https://api.modrinth.com/v2/project/{self.project['project_id']}/version",
                    params={"game_versions": json.dumps([self.mc_version])},
                    timeout=10,
                ) as r:
                    r.raise_for_status()
                    self.project_versions_info = json.loads(r.text)
                self.loaders_and_files = {}
                for project_version in self.project_versions_info:
                    for loader in project_version["loaders"]:
                        if loader not in self.loaders_and_files:
                            for file in project_version["files"]:
                                if file["primary"]:
                                    self.loaders_and_files[loader] = file
                                    break
                            else:
                                self.loaders_and_files[loader] = project_version[
                                    "files"
                                ][0]

                self.loaders_container = QtWidgets.QWidget()
                self.loaders_layout = QtWidgets.QVBoxLayout(self.loaders_container)

                self.scroll_area = QtWidgets.QScrollArea(self)
                self.scroll_area.setFixedSize(300, 200)
                self.scroll_area.setWidget(self.loaders_container)
                self.scroll_area.setWidgetResizable(True)

                if self.project["project_type"] == "modpack":
                    self.progressbar = QtWidgets.QProgressBar(self, textVisible=False)
                    self.progressbar.setFixedWidth(260)
                    self.progressbar.move(20, 430)

                    self.download_info_label = QtWidgets.QLabel(self)
                    self.download_info_label.setFixedWidth(290)
                    self.download_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.download_info_label.move(5, 450)

                for loader in self.loaders_and_files:
                    download_button = ClickableLabel(self)
                    download_button.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    download_button.setText(loader)

                    if self.project["project_type"] == "modpack":
                        download_button.clicked.connect(
                            lambda *args,
                            current_loader=loader: self.ProjectInstallWindow.download_project_process(
                                self,
                                self.loaders_and_files[current_loader],
                                self.project,
                                None,
                                self.mc_version,
                                current_loader,
                            )
                        )
                    else:
                        download_button.clicked.connect(
                            lambda *args,
                            current_loader=loader: self.ProjectInstallWindow(
                                self,
                                self.project,
                                self.mc_version,
                                current_loader,
                                self.minecraft_directory,
                                self.loaders_and_files,
                            )
                        )
                    self.loaders_layout.addWidget(download_button)

                self.show()

        def __init__(
            self, parent: QtWidgets.QWidget, project: Dict, minecraft_directory: str
        ):
            super().__init__(parent)
            self.minecraft_directory = minecraft_directory
            self.project = project
            self.type_to_russian_name = {
                "mod": "мод",
                "resourcepack": "ресурспак",
                "modpack": "сборка",
                "shader": "шейдер",
            }
            self._make_ui()

        def _make_ui(self):
            self.setModal(True)
            self.setWindowTitle(self.project["title"])
            self.setFixedSize(300, 500)

            self.project_title = QtWidgets.QLabel(self)
            self.project_title.move(20, 20)
            self.downloads = f"{self.project['downloads']:_}".replace("_", " ")
            self.project_title.setText(
                f"{self.project['title']} ({self.type_to_russian_name.get(self.project['project_type'], 'проект').capitalize()} с {self.downloads} скачиваниями)"
            )
            self.project_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.project_title.setFixedWidth(260)

            self.icon = QtGui.QPixmap()
            self.icon_url = self.project["icon_url"]
            if self.icon_url:
                with requests.get(self.icon_url, timeout=10) as r:
                    r.raise_for_status()
                    self.icon.loadFromData(r.content)
                self.project_icon = QtWidgets.QLabel(self)
                self.icon = self.icon.scaled(100, 100)
                self.project_icon.setPixmap(self.icon)
                self.project_icon.move(100, 40)

            self.project_description = QtWidgets.QLabel(self)
            self.project_description.move(20, 140)
            self.project_description.setText(
                self.project["description"][:130]
                + ("..." if len(self.project["description"]) > 130 else "")
            )
            self.project_description.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.project_description.setFixedWidth(260)
            self.project_description.setWordWrap(True)

            self.versions_container = QtWidgets.QWidget()
            self.versions_layout = QtWidgets.QVBoxLayout(self.versions_container)

            self.scroll_area = QtWidgets.QScrollArea(self)
            self.scroll_area.move(0, 200)
            self.scroll_area.setFixedSize(300, 300)
            self.scroll_area.setWidget(self.versions_container)
            self.scroll_area.setWidgetResizable(True)

            mc_versions = self.project["versions"]
            for mc_version in mc_versions[::-1]:
                w = ClickableLabel(text=mc_version)
                w.clicked.connect(
                    lambda current_mc_version=mc_version: self.ProjectLoadersChooseWindow(
                        self, self.project, current_mc_version, self.minecraft_directory
                    )
                )
                self.versions_layout.addWidget(w)

            self.show()

    def reject(self):
        self.close()
        return super().reject()

    def closeEvent(self, event: QtGui.QCloseEvent):
        for filename in os.listdir(self.minecraft_directory):
            if filename.endswith(".mrpack"):
                os.remove(os.path.join(self.minecraft_directory, filename))
        return super().closeEvent(event)

    def __init__(self, parent: QtWidgets.QWidget, minecraft_directory: str):
        super().__init__(parent)
        self.minecraft_directory = minecraft_directory
        self._make_ui()

    def search(self, query: str):
        while self.p_layout.count():
            widget = self.p_layout.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        with requests.get(
            "https://api.modrinth.com/v2/search", params={"query": query}, timeout=10
        ) as r:
            r.raise_for_status()
            info = json.loads(r.text)
        for project in info["hits"]:
            w = ClickableLabel(text=project["title"])
            w.clicked.connect(
                lambda current_project=project: self.ProjectInfoWindow(
                    self, current_project, self.minecraft_directory
                )
            )
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
    def __init__(self):
        super().__init__(main_window)
        self._make_ui()

    def set_game_directory(self, directory: str):
        if directory:
            main_window.minecraft_directory = directory.replace("/", "\\")
            self.current_minecraft_directory.setText(
                f"Текущая папка с игрой:\n{main_window.minecraft_directory}"
            )

    def closeEvent(self, event: QtGui.QCloseEvent):
        os.makedirs(
            os.path.join(main_window.minecraft_directory, "instances"), exist_ok=True
        )
        main_window.java_arguments = self.java_arguments_entry.text()
        main_window.show_console = self.show_console_checkbox.isChecked()
        main_window.show_old_alphas = self.old_alphas_checkbox.isChecked()
        main_window.show_old_betas = self.old_betas_checkbox.isChecked()
        main_window.show_snapshots = self.snapshots_checkbox.isChecked()
        main_window.show_releases = self.releases_checkbox.isChecked()
        main_window.show_other_versions = self.other_versions_checkbox.isChecked()
        main_window.show_instances_and_packs = (
            self.instances_and_packs_checkbox.isChecked()
        )
        return super().closeEvent(event)

    def reject(self):
        self.close()
        return super().reject()

    def _make_ui(self):
        self.setWindowTitle("Настройки")
        self.setFixedSize(300, 500)
        self.setModal(True)

        self.java_arguments_label = QtWidgets.QLabel(self, text="java-аргументы")
        self.java_arguments_label.move(25, 25)
        self.java_arguments_label.setFixedWidth(250)
        self.java_arguments_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.java_arguments_entry = QtWidgets.QLineEdit(self)
        self.java_arguments_entry.setText(main_window.java_arguments)
        self.java_arguments_entry.move(25, 45)
        self.java_arguments_entry.setFixedWidth(250)

        self.show_console_checkbox = QtWidgets.QCheckBox(self)
        self.show_console_checkbox.setChecked(bool(main_window.show_console))
        self.show_console_checkbox.setText("Запуск с консолью")
        checkbox_width = self.show_console_checkbox.sizeHint().width()
        self.main_window_width = self.width()
        self.show_console_checkbox.move(
            (self.main_window_width - checkbox_width) // 2, 85
        )

        self.versions_filter_label = QtWidgets.QLabel(self, text="Фильтр версий")
        self.versions_filter_label.move(25, 125)
        self.versions_filter_label.setFixedWidth(250)
        self.versions_filter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.old_alphas_checkbox = QtWidgets.QCheckBox(self)
        self.old_alphas_checkbox.setChecked(bool(main_window.show_old_alphas))
        self.old_alphas_checkbox.setText("Старые альфы")
        self.checkbox_width = self.old_alphas_checkbox.sizeHint().width()
        self.old_alphas_checkbox.move(
            (self.main_window_width - self.checkbox_width) // 2, 145
        )

        self.old_betas_checkbox = QtWidgets.QCheckBox(self)
        self.old_betas_checkbox.setChecked(bool(main_window.show_old_betas))
        self.old_betas_checkbox.setText("Старые беты")
        self.checkbox_width = self.old_betas_checkbox.sizeHint().width()
        self.old_betas_checkbox.move(
            (self.main_window_width - self.checkbox_width) // 2, 165
        )

        self.snapshots_checkbox = QtWidgets.QCheckBox(self)
        self.snapshots_checkbox.setChecked(bool(main_window.show_snapshots))
        self.snapshots_checkbox.setText("Снапшоты")
        self.checkbox_width = self.snapshots_checkbox.sizeHint().width()
        self.snapshots_checkbox.move(
            (self.main_window_width - self.checkbox_width) // 2, 185
        )

        self.releases_checkbox = QtWidgets.QCheckBox(self)
        self.releases_checkbox.setChecked(bool(main_window.show_releases))
        self.releases_checkbox.setText("Релизы")
        self.checkbox_width = self.releases_checkbox.sizeHint().width()
        self.releases_checkbox.move(
            (self.main_window_width - self.checkbox_width) // 2, 205
        )

        self.other_versions_checkbox = QtWidgets.QCheckBox(self)
        self.other_versions_checkbox.setChecked(bool(main_window.show_other_versions))
        self.other_versions_checkbox.setText("Прочие версии")
        self.checkbox_width = self.other_versions_checkbox.sizeHint().width()
        self.other_versions_checkbox.move(
            (self.main_window_width - self.checkbox_width) // 2, 225
        )

        self.instances_and_packs_checkbox = QtWidgets.QCheckBox(self)
        self.instances_and_packs_checkbox.setChecked(
            bool(main_window.show_instances_and_packs)
        )
        self.instances_and_packs_checkbox.setText("Экземпляры и сборки")
        self.checkbox_width = self.instances_and_packs_checkbox.sizeHint().width()
        self.instances_and_packs_checkbox.move(
            (self.main_window_width - self.checkbox_width) // 2, 245
        )

        for widget in (
            self.old_alphas_checkbox,
            self.old_betas_checkbox,
            self.snapshots_checkbox,
            self.releases_checkbox,
            self.other_versions_checkbox,
            self.instances_and_packs_checkbox,
        ):
            widget.stateChanged.connect(
                lambda: main_window.show_versions(
                    main_window,
                    self.old_alphas_checkbox.isChecked(),
                    self.old_betas_checkbox.isChecked(),
                    self.snapshots_checkbox.isChecked(),
                    self.releases_checkbox.isChecked(),
                    self.other_versions_checkbox.isChecked(),
                    self.instances_and_packs_checkbox.isChecked(),
                    main_window.versions_combobox.currentText(),
                )
            )

        self.minecraft_directory_button = QtWidgets.QPushButton(self)
        self.minecraft_directory_button.move(25, 285)
        self.minecraft_directory_button.setFixedWidth(250)
        self.minecraft_directory_button.clicked.connect(
            lambda: self.set_game_directory(
                QtWidgets.QFileDialog.getExistingDirectory(
                    self, "Выбор папки для файлов игры"
                )
            )
        )
        self.minecraft_directory_button.setText("Выбор папки для файлов игры")

        self.current_minecraft_directory = QtWidgets.QLabel(self)
        self.current_minecraft_directory.move(25, 315)
        self.current_minecraft_directory.setFixedWidth(250)
        self.current_minecraft_directory.setText(
            f"Текущая папка с игрой:\n{main_window.minecraft_directory}"
        )
        self.current_minecraft_directory.setWordWrap(True)
        self.current_minecraft_directory.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.launcher_version_label = QtWidgets.QLabel(self)
        self.launcher_version_label.setText(
            f"Версия лаунчера: {utils.Constants.LAUNCHER_VERSION}"
        )
        self.launcher_version_label.move(25, 450)
        self.launcher_version_label.setFixedWidth(250)
        self.launcher_version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.show()


class AccountWindow(QtWidgets.QDialog):
    class SkinChanger(QtWidgets.QDialog):
        def __init__(self, parent: QtWidgets.QWidget, launch_account_type: str):
            super().__init__(parent)
            self.launch_account_type = launch_account_type
            self._make_ui()

        def _make_ui(self):
            self.resize(1280, 720)

            self.view = QtWebEngineWidgets.QWebEngineView()
            self.view.setPage(
                QtWebEngineCore.QWebEnginePage(browser_instance, self.view)
            )
            if self.launch_account_type == "Ely.by":
                self.view.setUrl("https://ely.by/skins")
            elif self.launch_account_type == "Microsoft":
                self.view.setUrl(
                    "https://www.minecraft.net/ru-ru/msainstance/mygames/editskin"
                )

            self.view_layout = QtWidgets.QVBoxLayout(self)

            self.view_layout.addWidget(self.view)
            self.setWindowTitle("Изменение скина")

            self.show()

    class LoginWindow(QtWidgets.QDialog):
        def __init__(
            self,
            parent: QtWidgets.QWidget,
            sign_status_label: QtWidgets.QLabel,
            account_type: str,
        ):
            if main_window.auth_info[0]:
                QtWidgets.QMessageBox.critical(
                    parent, "Ошибка входа", "Сначала выйдите из аккаунта"
                )
                return
            super().__init__(parent)
            self.sign_status_label = sign_status_label
            self._make_ui(account_type)

        def _handle_url_change(self, url: QUrl, account_type: str):
            successful_login = False
            url: str = url.toString()
            if minecraft_launcher_lib.microsoft_account.url_contains_auth_code(url):
                auth_code = (
                    minecraft_launcher_lib.microsoft_account.parse_auth_code_url(
                        url, None
                    )
                )
                if account_type == "Microsoft":
                    try:
                        login_info = (
                            minecraft_launcher_lib.microsoft_account.complete_login(
                                utils.Constants.MICROSOFT_CLIENT_ID,
                                None,
                                utils.Constants.REDIRECT_URI,
                                auth_code,
                            )
                        )
                        launch_account_type = "Microsoft"
                        access_token = login_info["access_token"]
                        token_expires_at = time.time() + 86400
                        game_uuid = login_info["id"]
                        nickname = login_info["name"]
                        refresh_token = login_info["refresh_token"]
                        successful_login = True
                    except AccountNotOwnMinecraft:
                        self.close()
                        QtWidgets.QMessageBox.critical(
                            self,
                            "Ошибка входа",
                            "Вероятнее всего, вы не владеете игрой. Использование этого аккаунта невозможно",
                        )
                        logging.debug(
                            "Failed login using Microsoft account (AccountNotOwnMinecraft exception)"
                        )
                elif account_type == "Ely.by":
                    with requests.get(
                        f"{utils.Constants.ELY_PROXY_URL}/code",
                        params={"code": auth_code},
                        timeout=20,
                        headers={"User-Agent": utils.Constants.USER_AGENT},
                    ) as r:
                        r.raise_for_status()
                        login_info = r.json()
                    launch_account_type = "Ely.by"
                    access_token = login_info["access_token"]
                    token_expires_at = time.time() + login_info["expires_in"]
                    refresh_token = login_info["refresh_token"]
                    with requests.get(
                        "https://account.ely.by/api/account/v1/info",
                        headers={"Authorization": f"Bearer {access_token}"},
                        timeout=10,
                    ) as r:
                        r.raise_for_status()
                        full_login_info = r.json()
                    game_uuid = full_login_info["uuid"]
                    nickname = full_login_info["username"]
                    successful_login = True
                if successful_login:
                    logging.debug(f"Successful login using {account_type} account")
                    main_window.launch_account_type = launch_account_type
                    main_window.access_token = access_token
                    main_window.token_expires_at = token_expires_at
                    main_window.game_uuid = game_uuid
                    main_window.refresh_token = refresh_token
                    self.close()
                    main_window.nickname_entry.setText(nickname)
                    main_window.nickname_entry.setReadOnly(True)
                    QtWidgets.QMessageBox.information(
                        self, "Успешно!", "Вы успешно вошли в аккаунт"
                    )
                    main_window.auth_info = True, account_type
                    self.sign_status_label.setText(
                        utils.boolean_to_sign_status(main_window.auth_info)
                    )

        def _make_ui(self, account_type: str):
            self.resize(1280, 720)

            self.view = QtWebEngineWidgets.QWebEngineView()
            self.view.setPage(
                QtWebEngineCore.QWebEnginePage(browser_instance, self.view)
            )

            self.view.urlChanged.connect(
                lambda url: self._handle_url_change(url, account_type)
            )
            if account_type == "Microsoft":
                self.view.setUrl(
                    minecraft_launcher_lib.microsoft_account.get_login_url(
                        utils.Constants.MICROSOFT_CLIENT_ID,
                        utils.Constants.REDIRECT_URI,
                    )
                )
            elif account_type == "Ely.by":
                url = QUrl("https://account.ely.by/oauth2/v1")
                query = QUrlQuery()
                params = {
                    "client_id": utils.Constants.ELY_CLIENT_ID,
                    "redirect_uri": utils.Constants.REDIRECT_URI,
                    "response_type": "code",
                    "scope": "account_info offline_access minecraft_server_session",
                }
                for key, value in params.items():
                    query.addQueryItem(key, value)
                url.setQuery(query)
                self.view.setUrl(url)
            self.view_layout = QtWidgets.QVBoxLayout(self)

            self.view_layout.addWidget(self.view)
            self.setWindowTitle("Вход в аккаунт")

            self.show()

    def __init__(self):
        super().__init__(main_window)
        self._make_ui()

    def set_account_type(self, account_type: str):
        self.account_type = account_type

    def logout(self):
        main_window.game_uuid = ""
        main_window.access_token = ""
        main_window.token_expires_at = "0"
        main_window.nickname_entry.setReadOnly(False)
        main_window.refresh_token = ""
        main_window.auth_info = False, None
        self.sign_status_label.setText(
            utils.boolean_to_sign_status(main_window.auth_info)
        )
        browser_instance.clearHttpCache()
        browser_instance.cookieStore().deleteAllCookies()

    def _make_ui(self):
        self.setWindowTitle("Аккаунт")
        self.setFixedSize(300, 500)
        self.setModal(True)

        self.account_type_combobox = QtWidgets.QComboBox(self)
        self.account_type_combobox.addItems(["Microsoft", "Ely.by"])
        self.set_account_type(self.account_type_combobox.currentText())
        self.account_type_combobox.currentTextChanged.connect(self.set_account_type)
        self.account_type_combobox.setFixedWidth(200)
        self.account_type_combobox.move(50, 10)

        self.login_button = QtWidgets.QPushButton(self)
        self.login_button.setText("Войти в аккаунт")
        self.login_button.clicked.connect(
            lambda: self.LoginWindow(self, self.sign_status_label, self.account_type)
        )
        self.login_button.setFixedWidth(200)
        self.login_button.move(50, 40)

        self.logout_button = QtWidgets.QPushButton(self)
        self.logout_button.setText("Выйти из аккаунта")
        self.logout_button.clicked.connect(self.logout)
        self.logout_button.setFixedWidth(200)
        self.logout_button.move(50, 70)

        self.change_skin_button = QtWidgets.QPushButton(self)
        self.change_skin_button.setText("Изменить скин")
        self.change_skin_button.setFixedWidth(120)
        self.change_skin_button.move(90, 100)
        self.change_skin_button.clicked.connect(
            lambda: self.SkinChanger(self, main_window.launch_account_type)
        )

        self.sign_status_label = QtWidgets.QLabel(
            self, text=utils.boolean_to_sign_status(main_window.auth_info)
        )
        self.sign_status_label.setFixedWidth(280)
        self.sign_status_label.move(10, 130)
        self.sign_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.show()


class InstancesWindow(QtWidgets.QDialog):
    class CreateOwnInstance(QtWidgets.QDialog):
        def __init__(self, parent: QtWidgets.QWidget):
            super().__init__(parent)
            self._make_ui()

        def _make_ui(self):
            def create_folder():
                version_folder_name = os.path.basename(
                    self.instance_version_entry.text()
                )
                instance_name = self.instance_name_entry.text()
                version_installed = os.path.isfile(
                    os.path.join(
                        main_window.minecraft_directory,
                        "versions",
                        version_folder_name,
                        "installed.FVL",
                    )
                )
                if instance_name and version_folder_name and version_installed:
                    instance_path = os.path.join(
                        main_window.minecraft_directory,
                        "instances",
                        instance_name,
                    )
                    os.makedirs(instance_path, exist_ok=True)
                    with open(
                        os.path.join(instance_path, "instance_info.json"),
                        "w",
                        encoding="utf-8",
                    ) as instance_info_file:
                        json.dump(
                            {"mc_version": version_folder_name},
                            instance_info_file,
                            indent=4,
                        )
                    main_window.show_versions(
                        main_window,
                        main_window.show_old_alphas,
                        main_window.show_old_betas,
                        main_window.show_snapshots,
                        main_window.show_releases,
                        main_window.show_other_versions,
                        main_window.show_instances_and_packs,
                        main_window.versions_combobox.currentText(),
                    )
                    QtWidgets.QMessageBox.information(
                        self,
                        "Создание экземпляра",
                        f"Папка экземпляра успешно создана по пути {instance_path}",
                    )
                    logging.info(f"New instance created, path: {instance_path}")
                elif not version_installed:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Ошибка создания экземпляра",
                        "Выбранная вами версия некорректно устанолена",
                    )
                else:
                    QtWidgets.QMessageBox.critical(
                        self,
                        "Ошибка создания экземпляра",
                        "Укажите название экземпляра и выберите папку версии",
                    )

            self.setModal(True)
            self.setWindowTitle("Создание экземпляра")
            self.setFixedSize(300, 150)

            self.instance_name_entry = QtWidgets.QLineEdit(self)
            self.instance_name_entry.setFixedWidth(240)
            self.instance_name_entry.setPlaceholderText("Название экземпляра")
            self.instance_name_entry.move(10, 20)

            self.random_instance_name_button = QtWidgets.QPushButton(self)
            self.random_instance_name_button.setFixedWidth(30)
            self.random_instance_name_button.setText("🎲")
            self.random_instance_name_button.move(260, 20)
            self.random_instance_name_button.clicked.connect(
                lambda: self.instance_name_entry.setText(
                    faker.word(part_of_speech="adjective").capitalize()
                    + faker.word(part_of_speech="noun").capitalize()
                )
            )

            self.instance_version_entry = QtWidgets.QLineEdit(self)
            self.instance_version_entry.setFixedWidth(240)
            self.instance_version_entry.setPlaceholderText("Путь к папке версии")
            self.instance_version_entry.move(10, 50)

            self.choose_version_folder_button = QtWidgets.QPushButton(self)
            self.choose_version_folder_button.setFixedWidth(30)
            self.choose_version_folder_button.setText("📂")
            self.choose_version_folder_button.move(260, 50)
            self.choose_version_folder_button.clicked.connect(
                lambda: self.instance_version_entry.setText(
                    QtWidgets.QFileDialog.getExistingDirectory(
                        self,
                        "Выбор папки версии",
                        os.path.join(main_window.minecraft_directory, "versions"),
                    ).replace("/", "\\")
                )
            )

            self.create_own_instance_button = QtWidgets.QPushButton(self)
            self.create_own_instance_button.setFixedWidth(120)
            self.create_own_instance_button.move(90, 80)
            self.create_own_instance_button.setText("Создать экземпляр")
            self.create_own_instance_button.clicked.connect(create_folder)

            self.show()

    class ControlInstancesWindow(QtWidgets.QDialog):
        class InstanceProjectsWindow(QtWidgets.QDialog):
            class ProgressWindow(QtWidgets.QDialog):
                def __init__(self, parent):
                    super().__init__(parent)
                    self.parent_window = parent
                    self._make_ui()

                def _make_ui(self):
                    self.setModal(False)
                    self.setWindowTitle("Поиск проектов")
                    self.setFixedSize(300, 50)

                    self.progressbar = QtWidgets.QProgressBar(self, textVisible=False)
                    self.progressbar.setFixedWidth(280)
                    self.progressbar.move(10, 25)

                    self.download_info_label = QtWidgets.QLabel(self)
                    self.download_info_label.setFixedWidth(280)
                    self.download_info_label.move(10, 5)

                    self.show()

                def reject(self):
                    self.close()
                    return super().reject()

                def closeEvent(self, event: QtGui.QCloseEvent):
                    if hasattr(self.parent_window, "search_projects_process"):
                        self.parent_window.search_projects_process.terminate()
                    return super().closeEvent(event)

            def __init__(self, parent, instance_name: str):
                super().__init__(parent)
                self.instance_name = instance_name
                self.instance_path = os.path.join(
                    main_window.minecraft_directory, "instances", self.instance_name
                )
                self.projects_container = QtWidgets.QWidget()
                self.projects_layout = QtWidgets.QVBoxLayout(self.projects_container)

                self.scroll_area = QtWidgets.QScrollArea(self)
                self.scroll_area.setFixedSize(700, 500)
                self.scroll_area.setWidget(self.projects_container)
                self.scroll_area.setWidgetResizable(True)

                self.queue = multiprocessing.Queue()
                self.progress_window = self.ProgressWindow(self)
                self.progressbar = self.progress_window.progressbar
                self.download_info_label = self.progress_window.download_info_label
                self.search_projects_process = multiprocessing.Process(
                    target=utils.run_in_process_with_exceptions_logging,
                    args=(
                        utils.search_projects,
                        main_window.minecraft_directory,
                        self.instance_name,
                    ),
                    kwargs={"queue": self.queue},
                    daemon=True,
                )
                self.search_projects_process.start()
                self.timer = QTimer()
                self.timer.timeout.connect(lambda: update_ui_from_queue(self))
                self.timer.start(200)

            def delete_project(self, project_id: str):
                project_name = self.projects[project_id]["title"]
                project_type = self.projects[project_id]["project_type"]
                project_hash = self.projects[project_id]["hash"]
                try:
                    type_to_dir = {
                        "mod": "mods",
                        "resourcepack": "resourcepacks",
                        "shader": "shaderpacks",
                    }
                    if (
                        QtWidgets.QMessageBox.information(
                            self,
                            "Удаление экземпляра",
                            f"Вы уверены, что хотите удалить проект {project_name}?",
                            QtWidgets.QMessageBox.StandardButton.Yes
                            | QtWidgets.QMessageBox.StandardButton.No,
                        )
                        == QtWidgets.QMessageBox.StandardButton.Yes
                    ):
                        base_path = os.path.join(
                            self.instance_path,
                            type_to_dir[project_type],
                        )
                        for project_file_name in os.listdir(base_path):
                            full_project_path = os.path.join(
                                base_path,
                                project_file_name,
                            )
                            if (
                                hashlib.sha512(
                                    open(full_project_path, "rb").read()
                                ).hexdigest()
                                == project_hash
                            ):
                                os.remove(full_project_path)
                                QtWidgets.QMessageBox.information(
                                    self,
                                    "Успешно!",
                                    f"Прокет {project_name} был успешно удалён.",
                                )
                                self.projects[project_id]["container"].deleteLater()
                                del self.projects[project_id]
                                return
                        if project_type == "mod":
                            base_path = os.path.join(
                                self.instance_path,
                                "datapacks",
                            )
                            for project_file_name in os.listdir(base_path):
                                full_project_path = os.path.join(
                                    base_path, project_file_name
                                )
                                if (
                                    hashlib.sha512(
                                        open(full_project_path, "rb").read()
                                    ).hexdigest()
                                    == project_hash
                                ):
                                    os.remove(full_project_path)
                                    QtWidgets.QMessageBox.information(
                                        self,
                                        "Успешно!",
                                        f"Прокет {project_name} был успешно удалён.",
                                    )
                                    self.projects[project_id]["container"].deleteLater()
                                    del self.projects[project_id]
                                    return
                            QtWidgets.QMessageBox.critical(
                                self,
                                "Ошибка!",
                                f"Не удалось удалить проект {project_name}.",
                            )
                except FileNotFoundError:
                    pass

            def _make_ui(self):
                self.setModal(True)
                self.setWindowTitle("Управление экземплярами")
                self.setFixedSize(700, 500)
                self.projects_len = len(self.projects.items())

                for index, (project_id, project_info) in enumerate(
                    dict(
                        sorted(
                            self.projects.items(),
                            key=lambda project: project[1]["title"].capitalize(),
                        )
                    ).items(),
                    1,
                ):
                    project_name = project_info["title"]

                    container = QtWidgets.QWidget()
                    h_layout = QtWidgets.QHBoxLayout(container)
                    h_layout.setSpacing(5)

                    icon_bytes = project_info.get("icon_bytes")

                    if icon_bytes is not None:
                        icon = QtGui.QPixmap()
                        icon.loadFromData(icon_bytes)
                        icon = icon.scaled(50, 50)
                        project_icon = QtWidgets.QLabel(self)
                        project_icon.setPixmap(icon)
                        self.progressbar.setValue(index / self.projects_len * 100)

                    project_name_label = QtWidgets.QLabel(container, text=project_name)
                    delete_label = ClickableLabel(container, text="Удалить")
                    delete_label.clicked.connect(
                        lambda cur_project_id=project_id: self.delete_project(
                            cur_project_id
                        )
                    )

                    h_layout.addWidget(project_icon)
                    h_layout.addWidget(project_name_label)
                    h_layout.addStretch()
                    h_layout.addWidget(delete_label)
                    self.projects[project_id]["container"] = container

                    self.projects_layout.addWidget(container)

                self.projects_layout.addWidget(
                    ClickableLabel(self, text="Экспорт в .mrpack")
                )

                self.progressbar_window.close()
                self.show()

        def __init__(self, parent: QtWidgets.QWidget):
            super().__init__(parent)

            self.instances_container = QtWidgets.QWidget()
            self.instances_layout = QtWidgets.QVBoxLayout(self.instances_container)

            self.scroll_area = QtWidgets.QScrollArea(self)
            self.scroll_area.setFixedSize(700, 500)
            self.scroll_area.setWidget(self.instances_container)
            self.scroll_area.setWidgetResizable(True)

            self._make_ui()

        def change_instance_mc_version(self, instance_name: str):
            mc_version = os.path.basename(
                QtWidgets.QFileDialog.getExistingDirectory(
                    self,
                    "Выбор папки версии",
                    os.path.join(main_window.minecraft_directory, "versions"),
                ).replace("/", "\\")
            )
            if mc_version:
                with open(
                    os.path.join(
                        main_window.minecraft_directory,
                        "instances",
                        instance_name,
                        "instance_info.json",
                    ),
                    "w",
                    encoding="utf-8",
                ) as instance_info_file:
                    json.dump({"mc_version": mc_version}, instance_info_file)
                    QtWidgets.QMessageBox.information(
                        self,
                        "Успешно!",
                        f"Версия экземпляра успешно изменена на {mc_version}",
                    )
                    self._make_ui()

        def rename_instance(self, instance_name: str):
            new_name, ok = QtWidgets.QInputDialog.getText(
                self, "Переименование экземпляра", "Введите новое имя экземпляра"
            )
            if ok:
                base_path = os.path.join(main_window.minecraft_directory, "instances")
                os.rename(
                    os.path.join(base_path, instance_name),
                    os.path.join(base_path, new_name),
                )
                QtWidgets.QMessageBox.information(
                    self,
                    "Успешно!",
                    f"Экземпляр {instance_name} был успешно переименован в {new_name}.",
                )
                self._make_ui()

        def delete_instance(self, instance_name: str):
            if (
                QtWidgets.QMessageBox.information(
                    self,
                    "Удаление экземпляра",
                    f"Вы уверены, что хотите удалить экземпляр {instance_name}?",
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No,
                )
                == QtWidgets.QMessageBox.StandardButton.Yes
            ):
                shutil.rmtree(
                    os.path.join(
                        main_window.minecraft_directory, "instances", instance_name
                    )
                )
                QtWidgets.QMessageBox.information(
                    self, "Успешно!", f"Экземпляр {instance_name} был успешно удалён."
                )
                self._make_ui()

        def _make_ui(self):
            self.setModal(True)
            self.setWindowTitle("Управление экземплярами")
            self.setFixedSize(700, 500)

            while self.instances_layout.count():
                widget = self.instances_layout.takeAt(0).widget()
                if widget is not None:
                    widget.deleteLater()

            for instance_name in os.listdir(
                os.path.join(main_window.minecraft_directory, "instances")
            ):
                instance_info_path = os.path.join(
                    main_window.minecraft_directory,
                    "instances",
                    instance_name,
                    "instance_info.json",
                )
                if os.path.isfile(instance_info_path):
                    with open(
                        instance_info_path, encoding="utf-8"
                    ) as instance_info_json:
                        mc_version = json.load(instance_info_json)["mc_version"]
                    container = QtWidgets.QWidget()
                    h_layout = QtWidgets.QHBoxLayout(container)
                    h_layout.setSpacing(5)

                    main_label = QtWidgets.QLabel(
                        container, text=f"{instance_name} ({mc_version})"
                    )
                    rename_label = ClickableLabel(container, text="Переименовать")
                    rename_label.clicked.connect(
                        lambda cur_instance_name=instance_name: self.rename_instance(
                            cur_instance_name
                        )
                    )
                    change_version_label = ClickableLabel(
                        container, text="Изменить версию"
                    )
                    change_version_label.clicked.connect(
                        lambda cur_instance_name=instance_name,
                        cur_label=main_label: self.change_instance_mc_version(
                            cur_instance_name, cur_label
                        )
                    )
                    projects_label = ClickableLabel(
                        container, text="Управление проектами"
                    )
                    projects_label.clicked.connect(
                        lambda cur_instance_name=instance_name: self.InstanceProjectsWindow(
                            self, cur_instance_name
                        )
                    )
                    delete_label = ClickableLabel(container, text="Удалить")
                    delete_label.clicked.connect(
                        lambda cur_instance_name=instance_name: self.delete_instance(
                            cur_instance_name
                        )
                    )

                    h_layout.addWidget(main_label)
                    h_layout.addStretch()
                    h_layout.addWidget(change_version_label)
                    h_layout.addWidget(rename_label)
                    h_layout.addWidget(delete_label)
                    h_layout.addWidget(projects_label)

                    self.instances_layout.addWidget(container)

            self.show()

    def __init__(self, main_window: QtWidgets.QWidget):
        super().__init__(main_window)
        self._make_ui()

    def closeEvent(self, event: QtGui.QCloseEvent):
        if hasattr(self, "import_mrpack_process"):
            self.import_mrpack_process.terminate()
        return super().closeEvent(event)

    def reject(self):
        self.close()
        return super().reject()

    def _handle_open_mrpack_choosing_window(self, mrpack_path):
        if mrpack_path is None:
            mrpack_path = QtWidgets.QFileDialog.getOpenFileName(
                self, "Выберите файл сборки", "", "*.mrpack"
            )[0].replace("/", "\\")

        if mrpack_path:
            self.queue = multiprocessing.Queue()
            self.import_mrpack_process = multiprocessing.Process(
                target=utils.run_in_process_with_exceptions_logging,
                args=(
                    utils.download_instance_from_mrpack,
                    main_window.minecraft_directory,
                    mrpack_path,
                    main_window.no_internet_connection,
                ),
                kwargs={"queue": self.queue},
                daemon=True,
            )
            self.import_mrpack_process.start()
            self.timer = QTimer()
            self.timer.timeout.connect(lambda: update_ui_from_queue(self))
            self.timer.start(200)

    def _make_ui(self):
        self.setModal(True)
        self.setWindowTitle("Действия с экземплярами")
        self.setFixedSize(300, 500)

        self.choose_mrpack_file_button = QtWidgets.QPushButton(self)
        self.choose_mrpack_file_button.setFixedWidth(120)
        self.choose_mrpack_file_button.move(90, 90)
        self.choose_mrpack_file_button.setText("Импорт из .mrpack")
        self.choose_mrpack_file_button.clicked.connect(
            lambda: self._handle_open_mrpack_choosing_window(None)
        )

        self.progressbar = QtWidgets.QProgressBar(self, textVisible=False)
        self.progressbar.setFixedWidth(260)
        self.progressbar.move(20, 430)

        self.download_info_label = QtWidgets.QLabel(self)
        self.download_info_label.setFixedWidth(290)
        self.download_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.download_info_label.move(5, 450)

        self.create_instance_button = QtWidgets.QPushButton(self)
        self.create_instance_button.setFixedWidth(120)
        self.create_instance_button.move(90, 120)
        self.create_instance_button.setText("Создать экземпляр")
        self.create_instance_button.clicked.connect(
            lambda: self.CreateOwnInstance(self)
        )
        self.control_instances_button = QtWidgets.QPushButton(self)
        self.control_instances_button.setText("Управление экземплярами")
        self.control_instances_button.setFixedWidth(170)
        self.control_instances_button.move(65, 150)
        self.control_instances_button.clicked.connect(
            lambda: self.ControlInstancesWindow(self)
        )
        self.show()


class MainWindow(QtWidgets.QMainWindow):
    class ShowLogWindow(QtWidgets.QDialog):
        def __init__(self, parent: QtWidgets.QWidget, path: str):
            super().__init__(parent)
            self.path = path
            self._make_ui()

        def _make_ui(self):
            self.setWindowTitle("Просмотр лога")
            self.setFixedSize(700, 700)
            self.log_text = QtWidgets.QPlainTextEdit(self)
            self.log_text.setFixedSize(700, 700)
            self.log_text.setReadOnly(True)
            self.log_text.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
                | Qt.TextInteractionFlag.LinksAccessibleByMouse
            )
            with open(self.path, encoding="utf-8") as log_file:
                self.log_text.setPlainText(log_file.read())
            self.show()

    def check_java(self):
        self.java_path = minecraft_launcher_lib.utils.get_java_executable()
        if self.java_path == "java" or self.java_path == "javaw":
            QtWidgets.QMessageBox.critical(
                self,
                "Java не найдена",
                "На вашем компьютере отсутствует java, загрузите её с github лаунчера.",
            )
            logging.error("Error message showed while java checking: java not found")
            return False
        else:
            return True

    def __init__(
        self,
        chosen_version: str,
        chosen_mod_loader: str,
        chosen_nickname: str,
        chosen_java_arguments: str,
        optifine_position: str,
        saved_access_token: str,
        saved_token_expires_at: str,
        saved_game_uuid: str,
        saved_refresh_token: str,
        launch_account_type: str,
        show_console_position: str,
        show_old_alphas_position: str,
        show_old_betas_position: str,
        show_snapshots_position: str,
        show_releases_position: str,
        show_other_versions_position: str,
        show_instances_and_packs_position: str,
        saved_minecraft_directory: str,
        allow_experiments: str,
        hover_color: str,
    ):
        self.chosen_version = chosen_version
        self.chosen_mod_loader = chosen_mod_loader
        self.chosen_nickname = chosen_nickname
        self.chosen_java_arguments = chosen_java_arguments
        self.optifine_position = optifine_position
        self.saved_access_token = saved_access_token
        self.saved_token_expires_at = saved_token_expires_at
        self.saved_game_uuid = saved_game_uuid
        self.saved_refresh_token = saved_refresh_token
        self.launch_account_type = launch_account_type
        self.show_console_position = show_console_position
        self.show_old_alphas_position = show_old_alphas_position
        self.show_old_betas_position = show_old_betas_position
        self.show_snapshots_position = show_snapshots_position
        self.show_releases_position = show_releases_position
        self.show_other_versions_position = show_other_versions_position
        self.show_instances_and_packs_position = show_instances_and_packs_position
        self.saved_minecraft_directory = saved_minecraft_directory
        self.allow_experiments = allow_experiments
        self.hover_color = hover_color

        super().__init__()
        if self.check_java():
            logging.debug(f"Java path: {self.java_path}")
            self.save_config_on_close = True
            self._make_ui()
        else:
            self.save_config_on_close = False
            self.close()

    def closeEvent(self, event: QtGui.QCloseEvent):
        if self.save_config_on_close:
            self.optifine = self.optifine_checkbox.isChecked()
            self.mod_loader = self.loaders_combobox.currentText()
            self.raw_version = self.versions_combobox.currentText()
            self.nickname = self.nickname_entry.text()
            self.save_config()
        logging.debug("Launcher was closed")
        return super().closeEvent(event)

    def show_versions(
        self,
        main_window: QtWidgets.QWidget,
        show_old_alphas: Union[bool, int],
        show_old_betas: Union[bool, int],
        show_snapshots: Union[bool, int],
        show_releases: Union[bool, int],
        other_versions: Union[bool, int],
        instances_and_packs: Union[bool, int],
        current_version: str,
    ):
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
            if other_versions:
                for item in minecraft_launcher_lib.utils.get_installed_versions(
                    main_window.minecraft_directory
                ):
                    if all(
                        loader not in item["id"].lower() for loader in self.mod_loaders
                    ) and not minecraft_launcher_lib.utils.is_vanilla_version(
                        item["id"]
                    ):
                        versions_names_list.append(item["id"])
            if instances_and_packs:
                for item in os.listdir(
                    os.path.join(main_window.minecraft_directory, "instances")
                ):
                    if os.path.isfile(
                        os.path.join(
                            main_window.minecraft_directory,
                            "instances",
                            item,
                            "instance_info.json",
                        )
                    ):
                        versions_names_list.append(item)
            main_window.versions_combobox.clear()
            main_window.versions_combobox.addItems(versions_names_list)
            main_window.versions_combobox.setCurrentText(current_version)
        except requests.exceptions.ConnectionError:
            pass

    def save_config(self):
        config = {
            "Account": {
                "access_token": self.access_token,
                "token_expires_at": self.token_expires_at,
                "game_uuid": self.game_uuid,
                "refresh_token": self.refresh_token,
                "launch_account_type": self.launch_account_type,
            },
            "Preset": {
                "version": self.raw_version,
                "mod_loader": self.mod_loader,
                "nickname": self.nickname,
                "optifine": int(self.optifine),
            },
            "Settings": {
                "java_arguments": self.java_arguments,
                "show_console": int(self.show_console),
                "show_old_alphas": int(self.show_old_alphas),
                "show_old_betas": int(self.show_old_betas),
                "show_snapshots": int(self.show_snapshots),
                "show_releases": int(self.show_releases),
                "show_other_versions": int(self.show_other_versions),
                "show_instances_and_packs": int(self.show_instances_and_packs),
                "minecraft_directory": self.minecraft_directory,
            },
            "Experiments": {
                "allow_experiments": int(self.allow_experiments),
                "hover_color": self.hover_color,
            },
        }

        config_path = "FVLauncher.ini"
        parser = configparser.ConfigParser()
        for section, config_part in config.items():
            parser.add_section(section)
            parser[section] = config_part

        with open(config_path, "w", encoding="utf-8") as config_file:
            parser.write(config_file)

    def block_optifine_checkbox(self, *args: Any):
        if (
            os.path.isfile(
                os.path.join(
                    self.minecraft_directory,
                    "instances",
                    self.versions_combobox.currentText(),
                    "instance_info.json",
                )
            )
            and self.versions_combobox.currentText()
        ):
            with open(
                os.path.join(
                    self.minecraft_directory,
                    "instances",
                    self.versions_combobox.currentText(),
                    "instance_info.json",
                ),
                encoding="utf-8",
            ) as instance_info_file:
                mc_version = json.load(instance_info_file)["mc_version"]
                if "forge" in mc_version and "neoforge" not in mc_version:
                    self.optifine_checkbox.setDisabled(False)
                else:
                    self.optifine_checkbox.setDisabled(True)
        elif self.loaders_combobox.currentText() == "forge":
            self.optifine_checkbox.setDisabled(False)
        else:
            self.optifine_checkbox.setDisabled(True)

    def _after_stop_download_process(self):
        self.start_button_type = "Start"
        self.start_button.setText("Запуск")
        self.progressbar.setValue(0)
        self.download_info_label.setText("")

    def on_start_button(self):
        if self.start_button_type == "Start":
            self.optifine = self.optifine_checkbox.isChecked()
            self.mod_loader = self.loaders_combobox.currentText()
            self.raw_version = self.versions_combobox.currentText()
            self.nickname = self.nickname_entry.text()

            self.queue = multiprocessing.Queue()
            self.minecraft_download_process = multiprocessing.Process(
                target=utils.run_in_process_with_exceptions_logging,
                args=(
                    utils.launch,
                    self.minecraft_directory,
                    self.mod_loader,
                    self.raw_version,
                    self.optifine and self.optifine_checkbox.isEnabled(),
                    self.show_console,
                    self.nickname,
                    self.game_uuid,
                    self.access_token,
                    self.java_arguments,
                    self.launch_account_type,
                    self.no_internet_connection,
                ),
                kwargs={"queue": self.queue, "is_game_launch_process": True},
                daemon=True,
            )
            self.minecraft_download_process.start()
            self.timer = QTimer()
            self.timer.timeout.connect(lambda: update_ui_from_queue(self))
            self.timer.start(200)
            self.start_button_type = "Stop"
            self.start_button.setText("Отмена")
        else:
            self.minecraft_download_process.terminate()
            self._after_stop_download_process()

    def auto_login(self):
        if (
            not self.no_internet_connection
            and self.saved_game_uuid
            and self.saved_access_token
        ):
            if time.time() > self.token_expires_at:
                try:
                    if self.launch_account_type == "Microsoft":
                        try:
                            login_info = minecraft_launcher_lib.microsoft_account.complete_refresh(
                                utils.Constants.MICROSOFT_CLIENT_ID,
                                None,
                                utils.Constants.REDIRECT_URI,
                                self.saved_refresh_token,
                            )
                            self.auth_info = True, self.launch_account_type
                            self.nickname_entry.setReadOnly(True)
                            logging.debug(
                                "Successful login using Microsoft account (auto_login)"
                            )
                            return (
                                login_info["access_token"],
                                login_info["id"],
                                login_info["refresh_token"],
                                time.time() + 86400,
                            )
                        except (KeyError, AccountNotOwnMinecraft) as e:
                            self.auth_info = False, None
                            logging.debug(
                                f"Failed login using Microsoft account ({e} exception) (auto_login)"
                            )
                            return "", "", "", 0
                    elif self.launch_account_type == "Ely.by":
                        with requests.get(
                            f"{utils.Constants.ELY_PROXY_URL}/refresh",
                            params={"token": self.saved_refresh_token},
                            timeout=20,
                            headers={"User-Agent": utils.Constants.USER_AGENT},
                        ) as r:
                            r.raise_for_status()
                            login_info = r.json()
                        access_token = login_info["access_token"]
                        with requests.get(
                            "https://account.ely.by/api/account/v1/info",
                            headers={"Authorization": f"Bearer {access_token}"},
                            timeout=10,
                        ) as r:
                            r.raise_for_status()
                            full_login_info = r.json()
                        game_uuid = full_login_info["uuid"]
                        try:
                            self.auth_info = True, self.launch_account_type
                            self.nickname_entry.setReadOnly(True)
                            logging.debug(
                                "Successful login using Ely.by account (auto_login)"
                            )
                            return (
                                access_token,
                                game_uuid,
                                self.saved_refresh_token,
                                time.time() + float(login_info["expires_in"]),
                            )
                        except KeyError:
                            logging.debug(
                                "Failed login using Ely.by account (KeyError exception) (auto_login)"
                            )
                            self.auth_info = False, None
                            return "", "", "", 0
                except requests.RequestException as e:
                    self.auth_info = False, None
                    logging.debug(
                        f"Failed login using {self.launch_account_type} account ({e} exception) (auto_login)"
                    )
                    return (
                        self.saved_access_token,
                        self.saved_game_uuid,
                        self.saved_refresh_token,
                        self.token_expires_at,
                    )
            else:
                self.auth_info = True, self.launch_account_type
                self.nickname_entry.setReadOnly(True)
                logging.debug(
                    f"Token was not refreshed because it is still valid ({self.launch_account_type} account)"
                )
                return (
                    self.saved_access_token,
                    self.saved_game_uuid,
                    self.saved_refresh_token,
                    self.token_expires_at,
                )
        else:
            self.auth_info = False, None
            logging.debug(
                f"Failed login using {self.launch_account_type} account (No Internet connection or there is no any accounts to login) (auto_login)"
            )
            return (
                self.saved_access_token,
                self.saved_game_uuid,
                self.saved_refresh_token,
                self.token_expires_at,
            )

    def _make_ui(self):
        self.setWindowTitle("FVLauncher")
        self.setWindowIcon(utils.window_icon)
        self.setFixedSize(300, 500)

        self.is_authorized = None, None

        self.raw_version = self.chosen_version
        self.mod_loader = self.chosen_mod_loader
        self.optifine = int(self.optifine_position)
        self.nickname = self.chosen_nickname

        self.java_arguments = self.chosen_java_arguments
        self.show_console = int(self.show_console_position)

        self.token_expires_at = float(self.saved_token_expires_at)

        self.show_old_alphas = int(self.show_old_alphas_position)
        self.show_old_betas = int(self.show_old_betas_position)
        self.show_snapshots = int(self.show_snapshots_position)
        self.show_releases = int(self.show_releases_position)
        self.show_other_versions = int(self.show_other_versions_position)
        self.show_instances_and_packs = int(self.show_instances_and_packs_position)

        self.allow_experiments = int(self.allow_experiments)
        self.hover_color = self.hover_color

        self.start_button_type = "Start"

        self.mod_loaders = ["fabric", "forge", "quilt", "neoforge", "vanilla"]

        self.minecraft_directory = (
            self.saved_minecraft_directory
            if self.saved_minecraft_directory
            else minecraft_launcher_lib.utils.get_minecraft_directory()
        ).replace("/", "\\")
        os.makedirs(os.path.join(self.minecraft_directory, "instances"), exist_ok=True)

        self.versions_combobox = QtWidgets.QComboBox(self)
        self.versions_combobox.move(20, 20)
        self.versions_combobox.setFixedWidth(120)
        self.versions_combobox.setCurrentText(self.raw_version)
        self.show_versions(
            self,
            self.show_old_alphas,
            self.show_old_betas,
            self.show_snapshots,
            self.show_releases,
            self.show_other_versions,
            self.show_instances_and_packs,
            self.chosen_version,
        )
        self.versions_combobox.setFixedHeight(30)
        self.versions_combobox.setEditable(True)
        self.versions_combobox.currentTextChanged.connect(self.block_optifine_checkbox)

        self.nickname_entry = QtWidgets.QLineEdit(self)
        self.nickname_entry.move(20, 60)
        self.nickname_entry.setFixedWidth(260)
        self.nickname_entry.setPlaceholderText("Никнейм")
        self.nickname_entry.setText(self.nickname)

        self.optifine_checkbox = QtWidgets.QCheckBox(self)
        self.optifine_checkbox.setText("Optifine")
        self.optifine_checkbox.move(20, 100)
        self.optifine_checkbox.setFixedWidth(260)
        self.optifine_checkbox.setChecked(bool(self.optifine))

        self.loaders_combobox = QtWidgets.QComboBox(self)
        self.loaders_combobox.addItems(self.mod_loaders)
        self.loaders_combobox.move(160, 20)
        self.loaders_combobox.setFixedWidth(120)
        self.loaders_combobox.setCurrentText(self.mod_loader)
        self.loaders_combobox.currentTextChanged.connect(self.block_optifine_checkbox)
        self.loaders_combobox.setFixedHeight(30)
        self.loaders_combobox.setEditable(True)

        self.block_optifine_checkbox()

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

        self.create_instance_button = QtWidgets.QPushButton(self)
        self.create_instance_button.setText("Действия с экземплярами")
        self.create_instance_button.setFixedWidth(220)
        self.create_instance_button.move(40, 400)
        self.create_instance_button.clicked.connect(lambda: InstancesWindow(self))

        self.progressbar = QtWidgets.QProgressBar(self, textVisible=False)
        self.progressbar.setFixedWidth(260)
        self.progressbar.move(20, 430)

        self.download_info_label = QtWidgets.QLabel(self)
        self.download_info_label.setFixedWidth(290)
        self.download_info_label.move(5, 450)
        self.download_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.settings_button = QtWidgets.QPushButton(self)
        self.settings_button.setText("Настройки")
        self.settings_button.clicked.connect(SettingsWindow)
        self.settings_button.move(5, 465)
        self.settings_button.setFixedWidth(80)

        self.account_button = QtWidgets.QPushButton(self)
        self.account_button.setText("Аккаунт")
        self.account_button.clicked.connect(AccountWindow)
        self.account_button.move(215, 465)
        self.account_button.setFixedWidth(80)

        self.show()

        logging.debug("Checking Internet connection...")

        try:
            requests.get("https://google.com", timeout=10).raise_for_status()
            self.no_internet_connection = False
        except requests.exceptions.ConnectionError:
            self.no_internet_connection = True

        logging.debug(f"No Internet connection: {self.no_internet_connection}")
        self.rpc = Presence(utils.Constants.DISCORD_CLIENT_ID)

        if not self.no_internet_connection:
            try:
                self.rpc.connect()
                logging.debug("Rpc successfuly connected")
            except pypresence.exceptions.DiscordNotFound as e:
                logging.debug(f"There was an error while connecting rpc: {e}")
                pass
        utils.start_rich_presence(self.rpc)

        logging.debug("Logging in account...")
        self.access_token, self.game_uuid, self.refresh_token, self.token_expires_at = (
            self.auto_login()
        )
        logging.debug(f"Chosen account type: {self.launch_account_type}")
        logging.debug(f"Access token: {utils.hide_security_data(self.access_token)}")
        logging.debug(f"Refresh token: {utils.hide_security_data(self.refresh_token)}")
        logging.debug(f"Game uuid: {utils.hide_security_data(self.game_uuid)}")
        if not self.game_uuid:
            self.launch_account_type = "Ely.by"

        if (
            getattr(sys, "frozen", False)
            and not self.no_internet_connection
            and updater.is_new_version_released(utils.Constants.LAUNCHER_VERSION)
        ):
            if (
                QtWidgets.QMessageBox.information(
                    self,
                    "Новое обновление!",
                    "Вышло новое обновление лаунчера.<br>"
                    "Нажмите Оk для обновления.<br>"
                    "После загрузки инсталлера, согласитесь на внесение изменений на устройстве.<br>"
                    'Нажимая "Ok", вы соглашаетесь с текстами лицензий, расположенных по адресам:<br>'
                    '<a href="https://raw.githubusercontent.com/FerrumVega/FVLauncher/refs/heads/main/LICENSE">https://raw.githubusercontent.com/FerrumVega/FVLauncher/refs/heads/main/LICENSE</a><br>'
                    '<a href="https://raw.githubusercontent.com/FerrumVega/FVLauncher/refs/heads/main/THIRD_PARTY_LICENSES">https://raw.githubusercontent.com/FerrumVega/FVLauncher/refs/heads/main/THIRD_PARTY_LICENSES</a>',
                    QtWidgets.QMessageBox.StandardButton.Ok
                    | QtWidgets.QMessageBox.StandardButton.Cancel,
                )
                == QtWidgets.QMessageBox.StandardButton.Ok
            ):
                self.save_config_on_close = False
                self.close()
                multiprocessing.Process(
                    target=updater.update,
                    daemon=False,
                ).start()
                sys.exit()
            else:
                logging.debug(
                    f"User cancelled update. Current launcher version: {utils.Constants.LAUNCHER_VERSION}"
                )


if __name__ == "__main__":
    multiprocessing.freeze_support()
    open("FVLauncher.log", "w").close()
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.debug("Program started its work")
    config = load_config()
    logging.debug("Config loaded")
    faker = Faker()
    main_window = MainWindow(
        config["Preset"]["version"],
        config["Preset"]["mod_loader"],
        config["Preset"]["nickname"],
        config["Settings"]["java_arguments"],
        config["Preset"]["optifine"],
        config["Account"]["access_token"],
        config["Account"]["token_expires_at"],
        config["Account"]["game_uuid"],
        config["Account"]["refresh_token"],
        config["Account"]["launch_account_type"],
        config["Settings"]["show_console"],
        config["Settings"]["show_old_alphas"],
        config["Settings"]["show_old_betas"],
        config["Settings"]["show_snapshots"],
        config["Settings"]["show_releases"],
        config["Settings"]["show_other_versions"],
        config["Settings"]["show_instances_and_packs"],
        config["Settings"]["minecraft_directory"],
        config["Experiments"]["allow_experiments"],
        config["Experiments"]["hover_color"],
    )
    browser_instance = QtWebEngineCore.QWebEngineProfile("FVLauncher")
    sys.exit(utils.app.exec())
