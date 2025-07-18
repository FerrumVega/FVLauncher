import minecraft_launcher_lib, subprocess, os, time, ctypes, optipy, threading, sys, sv_ttk, configparser, tkinter as tk
from tkinter import ttk, messagebox

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass


def resolve_version_names(raw_version, mod_loader):
    name_of_version_to_install = raw_version
    name_of_version_folder = raw_version
    if mod_loader == "forge":
        for forge_version in minecraft_launcher_lib.forge.list_forge_versions():
            if forge_version.startswith(raw_version):
                name_of_version_to_install = forge_version
                name_of_version_folder = f"{name_of_version_to_install.split("-")[0]}-forge-{name_of_version_to_install.split("-")[1]}"
                return (name_of_version_to_install, name_of_version_folder)
        return None

    elif mod_loader == "fabric":
        if raw_version in minecraft_launcher_lib.fabric.get_all_minecraft_versions():
            name_of_version_folder = f"fabric-loader-{minecraft_launcher_lib.fabric.get_latest_loader_version()}-{name_of_version_to_install}"
            return (name_of_version_to_install, name_of_version_folder)
        return None

    return (name_of_version_to_install, name_of_version_folder)


def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.abspath(relative_path)


def load_config():
    file_path = "FVLauncher.ini"
    parser = configparser.ConfigParser()

    if not os.path.isfile(file_path):
        parser.add_section("Settings")
        parser.set("Settings", "version", "1.16.5")
        parser.set("Settings", "mod_loader", "vanilla")
        parser.set("Settings", "nickname", "Player")
        parser.set("Settings", "fix_mode", "0")
        parser.set("Settings", "java_arguments", "")
        with open(file_path, "w", encoding="utf-8") as config_file:
            parser.write(config_file)

    parser.read(file_path, encoding="utf-8")

    return (parser.get("Settings", option) for option in parser.options("Settings"))


def gui(
    choosen_version,
    choosen_mod_loader,
    choosen_nickname,
    fix_mode_position,
    choosen_java_arguments,
):
    def safe_config():
        file_path = "FVLauncher.ini"
        parser = configparser.ConfigParser()

        parser.add_section("Settings")
        parser.set("Settings", "version", version_var.get())
        parser.set("Settings", "mod_loader", mod_loader_var.get())
        parser.set("Settings", "nickname", nickname_var.get())
        parser.set("Settings", "fix_mode", str(fix_mode_var.get()))
        parser.set("Settings", "java_arguments", java_arguments_var.get())
        with open(file_path, "w", encoding="utf-8") as config_file:
            parser.write(config_file)
        os._exit(0)

    def on_start_button():
        start_button["state"] = "disabled"
        mod_loader = mod_loader_var.get()
        raw_version = version_var.get()
        nickname = nickname_var.get()
        fix_mode = fix_mode_var.get()
        java_arguments = java_arguments_var.get().split()
        returned_versions_data = resolve_version_names(raw_version, mod_loader)

        if raw_version not in versions_names_list:
            messagebox.showerror("Ошибка запуска", "Выберите версию из списка.")
            start_button["state"] = "normal"
        elif returned_versions_data:
            version, version_name = returned_versions_data
            if all((mod_loader, nickname, version)):
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

    def open_settings():
        settings_window = tk.Toplevel()
        settings_window.title("Настройки")
        settings_window.iconbitmap(resource_path("minecraft_title.ico"))
        root.iconphoto(True, tk.PhotoImage(file=resource_path("minecraft_title.png")))
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
        fix_mode_checkbox.place(relx=0.5, y=110, anchor="center")

    root = tk.Tk()
    root.title("FVLauncher")
    root.iconbitmap(resource_path("minecraft_title.ico"))
    root.iconphoto(True, tk.PhotoImage(file=resource_path("minecraft_title.png")))
    root.geometry("300x500")
    root.resizable(width=False, height=False)

    version_var = tk.StringVar()
    version_var.set(choosen_version)

    mod_loader_var = tk.StringVar()
    mod_loader_var.set(choosen_mod_loader)

    nickname_var = tk.StringVar()
    nickname_var.set(choosen_nickname)

    progress_var = tk.DoubleVar()

    download_info = tk.StringVar()
    download_info.set("Здесь будет информация о загрузке игры.")

    java_arguments_var = tk.StringVar()
    java_arguments_var.set(choosen_java_arguments)

    fix_mode_var = tk.IntVar()
    fix_mode_var.set(int(fix_mode_position))

    bg_image = tk.PhotoImage(file=resource_path("background1.png"))
    bg_label = ttk.Label(root, image=bg_image)
    bg_label.place(relwidth=1, relheight=1)

    versions_names_list = []
    versions_list = minecraft_launcher_lib.utils.get_version_list()
    for item in versions_list:
        versions_names_list.append(item["id"])
    versions_combobox = ttk.Combobox(
        root, values=versions_names_list, width=10, textvariable=version_var
    )
    versions_combobox.place(x=80, y=30, anchor="center")

    mod_loaders = ["fabric", "forge", "vanilla"]
    loaders_combobox = ttk.Combobox(
        root, values=mod_loaders, width=10, textvariable=mod_loader_var
    )
    loaders_combobox.place(x=220, y=30, anchor="center")

    nickname_entry = ttk.Entry(root, textvariable=nickname_var, width=31)
    nickname_entry.place(relx=0.5, y=70, anchor="center")

    start_button = ttk.Button(
        root, text="Запустить игру", command=on_start_button, width=31
    )
    start_button.place(relx=0.5, y=110, anchor="center")

    progressbar = ttk.Progressbar(root, variable=progress_var, length=295)
    progressbar.place(relx=0.5, y=400, anchor="center")

    download_info_label = ttk.Label(textvariable=download_info, font=("", 8))
    download_info_label.place(relx=0.5, y=430, anchor="center")

    settings_button = ttk.Button(root, text="⚙️", command=open_settings, width=3)
    settings_button.place(x=270, y=480, anchor="center")

    sv_ttk.set_theme("dark")
    root.protocol("WM_DELETE_WINDOW", safe_config)
    root.mainloop()


