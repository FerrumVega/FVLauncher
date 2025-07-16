import minecraft_launcher_lib, subprocess, os, time, ctypes, optipy, threading, tkinter as tk
from tkinter import ttk


try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)  # SYSTEM_AWARE
except Exception:
    pass


# начальные значения прогресса загрузки
progress = 0
progress_max = 100


def resolve_version_names(raw_version, mod_loader):
    version = raw_version
    version_name = ""
    # задание последней версии forge
    if mod_loader == "forge":
        for forge_version in minecraft_launcher_lib.forge.list_forge_versions():
            if forge_version.startswith(raw_version):
                version = forge_version
                break

    # задание названий папок с версией
    if mod_loader == "fabric":
        version_name = (
            "fabric-loader-"
            + minecraft_launcher_lib.fabric.get_latest_loader_version()
            + f"-{version}"
        )
    elif mod_loader == "forge":
        version_name = version.split("-")[0] + "-forge-" + version.split("-")[1]
    else:
        version_name = version

    return (version, version_name)


# отображение прогресса
def update_progress_value(info):
    global progress
    progress = info


# отображение прогресса
def update_progress_max(info):
    global progress_max
    progress_max = info


# отображение прогресса
def display_download_status(info):
    global progress, progress_max, progress_var, download_info
    percents = progress / progress_max * 100
    if percents > 100.0:
        percents = 100.0
    progress_var.set(percents)
    download_info.set(info)


def gui():
    global progress_var, download_info

    def on_start_button():
        nonlocal mod_loader, version, nickname, fix_mode
        mod_loader = loaders_combobox.get()
        version = versions_combobox.get()
        nickname = nickname_entry.get()
        fix_mode = fix_mode_var.get()
        version, version_name = resolve_version_names(version, mod_loader)
        threading.Thread(
            target=launch,
            args=(mod_loader, nickname, version, version_name, fix_mode),
            daemon=True,
        ).start()
        return

    mod_loader = ""
    version = ""
    nickname = ""
    fix_mode = 0

    root = tk.Tk()
    root.title("FVLauncher")
    root.iconbitmap(r"C:\Users\user\Desktop\minecraft_title.ico")
    fix_mode_var = tk.IntVar()
    download_info = tk.StringVar()
    progress_var = tk.DoubleVar()
    root.geometry("300x500")

    mod_loaders = ["fabric", "forge", "vanilla"]
    loaders_combobox = ttk.Combobox(root, values=mod_loaders)
    loaders_combobox.pack(pady=20)

    versions_names_list = []
    versions_list = minecraft_launcher_lib.utils.get_version_list()
    for item in versions_list:
        versions_names_list.append(item["id"])
    versions_combobox = ttk.Combobox(root, values=versions_names_list)
    versions_combobox.pack(pady=20)

    nickname_entry = ttk.Entry(root)
    nickname_entry.pack(pady=20)

    fix_mode_checkbox = ttk.Checkbutton(root, text="fix-mode", variable=fix_mode_var)
    fix_mode_checkbox.pack(pady=20)

    start_button = ttk.Button(root, text="Запустить игру", command=on_start_button)
    start_button.pack(pady=20)

    progressbar = ttk.Progressbar(root, variable=progress_var)
    progressbar.pack(pady=20)

    label = ttk.Label(textvariable=download_info)
    label.pack(pady=20)

    root.mainloop()

    return (
        version,
        version_name,
        mod_loader,
        fix_mode,
        nickname,
    )


def prepare_installation_parameters(mod_loader, nickname):
    # задание типа установки в зависимости от загрузчика
    if mod_loader == "fabric":
        install_type = minecraft_launcher_lib.fabric.install_fabric
    elif mod_loader == "forge":
        install_type = minecraft_launcher_lib.forge.install_forge_version
    else:
        install_type = minecraft_launcher_lib.install.install_minecraft_version

    # аргументы майнкрафта и директория майнкрафта
    options = {
        "username": nickname,
        "uuid": "a00a0aaa-0aaa-00a0-a000-00a0a00a0aa0",
        "token": "",
    }
    minecraft_directory = minecraft_launcher_lib.utils.get_minecraft_directory()
    return install_type, minecraft_directory, options


def install_version(version, version_name, install_type, fix_mode, minecraft_directory):
    # если версия не скачана
    if (
        not os.path.isdir(os.path.join(minecraft_directory, "versions", version_name))
        or fix_mode
    ):
        # скачивание версии
        install_type(
            version,
            minecraft_directory,
            callback={
                "setProgress": update_progress_value,
                "setMax": update_progress_max,
                "setStatus": display_download_status,
            },
        )


def launch(mod_loader, nickname, version, version_name, fix_mode):
    install_type, minecraft_directory, options = prepare_installation_parameters(
        mod_loader, nickname
    )
    install_version(version, version_name, install_type, fix_mode, minecraft_directory)
    # получение команды для запуска майна
    minecraft_command = minecraft_launcher_lib.command.get_minecraft_command(
        version_name, minecraft_directory, options
    )
    # блокировка интернета
    os.system(
        f'netsh advfirewall firewall add rule name="Block Minecraft" dir=out action=block program={os.path.join(minecraft_directory, "runtime\\jre-legacy\\windows-x64\\jre-legacy\\bin\\java.exe")} enable=yes'
    )

    # запуск майна
    subprocess.Popen(minecraft_command, cwd=minecraft_directory)

    # ждем запуска майна
    time.sleep(20)

    # разблокировка инета
    os.system(f'netsh advfirewall firewall delete rule name="Block Minecraft"')


version, version_name, mod_loader, fix_mode, nickname = gui()
