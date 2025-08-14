# Mac Lecture Recorder

## Описание
Мощный инструмент для записи учебных занятий, конференций и других образовательных мероприятий с возможностью автоматической транскрипции и генерации конспектов.

## Основные функции
- **Запись аудио** - Одновременная запись микрофона и системного звука
- **Транскрипция** - Локальная (faster-whisper) и облачная (OpenAI Whisper)
- **Генерация конспектов** - Структурированные конспекты через OpenAI
- **Интеграция с Notion** - Отправка конспектов в Notion
- **Полный цикл** - Запись → Транскрипция → Конспект

## Установка
```bash
pip install -r requirements.txt
```

Для GUI интерфейса:
```bash
pip install -r requirements_gui.txt
```

## Использование

### Консольный интерфейс
```bash
# Показать доступные устройства
python app.py devices

# Запись занятия
python app.py session --student "Иван Иванов" --topic "Основы гитары"

# Транскрипция
python app.py transcribe --audio sessions/session-20250101-120000.wav

# Генерация конспекта
python app.py summarize --transcript sessions/session-20250101-120000.wav.txt
```

### Графический интерфейс
```bash
streamlit run streamlit_app.py
```

## Конфигурация
Создайте файл `.env` на основе `.env.example`:
- `OPENAI_API_KEY` - для облачных функций
- `NOTION_TOKEN` и `NOTION_DATABASE_ID` - для интеграции с Notion

## Требования
- macOS (AVFoundation framework)
- Python 3.8+
- ffmpeg
- BlackHole 2ch (для записи системного звука)