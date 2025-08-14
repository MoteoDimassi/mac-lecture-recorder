#!/usr/bin/env python3
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich import print
from rich.prompt import Prompt, Confirm
from rich.table import Table
from tqdm import tqdm

# Load .env
load_dotenv()

app = typer.Typer(add_help_option=True, no_args_is_help=True)

STATE_DIR = Path("state")
SESSIONS_DIR = Path("sessions")
STATE_DIR.mkdir(parents=True, exist_ok=True)
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

PID_FILE = STATE_DIR / "ffmpeg.pid"
LOG_FILE = STATE_DIR / "ffmpeg.log"

DEFAULT_SR = 48000
DEFAULT_CHANNELS = 1

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_SUMMARY = os.getenv("OPENAI_MODEL_SUMMARY", "gpt-4o-mini")

def run_cmd(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

def list_avfoundation_devices() -> str:
    # ffmpeg prints device list in stderr/out with -list_devices true
    cmd = 'ffmpeg -f avfoundation -list_devices true -i ""'
    cp = run_cmd(cmd)
    return cp.stdout

def parse_audio_devices(ffmpeg_output: str):
    audio_section = False
    devices = []
    for line in ffmpeg_output.splitlines():
        if "AVFoundation audio devices:" in line:
            audio_section = True
            continue
        if "AVFoundation video devices:" in line and audio_section:
            break
        if audio_section:
            # Lines look like: [AVFoundation input device @ 0x...] [2] BlackHole 2ch
            m = re.search(r"\[(\d+)\]\s+(.+)$", line.strip())
            if m:
                idx = int(m.group(1))
                name = m.group(2).strip()
                devices.append((idx, name))
    return devices

@app.command()
def devices():
    """Показать список аудиоустройств (индексы для ffmpeg/avfoundation)."""
    out = list_avfoundation_devices()
    devs = parse_audio_devices(out)
    if not devs:
        print("[red]Не удалось получить список аудиоустройств. Убедитесь, что ffmpeg установлен.[/red]")
        print(out)
        raise typer.Exit(code=1)
    table = Table(title="AVFoundation audio devices")
    table.add_column("Индекс", justify="right")
    table.add_column("Название")
    for idx, name in devs:
        table.add_row(str(idx), name)
    print(table)
    print("\nВыберите тут ваш микрофон и BlackHole 2ch. Для записи используйте `--mic-index` и `--sys-index`.")

def is_recording() -> bool:
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return True
        except Exception:
            return False
    return False

def start_ffmpeg_record(mic_index: int, sys_index: int, out_path: Path, sample_rate: int = DEFAULT_SR, channels: int = DEFAULT_CHANNELS):
    """
    Запуск ffmpeg для записи **двух входов** (микрофон и BlackHole), микширование в один WAV.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Build ffmpeg command
    # - Вход 0: микрофон => ":mic_index"
    # - Вход 1: системный звук (BlackHole) => ":sys_index"
    # - Ресемплинг + выравнивание таймингов, amix, нормализация громкости
    # - Моно, 48kHz, PCM S16LE (совместимый WAV)
    cmd = f"""
ffmpeg -hide_banner -loglevel info \
-f avfoundation -i ":{mic_index}" \
-f avfoundation -i ":{sys_index}" \
-filter_complex "[0:a]aresample=async=1:first_pts=0,volume=1.0[a0];\
[1:a]aresample=async=1:first_pts=0,volume=1.0[a1];\
[a0][a1]amix=inputs=2:duration=longest:dropout_transition=3, dynaudnorm" \
-ac {channels} -ar {sample_rate} -c:a pcm_s16le -y "{out_path}"
""".strip()

    # Start as subprocess
    with open(LOG_FILE, "w") as lf:
        proc = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=lf, stderr=lf, text=True)
    PID_FILE.write_text(str(proc.pid))
    print(f"[green]Запись запущена.[/green] PID={proc.pid}\nЛог: {LOG_FILE}\nВыходной файл: {out_path}")
    print("Чтобы остановить: `python app.py stop` или отправьте SIGINT процессу ffmpeg.")

@app.command()
def record(
    mic_index: Optional[int] = typer.Option(None, help="Индекс микрофона из `devices`"),
    sys_index: Optional[int] = typer.Option(None, help="Индекс системного звука (BlackHole) из `devices`"),
    out: Path = typer.Option(SESSIONS_DIR / "lesson.wav", help="Путь для записи WAV"),
    sample_rate: int = typer.Option(DEFAULT_SR, help="Частота дискретизации"),
    channels: int = typer.Option(DEFAULT_CHANNELS, help="Каналы (1=mono, 2=stereo)"),
):
    """Начать запись (микрофон + системный звук)."""
    if is_recording():
        print("[yellow]Уже идёт запись. Остановите её командой `python app.py stop`.[/yellow]")
        raise typer.Exit()

    # If indexes not provided, ask interactively
    out_text = list_avfoundation_devices()
    devs = parse_audio_devices(out_text)
    if mic_index is None:
        print("\nСписок аудиоустройств:")
        for idx, name in devs:
            print(f"  {idx}: {name}")
        mic_index = int(Prompt.ask("Введите индекс МИКРОФОНА"))
    if sys_index is None:
        sys_index = int(Prompt.ask("Введите индекс СИСТЕМНОГО ЗВУКА (BlackHole 2ch)"))

    start_ffmpeg_record(mic_index, sys_index, out, sample_rate, channels)

@app.command()
def stop():
    """Остановить запись."""
    if not PID_FILE.exists():
        print("[yellow]PID не найден. Возможно, запись уже остановлена.[/yellow]")
        raise typer.Exit()

    try:
        pid = int(PID_FILE.read_text().strip())
    except Exception:
        print("[red]Не удалось прочитать PID.[/red]")
        PID_FILE.unlink(missing_ok=True)
        raise typer.Exit(code=1)

    try:
        # Попробуем корректно: отправим SIGINT
        print(f"Останавливаю ffmpeg (PID={pid})...")
        os.kill(pid, signal.SIGINT)
        time.sleep(1.0)
    except ProcessLookupError:
        print("[yellow]Процесс не найден.[/yellow]")
    finally:
        PID_FILE.unlink(missing_ok=True)

    print("[green]Запись остановлена.[/green]")

def ensure_file(p: Path):
    if not p.exists():
        print(f"[red]Файл не найден: {p}[/red]")
        raise typer.Exit(code=1)

@app.command()
def transcribe(
    audio: Path = typer.Option(..., help="Путь к WAV/MP3/M4A/…"),
    engine: str = typer.Option("local", help="local | openai"),
    language: str = typer.Option("ru", help="Язык (ru, en, auto=пусто)"),
    local_model: str = typer.Option("small", help="Модель faster-whisper: tiny/base/small/medium/large-v3"),
    chunking: bool = typer.Option(True, help="Чанкование для больших файлов (local)"),
):
    """Сделать транскрипт (локально через faster-whisper или через OpenAI). Создаёт .txt рядом с аудио."""
    ensure_file(audio)

    out_txt = Path(str(audio) + ".txt")

    if engine == "local":
        try:
            from faster_whisper import WhisperModel
        except Exception as e:
            print("[red]Не установлен faster-whisper. Установите зависимости: `pip install -r requirements.txt`[/red]")
            raise typer.Exit(code=1)

        print(f"Загружаю модель faster-whisper: {local_model} (это может занять время при первом запуске)")
        model = WhisperModel(local_model, device="auto", compute_type="int8")

        segments, info = model.transcribe(str(audio), language=None if not language or language=="auto" else language, vad_filter=True)
        with open(out_txt, "w") as f:
            for seg in segments:
                f.write(f"{seg.start:.2f}-{seg.end:.2f}: {seg.text.strip()}\n")
        print(f"[green]Транскрипт сохранён:[/green] {out_txt}")

    elif engine == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            print("[red]OPENAI_API_KEY не указан в .env[/red]")
            raise typer.Exit(code=1)
        try:
            from openai import OpenAI
        except Exception:
            print("[red]Библиотека openai не установлена. `pip install -r requirements.txt`[/red]")
            raise typer.Exit(code=1)

        client = OpenAI()
        print("Отправляю файл в OpenAI Whisper…")
        with open(audio, "rb") as f:
            # Модель whisper-1 исторически доступна, можно заменить при необходимости
            tr = client.audio.transcriptions.create(model="whisper-1", file=f, language=None if language=="auto" else language)
        with open(out_txt, "w") as fo:
            fo.write(tr.text)
        print(f"[green]Транскрипт сохранён:[/green] {out_txt}")
    else:
        print("[red]Неизвестный engine. Используйте local|openai[/red]")
        raise typer.Exit(code=1)

@app.command()
def summarize(
    transcript: Path = typer.Option(..., help="Путь к .txt"),
    student: str = typer.Option("", help="Имя ученика"),
    topic: str = typer.Option("", help="Тема занятия"),
    out_md: Optional[Path] = typer.Option(None, help="Куда сохранить Markdown"),
):
    """Сгенерировать конспект: итоги, ошибки, домашнее задание. Требуется OpenAI API."""
    ensure_file(transcript)
    if not os.getenv("OPENAI_API_KEY"):
        print("[red]OPENAI_API_KEY не указан в .env[/red]")
        raise typer.Exit(code=1)

    from openai import OpenAI
    client = OpenAI()

    with open(transcript, "r") as f:
        txt = f.read()

    system = "Ты — методичный преподаватель музыки и гитары. Кратко и структурно выделяешь итоги, ошибки ученика и домашнее задание. Пиши по-русски, лаконично и понятно."
    user = f"""Сформируй конспект по транскрипту занятия.

Контекст:
- Ученик: {student or "—"}
- Тема: {topic or "—"}

Требуется:
1) Итоги урока — 5–8 пунктов.
2) Ошибки и рекомендации — 5–10 пунктов (каждый пункт: [ошибка] → [как исправить]).
3) Домашнее задание — чёткий чек-лист с пунктами и целями, отметь \\"Домашнее задание\\" заголовком.

