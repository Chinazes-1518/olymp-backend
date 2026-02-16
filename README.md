# Асинхронно 1518
Репозиторий, содержащий исходный код бэкенда команды "Асинхронно 1518" для Московской Предпрофессиональной олимпиады **Кейс №1 Сервис для подготовки к олимпиадам**.

### **Вы также можете ознакомиться с функционалом API, перейдя на https://api.saslo.fun/docs.**

## Инструкция по установке / развёртыванию
1. Клонируем данный репозиторий
2. В файле .env укажите конфигурацию:

| Ключ | Описание | Значение |
|---|---|---|
| `DB_HOST` | IP адрес хоста и порт | **80.66.89.220:5432** |
| `DB_USER` | Имя пользователя | **postgres** |
| `DB_PASSWORD` | Пароль от базы данных | **chupep8saslo228** |
| `DB_NAME` | Название базы данных | **postgres** |
| `GIGACHAT_AUTHORIZATION_KEY` | API ключ для ИИ GigaChat | **API ключ** |
| `CLIENT_ID` | Client ID для ИИ GigaChat | **Client ID** |
| `SCOPE` | Scope для ИИ GigaChat | **GIGACHAT_API_PERS** |

3. Запустите бекенд
```shell
python -m venv venv
.\venv\Scripts\Activate.ps1 (в зависимости от оболочки командной строки)
pip install -r .\requirements.txt
python main.py
```

## Видеоролик
Тут Вы можете ознакомиться с [видеороликом](https://rutube.ru/video/private/fee7b78ef31f781b719625ba05e1d242/?p=ZeEoDeD9HPmBawh_zUjT9g), который показывает работу программы.
