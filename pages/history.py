#!/usr/bin/env python3
"""
Страница истории записей для Mac Lecture Recorder
"""

import streamlit as st
import os
from pathlib import Path
import time

def main():
    st.set_page_config(
        page_title="История записей", 
        page_icon="📚",
        layout="wide"
    )
    
    st.title("📚 История записей")
    st.markdown("---")
    
    # Создаем директорию sessions если её нет
    sessions_dir = Path("sessions")
    sessions_dir.mkdir(exist_ok=True)
    
    # Получаем список сессий
    sessions = []
    for file in sessions_dir.glob("session-*.wav"):
        session_name = file.stem
        wav_file = file
        txt_file = file.with_suffix('.wav.txt')
        md_file = file.with_suffix('.wav.md')
        
        # Получаем время создания
        creation_time = file.stat().st_mtime
        creation_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(creation_time))
        
        sessions.append({
            'name': session_name,
            'wav': wav_file,
            'txt': txt_file,
            'md': md_file,
            'time': creation_str,
            'size': file.stat().st_size
        })
    
    # Сортируем по времени (новые первыми)
    sessions.sort(key=lambda x: x['time'], reverse=True)
    
    if not sessions:
        st.info("Пока нет записей. Начните новую запись на главной странице.")
        return
    
    # Отображаем список сессий
    for session in sessions:
        with st.expander(f"📝 {session['name']} - {session['time']}", expanded=False):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.write(f"**Время:** {session['time']}")
                size_mb = session['size'] / (1024 * 1024)
                st.write(f"**Размер:** {size_mb:.1f} MB")
            
            with col2:
                if session['txt'].exists():
                    st.success("✅ Транскрипт готов")
                else:
                    st.warning("⏳ Нет транскрипта")
                
                if session['md'].exists():
                    st.success("✅ Конспект готов")
                else:
                    st.warning("⏳ Нет конспекта")
            
            with col3:
                if session['wav'].exists():
                    if st.button("📥 Скачать WAV", key=f"wav_{session['name']}"):
                        with open(session['wav'], "rb") as f:
                            st.download_button(
                                label="Скачать аудио",
                                data=f.read(),
                                file_name=f"{session['name']}.wav",
                                mime="audio/wav"
                            )
                
                if session['txt'].exists():
                    if st.button("📄 Скачать TXT", key=f"txt_{session['name']}"):
                        with open(session['txt'], "r") as f:
                            st.download_button(
                                label="Скачать транскрипт",
                                data=f.read(),
                                file_name=f"{session['name']}.txt",
                                mime="text/plain"
                            )
                
                if session['md'].exists():
                    if st.button("📑 Скачать MD", key=f"md_{session['name']}"):
                        with open(session['md'], "r") as f:
                            st.download_button(
                                label="Скачать конспект",
                                data=f.read(),
                                file_name=f"{session['name']}.md",
                                mime="text/markdown"
                            )
            
            # Показываем содержимое файлов
            if session['txt'].exists():
                st.subheader("Транскрипт:")
                with open(session['txt'], "r") as f:
                    transcript_content = f.read()
                    st.text_area("", transcript_content, height=150, key=f"transcript_{session['name']}")
            
            if session['md'].exists():
                st.subheader("Конспект:")
                with open(session['md'], "r") as f:
                    summary_content = f.read()
                    st.markdown(summary_content)

if __name__ == "__main__":
    main()
