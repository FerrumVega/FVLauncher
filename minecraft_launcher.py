import minecraft_launcher_lib, subprocess, os, time, json, nickname_generator


# создание конфига
if not os.path.isfile("config.json"):
    data = {
        "version": minecraft_launcher_lib.utils.get_latest_version(),
        "mod_loader": "vanilla",
        "fix_mode": 0,
        "mrpack_path": "",
        "nickname": nickname_generator.generate(),
        "internet_block_delay": 20,
    }
    with open("config.json", "w") as file:
        json.dump(data, file)

# загрузка конфига
with open("config.json") as config_file:
    config = json.load(config_file)

# загрузка конфига
version = config["version"]
mod_loader = config["mod_loader"]
fix_mode = config["fix_mode"]
mrpack_path = config["mrpack_path"]
nickname = config["nickname"]
internet_block_delay = config["internet_block_delay"]

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

print(
    f"Запуск Minecraft на версии {version} и с ником {nickname}. Загрузчик модов: {mod_loader}."
)

# начальные значения прогресса загрузки
progress = 0
progress_max = 100


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


# скачивание mrpack
if mrpack_path:
    minecraft_launcher_lib.mrpack.install_mrpack(
        mrpack_path,
        minecraft_directory,
        callback={
            "setProgress": set_progress,
            "setMax": set_max,
            "setStatus": print_status,
        },
    )

# удаление mrpacka из конфига
new_config = config
new_config["mrpack_path"] = ""
with open("config.json", "w") as config_file:
    json.dump(new_config, config_file)


# задание последней версии forge
if mod_loader == "forge":
    for forge_version in minecraft_launcher_lib.forge.list_forge_versions():
        if forge_version.startswith(version):
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
time.sleep(internet_block_delay)

# разблокировка инета
os.system(f'netsh advfirewall firewall delete rule name="Block Minecraft"')
