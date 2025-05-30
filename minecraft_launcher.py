import minecraft_launcher_lib, subprocess, os, time

# начальные значения прогресса загрузки
progress = 0
progress_max = 100


def get_version(raw_version, mod_loader):
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
def set_progress(info):
    global progress
    progress = info


# отображение прогресса
def set_max(info):
    global progress_max
    progress_max = info


# отображение прогресса
def print_status(info):
    global progress, progress_max
    percents = progress / progress_max * 100
    if percents > 100.0:
        percents = 100.0
    print(f"{info} ({percents:.1f}%)")


def main():
    options = ["Запуск игры", "Восстановление файлов игры", "Загрузка сборки"]
    for i, j in enumerate(options, 1):
        print(f"{i}) {j}")
    selected = int(input())

    if selected == 1 or selected == 2:
        mod_loaders = ["fabric", "forge", "vanilla"]
        print("Выберите загрузчик модов:")
        for i, j in enumerate(mod_loaders, 1):
            print(f"{i}) {j}")
        mod_loader = int(input())

        version, version_name = get_version(
            input("Выберите версию: "), mod_loaders[mod_loader - 1]
        )
        nickname = input("Введите никнейм: ")
    else:
        version, version_name, mod_loader, nickname = "", "", "", ""
    if selected == 2:
        fix_mode = 1
    else:
        fix_mode = 0

    if selected == 3:
        mrpack_path = input("Введите путь к mrpack'у: ")
    else:
        mrpack_path = ""
    return (
        version,
        version_name,
        mod_loaders[mod_loader - 1],
        fix_mode,
        mrpack_path,
        nickname,
    )


def initialize(mod_loader, nickname):
    # задание типа установки в зависимости от загрузчика
    if mod_loader == "fabric":
        install_type = minecraft_launcher_lib.fabric.install_fabric
    elif mod_loader == "forge":
        install_type = minecraft_launcher_lib.forge.install_forge_version
    else:
        install_type = minecraft_launcher_lib.install.install_minecraft_version

    # аргументы майнкрафта и директория майнкрафта
    options = {"username": nickname, "uuid": "", "token": ""}
    minecraft_directory = minecraft_launcher_lib.utils.get_minecraft_directory()
    return install_type, minecraft_directory, options


# скачивание mrpack
def install_mrpack(mrpack_path, minecraft_directory):
    minecraft_launcher_lib.mrpack.install_mrpack(
        mrpack_path,
        minecraft_directory,
        callback={
            "setProgress": set_progress,
            "setMax": set_max,
            "setStatus": print_status,
        },
    )


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
                "setProgress": set_progress,
                "setMax": set_max,
                "setStatus": print_status,
            },
        )


while True:
    version, version_name, mod_loader, fix_mode, mrpack_path, nickname = main()
    install_type, minecraft_directory, options = initialize(mod_loader, nickname)

    if mrpack_path:
        install_mrpack(mrpack_path, minecraft_directory)
        continue
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
