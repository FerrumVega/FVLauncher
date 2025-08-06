# FVLauncher

## Telegram

Официальный Telegram-канал лаунчера: <https://t.me/FVLauncher>

## Загрузка лаунчера

1. Кликнтие [сюда](https://github.com/FerrumVega/FVLauncher/releases/latest/download/FVLauncher_Installer.exe) для загрузки инсталлера последней версии лаунчера
2. Скачайте [java](https://adoptium.net/)

## Частые вопросы и ответы на них

### Проблемы

1. Проблема: Краш игры при запуске на старых версиях
Решение: Удалить options.txt
2. Проблема: Игра не запускается
Решение: Включите "Запуск с консолью" в настройках и откройте issue на github лаунчера с видео запуска

### Вопросы

1. Вопрос: Почему антивирус обнаруживает угрозу в файле?
Ответ: Это связано с системой упаковки exe-файла. Вы можете удостовериться в этом, собрав exe самостоятельно
2. Вопрос: Почему я должен скачать именно этот лаунчер?
Ответ: Мой лаунчер имеет открытый исходный код, весит менее 30 мб и использует официальные версии с сайта разработчиков игры

## Скриншоты

<img width="302" height="539" alt="Главное меню лаунчера" src="https://github.com/user-attachments/assets/08882b95-0036-4b79-9267-43ef273eb62d" />
<img width="302" height="539" alt="Настройки лаунчера" src="https://github.com/user-attachments/assets/ebfe3246-1a94-4a8a-bf6b-85c605ab63c1" />
<img width="302" height="539" alt="Аккаунт системы скинов" src="https://github.com/user-attachments/assets/3398de0c-a800-43b4-bc35-1898d6c5c088" />


## Клонирование репозитория

1. Используйте команду `git clone https://github.com/FerrumVega/FVLauncher` в консоли/терминале
2. Создайте виртуальное окружение корне проекта (`python -m venv venv`)
3. Установите зависимости (`pip install -r requirements.txt`)
4. Для сборки в exe используйте команду из build.bat, для создания инсталлера используйте installer.iss
