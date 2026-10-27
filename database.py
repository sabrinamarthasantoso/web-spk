import os

import mysql.connector
from dotenv import load_dotenv


# Membaca konfigurasi dari file .env
load_dotenv()


def get_db_connection():
    """Membuat koneksi ke database MySQL."""

    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        connection_timeout=5
    )
