from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from contextlib import contextmanager
import requests

# Загрузка переменных окружения
load_dotenv()

app = FastAPI(title="Сайт репетитора")


# Конфигурация
class Config:
    STATIC_DIR = "static"
    TEMPLATES_DIR = "templates"
    DB_CONFIG = {
        'host': 'localhost',
        'user': 'postgres',
        'password': 'cyu78673',
        'port': '5432',
        'dbname': 'postgres'
    }
    BOT_TOKEN = "7553871276:AAGi3eqORXtj7pM20--SMr33qMtb_8EVy60"
    ADMIN_CHAT_ID = "798402907"


# Создание директорий
os.makedirs(Config.TEMPLATES_DIR, exist_ok=True)
os.makedirs(Config.STATIC_DIR, exist_ok=True)

# Монтирование статических файлов
app.mount("/static", StaticFiles(directory=Config.STATIC_DIR), name="static")
templates = Jinja2Templates(directory=Config.TEMPLATES_DIR)

# Настройки CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Модель данных
class BookingRequest(BaseModel):
    name: str
    email: str
    phone: str
    lesson_type: str
    message: str = None


# Подключение к БД с контекстным менеджером
@contextmanager
def get_db_cursor():
    conn = None
    cursor = None
    try:
        conn = psycopg2.connect(
            cursor_factory=RealDictCursor,
            **Config.DB_CONFIG
        )
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        )
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# Проверка существования таблицы при старте
def check_db_table():
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS booking_requests (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    email VARCHAR(100) NOT NULL,
                    phone VARCHAR(20) NOT NULL,
                    lesson_type VARCHAR(50) NOT NULL,
                    message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status VARCHAR(20) DEFAULT 'new'
                )
            """)
    except Exception as e:
        print(f"Ошибка при создании таблицы: {str(e)}")


# Функция отправки в Telegram
def send_telegram_notification(booking: BookingRequest):
    message = f"""
    📢 Новая заявка на занятие!

    👤 Имя: {booking.name}
    📧 Email: {booking.email}
    📞 Телефон: {booking.phone}
    🎓 Тип занятия: {booking.lesson_type}
    📝 Сообщение: {booking.message or 'Нет дополнительного сообщения'}
    """

    url = f"https://api.telegram.org/bot{Config.BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": Config.ADMIN_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"Ошибка отправки в Telegram: {e}")


# Выполняем проверку при старте
check_db_table()


# Роуты для страниц
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/about")
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/contacts")
async def contacts(request: Request):
    return templates.TemplateResponse("contacts.html", {"request": request})


@app.get("/booking")
async def booking(request: Request):
    return templates.TemplateResponse("booking.html", {"request": request})


# API endpoints
@app.post("/api/bookings")
async def create_booking(booking: BookingRequest):
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO booking_requests 
                (name, email, phone, lesson_type, message)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                booking.name,
                booking.email,
                booking.phone,
                booking.lesson_type,
                booking.message
            ))

            send_telegram_notification(booking)

            return {"message": "Заявка успешно отправлена!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating booking: {str(e)}"
        )


@app.get("/api/bookings")
async def get_bookings():
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM booking_requests 
                ORDER BY created_at DESC
            """)
            return cursor.fetchall()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching bookings: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="localhost",
        port=8000,
        reload=True,
        log_level="debug"
    )