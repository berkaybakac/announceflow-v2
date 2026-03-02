# Backlog

- [P1] XTTS Zero-shot Voice Cloning (xtts_clone): Kullanıcıların kendi `.wav` dosyalarını yükleyerek anında ses klonlaması yapabilmesi için resolver güvenliği (path traversal önlemleri) ve FFmpeg ön işlemesi.
- [P1] Voice profile registry doğrulaması için startup health-check: `TTS_VOICE_PROFILE_REGISTRY_PATH` dosya varlığı, JSON şema uyumu ve default profile doğrulamasının uygulama açılışında fail-fast raporlanması.
- [P1] `/api/v1/media/tts/voices` endpoint’i: Aktif voice profile alias listesini (`enabled=true`) döndürerek dashboard tarafında güvenli seçim menüsü sağlanması.
- [P1] Teknik Borç / Ölçeklenme: Multi-admin veya çoklu kullanıcı senaryosuna geçilirse, Scheduler API'deki check-then-insert işlemi (çakışma motoru) race condition'ı önlemek için atomikleştirilmelidir (örn: Serializable TX veya Distributed Lock ile).

## Faz 3 Stabilizasyon Kapanışı (2026-03-02)

- [P0] ~~Shutdown sonrası process kapanmıyor (signal/shutdown akışı)~~ **DONE (2026-03-02):** `shutdown_event` sinyal akışı ile boot bekleme döngüsü kontrollü sonlandırılıyor (`agent/main.py`).
- [P1] ~~pytest discovery agent testlerini kapsamıyor~~ **DONE (2026-03-02):** `pytest.ini` içinde `testpaths = tests agent/tests` tanımı ile varsayılan toplu test koşusunda her iki dizin de collect ediliyor.
- [P1] ~~SQLite foreign key enforcement kapalı~~ **DONE (2026-03-02):** Agent SQLite bağlantısına `PRAGMA foreign_keys=ON` eklendi (`agent/core/database.py`) ve FK davranışı testlerle doğrulandı (`agent/tests/test_database_init.py`).

## Faz 3 — Teknik Borç ve İyileştirme Önerileri

- [P1] **Agent Sync Engine — FK-safe apply sırası + transaction sınırı:** Sync implementasyonunda DB apply adımları tek transaction içinde yürütülmeli (upsert media → upsert schedules → delete schedules → delete media). Amaç: FK ihlalinde partial state bırakmamak. **Tetikleyici:** `agent/sync` orkestrasyon kodu yazılırken.
- [P1] **Agent Sync IntegrityError yönetimi:** `local_schedules` FK ihlalinde crash yerine kontrollü hata yönetimi zorunlu (try/except, rollback, structured log, `sync_confirm=partial`/retry politikası). **Tetikleyici:** Manifest sync write path devreye alınırken.
- [P2] **Sync sonrası FK self-check:** Sync tamamında `PRAGMA foreign_key_check` ile otomatik doğrulama/telemetry metriği eklenmeli. Amaç: olası veri bozulmasını erken tespit. **Tetikleyici:** Sync servisinin ilk production hardening turu.
- [P1] **python-json-logger bağımlılığı:** `pythonjsonlogger` kütüphanesi aktif geliştirmede değil ve 3.x'te import path değişikliği (breaking change) yaptı. Şu an çalışıyor (YAGNI). İleride sorun çıkarsa iki alternatif: (1) `structlog` (daha popüler, ama daha ağır), (2) Python `logging` modülü üzerine 10 satırlık kendi `JsonFormatter`'ımızı yazmak. **Tetikleyici:** Kütüphane yeni bir breaking change yaparsa veya güvenlik açığı bulunursa.
- [P1] **Singleton `_connection` test kırılganlığı:** `agent/core/database.py`'deki global `_connection` singleton, production'da doğru çalışıyor. Ancak testlerde fixture ile `_connection = None` reset etmek gerekiyor — bu kırılgan. Test sayısı artarsa `get_db()` fonksiyonuna `reset=True` parametresi eklemek veya bir `DatabaseManager` sınıfına dönüştürmek düşünülmeli. **Tetikleyici:** Agent test sayısı 20'yi aşarsa veya test izolasyonu sorun olmaya başlarsa.
- [P1] **Signal handler lambda closure:** `agent/main.py`'deki `loop.add_signal_handler(sig, lambda: ...)` pattern'i Python'da "late binding closure" uyarısı verebilir (burada `sig` lambda içinde kullanılmadığı için sorun yok). Statik analiz araçları (ruff, mypy) ileride uyarı basabilir. **Tetikleyici:** CI/CD pipeline'a linter eklenirse.
- [P1] **`requirements.txt` pin stratejisi:** Development'ta `>=` ile minimum versiyon belirttik (doğru). Production Docker imajı build edildiğinde (Faz 4) tüm bağımlılıklar `pip freeze > requirements.lock` ile kesin versiyona kilitlenmeli. **Tetikleyici:** Faz 4 — Dockerfile.agent yazılırken.

## Donanım İyileştirmeleri

