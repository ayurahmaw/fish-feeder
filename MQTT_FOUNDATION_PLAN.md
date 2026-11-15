# MQTT Foundation Plan — ESP32 Aquaponic Autofeeder

> **ARSIP — fase ini selesai (2026-09-27) dan dicatat sebagai sejarah.**
> Rencana fase awal (instalasi Mosquitto, Node-RED, verifikasi publish/subscribe, desain topik &
> message schema) sudah dieksekusi dan digantikan arsitektur sekarang: **broker MQTT tertanam
> (amqtt) + SQLite + dashboard Streamlit dalam satu proses Python**.
>
> - Kontrak MQTT final (topik, payload, ack): `CONTEXT.md` §6 & §10.
> - Cara menjalankan & verifikasi: `CONTEXT.md` §19.
> - Catatan sejarah: setup Mosquitto sempat terblokir oleh Homebrew 4.3.24 yang usang; akhirnya
>   dipakai broker tertanam, sehingga Mosquitto/Node-RED tidak lagi wajib.
>
> Berkas ini disimpan hanya sebagai penunjuk. Selalu rujuk `CONTEXT.md`.
