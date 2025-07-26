import minecraft_launcher_lib
import subprocess
import os
import requests
import ctypes
import threading
import sys
import sv_ttk
import configparser
import uuid
import json
import winshell
import xml.etree.ElementTree as ET
import tkinter as tk
from tkinter import ttk, messagebox


try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

java_path = None
for path in os.environ["PATH"].split(";"):
    speculative_java_path = os.path.join(path.strip('"'), "java.exe")
    if os.path.isfile(speculative_java_path):
        java_path = speculative_java_path
        break
if java_path is None:
    messagebox.showerror(
        "Java не найдена",
        "На вашем компьюетере отсутствует java, загрузите её с github лаунчера.",
    )
    os._exit(1)


def catch_errors(func):
    global start_button, progress_var, download_info

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Произошла ошибка в {func.__name__}:\n{e}")
            try:
                start_button["state"] = "normal"
                progress_var.set(0)
                download_info.set("Во время загрузки произошла ошибка.")
            except Exception:
                pass

    return wrapper


@catch_errors
def resolve_version_names(raw_version, mod_loader):
    name_of_version_to_install = raw_version
    name_of_version_folder = raw_version
    if mod_loader == "forge":
        if minecraft_launcher_lib.forge.find_forge_version(raw_version):
            name_of_version_to_install = (
                minecraft_launcher_lib.forge.find_forge_version(raw_version)
            )
            name_of_version_folder = f"{name_of_version_to_install.split('-')[0]}-forge-{name_of_version_to_install.split('-')[1]}"
            return (name_of_version_to_install, name_of_version_folder)
        else:
            return None
    elif mod_loader == "fabric":
        if minecraft_launcher_lib.fabric.is_minecraft_version_supported(raw_version):
            name_of_version_folder = f"fabric-loader-{minecraft_launcher_lib.fabric.get_latest_loader_version()}-{name_of_version_to_install}"
            return (name_of_version_to_install, name_of_version_folder)
        else:
            return None

    return (name_of_version_to_install, name_of_version_folder)


@catch_errors
def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(relative_path)


@catch_errors
def load_config():
    default_config = {
        "version": "1.16.5",
        "mod_loader": "fabric",
        "nickname": "Player",
        "fix_mode": "0",
        "java_arguments": "",
        "sodium": "1",
        "access_token": "",
        "ely_uuid": "",
        "show_console": "0",
    }
    appdata_path = os.environ["APPDATA"]
    file_path = f"{appdata_path}\\FVLauncher\\FVLauncher.ini"
    if not os.path.isdir(f"{appdata_path}\\FVLauncher"):
        os.mkdir(f"{appdata_path}\\FVLauncher")
        if getattr(sys, "frozen", False):
            winshell.CreateShortcut(
                Path="C:\\Users\\user\\Desktop\\FVLauncher.lnk",
                Target=sys.executable,
                Icon=(resource_path("minecraft_title.ico"), 0),
            )
    parser = configparser.ConfigParser()

    if not os.path.isfile(file_path):
        parser.add_section("Settings")
        parser["Settings"] = default_config
        with open(file_path, "w", encoding="utf-8") as config_file:
            parser.write(config_file)
    else:
        updated = False
        parser.read(file_path, encoding="utf-8")
        for key, value in default_config.items():
            if key not in parser["Settings"]:
                parser["Settings"][key] = value
                updated = True
        if updated:
            with open(file_path, "w", encoding="utf-8") as config_file:
                parser.write(config_file)

    return {key: parser["Settings"][key] for key in parser.options("Settings")}