- [DOC] Raspberry Pi 4 cihazlarına DS3231 RTC (Gerçek Zamanlı Saat) modülü takılması MVP aşamasında ertelenmiştir. Ticari sürümde, elektrik/internet kesintisi kaynaklı saat sapmalarını (Clock Drift) önlemek için bu modül (ihtiyaç olduğu tespit edilirse) donanıma eklenecektir.

## R&D ve Gelecek Vizyonu

- [DOC] Piper (offline, CPU-friendly): Türkçe anons kalitesi, hız ve kaynak tüketimi karşılaştırması; Raspberry Pi üzerinde gerçek zamanlılık ve ses doğallığı benchmark'ı.
- [DOC] Kokoro (hafif model ailesi): XTTS v2 ile Türkçe okunabilirlik/prosodi A-B testi; düşük gecikme ve düşük bellek profili için aday entegrasyon araştırması.
- [DOC] F5-TTS (yüksek kalite odağı): Master node üzerinde kalite kazanımı vs. donanım maliyeti analizi; edge cihazlara uygunluk sınırı ve hibrit mimari değerlendirmesi.
- [DOC] Test Stratejisi: Projenin bağımlılıklarını (dependency) kirletmemek adına, alternatif TTS modelleri asla projenin ana .venv ortamına kurulmamalıdır. Hızlı testler Hugging Face Spaces üzerinden, izole lokal donanım testleri ise Pinokio (pinokio.computer) gibi 1-tıkla çalışan sanal ortam kurucuları üzerinden yapılmalıdır.

## Faz 4 (Entegrasyon & Dockerization) Öncesi Çözülecek Teknik Borçlar

- [P0] ~~Unique Constraint Eksiği (Backend): branches.token kolonu benzersiz (unique) değil. Provisioning çakışmalarını önlemek için DB şemasına unique constraint eklenecek.~~ **DONE (2026-02-26):** `branches.token` için unique constraint eklendi (`uq_branches_token`, Alembic: `91cec57a7c2c`).
- [P0] Download endpoint ACL zafiyeti (is_global/media_targets bazlı yetkilendirme): Device JWT ile medya indirme endpoint'i branch kapsamı doğrulaması yapmıyor. Şube bazlı erişim kısıtı ACL sözleşmesine göre zorunlu hale getirilecek.
- [P1] Agent DB Volume Path (DevOps): Dockerization aşamasında agent.db kalıcılığını sağlamak için SQLite yolu relative (sqlite:///agent.db) halinden absolute bir volume path'ine (/data/agent.db) taşınacak ve settings.py buna göre güncellenecek.
- [P1] Transaction Sınırı Dağınıklığı (Backend): get_db() auto-commit davranışı ile router seviyesindeki manuel commit karmaşası giderilecek. Rollback semantiği güvenli hale getirilecek.
- [DOC] ~~Blueprint Drift: Geliştirme sürecinde alınan mimari kararlar (BackgroundScheduler kullanımı, music ve announcements listelerinin ayrılması, hedeflenmiş yayın yerine global yayın seçilmesi) AnnounceFlow_V2_MasterBlueprint_FINAL.md dosyasına "As-Built" olarak yansıtılacak.~~ **DONE (2026-02-26):** Blueprint 3B.3 (manifest sözleşmesi), 3D.2 (TTS), 3D.4 (media_targets, dosya yolları) As-Built notlarıyla güncellendi. branches ek kolonları, media_files ek kolonları, tts_jobs ve logs tablo tanımları eklendi.

## Faz 3 Adım 2 Öncesi Denetim Bulguları (2026-02-26)

- [P1] **schedule_service HTTPException kirlenmesi:** `backend/services/schedule_service.py` — 7 noktada `HTTPException` doğrudan service katmanından fırlatılıyor (satırlar 60, 65, 97, 167, 185, 189, 229). Service katmanı domain exception fırlatmalı, router HTTP'ye çevirmeli. **Tetikleyici:** Service layer başka bir context'te (CLI, başka framework) reuse edilirse.
- [P1] **MQTT cmd publish mekanizması eksik:** Blueprint 3B.1 `announceflow/{city}/{branch_id}/cmd` topic'ini tanımlıyor ama Backend'de cmd publish eden endpoint/servis yok. `mqtt_listener.py` sadece `/status` ve `/lwt` dinliyor. **Tetikleyici:** Agent MQTT client'ı yazılırken (Adım 2+).
- [P1] **Logger tutarsızlığı:** `backend/services/manifest_service.py:27` `shared.logger.get_logger()` kullanıyor; diğer tüm backend servisleri `logging.getLogger(__name__)` kullanıyor. Bir servis JSON namespace'li log üretirken diğerleri standart Python logger kullanıyor. **Tetikleyici:** Log analizi veya merkezi log formatı standardizasyonu gerektiğinde.
- [P1] ~~**SyncConfirmRequest.status validation eksik:** `backend/schemas/manifest.py:55` — `status: str = "ok"` herhangi bir string kabul ediyor. `Literal["ok", "partial"]` veya Enum olmalı.~~ **DONE (2026-02-26):** `SyncConfirmRequest.status` alanı `Literal["ok", "partial"]` kısıtıyla güncellendi (`backend/schemas/manifest.py:56`).
