# Backlog

- [Feature] XTTS Zero-shot Voice Cloning (xtts_clone): Kullanıcıların kendi `.wav` dosyalarını yükleyerek anında ses klonlaması yapabilmesi için resolver güvenliği (path traversal önlemleri) ve FFmpeg ön işlemesi.
- [Tech Debt] Voice profile registry doğrulaması için startup health-check: `TTS_VOICE_PROFILE_REGISTRY_PATH` dosya varlığı, JSON şema uyumu ve default profile doğrulamasının uygulama açılışında fail-fast raporlanması.
- [Feature] `/api/v1/media/tts/voices` endpoint’i: Aktif voice profile alias listesini (`enabled=true`) döndürerek dashboard tarafında güvenli seçim menüsü sağlanması.
- [Tech Debt] Teknik Borç / Ölçeklenme: Multi-admin veya çoklu kullanıcı senaryosuna geçilirse, Scheduler API'deki check-then-insert işlemi (çakışma motoru) race condition'ı önlemek için atomikleştirilmelidir (örn: Serializable TX veya Distributed Lock ile).

## Faz 3 — Teknik Borç ve İyileştirme Önerileri

- [Tech Debt] **python-json-logger bağımlılığı:** `pythonjsonlogger` kütüphanesi aktif geliştirmede değil ve 3.x'te import path değişikliği (breaking change) yaptı. Şu an çalışıyor (YAGNI). İleride sorun çıkarsa iki alternatif: (1) `structlog` (daha popüler, ama daha ağır), (2) Python `logging` modülü üzerine 10 satırlık kendi `JsonFormatter`'ımızı yazmak. **Tetikleyici:** Kütüphane yeni bir breaking change yaparsa veya güvenlik açığı bulunursa.
- [Tech Debt] **Singleton `_connection` test kırılganlığı:** `agent/core/database.py`'deki global `_connection` singleton, production'da doğru çalışıyor. Ancak testlerde fixture ile `_connection = None` reset etmek gerekiyor — bu kırılgan. Test sayısı artarsa `get_db()` fonksiyonuna `reset=True` parametresi eklemek veya bir `DatabaseManager` sınıfına dönüştürmek düşünülmeli. **Tetikleyici:** Agent test sayısı 20'yi aşarsa veya test izolasyonu sorun olmaya başlarsa.
- [Tech Debt] **Signal handler lambda closure:** `agent/main.py`'deki `loop.add_signal_handler(sig, lambda: ...)` pattern'i Python'da "late binding closure" uyarısı verebilir (burada `sig` lambda içinde kullanılmadığı için sorun yok). Statik analiz araçları (ruff, mypy) ileride uyarı basabilir. **Tetikleyici:** CI/CD pipeline'a linter eklenirse.
- [Faz 4] **`requirements.txt` pin stratejisi:** Development'ta `>=` ile minimum versiyon belirttik (doğru). Production Docker imajı build edildiğinde (Faz 4) tüm bağımlılıklar `pip freeze > requirements.lock` ile kesin versiyona kilitlenmeli. **Tetikleyici:** Faz 4 — Dockerfile.agent yazılırken.

## Donanım İyileştirmeleri

- [Hardware] Raspberry Pi 4 cihazlarına DS3231 RTC (Gerçek Zamanlı Saat) modülü takılması MVP aşamasında ertelenmiştir. Ticari sürümde, elektrik/internet kesintisi kaynaklı saat sapmalarını (Clock Drift) önlemek için bu modül (ihtiyaç olduğu tespit edilirse) donanıma eklenecektir.

## R&D ve Gelecek Vizyonu

- [R&D] Piper (offline, CPU-friendly): Türkçe anons kalitesi, hız ve kaynak tüketimi karşılaştırması; Raspberry Pi üzerinde gerçek zamanlılık ve ses doğallığı benchmark'ı.
- [R&D] Kokoro (hafif model ailesi): XTTS v2 ile Türkçe okunabilirlik/prosodi A-B testi; düşük gecikme ve düşük bellek profili için aday entegrasyon araştırması.
- [R&D] F5-TTS (yüksek kalite odağı): Master node üzerinde kalite kazanımı vs. donanım maliyeti analizi; edge cihazlara uygunluk sınırı ve hibrit mimari değerlendirmesi.
- Test Stratejisi: Projenin bağımlılıklarını (dependency) kirletmemek adına, alternatif TTS modelleri asla projenin ana .venv ortamına kurulmamalıdır. Hızlı testler Hugging Face Spaces üzerinden, izole lokal donanım testleri ise Pinokio (pinokio.computer) gibi 1-tıkla çalışan sanal ortam kurucuları üzerinden yapılmalıdır.

## Faz 4 (Entegrasyon & Dockerization) Öncesi Çözülecek Teknik Borçlar

- [P0] Unique Constraint Eksiği (Backend): branches.token kolonu benzersiz (unique) değil. Provisioning çakışmalarını önlemek için DB şemasına unique constraint eklenecek.
- [P1] Agent DB Volume Path (DevOps): Dockerization aşamasında agent.db kalıcılığını sağlamak için SQLite yolu relative (sqlite:///agent.db) halinden absolute bir volume path'ine (/data/agent.db) taşınacak ve settings.py buna göre güncellenecek.
- [P2] Transaction Sınırı Dağınıklığı (Backend): get_db() auto-commit davranışı ile router seviyesindeki manuel commit karmaşası giderilecek. Rollback semantiği güvenli hale getirilecek.
- [Doc] Blueprint Drift: Geliştirme sürecinde alınan mimari kararlar (BackgroundScheduler kullanımı, music ve announcements listelerinin ayrılması, hedeflenmiş yayın yerine global yayın seçilmesi) AnnounceFlow_V2_MasterBlueprint_FINAL.md dosyasına "As-Built" olarak yansıtılacak.