@catch_errors
def gui(
    chosen_version,
    chosen_mod_loader,
    chosen_nickname,
    fix_mode_position,
    chosen_java_arguments,
    sodium_position,
    saved_access_token,
    saved_ely_uuid,
    show_console_position,
):
    client_token = str(uuid.uuid5(uuid.NAMESPACE_DNS, str(uuid.getnode())))
    global start_button, progress_var, download_info

    @catch_errors
    def safe_config():
        settings = {
            "version": version_var.get(),
            "mod_loader": mod_loader_var.get(),
            "nickname": nickname_var.get(),
            "fix_mode": str(fix_mode_var.get()),
            "java_arguments": java_arguments_var.get(),
            "sodium": str(sodium_var.get()),
            "access_token": access_token,
            "ely_uuid": ely_uuid,
            "show_console": show_console_var.get(),
        }
        file_path = "FVLauncher.ini"
        parser = configparser.ConfigParser()

        parser.add_section("Settings")
        parser["Settings"] = settings

        with open(file_path, "w", encoding="utf-8") as config_file:
            parser.write(config_file)
        root.destroy()
        os._exit(0)

    @catch_errors
    def block_sodium_checkbox(*args):
        sodium_checkbox["state"] = (
            "normal" if mod_loader_var.get() == "fabric" else "disabled"
        )

    @catch_errors
    def on_start_button():
        start_button["state"] = "disabled"
        mod_loader = mod_loader_var.get()
        raw_version = version_var.get()
        nickname = nickname_var.get()
        fix_mode = fix_mode_var.get()
        java_arguments = java_arguments_var.get().split()
        sodium = sodium_var.get()
        show_console = show_console_var.get()
        returned_versions_data = resolve_version_names(raw_version, mod_loader)

        if raw_version not in versions_names_list:
            messagebox.showerror("Ошибка запуска", "Выберите версию из списка.")
            start_button["state"] = "normal"
        elif returned_versions_data:
            version, version_name = returned_versions_data
            if all((mod_loader, nickname, version)):
                download_info_label.place(relx=0.5, y=430, anchor="center")
                threading.Thread(
                    target=launch,
                    args=(
                        mod_loader,
                        nickname,
                        version,
                        version_name,
                        fix_mode,
                        java_arguments,
                        start_button,
                        progress_var,
                        download_info,
                        raw_version,
                        sodium,
                        ely_uuid,
                        access_token,
                        show_console,
                    ),
                    daemon=True,
                ).start()
            else:
                null_elements = ", ".join(
                    [
                        name
                        for element, name in zip(
                            (mod_loader, nickname, version),
                            ("загрузчик модов", "никнейм", "версия"),
                        )
                        if not element
                    ]
                ).capitalize()
                messagebox.showerror(
                    "Ошибка запуска",
                    f"Следующие поля не заполнены:\n{null_elements}.",
                )
                start_button["state"] = "normal"
        else:
            messagebox.showerror(
                "Ошибка", "Для данной версии нет выбранного вами загрузчика модов."
            )
            start_button["state"] = "normal"

    @catch_errors
    def open_settings():
        settings_window = tk.Toplevel()
        settings_window.title("Настройки")
        settings_window.geometry(root.geometry())
        settings_window.resizable(width=False, height=False)

        settings_window.bg_image = tk.PhotoImage(file=resource_path("background.png"))
        settings_bg_label = ttk.Label(settings_window, image=settings_window.bg_image)
        settings_bg_label.place(relwidth=1, relheight=1)

        java_arguments_label = ttk.Label(settings_window, text="java-аргументы")
        java_arguments_label.place(relx=0.5, y=30, anchor="center")

        java_arguments_entry = ttk.Entry(
            settings_window, textvariable=java_arguments_var
        )
        java_arguments_entry.place(relx=0.5, y=60, anchor="center")

        fix_mode_checkbox = ttk.Checkbutton(
            settings_window, text="fix-mode", variable=fix_mode_var
        )
        fix_mode_checkbox.place(relx=0.5, y=110, relwidth=0.6, anchor="center")

        show_console_checkbox = ttk.Checkbutton(
            settings_window, text="Запуск с консолью", variable=show_console_var
        )
        show_console_checkbox.place(relx=0.5, y=145, relwidth=0.6, anchor="center")

    @catch_errors
    def skins_system():

        @catch_errors
        def login():
            nonlocal access_token, ely_uuid
            data = requests.post(
                "https://authserver.ely.by/auth/authenticate",
                json={
                    "username": ely_username_var.get(),
                    "password": ely_password_var.get(),
                    "clientToken": client_token,
                    "requestUser": True,
                },
            )
            if sign_status_var.get() == "Статус: вы вошли в аккаунт":
                messagebox.showerror(
                    "Ошибка входа", "Сначала выйдите из аккаунта", parent=account
                )
            elif data.status_code == 200:
                access_token = data.json()["accessToken"]
                ely_uuid = data.json()["user"]["id"]
                nickname_var.set(data.json()["user"]["username"])
                nickname_entry["state"] = "disabled"
                messagebox.showinfo(
                    "Поздравляем!",
                    "Теперь вы будете видеть свой скин в игре.",
                    parent=account,
                )
                sign_status_var.set("Статус: вы вошли в аккаунт")
            else:
                messagebox.showerror(
                    "Ошибка входа",
                    f"Текст ошибки: {data.json()['errorMessage']}",
                    parent=account,
                )

        @catch_errors
        def signout():
            nonlocal access_token, ely_uuid
            data = requests.post(
                "https://authserver.ely.by/auth/invalidate",
                json={
                    "accessToken": access_token,
                    "clientToken": client_token,
                },
            )
            access_token = ""
            ely_uuid = ""
            nickname_entry["state"] = "normal"
            if data.status_code == 200:
                messagebox.showinfo(
                    "Выход из аккаунта", "Вы вышли из аккаунта", parent=account
                )
                sign_status_var.set("Статус: вы вышли из аккаунта")
            else:
                messagebox.showerror(
                    "Ошибка выхода",
                    data.json()["errorMessage"],
                    parent=account,
                )

        account = tk.Toplevel()
        account.title("Аккаунт")
        account.geometry(root.geometry())
        account.resizable(width=False, height=False)

        account.bg_image = tk.PhotoImage(file=resource_path("background.png"))
        account_bg_label = ttk.Label(account, image=account.bg_image)
        account_bg_label.place(relwidth=1, relheight=1)

        ely_username_placeholder_label = ttk.Label(
            account, text="Никнейм аккаунта ely.by"
        )
        ely_username_placeholder_label.place(y=40, relx=0.5, anchor="center")

        ely_username = ttk.Entry(account, textvariable=ely_username_var)
        ely_username.place(y=70, relx=0.5, anchor="center")

        ely_password_placeholder_label = ttk.Label(
            account, text="Пароль аккаунта ely.by"
        )
        ely_password_placeholder_label.place(y=100, relx=0.5, anchor="center")

        ely_password = ttk.Entry(account, textvariable=ely_password_var)
        ely_password.place(y=130, relx=0.5, anchor="center")

        login_button = ttk.Button(account, text="Войти в аккаунт", command=login)
        login_button.place(y=190, relx=0.5, anchor="center")

        signout_button = ttk.Button(account, text="Выйти из аккаунта", command=signout)
        signout_button.place(y=225, relx=0.5, anchor="center")

        sign_status_label = ttk.Label(account, textvariable=sign_status_var)
        sign_status_label.place(y=480, relx=0.5, anchor="center")

    @catch_errors
    def auto_login():
        if saved_ely_uuid and saved_access_token:
            valid_token_info = requests.post(
                "https://authserver.ely.by/auth/validate",
                json={"accessToken": saved_access_token},
            )
            if valid_token_info.status_code != 200:
                refreshed_token_info = requests.post(
                    "https://authserver.ely.by/auth/refresh",
                    json={
                        "accessToken": saved_access_token,
                        "clientToken": client_token,
                        "requestUser": True,
                    },
                )
                if refreshed_token_info.status_code != 200:
                    access_token = ""
                    ely_uuid = ""
                    sign_status_var.set("Статус: вы не вошли в аккаунт")
                    return access_token, ely_uuid
                else:
                    access_token = refreshed_token_info.json()["accessToken"]
                    ely_uuid = refreshed_token_info.json()["user"]["id"]
                    username = refreshed_token_info.json()["user"]["username"]
                    nickname_var.set(username)
                    nickname_entry["state"] = "disabled"
                    sign_status_var.set("Статус: вы вошли в аккаунт")
                    return access_token, ely_uuid
            else:
                username = chosen_nickname
                nickname_var.set(username)
                nickname_entry["state"] = "disabled"
                sign_status_var.set("Статус: вы вошли в аккаунт")
                return saved_access_token, saved_ely_uuid
        else:
            sign_status_var.set("Статус: вы не вошли в аккаунт")
            return saved_access_token, saved_ely_uuid

    root = tk.Tk()
    root.title("FVLauncher")
    root.iconbitmap(resource_path("minecraft_title.ico"))
    root.iconphoto(True, tk.PhotoImage(file=resource_path("minecraft_title.png")))
    root.geometry("300x500")
    root.resizable(width=False, height=False)

    version_var = tk.StringVar()
    version_var.set(chosen_version)

    mod_loader_var = tk.StringVar()
    mod_loader_var.set(chosen_mod_loader)

    nickname_var = tk.StringVar()
    nickname_var.set(chosen_nickname)

    sodium_var = tk.IntVar()
    sodium_var.set(sodium_position)

    progress_var = tk.DoubleVar()

    download_info = tk.StringVar()
    download_info.set("Загрузка...")

    java_arguments_var = tk.StringVar()
    java_arguments_var.set(chosen_java_arguments)

    fix_mode_var = tk.IntVar()
    fix_mode_var.set(int(fix_mode_position))

    show_console_var = tk.IntVar()
    show_console_var.set(int(show_console_position))

    ely_password_var = tk.StringVar()
    ely_username_var = tk.StringVar()

    sign_status_var = tk.StringVar()

    bg_image = tk.PhotoImage(file=resource_path("background1.png"))
    bg_label = ttk.Label(root, image=bg_image)
    bg_label.place(relwidth=1, relheight=1)

    versions_names_list = []
    versions_list = minecraft_launcher_lib.utils.get_version_list()
    for item in versions_list:
        versions_names_list.append(item["id"])
    versions_combobox = ttk.Combobox(
        root, values=versions_names_list, textvariable=version_var
    )
    versions_combobox.place(x=80, y=30, anchor="center", relwidth=0.43)

    mod_loaders = ["fabric", "forge", "vanilla"]
    loaders_combobox = ttk.Combobox(
        root, values=mod_loaders, textvariable=mod_loader_var
    )
    loaders_combobox.place(x=220, y=30, anchor="center", relwidth=0.43)

    nickname_entry = ttk.Entry(root, textvariable=nickname_var)
    nickname_entry.place(relx=0.5, y=70, anchor="center", relwidth=0.9)

    sodium_checkbox = ttk.Checkbutton(root, text="Sodium", variable=sodium_var)
    sodium_checkbox.place(relx=0.5, y=110, anchor="center", relwidth=0.9)
    block_sodium_checkbox()
    root.bind("<<ComboboxSelected>>", block_sodium_checkbox)

    start_button = ttk.Button(root, text="Запуск", command=on_start_button)
    start_button.place(relx=0.5, y=150, anchor="center", relwidth=0.9)

    progressbar = ttk.Progressbar(root, variable=progress_var, length=295)
    progressbar.place(relx=0.5, y=400, anchor="center")

    download_info_label = ttk.Label(textvariable=download_info, font=("", 8))

    settings_button = ttk.Button(root, text="⚙️", command=open_settings)
    settings_button.place(x=270, y=480, anchor="center", relwidth=0.15)

    account_button = ttk.Button(root, text="Аккаунт", command=skins_system)
    account_button.place(x=40, y=480, anchor="center")

    sv_ttk.set_theme("dark")
    root.protocol("WM_DELETE_WINDOW", safe_config)

    access_token, ely_uuid = auto_login()

    root.mainloop()


