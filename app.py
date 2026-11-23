
from flask import Flask, render_template, request, redirect, url_for, abort
import mysql.connector

from database import get_db_connection

app = Flask(__name__)

INSTRUMEN_VALID = ("Stanford-Binet Form L-M", "Raven")

def hitung_ca_bulan(tanggal_lahir, tanggal_tes):
    """Usia kronologis dalam bulan penuh. Sisa hari tidak dibulatkan."""
    bulan = (
        (tanggal_tes.year - tanggal_lahir.year) * 12
        + (tanggal_tes.month - tanggal_lahir.month)
    )

    if tanggal_tes.day < tanggal_lahir.day:
        bulan -= 1

    return bulan if bulan >= 0 else None

# Konversi angka romawi tingkat usia basal ke tahun
ROMAWI_TAHUN = {
    "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7,
    "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12,
    "XIII": 13, "XIV": 14,
}


def hitung_ma_iq(usia_basal, total_kredit, ca_bulan):
    """Mengikuti rumus studi kasus: MA = basal + kredit, IQ = MA / CA x 100.
    Mengembalikan (hasil, pesan). Jika belum bisa dihitung, hasil = None."""
    if not usia_basal:
        return None, "Usia basal belum diisi."

    tahun_basal = ROMAWI_TAHUN.get(usia_basal.strip().upper())

    if tahun_basal is None:
        return None, "Usia basal ini belum didukung (hanya tingkat II sampai XIV)."

    if not ca_bulan:
        return None, "Usia kronologis (CA) belum valid."

    ma_bulan = tahun_basal * 12 + total_kredit
    iq = round(ma_bulan / ca_bulan * 100, 2)

    return {"ma_bulan": ma_bulan, "iq": iq}, None

