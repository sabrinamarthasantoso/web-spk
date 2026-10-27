
from flask import Flask, render_template, request, redirect, url_for, abort
import mysql.connector

from database import get_db_connection

app = Flask(__name__)
@app.route("/")
def beranda():
    return render_template("index.html")


@app.route("/data-anak")
def data_anak():
    koneksi = None
    cursor = None

    # Membaca status aksi dari URL
    data_added = request.args.get("added") == "1"
    data_updated = request.args.get("updated") == "1"
    data_deleted = request.args.get("deleted") == "1"

    try:
        koneksi = get_db_connection()
        cursor = koneksi.cursor(dictionary=True)

        cursor.execute("""
            SELECT id, kode_anak, nama_panggilan, tanggal_lahir
            FROM anak
            ORDER BY id DESC
        """)

        daftar_anak = cursor.fetchall()

        return render_template(
            "data_anak.html",
            daftar_anak=daftar_anak,
            error_database=False,
            data_added=data_added,
            data_updated=data_updated,
            data_deleted=data_deleted
        )

    except mysql.connector.Error:
        app.logger.exception("Gagal mengambil data anak.")

        return render_template(
            "data_anak.html",
            daftar_anak=[],
            error_database=True,
            data_added=False,
            data_updated=False,
            data_deleted=False
        )

    finally:
        if cursor is not None:
            cursor.close()

        if koneksi is not None and koneksi.is_connected():
            koneksi.close()

@app.route("/data-anak/tambah", methods=["GET", "POST"])
def tambah_anak():
    if request.method == "POST":

        kode_anak = request.form.get(
            "kode_anak", ""
        ).strip()

        nama_panggilan = request.form.get(
            "nama_panggilan", ""
        ).strip()

        tanggal_lahir = request.form.get(
            "tanggal_lahir", ""
        ).strip()

        if not kode_anak or not nama_panggilan or not tanggal_lahir:
            return render_template(
                "tambah_anak.html",
                pesan_error="Semua kolom wajib diisi."
            )

        koneksi = None
        cursor = None

        try:
            koneksi = get_db_connection()
            cursor = koneksi.cursor()

            cursor.execute("""
                INSERT INTO anak
                    (kode_anak, nama_panggilan, tanggal_lahir)
                VALUES (%s, %s, %s)
            """, (
                kode_anak,
                nama_panggilan,
                tanggal_lahir
            ))
            koneksi.commit()

            return redirect(
                url_for("data_anak", added=1)
            )

        except mysql.connector.IntegrityError:
            return render_template(
                "tambah_anak.html",
                pesan_error=(
                    "Kode anak sudah digunakan. "
                    "Gunakan kode lain."
                )
            )

        except mysql.connector.Error:
            app.logger.exception("Gagal menyimpan data anak.")

            return render_template(
                "tambah_anak.html",
                pesan_error=(
                    "Data gagal disimpan. "
                    "Periksa koneksi database."
                )
            )

        finally:
            if cursor is not None:
                cursor.close()

            if koneksi is not None and koneksi.is_connected():
                koneksi.close()

    return render_template("tambah_anak.html")

# 4. Mengedit data anak
@app.route("/data-anak/edit/<int:anak_id>", methods=["GET", "POST"])
def edit_anak(anak_id):
    koneksi = None
    cursor = None
    anak = None

    try:
        koneksi = get_db_connection()
        cursor = koneksi.cursor(dictionary=True)

        # Mengambil data anak yang akan diedit
        cursor.execute("""
            SELECT id, kode_anak, nama_panggilan, tanggal_lahir
            FROM anak
            WHERE id = %s
        """, (anak_id,))

        anak = cursor.fetchone()

        # Jika data tidak ditemukan
        if anak is None:
            abort(404)

        # Jika formulir dikirim
        if request.method == "POST":
            kode_anak = request.form.get(
                "kode_anak", ""
            ).strip()

            nama_panggilan = request.form.get(
                "nama_panggilan", ""
            ).strip()

            tanggal_lahir = request.form.get(
                "tanggal_lahir", ""
            ).strip()

            if not kode_anak or not nama_panggilan or not tanggal_lahir:
                return render_template(
                    "edit_anak.html",
                    anak=anak,
                    pesan_error="Semua kolom wajib diisi."
                )

            cursor.execute("""
                UPDATE anak
                SET kode_anak = %s,
                    nama_panggilan = %s,
                    tanggal_lahir = %s
                WHERE id = %s
            """, (
                kode_anak,
                nama_panggilan,
                tanggal_lahir,
                anak_id
            ))

            koneksi.commit()

            return redirect(
                url_for("data_anak", updated=1)
            )

        # Jika halaman dibuka, tampilkan formulir edit
        return render_template(
            "edit_anak.html",
            anak=anak
        )

    except mysql.connector.IntegrityError:
        return render_template(
            "edit_anak.html",
            anak=anak,
            pesan_error="Kode anak sudah digunakan oleh data lain."
        )

    except mysql.connector.Error:
        app.logger.exception("Gagal mengedit data anak.")

        return "Terjadi kesalahan database. Periksa terminal Flask.", 500

    finally:
        if cursor is not None:
            cursor.close()

        if koneksi is not None and koneksi.is_connected():
            koneksi.close()