@catch_errors
def prepare_installation_parameters(
    mod_loader, nickname, java_arguments, ely_uuid, access_token
):
    minecraft_directory = minecraft_launcher_lib.utils.get_minecraft_directory()
    if mod_loader == "fabric":
        install_type = minecraft_launcher_lib.fabric.install_fabric
    elif mod_loader == "forge":
        install_type = minecraft_launcher_lib.forge.install_forge_version
    else:
        install_type = minecraft_launcher_lib.install.install_minecraft_version
    options = {
        "username": nickname,
        "uuid": ely_uuid,
        "token": access_token,
        "jvmArguments": java_arguments,
        "executablePath": java_path,
    }
    return install_type, minecraft_directory, options


@catch_errors
def download_injector(raw_version, minecraft_directory):
    authlib_version = None
    with open(
        os.path.join(
            minecraft_directory, "versions", raw_version, f"{raw_version}.json"
        )
    ) as file_with_downloads:
        for lib in json.load(file_with_downloads)["libraries"]:
            if lib["name"].startswith("com.mojang:authlib:"):
                authlib_version = lib["name"].split(":")[-1]
                break
    if authlib_version is not None:
        base_url = "https://maven.ely.by/releases/by/ely/authlib"
        xml_data = requests.get(f"{base_url}/maven-metadata.xml").content.decode(
            "utf-8"
        )
        found = False
        for version in ET.fromstring(xml_data).findall("./versioning/versions/version")[
            ::-1
        ]:
            if authlib_version in version.text:
                found = True
                break
        if found:
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
                        f"{base_url}/{version.text}/authlib-{version.text}.jar"
                    ).content
                )
            java_agent = False
        else:
            messagebox.showwarning(
                "Ошибка скина",
                "На данной версии нет патченной authlib. Скин будет отображен только в одиночной игре и на серверах с поддержкой ely.by",
            )
            with open(
                os.path.join(minecraft_directory, "authlib-injector.jar"), "wb"
            ) as injector_jar:
                injector_jar.write(
                    requests.get(
                        "https://github.com/yushijinhun/authlib-injector/releases/download/v1.2.5/authlib-injector-1.2.5.jar"
                    ).content
                )
            java_agent = True
    else:
        messagebox.showwarning(
            "Ошибка скина", "На данной версии нет authlib, скины не поддерживаются."
        )
        java_agent = False
    return java_agent


