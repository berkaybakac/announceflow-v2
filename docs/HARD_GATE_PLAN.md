# Hard Gate v3 Plan (DB Healthcheck + CUDA Fix + Warm-up + Race-Safe Cleanup)

Bu plan Faz 4 Dockerization tamamlandıktan sonra aktif edilecektir.

SİLİNECEK NOT:
NİHAİ KARAR: Hard Gate Planı çöpe gitmiyor. Onu Faz 4'ün (Deployment & Dağıtım) ilk adımı olarak, yani Agent'ı da bitirip donanımları konuşturacağımız uçtan uca (End-to-End) entegrasyon testlerinin başına taşıyoruz. Şu an vakit kaybetmeden doğrudan Raspberry Pi'nin kalbine (Agent Faz 3) iniyoruz.


## Özet
Bu plan, **Faz 4 (Dockerization & Deployment) başlangıcında**, uçtan uca entegrasyon testlerinden hemen önce uygulanacak fiziksel doğrulama kapısıdır.

Ana hedef: TTS/Media katmanında pytest'in tek başına yakalayamayacağı 4 kritik riski gerçek çalışma ortamında doğrulamak.

## Kritik Mimari Kararlar
1. `depends_on` tek başına yeterli kabul edilmez; `db` için healthcheck + `service_healthy` zorunlu.
2. Mac/Docker ortamında XTTS için backend container'da `CUDA_VISIBLE_DEVICES=""` zorunlu.
3. Cold start false negative'i önlemek için Gate-1 öncesi warm-up zorunlu.
4. `gate_user` cleanup backend'e bağımlı olmayacak; `db` container içindeki `psql` ile silinecek.
5. Geçici script yaklaşımı kullanılacak: tek `temp_gate_check.sh`, koşum sonunda self-delete.

## Kapsam
- TTS async tıkanma riski
- Docker binary/parity riski (ffmpeg/ffprobe/libsndfile)
- Disk/volume yazma izni riski
- DB kalıcılık riski (restart/down-up sonrası)

## Değişecek Dosyalar
1. `Dockerfile.backend` (yeni)
2. `docker-compose.dev.yml` (güncelleme)
3. `temp_gate_check.sh` (geçici; koşum sonunda kendini siler)

---

## 1) Dockerfile.backend

### Hedef
- Base image: `python:3.11-slim`
- Sistem paketleri:
  - `ffmpeg`
  - `libsndfile1`
  - `curl`
  - `ca-certificates`
- `WORKDIR /app`
- `backend/requirements.txt` kurulumu
- Kod kopyalama:
  - `/app/backend`
  - `/app/shared`
- `ENV PYTHONPATH=/app`
- Başlatma komutu:
  - `alembic -c backend/alembic.ini upgrade head`
  - `uvicorn backend.main:app --host 0.0.0.0 --port 8000`

---

## 2) docker-compose.dev.yml

### db servisi
- `healthcheck` eklenecek:
  - `pg_isready -U ${POSTGRES_USER:-admin} -d ${POSTGRES_DB:-announceflow}`
  - `interval: 5s`
  - `timeout: 3s`
  - `retries: 20`
  - `start_period: 5s`

### backend servisi
- `build`:
  - `context: .`
  - `dockerfile: Dockerfile.backend`
- `depends_on`:
  - `db: { condition: service_healthy }`
  - `mqtt: { condition: service_started }`
- `ports`:
  - `8000:8000`
- `environment`:
  - `DATABASE_URL=postgresql+asyncpg://admin:admin@db:5432/announceflow`
  - `SECRET_KEY=<32+>`
  - `APP_NAME=AnnounceFlow`
  - `DEBUG=False`
  - `MEDIA_STORAGE_PATH=/app/data/media`
  - `MEDIA_TEMP_PATH=/app/data/media/temp`
  - `COQUI_TOS_AGREED=1`
  - `CUDA_VISIBLE_DEVICES=""`
  - `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1`
  - `TTS_VOICE_PROFILE_REGISTRY_PATH=./backend/config/voice_profiles.json`
- `volumes`:
  - `./data:/app/data`
  - `tts_cache:/root/.local/share/tts`
- `healthcheck`:
  - `curl -fsS http://localhost:8000/docs >/dev/null || exit 1`

### volumes
- Mevcut: `postgres_data`
- Yeni: `tts_cache`

---

## 3) Geçici Script: temp_gate_check.sh

### Script Kuralları
- `set -euo pipefail`
- `trap 'cleanup_db; rm -f "$0"' EXIT INT TERM`

### cleanup_db (zorunlu sıra)
1. İlk adım:
   - `docker compose -f docker-compose.dev.yml up -d db backend`
2. DB readiness bekleme:
   - `pg_isready` loop
3. `db` container içinde:
   - `DELETE FROM users WHERE username='gate_user';`
   - `SELECT COUNT(*) ... == 0` doğrulaması
4. Hata olsa da script dosyası silinecek.

### Koşum Akışı
1. `docker compose up -d --build db mqtt backend`
2. Readiness bekleme (`db health`, `backend /docs`)
3. Seed user oluşturma (`gate_user`, idempotent)
4. Login token alma

#### Warm-up (zorunlu)
5. Kısa TTS job gönder (`voice_profile=premium_market_tr`)
6. Job status poll (`/api/v1/media/tts/{id}`) -> `done`
7. Warm-up tamamlanmadan Gate-1 başlamaz

#### Gate-1 Async tıkanma
8. Uzun TTS job başlat
9. Aynı anda 30 login isteği
- PASS:
  - timeout = 0
  - p95 < 1.5s

#### Gate-2 Docker binary
10. backend container içinde:
- `ffmpeg -version`
- `ffprobe -version`
- `python -c "import soundfile"`
- PASS: hepsi başarılı

#### Gate-3 Volume permission
11. Script içinde 5–10MB valid wav üret
12. `/api/v1/media/upload` ile gönder
13. DB'de media satırında hash/path güncellemesini doğrula
- PASS:
  - Permission denied / 500 yok
  - işleme tamamlanıyor

#### Gate-4 DB persistence
14. marker `tts_job_id` oluştur
15. `docker compose down`
16. `docker compose up -d db mqtt backend`
17. Readiness bekleme
18. `GET /api/v1/media/tts/{marker}` doğrulama
- PASS:
  - kayıt korunmuş

### Rapor Çıktısı
Terminalde tek tablo:
- `WARMUP`
- `GATE1`
- `GATE2`
- `GATE3`
- `GATE4`
- `CLEANUP`
- `OVERALL`

Exit code:
- `0` -> tümü PASS
- `1` -> herhangi FAIL

---

## Kabul Kriterleri
1. Docker stack sağlıklı kalkar; backend migration sonrası çalışır.
2. Warm-up başarılı ve Gate-1 false negative üretmez.
3. 4 gate PASS.
4. `gate_user` test sonunda DB'de yok.
5. `temp_gate_check.sh` test sonunda yok (self-delete).

## Varsayımlar
1. Docker Compose v2 (`service_healthy` destekli).
2. İlk XTTS indirmesi için internet erişimi mevcut.
3. Bu faz API sözleşmesini değiştirmez; infra doğrulama fazıdır.

## Genişletme Notu
Bu plan şu an sadece TTS gate'lerini içeriyor.
Adım 3 tamamlanınca şu gate'ler eklenecek:
- Gate-5: MQTT Heartbeat bağlantısı
- Gate-6: Sync Engine dosya senkronizasyonu
- Gate-7: Scheduler job tetiklemesi
