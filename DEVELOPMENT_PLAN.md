# План разработки Streamlit интерфейса для Mac Lecture Recorder

## Общее описание
Создание единого диктофоноподобного интерфейса с интеграцией AI-функций для записи занятий, транскрипции и генерации конспектов.

## Структура проекта
```
mac-lecture-recorder/
├── app.py              # Существующее консольное приложение
├── streamlit_app.py    # Новый Streamlit интерфейс
├── requirements_gui.txt # Дополнительные зависимости для GUI
└── pages/             # Дополнительные страницы (если потребуется)
```

## Основной файл: streamlit_app.py

### 1. Импорты и настройка
```python
import streamlit as st
import time
import os
from pathlib import Path
from app import (
    list_avfoundation_devices, 
    parse_audio_devices, 
    record, 
    stop, 
    transcribe, 
    summarize
)
```

### 2. Основной layout приложения

#### Верхняя панель управления:
```python
# Статус и управление
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    record_button = st.button("⏺️ Запись", key="record")
    stop_button = st.button("⏹️ Стоп", key="stop")
with col2:
    status_indicator = st.empty()  # "Готов к записи" / "Запись..." / "Обработка..."
with col3:
    st.progress(0)  # Прогресс записи
```

#### Основная область: Информация о сессии
```python
# Конфигурация сессии
st.subheader("Информация о занятии")
student_name = st.text_input("Имя ученика", "")
lesson_topic = st.text_input("Тема занятия", "")

# Выбор устройств
st.subheader("Аудиоустройства")
ffmpeg_output = list_avfoundation_devices()
devices_list = parse_audio_devices(ffmpeg_output)

mic_options = {f"{name} ({idx})": idx for idx, name in devices_list}
sys_options = mic_options.copy()

selected_mic = st.selectbox("🎤 Микрофон", list(mic_options.keys()))
selected_sys = st.selectbox("🔊 Системный звук", list(sys_options.keys()))
```

#### Центральная область: Реал-тайм транскрипция
```python
# Транскрипция в реальном времени
st.subheader("Транскрипция")
transcript_area = st.empty()
transcript_text = st.text_area("", height=200, key="transcript")

# Прогресс обработки
processing_status = st.empty()
```

#### Нижняя область: Конспект и подсказки
```python
# Конспект
st.subheader("Конспект занятия")
summary_area = st.empty()

# Контекстные подсказки
st.subheader("Подсказки")
hints_area = st.empty()
```

## 3. Функциональные компоненты

### A. Управление записью:
```python
def start_recording():
    mic_index = mic_options[selected_mic]
    sys_index = sys_options[selected_sys]
    # Вызов существующей функции из app.py
    record(mic_index=mic_index, sys_index=sys_index, 
           out=f"sessions/session_{timestamp}.wav")
    st.session_state.is_recording = True
    st.session_state.start_time = time.time()

def stop_recording():
    stop()  # Вызов существующей функции
    st.session_state.is_recording = False
    # Автоматический запуск транскрипции
    process_recording()
```

### B. Транскрипция в реальном времени:
```python
def process_recording():
    # Показываем прогресс
    processing_status.info("Обработка записи...")
    
    # Транскрибация
    audio_file = f"sessions/session_{timestamp}.wav"
    transcribe(audio=audio_file, engine="local", language="ru")
    
    # Чтение и отображение транскрипта
    with open(f"{audio_file}.txt", "r") as f:
        transcript_content = f.read()
        transcript_area.text_area("Транскрипт", transcript_content, height=200)
    
    # Генерация конспекта
    generate_summary(transcript_content)
```

### C. Генерация конспекта:
```python
def generate_summary(transcript_text):
    # Вызов функции из app.py
    summarize(transcript=Path(f"sessions/session_{timestamp}.wav.txt"),
              student=student_name,
              topic=lesson_topic)
    
    # Отображение конспекта
    with open(f"sessions/session_{timestamp}.wav.md", "r") as f:
        summary_content = f.read()
        summary_area.markdown(summary_content)
```

### D. Контекстные подсказки:
```python
def generate_hints(topic, current_transcript):
    # Использование OpenAI для генерации подсказок
    hints_prompt = f"""
    Тема занятия: {topic}
    Текущий диалог: {current_transcript[-1000:]}  # Последние 1000 символов
    
    Сгенерируй 3-5 полезных подсказок для преподавателя:
    - Что можно улучшить в объяснении
    - На что обратить внимание
    - Следующие шаги в обучении
    """
    # Вызов OpenAI API
    hints = call_openai_api(hints_prompt)
    hints_area.markdown(hints)
```

## 4. State management
```python
# Инициализация состояния
if 'is_recording' not in st.session_state:
    st.session_state.is_recording = False
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
if 'transcript' not in st.session_state:
    st.session_state.transcript = ""
```

## 5. Автоматические обновления
```python
# Периодическое обновление транскрипции (каждые 5 секунд во время записи)
if st.session_state.is_recording:
    st.experimental_rerun()
```

## 6. Дополнительные страницы (в боковом меню):
```python
# Боковое меню
st.sidebar.title("Навигация")
page = st.sidebar.radio("Выберите раздел", 
                       ["Диктофон", "История", "Настройки", "Экспорт"])

if page == "История":
    show_history()
elif page == "Настройки":
    show_settings()
elif page == "Экспорт":
    show_export()
```

## 7. Обработка ошибок и пользовательский опыт:
```python
try:
    if record_button:
        start_recording()
        status_indicator.success("Запись начата!")
except Exception as e:
    st.error(f"Ошибка записи: {str(e)}")
    st.session_state.is_recording = False
```

## Этапы реализации

### Этап 1: Базовый интерфейс (1-2 дня)
- Создание основного layout
- Интеграция с существующими функциями app.py
- Базовое управление записью/стоп
- Отображение устройств

### Этап 2: Транскрипция (2-3 дня)
- Интеграция транскрипции
- Отображение результатов
- Прогресс-бары и статусы

### Этап 3: Конспекты и подсказки (2-3 дня)
- Генерация конспектов
- Контекстные подсказки
- Экспорт результатов

### Этап 4: Улучшения (1-2 дня)
- Стилизация интерфейса
- Обработка ошибок
- Документация

## Запуск приложения
```bash
streamlit run streamlit_app.py
```

## Требования к зависимостям
Добавить в requirements_gui.txt:
```
streamlit>=1.29.0
