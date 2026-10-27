import os
import mysql.connector
from dotenv import load_dotenv

# Membaca konfigurasi dari file .env
load_dotenv()

try:
    koneksi = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        connection_timeout=5
    )

    if koneksi.is_connected():
        cursor = koneksi.cursor()

        cursor.execute("SELECT DATABASE(), CURRENT_USER()")
        hasil = cursor.fetchone()

        print("Koneksi MySQL berhasil!")
        print("Database aktif:", hasil[0])
        print("Akun yang digunakan:", hasil[1])

        cursor.close()
        koneksi.close()

except (mysql.connector.Error, ValueError) as error:
    print("Koneksi MySQL gagal.")
    print("Detail error:", error)
