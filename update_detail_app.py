"""Update app.py to include jenis_instrumen and chronological age calculation."""

with open("app.py", "rb") as f:
    content = f.read()

# 1. Add chronological age helper function before detail_asesmen_binet
helper_func = (
    b"def hitung_usia_kronologis(tanggal_lahir, tanggal_tes):\r\n"
    b'    """Menghitung usia kronologis (CA) anak saat tanggal tes."""\r\n'
    b"    if not tanggal_lahir or not tanggal_tes:\r\n"
    b"        return None\r\n"
    b"\r\n"
    b"    tahun = tanggal_tes.year - tanggal_lahir.year\r\n"
    b"    bulan = tanggal_tes.month - tanggal_lahir.month\r\n"
    b"    hari = tanggal_tes.day - tanggal_lahir.day\r\n"
    b"\r\n"
    b"    if hari < 0:\r\n"
    b"        bulan -= 1\r\n"
    b"\r\n"
    b"    if bulan < 0:\r\n"
    b"        tahun -= 1\r\n"
    b"        bulan += 12\r\n"
    b"\r\n"
    b"    total_bulan = (tahun * 12) + bulan\r\n"
    b"    return {\r\n"
    b'        "tahun": tahun,\r\n'
    b'        "bulan": bulan,\r\n'
    b'        "total_bulan": total_bulan,\r\n'
    b'        "teks": f"{tahun} Tahun {bulan} Bulan"\r\n'
    b"    }\r\n\r\n\r\n"
)

old_detail_route = b"# 7. Detail sesi asesmen Binet\r\n@app.route(\"/asesmen-binet/sesi/<int:asesmen_id>\")"

if helper_func not in content and old_detail_route in content:
    content = content.replace(old_detail_route, helper_func + old_detail_route, 1)
    print("1. Helper function hitung_usia_kronologis added.")

# 2. Update SELECT query in detail_asesmen_binet to include ab.jenis_instrumen
old_select = (
    b"            SELECT\r\n"
    b"                ab.id AS asesmen_id,\r\n"
    b"                ab.anak_id,\r\n"
    b"                ab.tanggal_tes,\r\n"
    b"                ab.versi_instrumen,\r\n"
    b"                ab.status_asesmen,\r\n"
    b"                a.kode_anak,\r\n"
    b"                a.nama_panggilan,\r\n"
    b"                a.tanggal_lahir\r\n"
    b"            FROM asesmen_binet ab"
)

new_select = (
    b"            SELECT\r\n"
    b"                ab.id AS asesmen_id,\r\n"
    b"                ab.anak_id,\r\n"
    b"                ab.jenis_instrumen,\r\n"
    b"                ab.tanggal_tes,\r\n"
    b"                ab.versi_instrumen,\r\n"
    b"                ab.status_asesmen,\r\n"
    b"                a.kode_anak,\r\n"
    b"                a.nama_panggilan,\r\n"
    b"                a.tanggal_lahir\r\n"
    b"            FROM asesmen_binet ab"
)

if old_select in content:
    content = content.replace(old_select, new_select, 1)
    print("2. SELECT query updated to fetch ab.jenis_instrumen.")

# 3. Calculate CA and pass to render_template
old_render = (
    b"        return render_template(\r\n"
    b'            "detail_asesmen_binet.html",\r\n'
    b"            sesi=sesi\r\n"
    b"        )"
)

new_render = (
    b"        ca = hitung_usia_kronologis(sesi['tanggal_lahir'], sesi['tanggal_tes'])\r\n"
    b"        sesi['usia_kronologis'] = ca\r\n"
    b"\r\n"
    b"        return render_template(\r\n"
    b'            "detail_asesmen_binet.html",\r\n'
    b"            sesi=sesi\r\n"
    b"        )"
)

if old_render in content:
    content = content.replace(old_render, new_render, 1)
    print("3. Usia kronologis passed to detail_asesmen_binet.html.")

with open("app.py", "wb") as f:
    f.write(content)

print("app.py successfully updated.")