def prepare_installation_parameters(mod_loader, nickname, java_arguments):
    if mod_loader == "fabric":
        install_type = minecraft_launcher_lib.fabric.install_fabric
    elif mod_loader == "forge":
        install_type = minecraft_launcher_lib.forge.install_forge_version
    else:
        install_type = minecraft_launcher_lib.install.install_minecraft_version

    options = {
        "username": nickname,
        "uuid": "a00a0aaa-0aaa-00a0-a000-00a0a00a0aa0",
        "token": "",
        "jvmArguments": java_arguments,
    }
    minecraft_directory = minecraft_launcher_lib.utils.get_minecraft_directory()
    return install_type, minecraft_directory, options


def install_version(
    version,
    version_name,
    install_type,
    fix_mode,
    minecraft_directory,
    progress_var,
    download_info,
):
    progress = 0
    max_progress = 100

    def track_progress(value, type=None):
        nonlocal progress, max_progress
        if type == "progress":
            progress = value
        elif type == "max":
            max_progress = value
        else:
            download_info.set(value)
        percents = progress / max_progress * 100
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
    else:
        download_info.set("Версия уже установлена, запуск...")


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
):
    install_type, minecraft_directory, options = prepare_installation_parameters(
        mod_loader, nickname, java_arguments
    )
    try:
        install_version(
            version,
            version_name,
            install_type,
            fix_mode,
            minecraft_directory,
            progress_var,
            download_info,
        )
        download_info.set("Версия установлена, запуск...")
        minecraft_command = minecraft_launcher_lib.command.get_minecraft_command(
            version_name, minecraft_directory, options
        )
        start_button["state"] = "normal"
        subprocess.run(
            f'netsh advfirewall firewall add rule name="Block Minecraft" dir=out action=block program={os.path.join(minecraft_directory, "runtime\\jre-legacy\\windows-x64\\jre-legacy\\bin\\java.exe")} enable=yes',
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        subprocess.Popen(
            minecraft_command,
            cwd=minecraft_directory,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        time.sleep(20)

        subprocess.run(
            f'netsh advfirewall firewall delete rule name="Block Minecraft"',
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception as e:
        messagebox.showerror("Ошибка", f"Ошибка:\n{e}")
        start_button["state"] = "normal"


gui(*load_config())