Транскрипт (фрагменты): 
{txt[:15000]}
"""
    print("Генерирую конспект через OpenAI…")
    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL_SUMMARY", "gpt-4o-mini"),
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
        temperature=0.3,
    )
    md = resp.choices[0].message.content.strip()

    if out_md is None:
        out_md = Path(str(transcript).replace(".txt", ".md"))
    with open(out_md, "w") as f:
        f.write(f"# Конспект занятия\n\n**Ученик:** {student or '—'}  \n**Тема:** {topic or '—'}\n\n{md}\n")
    print(f"[green]Markdown сохранён:[/green] {out_md}")

    # Также сохраним JSON-структуру (приблизительное извлечение разделов)
    data = {"student": student, "topic": topic, "markdown": md}
    with open(Path(str(transcript).replace(".txt", ".json")), "w") as jf:
        import json
        json.dump(data, jf, ensure_ascii=False, indent=2)
    print(f"[green]JSON сохранён:[/green] {Path(str(transcript).replace('.txt', '.json'))}")

@app.command()
def session(
    student: str = typer.Option("", help="Имя ученика"),
    topic: str = typer.Option("", help="Тема урока"),
    engine: str = typer.Option("openai", help="Движок транскрипции: local|openai"),
    language: str = typer.Option("ru", help="Язык речи: ru|en|auto"),
    mic_index: Optional[int] = typer.Option(None, help="Индекс микрофона из `devices`"),
    sys_index: Optional[int] = typer.Option(None, help="Индекс системного звука (BlackHole) из `devices`"),
):
    """
    Полный цикл: запись -> стоп -> транскрипция -> конспект.
    Нажмите Enter, чтобы остановить запись.
    """
    # Выходной путь
    ts = time.strftime("%Y%m%d-%H%M%S")
    out_wav = SESSIONS_DIR / f"session-{ts}.wav"

    # Если не заданы индексы — спросим
    if mic_index is None or sys_index is None:
        out_text = list_avfoundation_devices()
        devs = parse_audio_devices(out_text)
        print("\nСписок аудиоустройств:")
        for idx, name in devs:
            print(f"  {idx}: {name}")
        if mic_index is None:
            mic_index = int(Prompt.ask("Введите индекс МИКРОФОНА"))
        if sys_index is None:
            sys_index = int(Prompt.ask("Введите индекс СИСТЕМНОГО ЗВУКА (BlackHole 2ch)"))

    # Старт записи
    start_ffmpeg_record(mic_index, sys_index, out_wav)

    # Ждём Enter
    input("\n[Enter] чтобы остановить запись…\n")
    # Останавливаем
    stop()

    # Транскрипция
    typer.echo("\n== Транскрипция ==")
    ctx = typer.get_current_context()
    ctx.invoke(transcribe, audio=out_wav, engine=engine, language=language)

    # Конспект
    typer.echo("\n== Конспект ==")
    ctx.invoke(summarize, transcript=Path(str(out_wav) + ".txt"), student=student, topic=topic)

@app.command()
def push_notion(
    md: Path = typer.Option(..., help="Файл Markdown с конспектом"),
    title: str = typer.Option("", help="Заголовок страницы (по умолчанию имя файла)"),
):
    """Отправить конспект в Notion (требует NOTION_TOKEN и NOTION_DATABASE_ID в .env)."""
    def ensure_file(p: Path):
        if not p.exists():
            print(f"[red]Файл не найден: {p}[/red]")
            raise typer.Exit(code=1)

    ensure_file(md)
    NOTION_TOKEN = os.getenv("NOTION_TOKEN")
    NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")
    if not NOTION_TOKEN or not NOTION_DATABASE_ID:
        print("[red]Заполните NOTION_TOKEN и NOTION_DATABASE_ID в .env[/red]")
        raise typer.Exit(code=1)

    from notion_client import Client
    client = Client(auth=NOTION_TOKEN)

    with open(md, "r") as f:
        content = f.read()

    if not title:
        title = md.stem

    # Простейшее создание страницы с блоком текста
    page = client.pages.create(
        parent={"database_id": NOTION_DATABASE_ID},
        properties={
            "Name": {"title": [{"text": {"content": title}}]}
        },
        children=[
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": content}}]}}
        ]
    )
    print("[green]Отправлено в Notion.[/green] Page ID:", page.get("id"))

if __name__ == "__main__":
    app()