@app.route("/")
def beranda():
    total_anak = 0
    total_sesi = 0
    koneksi = None
    cursor = None
    try:
        koneksi = get_db_connection()
        cursor = koneksi.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) AS total FROM anak")
        row_anak = cursor.fetchone()
        if row_anak:
            total_anak = row_anak["total"]

        cursor.execute("SELECT COUNT(*) AS total FROM asesmen_binet")
        row_sesi = cursor.fetchone()
        if row_sesi:
            total_sesi = row_sesi["total"]
    except Exception:
        app.logger.exception("Gagal mengambil statistik beranda.")
    finally:
        if cursor is not None:
            cursor.close()
        if koneksi is not None and koneksi.is_connected():
            koneksi.close()

    return render_template(
        "index.html",
        active_page="dashboard",
        total_anak=total_anak,
        total_sesi=total_sesi
    )


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
            SELECT
                a.id,
                a.kode_anak,
                a.nama_panggilan,
                a.tanggal_lahir,
                COUNT(ab.id) AS jumlah_sesi
            FROM anak a
            LEFT JOIN asesmen_binet ab ON a.id = ab.anak_id
            GROUP BY a.id, a.kode_anak, a.nama_panggilan, a.tanggal_lahir
            ORDER BY a.kode_anak ASC, a.id ASC
        """)

        daftar_anak = cursor.fetchall()

        return render_template(
            "data_anak.html",
            active_page="data_anak",
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
            active_page="data_anak",
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
                active_page="asesmen",
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

            jenis_instrumen = request.form.get(
                "jenis_instrumen", ""
            ).strip()

            # Tanggal tes dan jenis instrumen wajib diisi
            if not tanggal_tes or jenis_instrumen not in INSTRUMEN_VALID:
                cursor.execute("""
                    SELECT id, jenis_instrumen, tanggal_tes,
                           versi_instrumen, status_asesmen
                    FROM asesmen_binet
                    WHERE anak_id = %s
                    ORDER BY tanggal_tes DESC, id DESC
                """, (anak_id,))

                daftar_asesmen = cursor.fetchall()

                return render_template(
                    "asesmen_binet.html",
                    active_page="asesmen",
                    daftar_anak=[],
                    anak_terpilih=anak_terpilih,
                    daftar_asesmen=daftar_asesmen,
                    error_database=False,
                    asesmen_created=False,
                    pesan_error="Tanggal tes dan jenis instrumen wajib diisi."
                )

            # Membuat sesi baru dengan status draft
            cursor.execute("""
                INSERT INTO asesmen_binet (
                    anak_id,
                    jenis_instrumen,
                    tanggal_tes,
                    versi_instrumen,
                    status_asesmen
                )
                VALUES (%s, %s, %s, %s, 'draft')
            """, (
                anak_id,
                jenis_instrumen,
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
            SELECT id, jenis_instrumen, tanggal_tes,
                   versi_instrumen, status_asesmen
            FROM asesmen_binet
            WHERE anak_id = %s
            ORDER BY tanggal_tes DESC, id DESC
        """, (anak_id,))

        daftar_asesmen = cursor.fetchall()

        return render_template(
            "asesmen_binet.html",
            active_page="asesmen",
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

def hitung_usia_kronologis(tanggal_lahir, tanggal_tes):
    """Menghitung usia kronologis (CA) anak saat tanggal tes."""
    if not tanggal_lahir or not tanggal_tes:
        return None

    tahun = tanggal_tes.year - tanggal_lahir.year
    bulan = tanggal_tes.month - tanggal_lahir.month
    hari = tanggal_tes.day - tanggal_lahir.day

    if hari < 0:
        bulan -= 1

    if bulan < 0:
        tahun -= 1
        bulan += 12

    total_bulan = (tahun * 12) + bulan
    return {
        "tahun": tahun,
        "bulan": bulan,
        "total_bulan": total_bulan,
        "teks": f"{tahun} Tahun {bulan} Bulan"
    }


# 7. Endpoint sesi asesmen (dengan redirect cerdas ke sesi terbaru)
@app.route("/asesmen-binet/sesi")
def sesi_terbaru():
    koneksi = None
    cursor = None
    try:
        koneksi = get_db_connection()
        cursor = koneksi.cursor(dictionary=True)
        cursor.execute("SELECT id FROM asesmen_binet ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            return redirect(url_for("detail_asesmen_binet", asesmen_id=row["id"]))
    except Exception:
        pass
    finally:
        if cursor: cursor.close()
        if koneksi and koneksi.is_connected(): koneksi.close()
    return redirect(url_for("asesmen_binet"))


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
                ab.jenis_instrumen,
                ab.usia_basal,
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

        cursor.execute("""
            SELECT id, tingkat_usia, item_lulus, bulan_per_item
            FROM hasil_binet_tingkat
            WHERE asesmen_id = %s
            ORDER BY id
        """, (asesmen_id,))

        daftar_skor = cursor.fetchall()

        ca_bulan = hitung_ca_bulan(
            sesi["tanggal_lahir"],
            sesi["tanggal_tes"]
        )

        total_kredit = sum(
            s["item_lulus"] * s["bulan_per_item"]
            for s in daftar_skor
        )

        hasil_ma_iq, pesan_ma_iq = hitung_ma_iq(
            sesi["usia_basal"],
            total_kredit,
            ca_bulan
        )
        
        cursor.execute("""
            SELECT
                ab.id AS asesmen_id,
                ab.tanggal_tes,
                ab.jenis_instrumen,
                a.kode_anak,
                a.nama_panggilan
            FROM asesmen_binet ab
            JOIN anak a ON ab.anak_id = a.id
            ORDER BY ab.id DESC
        """)
        daftar_semua_sesi = cursor.fetchall()

        return render_template(
            "detail_asesmen_binet.html",
            active_page="detail_sesi",
            sesi=sesi,
            daftar_semua_sesi=daftar_semua_sesi,
            daftar_skor=daftar_skor,
            total_kredit=total_kredit,
            ca_bulan=ca_bulan,
            hasil_ma_iq=hasil_ma_iq,
            pesan_ma_iq=pesan_ma_iq,
            basal_tersimpan=request.args.get("basal") == "1",
            basal_error=request.args.get("error") == "basal",
            skor_tersimpan=request.args.get("skor") == "1",
            skor_error=request.args.get("error") == "skor"
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
# 8. Simpan skor mentah per tingkat usia
@app.route(
    "/asesmen-binet/sesi/<int:asesmen_id>/skor",
    methods=["POST"]
)
def simpan_skor_tingkat(asesmen_id):
    tingkat_usia = request.form.get("tingkat_usia", "").strip().upper()

    try:
        item_lulus = int(request.form.get("item_lulus", ""))
        bulan_per_item = int(request.form.get("bulan_per_item", ""))
    except ValueError:
        return redirect(url_for(
            "detail_asesmen_binet",
            asesmen_id=asesmen_id,
            error="skor"
        ))

    # Batas ini hanya pengaman teknis, bukan aturan pedoman Binet
    if (
        not tingkat_usia
        or len(tingkat_usia) > 10
        or not 0 <= item_lulus <= 50
        or not 1 <= bulan_per_item <= 12
    ):
        return redirect(url_for(
            "detail_asesmen_binet",
            asesmen_id=asesmen_id,
            error="skor"
        ))

    koneksi = None
    cursor = None

    try:
        koneksi = get_db_connection()
        cursor = koneksi.cursor(dictionary=True)

        cursor.execute(
            "SELECT id FROM asesmen_binet WHERE id = %s",
            (asesmen_id,)
        )

        if cursor.fetchone() is None:
            return "Sesi asesmen tidak ditemukan.", 404

        # Jika tingkat yang sama diisi lagi, nilainya diperbarui
        cursor.execute("""
            INSERT INTO hasil_binet_tingkat (
                asesmen_id, tingkat_usia, item_lulus, bulan_per_item
            )
            VALUES (%s, %s, %s, %s) AS baru
            ON DUPLICATE KEY UPDATE
                item_lulus = baru.item_lulus,
                bulan_per_item = baru.bulan_per_item
        """, (asesmen_id, tingkat_usia, item_lulus, bulan_per_item))

        koneksi.commit()

        return redirect(url_for(
            "detail_asesmen_binet",
            asesmen_id=asesmen_id,
            skor=1
        ))

    except mysql.connector.Error:
        if koneksi is not None and koneksi.is_connected():
            koneksi.rollback()

        app.logger.exception("Gagal menyimpan skor tingkat usia.")
        return "Terjadi kesalahan database.", 500

    finally:
        if cursor is not None:
            cursor.close()

        if koneksi is not None and koneksi.is_connected():
            koneksi.close()

# 9. Simpan usia basal sesi asesmen
@app.route(
    "/asesmen-binet/sesi/<int:asesmen_id>/basal",
    methods=["POST"]
)
def simpan_basal(asesmen_id):
    usia_basal = request.form.get("usia_basal", "").strip().upper()

    if not usia_basal or len(usia_basal) > 10:
        return redirect(url_for(
            "detail_asesmen_binet",
            asesmen_id=asesmen_id,
            error="basal"
        ))

    koneksi = None
    cursor = None

    try:
        koneksi = get_db_connection()
        cursor = koneksi.cursor(dictionary=True)

        cursor.execute(
            "UPDATE asesmen_binet SET usia_basal = %s WHERE id = %s",
            (usia_basal, asesmen_id)
        )

        koneksi.commit()

        return redirect(url_for(
            "detail_asesmen_binet",
            asesmen_id=asesmen_id,
            basal=1
        ))

    except mysql.connector.Error:
        if koneksi is not None and koneksi.is_connected():
            koneksi.rollback()

        app.logger.exception("Gagal menyimpan usia basal.")
        return "Terjadi kesalahan database.", 500

    finally:
        if cursor is not None:
            cursor.close()

        if koneksi is not None and koneksi.is_connected():
            koneksi.close()

# 10. Inisialisasi data simulasi Binet sesuai studi kasus prototype
@app.route(
    "/asesmen-binet/sesi/<int:asesmen_id>/simulasi",
    methods=["POST"]
)
def muat_simulasi_binet(asesmen_id):
    koneksi = None
    cursor = None

    try:
        koneksi = get_db_connection()
        cursor = koneksi.cursor()

        cursor.execute(
            "UPDATE asesmen_binet SET usia_basal = 'VIII', jenis_instrumen = 'Stanford-Binet Form L-M' WHERE id = %s",
            (asesmen_id,)
        )

        contoh = [
            ("IX", 4, 2),
            ("X", 5, 2),
            ("XI", 4, 2),
            ("XII", 3, 2),
            ("XIII", 2, 2),
            ("XIV", 2, 2),
            ("AA", 1, 2)
        ]

        for t, l, b in contoh:
            cursor.execute("""
                INSERT INTO hasil_binet_tingkat (
                    asesmen_id, tingkat_usia, item_lulus, bulan_per_item
                )
                VALUES (%s, %s, %s, %s) AS baru
                ON DUPLICATE KEY UPDATE
                    item_lulus = baru.item_lulus,
                    bulan_per_item = baru.bulan_per_item
            """, (asesmen_id, t, l, b))

        koneksi.commit()
        return redirect(url_for("detail_asesmen_binet", asesmen_id=asesmen_id))

    except mysql.connector.Error:
        if koneksi and koneksi.is_connected():
            koneksi.rollback()
        app.logger.exception("Gagal memuat data simulasi Binet.")
        return "Terjadi kesalahan database.", 500

    finally:
        if cursor:
            cursor.close()
        if koneksi and koneksi.is_connected():
            koneksi.close()


def hitung_keanggotaan_kemandirian(skor):
    """Menghitung derajat keanggotaan fuzzy kemandirian (Rendah, Sedang, Tinggi)
    sesuai nilai prototipe studi kasus SDN Burengan 5."""
    skor = max(0, min(4, float(skor)))

    if skor <= 1.0:
        rendah = 1.0
    elif 1.0 < skor < 2.5:
        rendah = (2.5 - skor) / (2.5 - 1.0)
    else:
        rendah = 0.0

    if skor <= 1.0 or skor >= 4.0:
        sedang = 0.0
    elif 1.0 < skor <= 3.0:
        sedang = (skor - 1.0) / (3.0 - 1.0)
    else:
        sedang = (4.0 - skor) / (4.0 - 3.0)

    if skor <= 2.5:
        tinggi = 0.0
    else:
        tinggi = (skor - 2.5) / (4.0 - 2.5)

    return {
        "rendah": round(rendah, 3),
        "sedang": round(sedang, 3),
        "tinggi": round(tinggi, 3)
    }

# 11. Halaman Kemandirian Belajar (Langkah 3)
@app.route("/asesmen-binet/sesi/<int:asesmen_id>/kemandirian")
def kemandirian_belajar(asesmen_id):
    koneksi = None
    cursor = None
    try:
        koneksi = get_db_connection()
        cursor = koneksi.cursor(dictionary=True)

        cursor.execute("""
            SELECT ab.id AS asesmen_id, ab.anak_id, a.nama_panggilan, a.kode_anak
            FROM asesmen_binet ab
            JOIN anak a ON ab.anak_id = a.id
            WHERE ab.id = %s
        """, (asesmen_id,))
        sesi = cursor.fetchone()
        if not sesi:
            return "Sesi asesmen tidak ditemukan.", 404

        cursor.execute("SELECT * FROM kemandirian_belajar WHERE asesmen_id = %s", (asesmen_id,))
        kemandirian = cursor.fetchone()

        # Jika belum ada data kemandirian, inisialisasi default 2 indikator sesuai mockup
        if not kemandirian:
            cursor.execute("""
                INSERT INTO kemandirian_belajar (
                    asesmen_id, memulai_tugas, langkah_tugas, meminta_bantuan, merapikan_perlengkapan, skor_total
                ) VALUES (%s, 1, 1, 0, 0, 2)
            """, (asesmen_id,))
            koneksi.commit()
            cursor.execute("SELECT * FROM kemandirian_belajar WHERE asesmen_id = %s", (asesmen_id,))
            kemandirian = cursor.fetchone()

        derajat = hitung_keanggotaan_kemandirian(kemandirian['skor_total'])

        cursor.execute("""
            SELECT
                ab.id AS asesmen_id,
                ab.tanggal_tes,
                ab.jenis_instrumen,
                a.kode_anak,
                a.nama_panggilan
            FROM asesmen_binet ab
            JOIN anak a ON ab.anak_id = a.id
            ORDER BY ab.id DESC
        """)
        daftar_semua_sesi = cursor.fetchall()

        return render_template(
            "kemandirian.html",
            active_page="kemandirian",
            sesi=sesi,
            kemandirian=kemandirian,
            derajat=derajat,
            daftar_semua_sesi=daftar_semua_sesi
        )
    except mysql.connector.Error:
        app.logger.exception("Gagal memuat modul kemandirian.")
        return "Terjadi kesalahan database.", 500
    finally:
        if cursor: cursor.close()
        if koneksi and koneksi.is_connected(): koneksi.close()


# 12. Simpan skor indikator kemandirian belajar
@app.route("/asesmen-binet/sesi/<int:asesmen_id>/kemandirian/simpan", methods=["POST"])
def simpan_kemandirian(asesmen_id):
    memulai = 1 if request.form.get('memulai_tugas') in ['1', 'true', 'on'] else 0
    langkah = 1 if request.form.get('langkah_tugas') in ['1', 'true', 'on'] else 0
    meminta = 1 if request.form.get('meminta_bantuan') in ['1', 'true', 'on'] else 0
    merapikan = 1 if request.form.get('merapikan_perlengkapan') in ['1', 'true', 'on'] else 0
    skor_total = memulai + langkah + meminta + merapikan

    koneksi = None
    cursor = None
    try:
        koneksi = get_db_connection()
        cursor = koneksi.cursor()
        cursor.execute("""
            INSERT INTO kemandirian_belajar (
                asesmen_id, memulai_tugas, langkah_tugas, meminta_bantuan, merapikan_perlengkapan, skor_total
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                memulai_tugas = VALUES(memulai_tugas),
                langkah_tugas = VALUES(langkah_tugas),
                meminta_bantuan = VALUES(meminta_bantuan),
                merapikan_perlengkapan = VALUES(merapikan_perlengkapan),
                skor_total = VALUES(skor_total)
        """, (asesmen_id, memulai, langkah, meminta, merapikan, skor_total))
        koneksi.commit()
        return redirect(url_for('kemandirian_belajar', asesmen_id=asesmen_id))
    except mysql.connector.Error:
        if koneksi and koneksi.is_connected(): koneksi.rollback()
        app.logger.exception("Gagal menyimpan kemandirian.")
        return "Terjadi kesalahan database.", 500
    finally:
        if cursor: cursor.close()
        if koneksi and koneksi.is_connected(): koneksi.close()


# 13. Modul Rekomendasi Strategi Pengajaran (Fuzzy Tsukamoto - Tahap 5)
def hitung_keanggotaan_iq(iq):
    """Menghitung derajat keanggotaan fuzzy IQ Binet (Rendah, Sedang, Tinggi)
    Simulasi studi kasus SDN Burengan 5 (Belum divalidasi final)."""
    iq = float(iq)
    if iq <= 70:
        rendah = 1.0
    elif 70 < iq < 90:
        rendah = (90 - iq) / (90 - 70)
    else:
        rendah = 0.0

    if iq <= 70 or iq >= 120:
        sedang = 0.0
    elif 70 < iq < 90:
        sedang = (iq - 70) / (90 - 70)
    elif 90 <= iq <= 110:
        sedang = 1.0
    else:
        sedang = (120 - iq) / (120 - 110)

    if iq <= 110:
        tinggi = 0.0
    elif 110 < iq < 120:
        tinggi = (iq - 110) / (120 - 110)
    else:
        tinggi = 1.0

    return {
        "rendah": round(rendah, 3),
        "sedang": round(sedang, 3),
        "tinggi": round(tinggi, 3)
    }


def proses_fuzzy_tsukamoto(mu_iq, mu_km):
    """Proses inferensi Fuzzy Tsukamoto 9 aturan kombinasi IQ dan Kemandirian."""
    rules = [
        {"no": 1, "kondisi": "IQ Rendah & Kemandirian Rendah", "iq_k": "rendah", "km_k": "rendah", "konsekuen": "Pendampingan Intensif", "z": 30},
        {"no": 2, "kondisi": "IQ Rendah & Kemandirian Sedang", "iq_k": "rendah", "km_k": "sedang", "konsekuen": "Pendampingan Intensif", "z": 40},
        {"no": 3, "kondisi": "IQ Rendah & Kemandirian Tinggi", "iq_k": "rendah", "km_k": "tinggi", "konsekuen": "Pendampingan Terarah", "z": 55},
        {"no": 4, "kondisi": "IQ Sedang & Kemandirian Rendah", "iq_k": "sedang", "km_k": "rendah", "konsekuen": "Pendampingan Intensif", "z": 45},
        {"no": 5, "kondisi": "IQ Sedang & Kemandirian Sedang", "iq_k": "sedang", "km_k": "sedang", "konsekuen": "Pendampingan Terarah", "z": 60},
        {"no": 6, "kondisi": "IQ Sedang & Kemandirian Tinggi", "iq_k": "sedang", "km_k": "tinggi", "konsekuen": "Dukungan Mandiri", "z": 75},
        {"no": 7, "kondisi": "IQ Tinggi & Kemandirian Rendah", "iq_k": "tinggi", "km_k": "rendah", "konsekuen": "Pendampingan Terarah", "z": 55},
        {"no": 8, "kondisi": "IQ Tinggi & Kemandirian Sedang", "iq_k": "tinggi", "km_k": "sedang", "konsekuen": "Dukungan Mandiri", "z": 80},
        {"no": 9, "kondisi": "IQ Tinggi & Kemandirian Tinggi", "iq_k": "tinggi", "km_k": "tinggi", "konsekuen": "Dukungan Mandiri", "z": 90},
    ]

    evaluated_rules = []
    sum_alpha_z = 0.0
    sum_alpha = 0.0

    for r in rules:
        alpha = min(mu_iq[r["iq_k"]], mu_km[r["km_k"]])
        evaluated_rules.append({
            "no": r["no"],
            "kondisi": r["kondisi"],
            "alpha": round(alpha, 3),
            "konsekuen": r["konsekuen"],
            "z": r["z"],
            "is_active": alpha > 0
        })
        sum_alpha_z += alpha * r["z"]
        sum_alpha += alpha

    z_final = round(sum_alpha_z / sum_alpha, 2) if sum_alpha > 0 else 50.0

    if z_final < 50.0:
        kategori = "Pendampingan Intensif (Dukungan Khusus)"
        badge_color = "amber"
        deskripsi = "Siswa memerlukan bimbingan guru secara berulang dan visual konkret. Setiap instruksi tugas dipecah menjadi langkah-langkah kecil (task analysis) dengan pendampingan langsung."
        strategi_guru = [
            "Gunakan metode Task Analysis: pecah instruksi menjadi 1-2 tahapan kecil dan berikan jeda waktu pengerjaan.",
            "Gunakan media visual konkret (gambar, kartu isyarat warna, benda riil) untuk memperjelas konsep materi pelajaran.",
            "Berikan penguatan positif (pujian / stiker pencapaian) setiap kali siswa berhasil menyelesaikan satu tahapan kecil."
        ]
        strategi_sekolah = [
            "Tempatkan posisi duduk anak di baris depan dekat meja guru untuk meminimalkan gangguan konsentrasi.",
            "Sediakan waktu pendampingan khusus bersama Guru Pendamping Khusus (GPK) di ruang sumber inklusi jika diperlukan.",
            "Koordinasikan penyesuaian target kurikulum (akomodasi waktu ujian dan penyederhanaan lembar kerja)."
        ]
        strategi_ortu = [
            "Latih kemandirian bina diri di rumah dengan jadwal harian bergambar (rutinitas makan, merapikan tas sekolah).",
            "Ulangi latihan fokus selama 10-15 menit per sesi tanpa distraksi layar gadget/televisi.",
            "Bangun komunikasi harian dengan guru kelas melalui buku penghubung perkembangan anak."
        ]
    elif 50.0 <= z_final < 75.0:
        kategori = "Pendampingan Terarah (Dukungan Sedang)"
        badge_color = "sky"
        deskripsi = "Siswa menunjukkan kesiapan kognitif dan perilaku belajar yang cukup baik, namun masih membutuhkan panduan terstruktur dan pengawasan berkala saat menghadapi materi baru atau tahapan tugas yang kompleks."
        strategi_guru = [
            "Berikan instruksi lisan singkat yang didukung panduan tertulis atau ceklis langkah kerja di meja anak.",
            "Terapkan model teman sebaya (peer tutoring) agar anak termotivasi mengikuti interaksi belajar kelompok.",
            "Pantau ketahanan fokus belajar setiap 15-20 menit dan berikan arahan lembut saat anak mulai terdistraksi."
        ]
        strategi_sekolah = [
            "Fasilitasi lingkungan kelas yang kondusif dengan membatasi kebisingan berlebih selama sesi pemahaman mandiri.",
            "Sediakan sudut baca atau media manipulatif interaktif untuk mendukung gaya belajar kinestetik/visual anak.",
            "Lakukan evaluasi berkala capaian belajar bersama guru kelas reguler dan psikolog sekolah."
        ]
        strategi_ortu = [
            "Biasakan anak menyiapkan perlengkapan sekolah dan pekerjaan rumah secara teratur dengan panduan ceklis.",
            "Berikan kesempatan anak menjelaskan kembali apa yang dipelajari di sekolah dengan bahasa sederhana.",
            "Dukung minat dan kebiasaan membaca bersama anggota keluarga setiap sore atau malam hari."
        ]
    else:
        kategori = "Dukungan Mandiri & Pengayaan"
        badge_color = "emerald"
        deskripsi = "Siswa memiliki potensi kognitif dan tingkat kemandirian belajar yang tinggi. Mampu menyelesaikan instruksi secara mandiri dan siap diberikan aktivitas pengayaan kognitif yang lebih bervariasi."
        strategi_guru = [
            "Berikan proyek pengayaan atau tugas problem-solving terbuka yang menantang kreativitas dan logika anak.",
            "Beri peran aktif di kelas, misalnya sebagai pemimpin kelompok kecil atau membantu mendampingi teman sebaya.",
            "Dorong anak untuk mempresentasikan hasil karya atau idenya secara verbal di hadapan kelompok."
        ]
        strategi_sekolah = [
            "Sediakan akses ke materi pengayaan atau literasi digital terarah di perpustakaan/lab komputer sekolah.",
            "Ikutkan siswa dalam kegiatan ekstrakurikuler yang sesuai dengan bakat dan minat kognitifnya.",
            "Berikan penghargaan atas inisiatif dan kemandirian siswa dalam kegiatan kelas maupun sekolah."
        ]
        strategi_ortu = [
            "Berikan tantangan harian baru yang mengasah daya nalar dan kreativitas (permainan puzzle, eksperimen sains sederhana).",
            "Latih tanggung jawab yang lebih luas di lingkungan keluarga (mengatur waktu belajar dan hobi secara mandiri).",
            "Apresiasi gagasan dan inisiatif anak untuk menumbuhkan rasa percaya diri yang stabil."
        ]

    return {
        "z_final": z_final,
        "kategori": kategori,
        "badge_color": badge_color,
        "deskripsi": deskripsi,
        "rules": evaluated_rules,
        "sum_alpha": round(sum_alpha, 3),
        "sum_alpha_z": round(sum_alpha_z, 2),
        "strategi_guru": strategi_guru,
        "strategi_sekolah": strategi_sekolah,
        "strategi_ortu": strategi_ortu
    }


@app.route("/asesmen-binet/sesi/<int:asesmen_id>/rekomendasi")
def rekomendasi_strategi(asesmen_id):
    koneksi = None
    cursor = None
    try:
        koneksi = get_db_connection()
        cursor = koneksi.cursor(dictionary=True)

        # 1. Mengambil data sesi asesmen dan profil anak
        cursor.execute("""
            SELECT
                ab.id AS asesmen_id,
                ab.anak_id,
                ab.jenis_instrumen,
                ab.tanggal_tes,
                ab.versi_instrumen,
                ab.status_asesmen,
                ab.usia_basal,
                a.kode_anak,
                a.nama_panggilan,
                a.tanggal_lahir
            FROM asesmen_binet ab
            JOIN anak a ON ab.anak_id = a.id
            WHERE ab.id = %s
        """, (asesmen_id,))
        sesi = cursor.fetchone()

        if not sesi:
            return "Sesi asesmen tidak ditemukan.", 404

        # 2. Mengambil skor mentah Binet per tingkat usia
        cursor.execute("""
            SELECT tingkat_usia, item_lulus, bulan_per_item
            FROM hasil_binet_tingkat
            WHERE asesmen_id = %s
            ORDER BY id ASC
        """, (asesmen_id,))
        daftar_skor = cursor.fetchall()

        # 3. Mengambil data kemandirian belajar anak
        cursor.execute("""
            SELECT * FROM kemandirian_belajar
            WHERE asesmen_id = %s
        """, (asesmen_id,))
        kemandirian = cursor.fetchone()

        if not kemandirian:
            kemandirian = {
                "memulai_tugas": 0,
                "langkah_tugas": 0,
                "meminta_bantuan": 0,
                "merapikan_perlengkapan": 0,
                "skor_total": 0
            }

        # 4. Hitung CA, Total Kredit, MA, dan IQ
        ca_bulan = hitung_ca_bulan(sesi["tanggal_lahir"], sesi["tanggal_tes"])
        total_kredit = sum(s["item_lulus"] * s["bulan_per_item"] for s in daftar_skor)
        hasil_ma_iq, _ = hitung_ma_iq(sesi["usia_basal"], total_kredit, ca_bulan)

        iq_nilai = hasil_ma_iq["iq"] if hasil_ma_iq else 100.0

        # 5. Fuzzifikasi IQ dan Kemandirian
        derajat_iq = hitung_keanggotaan_iq(iq_nilai)
        derajat_kemandirian = hitung_keanggotaan_kemandirian(kemandirian["skor_total"])

        # 6. Inferensi Fuzzy Tsukamoto & Defuzzifikasi
        hasil_fuzzy = proses_fuzzy_tsukamoto(derajat_iq, derajat_kemandirian)

        cursor.execute("""
            SELECT
                ab.id AS asesmen_id,
                ab.tanggal_tes,
                ab.jenis_instrumen,
                a.kode_anak,
                a.nama_panggilan
            FROM asesmen_binet ab
            JOIN anak a ON ab.anak_id = a.id
            ORDER BY ab.id DESC
        """)
        daftar_semua_sesi = cursor.fetchall()

        return render_template(
            "rekomendasi.html",
            active_page="rekomendasi",
            sesi=sesi,
            ca_bulan=ca_bulan,
            total_kredit=total_kredit,
            hasil_ma_iq=hasil_ma_iq,
            iq_nilai=iq_nilai,
            kemandirian=kemandirian,
            derajat_iq=derajat_iq,
            derajat_kemandirian=derajat_kemandirian,
            hasil_fuzzy=hasil_fuzzy,
            daftar_semua_sesi=daftar_semua_sesi
        )

    except mysql.connector.Error:
        app.logger.exception("Gagal memuat modul rekomendasi.")
        return "Terjadi kesalahan database.", 500
    finally:
        if cursor: cursor.close()
        if koneksi and koneksi.is_connected(): koneksi.close()


if __name__ == "__main__":
    app.run(debug=True)