@catch_errors
def install_version(
    version,
    version_name,
    install_type,
    fix_mode,
    minecraft_directory,
    progress_var,
    download_info,
    raw_version,
):
    progress = 0
    max_progress = 100

    @catch_errors
    def track_progress(value, type=None):
        nonlocal progress, max_progress
        if type == "progress":
            progress = value
        elif type == "max":
            max_progress = value
        else:
            download_info.set(value)
        try:
            percents = progress / max_progress * 100
        except ZeroDivisionError:
            percents = 0
        if percents > 100.0:
            percents = 100.0
        progress_var.set(percents)

    if (
        not os.path.isdir(os.path.join(minecraft_directory, "versions", version_name))
        or fix_mode
    ):
        install_type(
            version,
            minecraft_directory,
            callback={
                "setProgress": lambda value: track_progress(value, "progress"),
                "setMax": lambda value: track_progress(value, "max"),
                "setStatus": lambda value: track_progress(value),
            },
        )
        download_info.set("Загрузка injector...")
        if download_injector(raw_version, minecraft_directory):
            return True
    else:
        download_info.set("Версия уже установлена, запуск...")


@catch_errors
def download_sodium(sodium_path, raw_version, download_info):
    url = None
    for sodium_version in requests.get(
        "https://api.modrinth.com/v2/project/sodium/version"
    ).json():
        if (
            raw_version in sodium_version["game_versions"]
            and "fabric" in sodium_version["loaders"]
        ):
            url = sodium_version["files"][0]["url"]
            break
    else:
        messagebox.showwarning(
            "Запуск без sodium", "Sodium недоступен на выбранной вами версии."
        )
    if url:
        download_info.set("Загрузка Sodium...")
        with open(sodium_path, "wb") as sodium_jar:
            sodium_jar.write(requests.get(url).content)