# 5. Menghapus data anak
@app.route("/data-anak/hapus/<int:anak_id>", methods=["POST"])
def hapus_anak(anak_id):
    koneksi = None
    cursor = None

    try:
        koneksi = get_db_connection()
        cursor = koneksi.cursor()

        # Menghapus hanya data dengan ID yang dipilih
        cursor.execute(
            "DELETE FROM anak WHERE id = %s",
            (anak_id,)
        )

        # Pastikan data dengan ID tersebut memang ada
        if cursor.rowcount == 0:
            return redirect(url_for("data_anak"))

        # Simpan perubahan ke MySQL
        koneksi.commit()

        return redirect(url_for("data_anak", deleted=1))

    except mysql.connector.Error:
        if koneksi is not None and koneksi.is_connected():
            koneksi.rollback()

        app.logger.exception("Gagal menghapus data anak.")
        return "Data gagal dihapus. Periksa terminal Flask.", 500

    finally:
        if cursor is not None:
            cursor.close()

        if koneksi is not None and koneksi.is_connected():
            koneksi.close()

# 6. Modul asesmen Binet
@app.route("/asesmen-binet", defaults={"anak_id": None})
@app.route(
    "/asesmen-binet/<int:anak_id>",
    methods=["GET", "POST"]
)
def asesmen_binet(anak_id):
    koneksi = None
    cursor = None

    try:
        koneksi = get_db_connection()
        cursor = koneksi.cursor(dictionary=True)

        # Halaman daftar anak untuk memilih asesmen
        if anak_id is None:
            cursor.execute("""
                SELECT id, kode_anak, nama_panggilan, tanggal_lahir
                FROM anak
                ORDER BY nama_panggilan ASC
            """)

            daftar_anak = cursor.fetchall()

            return render_template(
                "asesmen_binet.html",
                daftar_anak=daftar_anak,
                anak_terpilih=None,
                daftar_asesmen=[],
                error_database=False,
                asesmen_created=False,
                pesan_error=None
            )

        # Mengambil anak yang dipilih
        cursor.execute("""
            SELECT id, kode_anak, nama_panggilan, tanggal_lahir
            FROM anak
            WHERE id = %s
        """, (anak_id,))

        anak_terpilih = cursor.fetchone()

        if anak_terpilih is None:
            return "Data anak tidak ditemukan.", 404

        # Memproses formulir pembuatan sesi asesmen
        if request.method == "POST":
            tanggal_tes = request.form.get(
                "tanggal_tes", ""
            ).strip()

            versi_instrumen = request.form.get(
                "versi_instrumen", ""
            ).strip() or None

            # Tanggal tes wajib diisi
            if not tanggal_tes:
                cursor.execute("""
                    SELECT id, tanggal_tes, versi_instrumen,
                           status_asesmen
                    FROM asesmen_binet
                    WHERE anak_id = %s
                    ORDER BY tanggal_tes DESC, id DESC
                """, (anak_id,))

                daftar_asesmen = cursor.fetchall()

                return render_template(
                    "asesmen_binet.html",
                    daftar_anak=[],
                    anak_terpilih=anak_terpilih,
                    daftar_asesmen=daftar_asesmen,
                    error_database=False,
                    asesmen_created=False,
                    pesan_error="Tanggal tes wajib diisi."
                )

            # Membuat sesi baru dengan status draft
            cursor.execute("""
                INSERT INTO asesmen_binet (
                    anak_id,
                    tanggal_tes,
                    versi_instrumen,
                    status_asesmen
                )
                VALUES (%s, %s, %s, 'draft')
            """, (
                anak_id,
                tanggal_tes,
                versi_instrumen
            ))

            koneksi.commit()

            return redirect(
                url_for(
                    "asesmen_binet",
                    anak_id=anak_id,
                    created=1
                )
            )

        cursor.execute("""
            SELECT id, tanggal_tes, versi_instrumen,
                   status_asesmen
            FROM asesmen_binet
            WHERE anak_id = %s
            ORDER BY tanggal_tes DESC, id DESC
        """, (anak_id,))

        daftar_asesmen = cursor.fetchall()

        return render_template(
            "asesmen_binet.html",
            daftar_anak=[],
            anak_terpilih=anak_terpilih,
            daftar_asesmen=daftar_asesmen,
            error_database=False,
            asesmen_created=request.args.get("created") == "1",
            pesan_error=None
        )

    except mysql.connector.Error:
        if koneksi is not None and koneksi.is_connected():
            koneksi.rollback()

        app.logger.exception(
            "Gagal memproses modul asesmen Binet."
        )

        return "Terjadi kesalahan database. Periksa terminal Flask.", 500

    finally:
        if cursor is not None:
            cursor.close()

        if koneksi is not None and koneksi.is_connected():
            koneksi.close()

# 7. Detail sesi asesmen Binet
@app.route("/asesmen-binet/sesi/<int:asesmen_id>")
def detail_asesmen_binet(asesmen_id):
    koneksi = None
    cursor = None

    try:
        koneksi = get_db_connection()
        cursor = koneksi.cursor(dictionary=True)

        # Mengambil sesi asesmen beserta identitas anak
        cursor.execute("""
            SELECT
                ab.id AS asesmen_id,
                ab.anak_id,
                ab.tanggal_tes,
                ab.versi_instrumen,
                ab.status_asesmen,
                a.kode_anak,
                a.nama_panggilan,
                a.tanggal_lahir
            FROM asesmen_binet ab
            JOIN anak a ON ab.anak_id = a.id
            WHERE ab.id = %s
        """, (asesmen_id,))

        sesi = cursor.fetchone()

        if sesi is None:
            return "Sesi asesmen tidak ditemukan.", 404

        return render_template(
            "detail_asesmen_binet.html",
            sesi=sesi
        )

    except mysql.connector.Error:
        app.logger.exception(
            "Gagal mengambil detail sesi asesmen."
        )
        return "Terjadi kesalahan database.", 500

    finally:
        if cursor is not None:
            cursor.close()

        if koneksi is not None and koneksi.is_connected():
            koneksi.close()

if __name__ == "__main__":
    app.run(debug=True)
