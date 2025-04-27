import streamlit as st
import ollama
import whisper
import tempfile
import openai
from openai import OpenAI
import os
import sqlite3
import uuid
import subprocess
import pandas as pd
import torch
import platform
import re
import gdown
import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Путь к FFmpeg
ffmpeg_path = r"C:\Program Files\FFmpeg\bin\ffmpeg.exe"

# Установка пути к FFmpeg
os.environ['PATH'] += os.pathsep + os.path.dirname(ffmpeg_path)

# Загрузка модели Whisper для транскрибации
model = whisper.load_model("base")

client = OpenAI(api_key='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')

# Инициализация базы данных
def init_db():
    db_path = os.path.join(os.getcwd(), 'audio_insights.db')
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Таблица инсайтов
    c.execute('''CREATE TABLE IF NOT EXISTS insights
                 (id TEXT PRIMARY KEY,
                  audio_name TEXT,
                  transcription TEXT,
                  insights TEXT,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    # Таблица тестов
    c.execute('''CREATE TABLE IF NOT EXISTS quizzes
                 (id TEXT PRIMARY KEY,
                  audio_name TEXT,
                  questions TEXT,
                  answers TEXT)''')

    # Таблица результатов тестов
    c.execute('''CREATE TABLE IF NOT EXISTS quiz_results
                 (id TEXT PRIMARY KEY,
                  quiz_id TEXT,
                  user_answers TEXT,
                  correct_answers TEXT,
                  score INTEGER)''')

    conn.commit()
    conn.close()


# Вызов инициализации базы данных при запуске
init_db()


def transcribe_audio(audio_path):
    """Транскрибация аудио с помощью Whisper"""
    result = model.transcribe(audio_path, fp16=False)
    return result['text']


def generate_insights(text):
    """GPT Powered Edu assistant"""
    try:
        # Store the original platform.platform function
        original_platform_func = platform.platform

        # Replace with a dummy function to avoid the issue
        platform.platform = lambda: "Windows"

        response = client.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=[
                {
                    'role': 'system',
                    'content': 'Ты эксперт по извлечению ключевых инсайтов из текста.'
                },
                {
                    'role': 'user',
                    'content': f'Извлеки ключевые инсайты из следующего текста: {text}'
                }
            ]
        )

        # Restore the original function
        platform.platform = original_platform_func

        # Сохранение инсайтов в базу данных
        insights = response.choices[0].message.content
        conn = sqlite3.connect('audio_insights.db')
        c = conn.cursor()
        insight_id = str(uuid.uuid4())
        c.execute("INSERT INTO insights (id, transcription, insights) VALUES (?, ?, ?)",
                  (insight_id, text, insights))
        conn.commit()
        conn.close()

        return insights

    except Exception as e:
        # Restore the original function in case of error
        platform.platform = original_platform_func
        raise e


def generate_quiz(text):
    """Генерация теста на основе текста"""
    response = client.chat.completions.create(
        model='gpt-3.5-turbo',
        messages=[
            {
                'role': 'system',
                'content': 'Ты эксперт по созданию образовательных тестов.'
            },
            {
                'role': 'user',
                'content': f'Создай 5 многовариантных вопросов с правильными ответами по следующему тексту: {text}'
            }
        ]
    )

    # Сохранение теста в базу данных
    quiz_text = response.choices[0].message.content
    conn = sqlite3.connect('audio_insights.db')
    c = conn.cursor()
    quiz_id = str(uuid.uuid4())
    c.execute("INSERT INTO quizzes (id, questions) VALUES (?, ?)",
              (quiz_id, quiz_text))
    conn.commit()
    conn.close()

    return quiz_id, quiz_text
def search_in_text(text, query):
    """Расширенный поиск в тексте с поддержкой разных языков"""
    if not text or not query:
        return []

    # Преобразуем текст и запрос в нижний регистр
    text_lower = text.lower()
    query_lower = query.lower()

    # Используем более продвинутый поиск
    results = []
    start_index = 0

    # Разбиваем текст на предложения с учетом многоязычности
    sentences = re.split(r'[.!?]', text)

    for sentence in sentences:
        # Проверяем наличие запроса в предложении
        if query_lower in sentence.lower().strip():
            # Очищаем предложение от лишних пробелов
            clean_sentence = sentence.strip()

            # Добавляем предложение, если оно еще не было добавлено
            if clean_sentence and clean_sentence not in results:
                results.append(clean_sentence)

    return results



def download_video_from_drive(drive_link):
    """Загрузка видео с Google Диска по ссылке"""
    match = re.search(r'drive.google.com/file/d/(.*?)/', drive_link)
    if not match:
        return None, "Неверная ссылка на Google Диск."

    file_id = match.group(1)
    download_url = f"https://drive.google.com/uc?id={file_id}"

    temp_video_path = os.path.join(tempfile.gettempdir(), f"{file_id}.mp4")
    try:
        gdown.download(download_url, temp_video_path, quiet=False)
        return temp_video_path, None
    except Exception as e:
        return None, f"Ошибка загрузки: {str(e)}"

def extract_audio(video_path):
    """Извлекает аудио из видео"""
    audio_path = video_path.replace(".mp4", ".wav")
    command = [ffmpeg_path, "-i", video_path, "-q:a", "0", "-map", "a", audio_path]
    subprocess.run(command)
    return audio_path


def main():
    st.title('EduTube Ollama powered')
    # Боковое меню
    menu = st.sidebar.radio("Выберите раздел",
                            ["Загрузка Аудио",
                             "Сохраненные Инсайты",
                             "Пройти Тест",
                             "Поиск в Тексте"])

    if menu == "Загрузка Аудио":
        st.header("Выберите способ загрузки:")

        upload_option = st.radio("Источник загрузки", ("Локальный файл", "Ссылка на Google Диск"))

        video_path = None
        error = None
        uploaded_file = None
        drive_link = None

        if upload_option == "Локальный файл":
            uploaded_file = st.file_uploader("Загрузите видеофайл", type=['mp4', 'mov', 'avi'], key="local_upload")
            if uploaded_file is not None:
                # Сохраняем загруженный файл во временную папку
                temp_path = os.path.join(tempfile.gettempdir(), uploaded_file.name)
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.read())
                video_path = temp_path
                st.success(f"Файл загружен: {uploaded_file.name}")

        elif upload_option == "Ссылка на Google Диск":
            drive_link = st.text_input("Введите ссылку на видео с Google Диска:", key="drive_link")
            if st.button("Скачать видео", key="download_button"):
                if drive_link:
                    video_path, error = download_video_from_drive(drive_link)
                    if error:
                        st.error(error)
                    else:
                        st.success(f"Видео скачано: {video_path}")

                    # Извлекаем аудио
                    try:
                        audio_path = extract_audio(video_path)
                        st.success(f"Аудио извлечено: {audio_path}")

                        # Транскрибация
                        transcription = transcribe_audio(audio_path)
                        st.write("Транскрипция:", transcription)

                        # Генерация инсайтов
                        insights = generate_insights(transcription)
                        st.write("Ключевые инсайты:", insights)
                    except Exception as e:
                        st.error(f"Ошибка обработки: {str(e)}")

        if uploaded_file is not None:
            # Сохранение временного файла
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as temp_file:
                temp_file.write(uploaded_file.getvalue())
                temp_file_path = temp_file.name

            # Транскрибация
            st.subheader("📝 Транскрипция")
            with st.spinner('Транскрибация аудио...'):
                transcription = transcribe_audio(temp_file_path)
            st.text_area("Расшифрованный текст:", transcription, height=200)

            # Колонки для функций
            col1, col2 = st.columns(2)

            with col1:
                if st.button('Сгенерировать инсайты'):
                    with st.spinner('Генерация инсайтов...'):
                        insights = generate_insights(transcription)
                    st.success("Инсайты сохранены!")

            with col2:
                if st.button('Создать тест'):
                    with st.spinner('Создание теста...'):
                        quiz_id, quiz_text = generate_quiz(transcription)
                    st.success(f"Тест создан. ID: {quiz_id}")

            # Удаление временного файла
            os.unlink(temp_file_path)

    elif menu == "Сохраненные Инсайты":
        st.subheader("💡 Сохраненные Инсайты")
        conn = sqlite3.connect('audio_insights.db')
        insights = pd.read_sql_query("SELECT * FROM insights ORDER BY created_at DESC", conn)
        conn.close()

        for _, insight in insights.iterrows():
            with st.expander(f"Инсайт"):
                st.write(insight['insights'])

    elif menu == "Пройти Тест":
        st.subheader("❓ Доступные Тесты")
        conn = sqlite3.connect('audio_insights.db')
        quizzes = pd.read_sql_query("SELECT * FROM quizzes", conn)
        conn.close()

        selected_quiz = st.selectbox("Выберите тест", quizzes['id'])

        if selected_quiz:
            conn = sqlite3.connect('audio_insights.db')
            quiz = pd.read_sql_query(f"SELECT * FROM quizzes WHERE id = '{selected_quiz}'", conn)
            conn.close()

            st.write(quiz['questions'].values[0])



    elif menu == "Поиск в Тексте":

        st.subheader("🔍 Поиск в Транскрипции")

        # Получаем все транскрипции

        conn = sqlite3.connect('audio_insights.db')

        transcriptions = pd.read_sql_query("SELECT transcription FROM insights", conn)

        conn.close()

        # Проверяем, есть ли транскрипции

        if transcriptions.empty:

            st.warning("Нет сохраненных транскрипций. Сначала загрузите аудио.")

        else:

            # Объединяем все транскрипции в один текст

            full_text = " ".join(transcriptions['transcription'])

            query = st.text_input("Введите текст для поиска")

            if query:

                results = search_in_text(full_text, query)

                if results:

                    st.write(f"Найдено совпадений: {len(results)}")

                    for i, result in enumerate(results, 1):
                        st.text(f"{i}. {result}")

                else:

                    st.info("Совпадений не найдено.")




if __name__ == "__main__":
    main()