@catch_errors
def launch(
    mod_loader,
    nickname,
    version,
    version_name,
    fix_mode,
    java_arguments,
    start_button,
    progress_var,
    download_info,
    raw_version,
    sodium,
    ely_uuid,
    access_token,
    show_console,
):
    global java_path

    install_type, minecraft_directory, options = prepare_installation_parameters(
        mod_loader, nickname, java_arguments, ely_uuid, access_token
    )

    if install_version(
        version,
        version_name,
        install_type,
        fix_mode,
        minecraft_directory,
        progress_var,
        download_info,
        raw_version,
    ):
        options["jvmArguments"].append(
            f"-javaagent:{os.path.join(minecraft_directory, 'authlib-injector.jar')}=ely.by"
        )
    sodium_path = os.path.join(minecraft_directory, "mods", "sodium.jar")

    if not os.path.isdir(os.path.join(minecraft_directory, "mods")):
        os.mkdir(os.path.join(minecraft_directory, "mods"))
    if os.path.isfile(sodium_path):
        os.remove(sodium_path)
    if sodium and mod_loader == "fabric":
        download_sodium(sodium_path, raw_version, download_info)

    download_info.set("Версия установлена, запуск...")

    minecraft_command = minecraft_launcher_lib.command.get_minecraft_command(
        version_name, minecraft_directory, options
    )

    start_button["state"] = "normal"

    subprocess.Popen(
        minecraft_command,
        cwd=minecraft_directory,
        **{"creationflags": subprocess.CREATE_NO_WINDOW} if not show_console else {},
    )
    download_info.set("Игра запущена")
    progress_var.set(100)


config = load_config()
gui(
    config["version"],
    config["mod_loader"],
    config["nickname"],
    config["fix_mode"],
    config["java_arguments"],
    config["sodium"],
    config["access_token"],
    config["ely_uuid"],
    config["show_console"],
)
