#!/usr/bin/env python3
"""
Streamlit GUI для Mac Lecture Recorder
Единый диктофоноподобный интерфейс с AI-функциями
"""

import streamlit as st
import time
import os
import threading
from pathlib import Path

# Импортируем функции из основного приложения
from app import (
    list_avfoundation_devices, 
    parse_audio_devices, 
    record as app_record, 
    stop as app_stop, 
    transcribe as app_transcribe, 
    summarize as app_summarize
)

def show_history():
    """Отображение истории записей"""
    try:
        from pages.history import main as history_main
        history_main()
    except ImportError:
        st.error("Страница истории не найдена")
    except Exception as e:
        st.error(f"Ошибка загрузки истории: {str(e)}")

def show_settings():
    """Отображение настроек"""
    try:
        from pages.settings import main as settings_main
        settings_main()
    except ImportError:
        st.error("Страница настроек не найдена")
    except Exception as e:
        st.error(f"Ошибка загрузки настроек: {str(e)}")

def main():
    st.set_page_config(
        page_title="Mac Lecture Recorder", 
        page_icon="🎤",
        layout="wide"
    )
    
    # Навигация
    st.sidebar.title("🎤 Mac Lecture Recorder")
    page = st.sidebar.radio(
        "Навигация",
        ["Диктофон", "История", "Настройки"],
        index=0
    )
    
    if page == "История":
        show_history()
        return
    elif page == "Настройки":
        show_settings()
        return
    
    # Главная страница - Диктофон
    st.title("🎤 Mac Lecture Recorder")
    st.markdown("---")
    
    # Инициализация состояния
    if 'is_recording' not in st.session_state:
        st.session_state.is_recording = False
    if 'start_time' not in st.session_state:
        st.session_state.start_time = None
    if 'current_session' not in st.session_state:
        st.session_state.current_session = None
    if 'processing' not in st.session_state:
        st.session_state.processing = False
    
    # Верхняя панель управления
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        record_button = st.button("⏺️ Запись", key="record", 
                                disabled=st.session_state.is_recording or st.session_state.processing)
        stop_button = st.button("⏹️ Стоп", key="stop", 
                              disabled=not st.session_state.is_recording)
    with col2:
        if st.session_state.processing:
            status_text = "Обработка..."
        elif st.session_state.is_recording:
            status_text = "Запись активна..."
        else:
            status_text = "Готов к записи"
        st.info(status_text)
    with col3:
        if st.session_state.is_recording and st.session_state.start_time:
            elapsed = time.time() - st.session_state.start_time
            st.progress(min(elapsed / 3600, 1.0))  # Прогресс (max 1 час)
            st.caption(f"⏱️ {time.strftime('%H:%M:%S', time.gmtime(elapsed))}")
        elif st.session_state.processing:
            st.caption("Обработка результатов...")
    
    st.markdown("---")
    
    # Основная область
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Конфигурация сессии
        st.subheader("Информация о занятии")
        student_name = st.text_input("Имя ученика", "")
        lesson_topic = st.text_input("Тема занятия", "")
        
        # Выбор устройств
        st.subheader("Аудиоустройства")
        try:
            ffmpeg_output = list_avfoundation_devices()
            devices_list = parse_audio_devices(ffmpeg_output)
            
            if devices_list:
                mic_options = {f"{name} ({idx})": idx for idx, name in devices_list}
                sys_options = mic_options.copy()
                
                selected_mic = st.selectbox("🎤 Микрофон", list(mic_options.keys()))
                selected_sys = st.selectbox("🔊 Системный звук", list(sys_options.keys()))
                
                if record_button:
                    start_recording(mic_options[selected_mic], sys_options[selected_sys], 
                                  student_name, lesson_topic)
                
                if stop_button:
                    stop_recording()
            else:
                st.error("Не удалось получить список аудиоустройств")
                st.code(ffmpeg_output)
        except Exception as e:
            st.error(f"Ошибка получения устройств: {str(e)}")
    
    with col2:
        # Транскрипция и конспект
        st.subheader("Результаты")
        
        # Транскрипция
        st.markdown("**Транскрипция:**")
        transcript_area = st.empty()
        
        # Конспект
        st.markdown("**Конспект:**")
        summary_area = st.empty()
        
        # Если есть текущая сессия, показываем результаты
        if st.session_state.current_session:
            session_file = st.session_state.current_session
            transcript_file = f"{session_file}.txt"
            summary_file = f"{session_file}.md"
            
            # Показываем транскрипт
            if os.path.exists(transcript_file):
                with open(transcript_file, "r") as f:
                    transcript_content = f.read()
                    transcript_area.text_area("", transcript_content, height=200, key="transcript_display")
            
            # Показываем конспект
            if os.path.exists(summary_file):
                with open(summary_file, "r") as f:
                    summary_content = f.read()
                    summary_area.markdown(summary_content)

def start_recording(mic_index, sys_index, student_name, lesson_topic):
    """Начать запись"""
    try:
        # Создаем имя файла с временной меткой
        timestamp = time.strftime("%Y%m%d-%H%M%S")
        session_file = f"sessions/session-{timestamp}"
        
        st.session_state.current_session = session_file
        st.session_state.start_time = time.time()
        st.session_state.is_recording = True
        
        # Запуск записи в отдельном потоке
        def record_thread():
            try:
                app_record(
                    mic_index=mic_index,
                    sys_index=sys_index,
                    out=Path(f"{session_file}.wav")
                )
            except Exception as e:
                st.error(f"Ошибка записи: {str(e)}")
        
        thread = threading.Thread(target=record_thread)
        thread.daemon = True
        thread.start()
        
        st.success(f"Запись начата: {session_file}.wav")
        
    except Exception as e:
        st.error(f"Ошибка начала записи: {str(e)}")

def stop_recording():
    """Остановить запись и начать обработку"""
    try:
        st.session_state.is_recording = False
        st.session_state.processing = True
        
        # Остановка записи
        app_stop()
        
        if st.session_state.current_session:
            # Начинаем обработку в отдельном потоке
            def process_thread():
                try:
                    session_file = st.session_state.current_session
                    wav_file = f"{session_file}.wav"
                    
                    # Транскрипция
                    app_transcribe(
                        audio=Path(wav_file),
                        engine="local",
                        language="ru"
                    )
                    
                    # Генерация конспекта
                    app_summarize(
                        transcript=Path(f"{session_file}.txt"),
                        student="",  # Пока не передаем, можно добавить позже
                        topic="",    # Пока не передаем, можно добавить позже
                        out_md=Path(f"{session_file}.md")
                    )
                    
                    st.session_state.processing = False
                    
                except Exception as e:
                    st.session_state.processing = False
                    st.error(f"Ошибка обработки: {str(e)}")
            
            thread = threading.Thread(target=process_thread)
            thread.daemon = True
            thread.start()
        
        st.success("Запись остановлена, начинается обработка...")
        
    except Exception as e:
        st.session_state.processing = False
        st.error(f"Ошибка остановки записи: {str(e)}")

if __name__ == "__main__":
    main()
