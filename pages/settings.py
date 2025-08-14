#!/usr/bin/env python3
"""
Страница настроек для Mac Lecture Recorder
"""

import streamlit as st
import os
from pathlib import Path

def main():
    st.set_page_config(
        page_title="Настройки", 
        page_icon="⚙️",
        layout="wide"
    )
    
    st.title("⚙️ Настройки")
    st.markdown("---")
    
    # Загружаем текущие настройки из .env если есть
    env_file = Path(".env")
    env_vars = {}
    
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    key, value = line.strip().split("=", 1)
                    env_vars[key] = value
    
    # Форма настроек
    st.subheader("🔑 API Ключи")
    
    openai_key = st.text_input(
        "OpenAI API Key", 
        value=env_vars.get("OPENAI_API_KEY", ""),
        type="password",
        help="Для облачной транскрипции и генерации конспектов"
    )
    
    openai_model = st.text_input(
        "Модель OpenAI", 
        value=env_vars.get("OPENAI_MODEL_SUMMARY", "gpt-4o-mini"),
        help="Модель для генерации конспектов"
    )
    
    st.subheader("📝 Интеграция с Notion")
    
    notion_token = st.text_input(
        "Notion Token", 
        value=env_vars.get("NOTION_TOKEN", ""),
        type="password",
        help="Для отправки конспектов в Notion"
    )
    
    notion_db_id = st.text_input(
        "Notion Database ID", 
        value=env_vars.get("NOTION_DATABASE_ID", ""),
        help="ID базы данных в Notion"
    )
    
    st.subheader("🎵 Настройки записи")
    
    sample_rate = st.selectbox(
        "Частота дискретизации", 
        options=[16000, 22050, 44100, 48000],
        index=3,  # 48000 по умолчанию
        help="Частота дискретизации аудио"
    )
    
    channels = st.selectbox(
        "Каналы", 
        options=[1, 2],
        index=0,  # mono по умолчанию
        format_func=lambda x: "Моно" if x == 1 else "Стерео"
    )
    
    # Кнопка сохранения
    if st.button("💾 Сохранить настройки", type="primary"):
        # Создаем/обновляем .env файл
        env_content = f"""OPENAI_API_KEY={openai_key}
OPENAI_MODEL_SUMMARY={openai_model}
NOTION_TOKEN={notion_token}
NOTION_DATABASE_ID={notion_db_id}
"""
        
        with open(".env", "w") as f:
            f.write(env_content)
        
        st.success("✅ Настройки сохранены!")
        st.info("Перезапустите приложение для применения изменений")
    
    # Информация о текущих настройках
    st.markdown("---")
    st.subheader("ℹ️ Текущие настройки")
    
    if env_file.exists():
        with open(".env", "r") as f:
            current_env = f.read()
        st.code(current_env)
    else:
        st.info("Файл .env не найден. Настройки будут сохранены при первом сохранении.")

if __name__ == "__main__":
    main()