**STATEK SOUND**

**AnnounceFlow V2**

MASTER BLUEPRINT — SOURCE OF TRUTH (FINAL)


> **Kimlik:** Hub & Spoke, Offline-First, Token Korumalı IoT Ses Sistemi


> **Mimari:** Modüler Monolit | Monorepo (Tek Klasör, Tek Repo)


> **Öncelik Sırası:** Ezan / Mesai Dışı (Sessiz) > Anons (Müzik Durur) > Fon Müziği


> **Marka:** Statek Sound — Tüm arayüzler bu kimlik altında çalışır


> **Versiyon:** FINAL (v6.0 → v12.21 tüm güncellemeleri birleştirildi, çakışmalar çözüldü)


# BÖLÜM 1 — TEKNİK ANAYASA (PROTOKOLLER)

Bu kurallar her adımda, istisnasız geçerlidir. Hiçbir modül veya özellik bu protokollerin dışına çıkamaz.


## 1. Clean Slate Migration (Temiz Sayfa)

- V1 kodları (legacy_reference/ dizini) asla doğrudan import edilmez.

- Yalnızca V1 mantığına bakılır; backend ve agent klasörlerine sıfırdan yeniden yazılır.


## 2. Consultative Development (Danışmalı Geliştirme)

- Yeni bir modüle başlamadan önce kod yazmadan önce 'En iyi kütüphane / yaklaşım nedir?' analizi yapılır.

- Sprint Operasyon Standardı (Multi-Agent Workflow):

    - Danışma: Mimari onay ve Best Practice soruları 'Hoca-Lider'den alınır.

    - Üretim: Kod, PROJECT_VISION_PROMPT.md ile beslenmiş 'İşçi LLM' tarafından izole ortamda yazılır.

    - Denetim: Yazılan kod, AUDITOR_PROMPT.md kriterlerine göre denetlenmeden ana projeye alınmaz.

    - Montaj: Denetimden geçen kod manuel olarak projeye eklenir ve commit edilir.


## 3. Testing Strategy (Test Stratejisi)

> ✓ KURAL: TDD yerine 'Kritik Yol Testi' (Critical Path Testing) uygulanır.

- Araç: Pytest + AI Assistant (Cursor/Copilot). Ekstra SaaS bağımlılığı (TestSprite vb.) oluşturulmaz.

- Kapsam — Zorunlu Test Gerektiren Modüller:

    - Auth (JWT & Handshake)

    - Priority Manager (Ezan/Anons/Müzik State Machine)

    - Sync Engine (Manifest Hash Karşılaştırma)

- Yasak: Basit CRUD işlemleri için test yazmak — over-engineering olarak kabul edilir.

- Kural: Testten geçmeyen kod Main Branch'e alınmaz.


## 4. Design Patterns

- Repository Pattern: ZORUNLUDUR. Veri erişimi ile iş mantığı birbirinden ayrılır.

- Singleton: Veritabanı bağlantısı için uygulanır.

- Modüler Monolit: Sistem bu mimariyle tasarlanır.

- Mikroservis Mimarisi: YASAKTIR. Solo Dev yönetim zorluğu nedeniyle kesinlikle uygulanmaz.


## 5. Logging Strategy (Loglama Stratejisi)

> ✓ KURAL: SD kartı korumak için cihazda genel log dosyası tutulmaz. Loglar merkeze akar. Sadece 'Crash Dump' cihazda kalır.

- Format: JSON (Structured Logging). Arama ve makine okumaya uygun.

- Yasak: Kod içinde gelişigüzel print() kullanımı kesinlikle yasaktır.

- Zorunluluk: Tek bir merkezi Logger sınıfı kullanılır; tüm loglar buradan üretilir.

- Seviye: Varsayılan INFO. DEBUG modu sadece ENV değişkeni ile geçici olarak aktif edilir.

- Flood Protection: Aynı hata mesajı saniyede >10 kez gelirse loglama duraklatılır, özet geçilir (Error Throttling).

- Log Rotation (Cihaz / Agent):

    - Docker Driver: json-file, max-size=10m, max-file=3 → Toplam 30MB tavan.

- Log Rotation (Merkez / Master):

    - Docker seviyesinde sabit limit uygulanmaz; tüm geçmiş saklanır.

    - Disk dolmadan önce uyarı için heartbeat payload içinde disk_usage izlenir.

> ⚠ ÇÖZÜLEN ÇAKIŞMA: v12.20 'master disk dolana kadar sakla' ile v12.21 'tüm servisler 10m/3file' çakışıyordu. Çözüm: Agent=30MB sabit tavan, Master=disk izleme ile esnek saklama.


## 6. Code Review Protocol (Self-Correction)

- Her özellik tamamlandığında, Main Branch'e geçmeden önce AUDITOR_PROMPT.md ile güvenlik ve mantık hatası taraması yapılır.

- Hiçbir modül denetimden geçmeden ana koda dahil edilemez.


## 7. OTA Deployment Protocol (Temassız Dağıtım)

> ✓ KURAL: Şubelere kod güncellemek için manuel SSH bağlantısı veya git pull YASAKTIR.

- Güncellemeler merkezi Docker Registry (GHCR) üzerinden otomatik olarak Watchtower tarafından çekilir.

- İşleyiş: Merkez 'Push' yapar → Watchtower yeni imajı algılar → Eski container durdurulur → Yeni imaj çekilip başlatılır (Sıfır Manuel Müdahale).


## 8. Architectural Integrity (Mimari Bütünlük)

- Kural: Modüler Monolit mimarisi.

- Yasak: Mikroservis Mimarisi (Solo Dev yönetim zorluğu).

- Monorepo Klasör Yapısı: /backend (Merkez), /agent (Şube), /shared (Ortak Modeller).


## 9. Development Standards (Geliştirme Standartları)

- API First: Kod yazılmadan önce Pydantic şemaları (Sözleşme) hazırlanır.

- Type Safety: Tüm Python kodlarında Type Hinting zorunludur.

- SOLID prensipleri zorunludur. Repository Pattern (Veri/İş Mantığı ayrımı) şarttır.


## 10. Intellectual Property & Security (Fikri Mülkiyet — 3 Katmanlı Savunma)

- Katman 1 — Kod Gizleme (Compilation & Obfuscation):

    - Teknoloji: Nuitka (veya Cython).

    - Python kaynak kodları (.py), sahaya gitmeden önce C++ üzerinden makine diline (.bin/.so) derlenir.

    - SD kartta okunabilir kod bulunmaz; sadece binary dosyalar yer alır.

    - Zamanlama: Kodlar tamamlandığında, SD karta yüklemeden hemen önce (Faz 4).

- Katman 2 — Donanım Kilidi (Hardware Binding — Offline):

    - Derlenmiş yazılım açılışta Raspberry Pi'nin CPU Serial numarasını okur.

    - Merkezden gelen şifreli 'Lisans Dosyası'ndaki seri numara eşleşmezse yazılım kendini kapatır.

    - Bu kontrol internet gerektirmez (SD kart kopyalanmaya karşı tam koruma).

- Katman 3 — Sunucu Yetkilendirmesi (Token Auth — Online):

    - JWT & Device Whitelist. Kill Switch: Sunucu, yetkisiz cihaza dosya göndermez (403 Forbidden) ve kara listeye alır.

    - Ağ Güvenliği: Şubeler GitHub kaynak koduna erişemez; yalnızca derlenmiş Docker imajına (Registry) erişir.

- Donanım Kilidi esastır. PyArmor (maliyetli yazılım koruması) tercih edilmez.


# BÖLÜM 2 — UYGULAMA DETAYLARI (IMPLEMENTATION SPECS — FINAL)


## 1. Topoloji & Bağlantı (Connectivity — Zero-Touch)

- Merkez (Hub): Sabit IP veya Domain (DNS) ZORUNLUDUR. Şubeler burayı 'Ev' bilir.

- Şube (Agent): Dinamik IP alabilir. NAT arkasında çalışabilir. Statik IP gerekmez.

- Yön: Outbound (Şube → Merkez). Port Forwarding YOK.

- Zero-Touch Aktivasyon: SD karta fabrikada gömülen device_token.txt ile cihaz, internete girdiği an merkeze 'Ben Geldim' mesajı gönderir.

- Güvenlik: Cihaz ID + JWT Token.

- Protokol: MQTT (Komut/Kontrol) + HTTP/HTTPS (Veri/Dosya).


## 2. İletişim Protokolleri (Hybrid Protocol)

- Control Plane: MQTT (Port 1883/8883). Anlık emirler, LWT (Last Will & Testament), Heartbeat.

- Data Plane: HTTP/HTTPS (Port 80/443). Büyük dosya transferi ve Log upload.

- Sync Yöntemi: Manifest Sync. Merkez manifest.json sunar. Şube farkı (Diff) bulup yalnızca gerekeni çeker.


## 3. Sunucu Güvenliği (Server Hardening & Anti-Lockout)

- Firewall (UFW): Sadece zorunlu portlar açık — 80, 443, 1883, 22. Diğerleri DROP.

- Fail2Ban: Brute-Force koruması (5 başarısız deneme → 1 saat ban).

- Sigorta (Anti-Lockout): Admin IP'si ve Tailscale VPN IP bloğu Fail2Ban ignoreip (Whitelist) listesine eklenir. Admin asla banlanamaz.


## 4. Uzaktan Müdahale (Remote Access Strategy) — DOĞRU VERSİYON

> ✓ KURAL: Birincil: Alpemix. SSH (Port 22) her zaman açık — backbone. Tailscale/ZeroTier: Ücretsiz VPN alternatifleri olarak opsiyonel not.

> ⚠ ÇÖZÜLEN ÇAKIŞMA: Önceki versiyonda 'Tailscale öncelikli, Alpemix opsiyonel' yazıyordu. Tailscale ücretli olduğu için YANLIŞ. Düzeltildi: Alpemix birincil, ücretsiz alternatifler not olarak belgelendi.

- Katman 1 — SSH (Her Zaman Açık, Backbone):

    - Port 22 her zaman açık. Bu sistemin 'arka kapısı'. Alpemix kilitlense bile terminal erişimi garantidir.

    - Fail2Ban whitelist'e kendi sabit IP'n eklenir. Admin asla banlanamaz.

- Katman 2 — Alpemix (Birincil Uzaktan Müdahale Aracı):

    - Müşteri ekranını görebilir, terminal açabilirsin. Sorun tespiti için görsel müdahale imkânı.

    - Müşteri alışkanlığıyla uyumlu. Kurulumda standart olarak yüklenir.

    - RAM Takibi: Heartbeat payload'daki ram_usage verisiyle Alpemix'in 1GB üzerindeki etkisi izlenir.

- Katman 3 — Ücretsiz VPN Alternatifleri (Opsiyonel Not):

**Ücretsiz VPN Alternatifleri**

| Araç | Ücretsiz Limit | Not |
| --- | --- | --- |
| Tailscale | 3 kullanıcı, 100 cihaz (Free Tier) | Ücretsiz tier yeterli. Ücretli plan gerekmez. Alpemix kasarsa B planı. |
| ZeroTier | 25 cihaz (Free Tier) | Tailscale alternatifi. Kurulumu biraz daha karmaşık ama tamamen ücretsiz. |
| WireGuard | Tamamen ücretsiz (self-hosted) | En güçlü ama kurulumu manuel. Sadece çok sıkışırsan düşün. |


- Öneri: Alpemix çalışıyor. Tailscale/ZeroTier'ı şimdi kurma, ihtiyaç olursa 30 dakikada eklenir.


## 5. Gözlemleme ve Uyarı (Fleet Monitoring & Telemetry)

- Mekanizma 1 — LWT (Anlık): MQTT Last Will & Testament. Cihaz bağlantısı koptuğu anda Broker otomatik 'OFFLINE' (🔴) mesajı yayınlar.

- Mekanizma 2 — Heartbeat Payload (Periyodik): Cihaz her 1 dakikada bir şu JSON paketini atar:

> ⚠ ÇÖZÜLEN ÇAKIŞMA: v12.4 'her 5 dakikada bir' ile v12.9 'her 1 dakikada bir' çakışıyordu. v12.9 (daha güncel ve detaylı) seçildi: 1 dakika.

    - status: ONLINE (🟢) veya WARNING (🟡)

    - current_track: O an çalan dosya adı

    - disk_usage: SD Kart doluluk oranı (%)

    - cpu_temp: İşlemci sıcaklığı (°C)

    - ram_usage: RAM kullanımı (%) — Alpemix izleme için de kullanılır

    - last_sync: Son başarılı eşitleme zamanı (ISO 8601)

    - loop_active: Loop modu aktif mi? (boolean)

- Dashboard Durum Mantığı:

    - 🟢 Yeşil: Her şey yolunda.

    - 🟡 Sarı: disk_usage > %90 veya cpu_temp > 80°C.

    - 🔴 Kırmızı: LWT tetiklendi veya 3 art arda Heartbeat alınamadı.

- Alerting: Kırmızı ve Sarı durumlarda Admin'e Telegram bildirimi gider.


## 6. TTS & Ses Üretim Stratejisi (Master-Side Synthesis)

> ✓ KURAL: Mimari: Ses üretimi (AI/RAM yükü) yalnızca Merkezde yapılır. Şubeler (1GB Pi) sadece MP3 indirip çalar.

- Donanım: Merkez (8GB Pi 4) üretir → MP3 olarak Şubeye (1GB Pi 4) iletir.

- Motor: Coqui XTTS v2 (Voice Cloning opsiyonel; asıl amaç Text-to-Speech, anons sesi üretmektir).

- İşleyiş: Asenkron (Fire-and-Forget). İstek kuyruğa atılır, arka planda işlenir, API bekletilmez.

- Gecikme: 1–10 saniye kabul edilir (kuyruk + üretim + indirme). 15 dakika tolerans içindedir.

> ⚠ ÇÖZÜLEN ÇAKIŞMA: v12.3 '5-10 saniye' ile v12.5 '1-5 saniye' çakışıyordu. Çözüm: '1-10 saniye' (birleştirilmiş aralık).

- B Planı: Performans yetmezse VITS modeline geçilir.


## 7. Voice Engine Soyutlama Katmanı (Architecture)

> ✓ KURAL: Ses işleme mantığı 'voice_engine' adlı bir abstraction layer üzerinden yürütülür.

- Esneklik: MP3 dosyası mı, yoksa TTS motoru mu kullanılacağı tek bir konfigürasyon değişikliğiyle yönetilebilir.

- Gelecek Koruması: Bu yapı sistemi v3, v4 için teknolojik değişimlere karşı hazır tutar.


## 8. Ses Motoru ve Öncelik (Audio Engine)

> ✓ KURAL: Yöntem: Pause & Resume. Ducking (Ses Alçaltma) YOKTUR. Mixing (Karıştırma) YAPILMAZ.

- Akış: Anons gelir → Müzik PAUSE → Anons kendi ses seviyesinde çalar → Anons biter → Müzik kaldığı saniyeden RESUME.

- Kanal Yönetimi (Discrete Volume):

    - volume_music: Fon müziği ses seviyesi (%0–100), bağımsız yönetilir.

    - volume_announce: Anons ses seviyesi (%0–100), bağımsız yönetilir.

    - Dashboard'da iki ayrı slider bulunur.

- Persistent Loop State (Kalıcı Loop Modu):

    - 'Loop' butonu basıldığında durum kalıcı hafızaya (SQLite/Disk) yazılır.

    - Ezan, Anons veya Mesai Dışı kesintileri Loop modunu BOZMAZ.

    - Kesinti bittiğinde sistem 'loop_active' bayrağını kontrol edip döngüyü otomatik başlatır.


## 9. Konfigürasyon Orkestrasyonu (Tag-Based Management)

> ✓ KURAL: Mantık: Metadata-Driven. Şubeler, veritabanındaki etiketlerine göre kendi Playlist'ini dinamik oluşturur.

- Hiyerarşi (öncelik sırasıyla):

    - Local (Şube Bazlı): Örn. 'Mağaza Kapanıyor'

    - Regional (İl/İlçe Bazlı): Örn. 'İstanbul Kampanyası'

    - Global (Tüm Şubeler): Örn. 'Marka Jingle'

- İlke: Idempotency — Merkezden gelen aynı komut tekrar tekrar işlense bile sistem durumunu bozmaz.

- Şube İsimlendirme: Şehir-İlçe-Tip-Ad formatı (Hiyerarşik String). Hem SQL sorgularında hem MQTT topic'te (Örn: announceflow/Gaziantep/Mini/#) anında filtreleme sağlar.


## 10. Dağıtım Modeli (CI/CD & OTA — Hybrid-Cloud Deployment)

- Araçlar: GitHub Actions (Paketleyici) + GitHub Packages / GHCR (Ücretsiz Registry).

- İzolasyon: Agent Container imajı, Dashboard kodlarını İÇERMEZ. Şubeye yalnızca gerekli çalışma dosyaları gönderilir.

- OTA Güncelleme: Watchtower. Şubeler GHCR'ı izler, yeni imaj varsa çeker ve yeniden başlatır.

- Kurtarma (Plug-and-Play Replacement): SD kart bozulursa, yeni kart takılır takılmaz merkezden 'State' (son durum) çekilir.

- Trafik Yönetimi (Jitter): 100 şube aynı anda güncelleme çekmez. '03:00–04:00 arası rastgele zaman' kuralı uygulanır (Thundering Herd engelleme).


## 11. Veri Güvenliği ve SD Kart Koruma

- Yöntem: SQLite WAL Mode (Write-Ahead Logging).

- Overlay FS: KULLANILMAZ. (Yönetim zorluğu ve tutarsızlık nedeniyle iptal — tüm versiyonlarda tutarlı karar).

- Docker Log Rotation: Agent için max-size=10m, max-file=3 (30MB tavan).


## 12. Performans & Yük Yönetimi

- Memory Safety — RAM Koruması:

    - Dosya yüklemede Streaming (Chunked Upload) ZORUNLUDUR.

    - FastAPI spool_max_size ayarıyla büyük dosyalar RAM'e değil diske tamponlanır.

- Concurrency: asyncio (Non-blocking I/O) ile tek çekirdekte binlerce istek karşılanır.

- Veri Gösterimi: Arayüzde Pagination (Sayfalama) ZORUNLUDUR.


## 13. Kendi Kendini Onarma (Self-Healing)

- Yazılım: Docker restart: unless-stopped.

- Donanım: Linux Hardware Watchdog. İşletim sistemi kilitlenirse cihaz otomatik resetlenir.


## 14. Frontend & Dashboard Stratejisi

- Teknoloji: Server-Side Rendering (SSR). Stack: FastAPI + Jinja2 + Tabler (Bootstrap UI).

- Avantaj: Ayrı bir Frontend projesi (React/Vue) ve build süreci yönetilmez. Tek uygulama olarak çalışır.

- Görünüm Modları:

    - Grid View (Kartlar): Şubeler kart olarak listelenir; Yeşil/Kırmızı durum ışığı, çalan şarkı ve ses seviyesi görünür.

    - Data Table (Liste): Toplu yönetim ve filtreleme (Örn: 'Sadece Offline Olanları Göster') için detaylı liste.

    - Map View (Harita): FAZ 2 HEDEFİ. MVP'de yer almaz. (LeafletJS/Google Maps — Solo Dev için Nice-to-have.)

- Yönetim Fonksiyonları:

    - Coğrafi: İl/İlçe seçimi (koordinat yerine API parametresi).

    - Zaman: Mesai saatleri (Açılış/Kapanış).

    - Ses: volume_music ve volume_announce ayrı slider'lar.

    - Targeting UI (Hedefleme): Anons planlarken Multi-select Tree View kullanılır. 'Tüm Antep Grubu' veya tek şube tek tıkla seçilir.


## 15. Statek Control Desktop (Windows EXE)

- Paketleme: Stakeholder için Windows Executable (EXE) kontrol uygulaması.

- Kurulum: Kurumsal logo, 'Statek' markası ve EULA onay ekranı içeren profesyonel Setup.exe.

- System Tray: Uygulama Windows görev çubuğunda saatin yanında (Tray Icon) çalışır.

- Hızlı Aksiyonlar (Sağ Tık Menüsü): 'Anlık Anons Geç', 'Sesi Kapat/Aç', 'Master Paneli Aç'.

- UX Mantığı: Karmaşık ayarlar web panelinde kalır; günlük operasyonel hız EXE kısayolu üzerinden sağlanır.


## 16. Ticari Yapı (Isolated Instances)

> ✓ KURAL: Model: Standalone Master per Client. Her müşteri için ayrı Merkez Sunucu (VPS/Pi) kurulur. Veri izolasyonu tam.

- Multi-tenant (SaaS) mimarisi şimdilik uygulanmaz.

- Sunucu Bütçesi: Ticari süreklilik için aylık ~5$ VPS (Hetzner, DigitalOcean) projenin işletme maliyeti olarak kabul edilir.


## 17. Saha Operasyonu (Factory Protocol — Gold Image)

- Yöntem: Gold Image + Token Injection.

- Temel Linux+Docker imajı (Gold Image) hazırlanır.

- SD karta yazılır.

- **Her SD karta, o cihaza özel benzersiz bir device_token.txt (Script ile) enjekte edilir.**

- Cihaz sahaya gider, fişe takılır ve bu token ile merkeze bağlanır.


# BÖLÜM 3 — VERİTABANI ŞEMASI (FINAL — PostgreSQL Merkez)


Şema %100 tamamlanmıştır. Tablolar arası ilişkiler netleşmiştir.


**Tablo: users (Yetkilendirme — Single Admin, RBAC YOK)**

| Sütun | Tip | Zorunlu | Açıklama |
| --- | --- | --- | --- |
| id | Integer (PK) | ✓ | Primary Key, Auto Increment |
| username | String | ✓ | Kullanıcı adı |
| password_hash | String | ✓ | Argon2 ile hash'lenmiş şifre |
| is_vendor_admin | Boolean | ✓ | True=Geliştirici (/admin/* erişimi), False=Müşteri. Feature Flag Pattern. |
| is_active | Boolean | ✓ | Hesap aktif mi? |


**Tablo: branches (Şubeler — Ana Varlık)**

| Sütun | Tip | Zorunlu | Açıklama |
| --- | --- | --- | --- |
| id | Integer (PK) | ✓ | Primary Key |
| name | String | ✓ | Şehir-İlçe-Tip-Ad formatı (Örn: Gaziantep-Şahinbey-Mini-Merkez) |
| city | String | ✓ | İl (Filtreleme ve MQTT topic için zorunlu) |
| district | String | ✓ | İlçe (Filtreleme için zorunlu) |
| group_tag | String | — | Opsiyonel. Özel gruplamalar için joker alan |
| token | String | ✓ | Cihaz kimlik doğrulama anahtarı (JWT) |
| status | Boolean | ✓ | Online/Offline durumu |
| volume_music | Integer (0-100) | ✓ | Fon müziği ses seviyesi |
| volume_announce | Integer (0-100) | ✓ | Anons ses seviyesi |


> ⚠ ÇÖZÜLEN ÇAKIŞMA: v12.6'da tek 'volume_level' sütunu vardı. v12.11 iki ayrı slider tanımladı. Çözüm: volume_music ve volume_announce olarak ikiye ayrıldı.

> ⚠ AS-BUILT: branches tablosuna Heartbeat Monitor ve Sync Engine için 3 ek kolon eklendi: `is_online` (Boolean — LWT/Heartbeat durumu), `last_sync_at` (DateTime — son başarılı sync zamanı), `sync_status` (String — "ok"/"partial"). `status` kolonu `is_active` olarak yeniden adlandırıldı (Boolean — hesap aktif mi). Alembic migration'ları: `a1b2c3d4e5f6`, `37f6c5eaf145`, `b4d5e6f7a8b9`.

**Tablo: branch_settings (Şube Kuralları — One-to-One)**

| Sütun | Tip | Zorunlu | Açıklama |
| --- | --- | --- | --- |
| id | Integer (PK) | ✓ | Primary Key |
| branch_id | Integer (FK) | ✓ | branches.id — Hangi şube? |
| work_start | Time | ✓ | Mesai başlangıcı (Örn: 08:00) |
| work_end | Time | ✓ | Mesai bitişi (Örn: 20:00) |
| prayer_tracking | Boolean | ✓ | Ezan takibi aktif mi? |
| prayer_margin | Integer | ✓ | Ezan vaktinden kaç dk önce susulsun? (Örn: 1) |
| city_code | Integer | ✓ | Diyanet API plaka kodu |


**Tablo: media_files (Medya Deposu)**

| Sütun | Tip | Zorunlu | Açıklama |
| --- | --- | --- | --- |
| id | Integer (PK) | ✓ | Primary Key |
| file_name | String | ✓ | Görünen ad |
| file_path | String | ✓ | Fiziksel dosya yolu |
| type | Enum | ✓ | 'MUSIC' veya 'ANONS' |
| duration | Integer | ✓ | Süre (saniye) |
| file_hash | String | ✓ | SHA-256 hash (duplicate detection + manifest diff) |
| size_bytes | Integer | ✓ | Dosya boyutu (byte — manifest RAM koruması için) |
| created_at | Timestamp | ✓ | Yükleme zamanı |

> ⚠ AS-BUILT: `file_hash` ve `size_bytes` kolonları geliştirme sırasında eklendi. `file_hash` duplicate upload engelleme ve manifest hash-based diff için, `size_bytes` manifest RAM truncation koruması için kullanılır.


**Tablo: media_targets (Müzik Dağıtımı — ACL/Sync Katmanı)**

| Sütun | Tip | Zorunlu | Açıklama |
| --- | --- | --- | --- |
| id | Integer (PK) | ✓ | Primary Key |
| media_id | Integer (FK) | ✓ | media_files.id — Hangi müzik dosyası? |
| target_type | Enum | ✓ | 'BRANCH', 'GROUP' veya 'ALL' |
| target_id | Integer | — | Hedefin ID'si. ALL için NULL, GROUP için group_tag string |


> ⚠ ÇÖZÜLEN ÇAKIŞMA: media_targets SADECE MÜZİK içindir (ACL/Sync katmanı). Soru: 'Gaziantep şubesinde hangi müzikler çalacak?' → media_targets. Soru: 'Saat 14:00'te hangi anons çalacak?' → schedules. Separation of Concerns: kesin çizgi.

**Tablo: schedules (Anons Zamanlama — Event Trigger Katmanı)**

| Sütun | Tip | Zorunlu | Açıklama |
| --- | --- | --- | --- |
| id | Integer (PK) | ✓ | Primary Key |
| media_id | Integer (FK) | ✓ | media_files.id — Hangi anons? (type=ANONS) |
| target_type | Enum | ✓ | 'BRANCH', 'GROUP' veya 'ALL' |
| target_id | Integer | — | Hedef ID. ALL için NULL |
| play_at | Datetime | — | Tek seferlik tarih/saat |
| cron_expression | String | — | Tekrar eden görev ('0 9 * * 1' = Her Pazartesi 09:00) |
| end_time | Datetime | — | play_at + duration. Çakışma slot kilitleme için. |
| is_active | Boolean | ✓ | Görev aktif mi? |


> ⚠ ÇÖZÜLEN ÇAKIŞMA: schedules SADECE ANONS içindir (Event Trigger katmanı). playlists + playlist_items KALDIRILDI (over-engineering). Müzik shuffle/loop Agent State Machine'i tarafından dinamik olarak çözülür.

> ⚠ AS-BUILT: `schedules` tablosuna `created_at` (DateTime) kolonu ve çakışma motorunu hızlandıran partial index eklendi. Alembic migration: `d4e5f6a7b8c9`.


**Tablo: tts_jobs (TTS İş Kuyruğu — Genişleme)**

> ⚠ AS-BUILT: Bu tablo orijinal 7-tablo çekirdek şemasında yoktu. Backend TTS özelliği (Coqui XTTS v2) implement edilirken eklendi.

| Sütun | Tip | Zorunlu | Açıklama |
| --- | --- | --- | --- |
| id | Integer (PK) | ✓ | Primary Key |
| text_input | Text | ✓ | TTS'e gönderilen metin (max 1000 karakter) |
| language | String(10) | ✓ | Dil kodu (varsayılan: "tr") |
| voice_profile | String(100) | ✓ | Ses profili alias'ı (varsayılan: "default") |
| status | Enum | ✓ | PENDING / PROCESSING / DONE / FAILED |
| media_id | Integer (FK) | — | Üretilen MP3'ün media_files.id referansı (DONE olunca dolar) |
| output_path | String(500) | — | Üretilen dosya yolu |
| created_at | Timestamp | ✓ | İş oluşturma zamanı |
| processed_at | Timestamp | — | İşlem tamamlanma zamanı |


**Tablo: logs (Merkezi Log Deposu — Genişleme)**

> ⚠ AS-BUILT: Bu tablo orijinal 7-tablo çekirdek şemasında yoktu. Agent'lardan gelen JSON logların merkeze akması (Log Ingestion) için eklendi.

| Sütun | Tip | Zorunlu | Açıklama |
| --- | --- | --- | --- |
| id | Integer (PK) | ✓ | Primary Key |
| branch_id | Integer (FK) | ✓ | branches.id — Hangi şubeden? |
| level | String(10) | ✓ | Log seviyesi (INFO/WARNING/ERROR/CRITICAL) |
| module | String(100) | ✓ | Kaynak modül adı |
| message | Text | ✓ | Log mesajı |
| timestamp | Timestamp | ✓ | Orijinal log zamanı (Agent saati) |
| created_at | Timestamp | ✓ | Merkeze yazılma zamanı |


## Priority Stack — Agent State Machine (Kesin Hiyerarşi)

> ✓ KURAL: Agent'ın tüm ses kararları bu 5 seviyeli öncelik yığıtına göre çalışır. Merkez müdahalesi yoktur — Edge Autonomy. Üstteki her zaman alttakini ezer.

**Priority Stack — P0'dan P4'e (0 = En Yüksek)**

| Seviye | Olay (Event) | Tetikleyici | Agent Davranışı |
| --- | --- | --- | --- |
| P0 — KILL_SWITCH | Acil Durdurma | MQTT QoS 2: killswitch topic | TÜM ses anında STOP (pause değil). kill_active=True lokal SQLite'a yazılır. 'Resume' gelene kadar hiçbir şey çalmaz — reboot sonrası da. |
| P1 — PRAYER_TIME | Ezan ve Marj Süresi | Agent lokal prayer_times tablosu (30 günlük cache) | Müzik ve anons PAUSE. Ezan biter + marj geçer → alt önceliğe göre otomatik RESUME. Merkez karışmaz (Edge Autonomy). |
| P2 — OUT_OF_OFFICE | Mesai Dışı Saatler | branch_settings lokal config tablosu (work_start/work_end) | Hiçbir şey çalmaz. Cihaz 'uyku' modunda bekler. Mesai başlayınca P4 devreye girer. |
| P3 — SCHEDULED_ANNOUNCEMENT | Planlı Anons | APScheduler — local_schedules tablosundan yüklenir | Müzik PAUSE, anons çalar, biter → müzik RESUME. P1 aktifse anons P1 bitene kadar BEKLER (Runtime Blocking). |
| P4 — BACKGROUND_MUSIC | Fon Müziği | media_targets'tan gelen dosya listesi, boot sonrası otomatik | Shuffle+Loop ile sürekli çalar. Üst kısıt yoksa aktiftir. Her olayda PAUSE, olay bitince RESUME. |


- Runtime Blocking (P1 + P3 çakışması): P3 saati geldi ama P1 aktif → P3 bekler. P1 biter → P3 otonom RESUME. Merkez bu karara karışmaz.

- Implementasyon: Priority Stack bir Python Enum veya sıralı if/elif zinciri olarak kodlanır. AI editöre açık talimat: bu sıralamayı değiştirme, genişletme, yorum katma.

- Kill_active flag: P0 tetiklendiğinde lokal SQLite config tablosuna yazılır. Reboot sonrası da P0 aktif kalır. Sadece MQTT 'resume' komutu temizler.


# BÖLÜM 3B — KRİTİK EKSİK SPESIFIKASYONLAR (Son Dokunuşlar)

Bu bölüm, sistemin çalışması için zorunlu olan ancak önceki versiyonlarda belgelenmemiş 4 kritik spesifikasyonu içerir.


## 3B.1 MQTT Topic Naming Convention

> ✓ KURAL: Bu kural olmadan Agent ve Master birbirine bağlanamaz. Sistemin kalp damarıdır.

**MQTT Topic Yapısı**

| Topic Pattern | Yön | Açıklama / Örnek |
| --- | --- | --- |
| announceflow/{city}/{branch_id}/cmd | Master→Agent | Merkez'den şubeye komut. Örn: announceflow/Gaziantep/42/cmd |
| announceflow/{city}/{branch_id}/status | Agent→Master | Şubenin heartbeat JSON paketi. Örn: announceflow/Gaziantep/42/status |
| announceflow/{city}/{branch_id}/lwt | Broker→Master | Last Will & Testament. Cihaz koptuğunda Broker yayınlar. |
| announceflow/+/+/cmd | Wildcard | Tüm şubelere aynı anda komut göndermek için (Toplu Yayın). |
| announceflow/Gaziantep/# | Wildcard | Sadece Gaziantep şubelerini dinlemek için. |


- QoS Seviyesi:

    - Heartbeat (status): QoS 0 — Kayıp kabul edilir, performans öncelikli.

    - Komutlar (cmd): QoS 1 — En az bir kez iletim garantisi.

    - LWT: QoS 1 — Çevrimdışı tespiti kritik, kayıp kabul edilemez.

**Komut Payload Örnekleri (cmd topic)**

| action | JSON Payload |
| --- | --- |
| volume_set | {"action": "volume_set", "target": "music", "value": 40} |
| volume_set | {"action": "volume_set", "target": "announce", "value": 90} |
| play_announce | {"action": "play_announce", "file_url": "/media/anons_123.mp3", "priority": 1} |
| sync_now | {"action": "sync_now"} |
| restart | {"action": "restart"} |


## 3B.2 İlk Açılış Akışı (Boot Sequence)

> ✓ KURAL: Cihaz fişe takıldığında ilk 60 saniyede sırasıyla şunlar olur.

**Boot Sequence Adımları**

| Adım | İşlem | Başarısız Olursa |
| --- | --- | --- |
| 1 | CPU Serial oku → Lisans dosyasıyla karşılaştır | Yazılım kendini kapatır (Hardware Lock). |
| 2 | device_token.txt oku | Token yoksa hata logla, bekle. |
| 3 | İnternet bağlantısı kontrol et | Offline moduna geç (Adım 6'dan devam et). |
| 4 | Master'a HTTP POST /api/v1/agent/handshake (token ile) | 3 deneme, her biri 10sn bekle. Başarısız: Offline mod. |
| 5 | Master'dan manifest.json çek, lokal ile diff al | Diff başarısız: Mevcut lokal dosyalarla devam et. |
| 6 | Eksik/güncel MP3 dosyalarını indir (Arka planda) | İndirme başarısız: Lokal cache ile devam et, retry kuyruğu. |
| 7 | 30 günlük Ezan vakitlerini kontrol et (SQLite) | Cache yoksa veya <7 gün kaldıysa Diyanet API'den çek. |
| 8 | MQTT Broker'a bağlan (LWT tanımla) | Bağlantı başarısız: Retry (exponential backoff, max 5dk). |
| 9 | Mesai saatini kontrol et | Mesai dışıysa: Sessiz mod. Mesai içindeyse: Müzik başlat. |
| 10 | READY — Heartbeat başlat (1 dakika interval) | Her adım JSON loglanır. |


## 3B.3 Manifest Sync Sözleşmesi

> ✓ KURAL: Master'ın yayınladığı manifest.json formatı ve Diff algoritması.


**Master'ın Ürettiği manifest.json (As-Built — Gerçek Şema):**

> ⚠ AS-BUILT: Orijinal tasarımda tek `files[]` dizisi planlanmıştı. Geliştirme sırasında müzik ve anons ayrımının manifest'e yansıtılması için `music[]` + `announcements[]` + `settings{}` yapısına geçildi. Bu yapı `media_targets = Müzik ACL` / `schedules = Anons Trigger` ayrımıyla tutarlıdır.

```json
{
  "branch_id": 42,
  "generated_at": "2026-02-18T10:00:00+00:00",
  "music": [
    {
      "id": 15,
      "file_name": "jingle_marka.mp3",
      "file_hash": "sha256:abc...",
      "type": "MUSIC",
      "size_bytes": 2048576,
      "download_url": "/api/v1/media/15/download"
    }
  ],
  "announcements": [
    {
      "id": 3,
      "media_id": 22,
      "media_file_name": "kampanya_anons.mp3",
      "media_file_hash": "sha256:def...",
      "media_size_bytes": 1024000,
      "media_download_url": "/api/v1/media/22/download",
      "play_at": "2026-02-18T14:00:00+00:00",
      "cron_expression": null,
      "end_time": "2026-02-18T14:03:00+00:00"
    }
  ],
  "settings": {
    "work_start": "08:00",
    "work_end": "20:00",
    "volume_music": 60,
    "volume_announce": 90,
    "loop_mode": "shuffle"
  }
}
```

- Pydantic şema kaynağı: `backend/schemas/manifest.py` — `ManifestResponse`, `ManifestMediaItem`, `ManifestScheduleItem`, `ManifestSettingsItem`


**Manifest Sync Algoritması (Agent Tarafı)**

| Adım | İşlem |
| --- | --- |
| 1 | Master'dan /api/v1/manifest/{branch_id} endpoint'ini GET ile çek. |
| 2 | Lokal SQLite'daki dosya listesiyle karşılaştır (hash bazlı diff). |
| 3 | Lokal'de olup manifest'te olmayan dosyaları SİL (disk temizliği). |
| 4 | Manifest'te olup lokal'de olmayan veya hash'i farklı olan dosyaları İNDİR. |
| 5 | İndirme tamamlandıktan sonra hash'i doğrula. Eşleşmezse dosyayı sil ve tekrar indir. |
| 6 | Sync tamamlandığında Master'a POST /api/v1/agent/sync_confirm gönder. |


- Tetikleyiciler: Boot sırasında (Adım 5) + MQTT'den 'sync_now' komutu geldiğinde + Her gece 03:00-04:00 arası (Jitter ile).

- Kural: Sync işlemi arka planda (async) çalışır. Müzik çalmayı DURDURMAMALIR.


## 3B.4 Dosya Depolama Stratejisi (Master)

> ✓ KURAL: media_files.file_path sütununda yazılı olan fiziksel yolun nereye karşılık geldiği tanımlanmıştır.

- Master'da MP3 Depolama: /data/media/{branch_id}/{file_id}.mp3 (Docker volume ile kalıcı).

- Agent'ta MP3 Depolama: /data/media/{file_id}.mp3 (Lokal SQLite ile takip edilir).

- Upload Akışı: Web panelinden yükleme → FastAPI Chunked Upload → /data/media/temp/ → FFmpeg normalize → /data/media/{branch_id}/ → Manifest güncellenir → Şubeler bir sonraki sync'te alır.

- Backup: Master disk verisi Docker named volume ile ayrı tutulur. VPS snapshot veya düzenli rsync ile yedeklenir.

- Boyut Tahmini: Ortalama 5MB/MP3, şube başı 200 dosya → ~1GB/şube. 100 şube → ~100GB. Disk planlaması buna göre yapılır.


# BÖLÜM 3D — FİNAL KAPANIŞ SPESİFİKASYONLARI

Tüm soruların cevaplanmasıyla kapanan son açık maddeler. Bu bölümden sonra belgede hiçbir belirsizlik kalmamıştır.


## 3D.1 Anons Çakışma Yönetimi — Zaman Dilimi Kilitleme

> ✓ KURAL: Çakışma State Machine'de değil, UPLOAD ANINDA çözülür. Kullanıcı çakışan zaman dilimine anons yükleyemez. V1'den gelen battle-tested mantık.

**Anons Çakışma Senaryosu**

| Durum | Sistem Davranışı |
| --- | --- |
| 14:00'da 3 dakikalık anons planlanmış | 14:00–14:03 zaman dilimi o şube/grup için KİLİTLİ. |
| Kullanıcı 14:01'e yeni anons yüklüyor | UI 'Bu zaman dilimi dolu' uyarısı gösterir. Yükleme ENGELLENİR. |
| Kullanıcı 14:05'e yüklüyor | Başarılı — çakışma yok. |
| Global + Local aynı saate planlanmış gibi görünüyor | Bu durum oluşamaz — slot zaten kilitli, ikincisi sisteme giremez. |


- schedules tablosuna end_time (Timestamp) sütunu eklenir. play_at + duration hesaplanarak yazılır.

- API: POST /api/v1/schedules/check-conflict — Yükleme öncesi çakışma taraması. UI bu yanıta göre kullanıcıya gösterir.

- Avantaj: Agent tarafı 'iki anons aynı anda' durumuyla hiç karşılaşmaz. State machine tamamen temiz kalır.


## 3D.2 TTS — Faz 2'ye Ertelendi (voice_engine Soyutlaması Korunuyor)

> ✓ KURAL: MVP: Sadece MP3 yükleme. TTS Faz 2. voice_engine abstraction layer MVP'de yazılır — içi şimdilik boş, Faz 2'de dolar.

**MVP vs Faz 2 Karşılaştırması**

| Özellik | MVP | Faz 2 |
| --- | --- | --- |
| Anons üretme | MP3 dosyası yükle | Metni yaz → TTS otomatik MP3 üretir |
| voice_engine modülü | ✅ Yazılır (sadece MP3 oynatır) | TTS backend eklenir, config ile geçiş yapılır |
| Coqui XTTS v2 | ❌ Kurulmaz | Faz 2'de Master'a kurulur (8GB RAM gerektirir) |
| Voice cloning | ❌ | Faz 2'de opsiyonel özellik |


- TTS Kuyruk Tablosu: tts_jobs — id, text_input, voice_profile, status (PENDING/PROCESSING/DONE/FAILED), output_path, created_at, processed_at

> ⚠ AS-BUILT: tts_jobs tablosu ve TTS endpoint'leri Faz 2 hedefinden önce, Backend geliştirmesi sırasında implement edildi. Coqui XTTS v2 entegrasyonu, voice_profile_resolver ve asenkron iş kuyruğu aktif çalışmaktadır. `backend/models/tts.py`, `backend/services/tts_service.py`, `backend/services/voice_profile_resolver.py`.


## 3D.3 Harita (Map View) — Faz 2 Savaş Odası

> ✓ KURAL: Manuel koordinat girişi YOK. Sistem city + district verisinden Nominatim API ile otomatik geocoding yapar.

**Geocoding Pipeline**

| Adım | İşlem | Detay |
| --- | --- | --- |
| 1 | branches.city + branches.district okunur | Örn: 'Gaziantep' + 'Şahinbey' |
| 2 | Nominatim API'ye sorgu | GET nominatim.openstreetmap.org/search?city=...&district=...&format=json |
| 3 | lat/lng veritabanına yazılır | branches.lat, branches.lng sütunları (nullable — Faz 2'de doldurulur) |
| 4 | Başarısız olursa | İl merkezi koordinatı kullanılır (fallback). Manuel düzeltme imkânı bırakılır. |
| 5 | Rate limit koruması | Nominatim: 1 req/sn. Toplu geocoding gece 03:00'da çalışır. |


- Harita UI (LeafletJS): Her şube → Renkli canlı Marker. MQTT Heartbeat'ten güncellenir.

- 🟢 Online + müzik çalıyor  |  🟡 Disk>%90 veya CPU>80°C  |  🔴 LWT / Kill Switch aktif

- Marker tıklanınca popup: şube adı, çalan şarkı, disk %, CPU temp, son sync zamanı.


## 3D.4 Teknik Borç Kapatma — Önceki Versiyonlarda Eksik Kalanlar

### Dosya Yolu Stratejisi (As-Built)

> ⚠ AS-BUILT: Önceki versiyonda `{client_id}` referansı vardı. `clients` tablosu projede YOKTUR (Standalone Master per Client modeli — Bölüm 2.16). Dosya yolları aşağıdaki gibi çalışmaktadır:

- Master'da doğru yol: /data/media/{media_id}.mp3 (Docker volume ile kalıcı)

- Agent'ta doğru yol: /data/media/{media_id}.mp3 (lokal SQLite local_media tablosu ile takip edilir)

- media_files.file_path sütunu: normalize sonrası gerçek dosya yolunu tutar.


### Kaldırılan Tablolar — Karar ve Gerekçe

> ⚠ AS-BUILT: media_targets tablosu KALDIRILMADI — aktif olarak kullanılmaktadır. Önceki versiyondaki "kaldırıldı" kararı geliştirme sırasında geri alındı. media_targets = Müzik ACL katmanı (Hangi müzik hangi şubede?), schedules = Anons Trigger katmanı (Ne zaman hangi anons?). İki tablo farklı sorumlulukları üstlenir (Separation of Concerns). Bu ayrım Bölüm 3 şema tanımlarıyla ve PROJECT_VISION_PROMPT.md ile tutarlıdır.

> ⚠ ÇÖZÜLEN ÇAKIŞMA: playlists + playlist_items tabloları KALDIRILDI: V1'de yoktu, schedules + media_files yeterli. shuffle/loop bilgisi branch_settings'te saklanır. Over-engineering tespit edildi ve temizlendi.

- Sonuç: Veritabanı çekirdek şeması 7 tablo (users, branches, branch_settings, media_files, media_targets, schedules, prayer_times) + 2 genişleme tablosu (tts_jobs, logs). Toplam 9 tablo.


### Agent Lokal SQLite Şeması — Resmi 4 Tablo (Donduruldu)

> ✓ KURAL: AI editöre katı kural: Bu 4 tablodan başka tablo icat etme. Bu şema Agent'ın Offline-First yaşayabilmesinin garantisidir.

**Agent SQLite Tabloları (agent.db) — Kesin Liste**

| Tablo | Amacı | Sütunlar |
| --- | --- | --- |
| config | Key-Value Store — Cihazın anlık durumu ve tüm ayarları. MQTT config_update payload'u buraya yazılır. | work_start, work_end, volume_music, volume_announce, prayer_margin, loop_active, kill_active |
| local_media | Merkezin media_files tablosunun o cihaza düşen iz düşümü (Manifest Sync ile gelir). | id, file_name, file_hash, type (MUSIC/ANONS), local_path |
| local_schedules | Merkezin schedules tablosunun sadece bu cihazı ilgilendiren kısmı. | id, media_id, cron_expression, play_at, end_time |
| prayer_times | Diyanet API'den çekilmiş 30 günlük önbellekli ezan saatleri. | date, fajr, sunrise, dhuhr, asr, maghrib, isha, fetched_at |


- Tüm tablolar WAL Mode ile açılır: PRAGMA journal_mode=WAL — SD kart koruma, eş zamanlı okuma için şart.

- schema_version mekanizması: Tablolara ek olarak tek satırlık schema_version kaydı tutulur (OTA migration için). Ayrı tablo değil, config tablosuna 'schema_version' key'i olarak eklenir.

- APScheduler JobStore: schedule_jobs verisi APScheduler'ın kendi SQLAlchemy mekanizmasıyla aynı agent.db içine yazılır — ayrı tablo açılmaz, framework yönetir.

- Agent hiçbir zaman Master PostgreSQL'e direkt bağlanmaz. Sadece HTTP/MQTT üzerinden iletişim kurar.


### voice_engine Modülü — Facade Pattern (MVP + Faz 2 Stub)

> ✓ KURAL: MVP: LibVLC wrap'i. Faz 2: TTS stub dolar. Facade Pattern: Player.py hiçbir zaman ses backend'ini bilmez.

- Tasarım Deseni: Facade Pattern. voice_engine, player.py ile ses motoru arasında köprü kurar. MVP'de LibVLC, Faz 2'de TTS — player.py hiç değişmez.

- agent/voice_engine/__init__.py yapısı:

    - class VoiceEngine (abstract): play(path), pause(), resume(), stop(), set_volume(int)

    - class LibVLCBackend(VoiceEngine): — Gerçek implementasyon. python-vlc kullanır.

    - class TTSBackend(VoiceEngine): — Faz 2 stub. raise NotImplementedError('TTS: Faz 2')

    - settings.VOICE_BACKEND = 'libvlc' | 'tts' — pydantic-settings'ten gelir.

    - Factory: def get_voice_engine() -> VoiceEngine: return LibVLCBackend() if settings.VOICE_BACKEND == 'libvlc' else TTSBackend()


### Factory Injection Script — Otomasyon

> ✓ KURAL: Script var: Kart takılınca otomatik inject ediyor. Zero-Touch Provisioning vizyonunun kalbi.

- inject_token.sh çalışma akışı:

    - 1. /admin/branches/generate-token API'si çağrılır → UUID token üretilir, DB'ye 'provisioned=False' yazılır.

    - 2. SD kart PC'ye takılır → script boot partition'ı mount eder.

    - 3. /boot/device_token.txt'ye token yazılır. CPU Serial Lock kaydı eklenir.

    - 4. Unmount → Kart güvenli çıkarılır.

    - 5. Token DB'de 'provisioned=True' olarak işaretlenir. Aynı token iki kez kullanılamaz.

- Parametre: ./inject_token.sh <branch_id> <token_uuid> — İkisi de /admin panelinden kopyalanır.


### Best Practice: pydantic-settings + FastAPI BackgroundTasks

> ✓ KURAL: pydantic-settings: .env yönetiminin altın standardı. BackgroundTasks: Celery/Redis overkill, bu ölçek için yeterli.

- pydantic-settings kurulumu:

    - from pydantic_settings import BaseSettings

    - class Settings(BaseSettings): DATABASE_URL: str; MQTT_BROKER: str; VOICE_BACKEND: str = 'libvlc'; model_config = SettingsConfigDict(env_file='.env')

    - settings = Settings() — Uygulama genelinde tek instance. Hardcoded config yasak.


- FastAPI BackgroundTasks (FFmpeg için):

    - @router.post('/media/upload') async def upload(bg: BackgroundTasks, file: UploadFile):

    - bg.add_task(normalize_audio, temp_path, output_path) → return {'status': 'processing'}

    - Neden Celery değil: Celery = Redis + Worker process + Task queue + monitoring. Solo dev, tek sunucu, 100 şube için overkill. BackgroundTasks: FastAPI içinde, ekstra servis yok, 0 overhead.


### SQLite Agent Migration Stratejisi

> ✓ KURAL: OTA güncellemesinde SQLite şeması değişirse: Alembic değil, gömülü migration script.

- Neden Alembic değil? Nuitka ile binary'ye derlenen kodda .py migration dosyaları çalışmaz.

- Çözüm: Agent başlangıçta schema_version tablosunu kontrol eder. Versiyon gerideyse gömülü SQL'leri çalıştırır.

- Kural: Tüm migration SQL'leri idempotent olmalı (iki kez çalışsa bile bozulmasın).


### APScheduler Job Persistence (Reboot Sonrası)

> ✓ KURAL: Agent reboot'ta APScheduler job'larını SQLite'tan yükler. Offline-First ile tam uyumlu.

- JobStore: SQLAlchemyJobStore → Agent'ın SQLite dosyasına bağlanır.

- Kod: AsyncIOScheduler(jobstores={'default': SQLAlchemyJobStore(url='sqlite:///agent.db')})

- Sonuç: Cihaz kapanıp açılsa bile tüm zamanlanmış anonslar kaybolmaz.


# BÖLÜM 3C — KİŞİSELLEŞTİRİLMİŞ TEKNİK SPESİFİKASYONLAR

Bu bölüm, projeye özgü kararlar sorularak elde edilmiştir. Tüm maddeler onaylanmış ve projeye özeldir.


## 3C.1 Ses Çıkışı ve Audio Backend

> ✓ KURAL: Donanım: Raspberry Pi 4 — 3.5mm Jack (Pi'nin yerleşik analog çıkışı). Audio backend: python-vlc (LibVLC).

- Seçim Gerekçesi: Pi'nin 3.5mm jack'i ALSA üzerinden çalışır. Üç seçenek değerlendirildi:

**Audio Backend Karşılaştırması**

| Kütüphane | Artısı | Eksisi | Karar |
| --- | --- | --- | --- |
| python-vlc (LibVLC) | Pause/Resume mükemmel, format bağımsız (MP3/WAV/OGG), volume control API'si var, Pi'de savaşta test edilmiş | Kurulum gerektirir (libvlc-dev) | ✅ SEÇİLDİ |
| pygame.mixer | Basit API, yaygın | Sadece WAV native, MP3 decoder instabil, Pi'de ses takılması sorunu var | ❌ |
| subprocess + mpg123 | Hafif, shell üzerinden | Pause/Resume kontrolü zorlu, state machine kurmak zor | ❌ |


- Kurulum (Agent Dockerfile'a eklenecek): apt-get install -y libvlc-dev vlc-bin + pip install python-vlc

- ALSA Konfigürasyonu: /etc/asound.conf ile varsayılan cihaz 3.5mm jack'e sabitlenir. HDMI ses otomatik seçilmesini engeller.

- Volume Kontrolü: vlc.MediaPlayer().audio_set_volume(int) — 0-100 arası. volume_music ve volume_announce ayrı MediaPlayer instance'larıyla yönetilir.

- V1 Uyumu: V1'de de aynı çıkış kullanılıyorsa, audio backend seçimi büyük ihtimalle aynıdır. legacy_reference/player.py incelenirken hangi kütüphane kullandığı kontrol edilmeli ve uyum sağlanmalıdır.


## 3C.2 Ezan API — Diyanet İşleri Entegrasyonu

> ✓ KURAL: Veri Kaynağı: Diyanet İşleri Resmi API. Endpoint: https://api.ezanvakti.emushaf.net veya vakit.diyanet.gov.tr (V1'deki endpoint kontrol edilmeli).

- Strateji: Her bağlantıda önümüzdeki 30 günün vakitlerini çek → SQLite'a kaydet → İnternet yoksa cache'den oku.

- Cache Kontrolü: Her başlangıçta 'kaç günlük cache var?' kontrolü yapılır. 7 günün altına düşerse yenileme zorlanır.

- Kritik Not: Diyanet API'si plaka kodu (ilçe kodu) ile sorgu kabul eder. branch_settings.city_code sütunu bu değeri tutar.

**Ezan API Kullanım Detayları**

| Konu | Detay |
| --- | --- |
| Endpoint | V1'deki URL korunur. Değişmişse api.ezanvakti.emushaf.net/vakitler/{ilce_id} formatı denenecek. |
| Response Format | JSON — 30 günlük vakitler tek sorgu ile alınır (Fajr, Sunrise, Dhuhr, Asr, Maghrib, Isha). |
| Rate Limit | Diyanet resmi bir rate limit yayınlamaz. Günde 1 sorgu ile 30 gün önceden cache'lemek güvenli. |
| Retry | Bağlanamadıysa: 10dk, 30dk, 2sa, 6sa sonra tekrar dene (exponential backoff). Hepsi başarısız: Cache ile devam et. |
| Failover (Force Majeure) | Cache 0 güne düşerse ve internet yoksa: Ezan özelliği devre dışı kalır, sistem müzik+anons çalmaya devam eder. Loglanır ve admin'e Telegram bildirimi gider. |
| SQLite Tablo | prayer_times: id, branch_id, date (DATE), fajr, sunrise, dhuhr, asr, maghrib, isha (TIME), fetched_at (TIMESTAMP) |


- V1 Legacy Notu: V1'de ezan takibi prod'da sorunsuz çalışıyor. legacy_reference'dan Diyanet API fonksiyonu ve cache mantığı öncelikli olarak alınacak — bu kodu sıfırdan yazmaya gerek yok.


## 3C.3 Legacy Reference — Güncellenmiş Tablo (V1 Prod'da Çalışıyor)

> ✓ KURAL: V1'de müzik çalma, ezan takibi ve scheduler şube bazlı prod ortamında sorunsuz çalışıyor. Bu altın değerinde referanstır.

**V1'den Ne Alınır — Kesinleşmiş Tablo**

| Bileşen | Al mı? | Neden / Ne Yapılır? |
| --- | --- | --- |
| player.py — Müzik Çalma | ✅ AL | Pause/Resume, audio backend seçimi, volume control ÇALIŞIYOR. Mantığını oku, python-vlc ile modern async yapıda yeniden yaz. |
| player.py — Öncelik Mantığı | ✅ AL | Ezan>Anons>Müzik state machine ÇALIŞIYOR. Bu mantığı koruyarak yeniden yaz — en değerli referans. |
| scheduler.py — Tek seferlik | ✅ AL | Prod'da sorunsuz. Mantığını al, DB-driven (PostgreSQL/APScheduler) hale getir. |
| scheduler.py — Tekrarlı/Cron | ✅ AL | Günler + saatler kombinasyonu ÇALIŞIYOR. Aynı mantığı cron_expression formatına çevir. |
| Ezan/Prayer Modülü | ✅ AL | Diyanet API bağlantısı + 30 günlük cache ÇALIŞIYOR. Direkt referans al — büyük zaman tasarrufu. |
| Flask/eski routes | ❌ BIRAK | Mimari tamamen değişti. FastAPI+Repository Pattern ile sıfırdan. |
| Eski DB bağlantıları | ❌ BIRAK | SQLite→PostgreSQL geçişi var. Eski connection kodu işe yaramaz. |
| Config/Hardcoded secrets | ❌ BIRAK | Güvenlik riski. Tüm config .env'e taşınacak. |
| requirements.txt | ⚠️ İNCELE | Kütüphane listesine bak, güncel versiyonları araştır. Direkt kopyalama. |


## 3C.4 Auth, Rol Yapısı ve Dashboard Mimarisi — DOĞRU VERSİYON

> ✓ KURAL: Model: HaaS (Hardware as a Service). Altyapıyı sen kurarsın, Operasyonel Kontrolü müşteri yönetir. RBAC YOK. clients tablosu YOK. Lean Single-Admin JWT mimarisi.

> ⚠ ÇÖZÜLEN ÇAKIŞMA: Önceki versiyonda 'super_admin + client_admin + clients tablosu' eklenmiş. Bu YANLIŞ bir mimari karardı. Her kurulum izole ve bağımsız olduğu için multi-tenant yapıya gerek yok. Tamamen kaldırıldı.


### İş Modeli (HaaS — Hardware as a Service)

**Sorumluluk Sınırları**

| Kim | Ne Yapar? | Ne Yapmaz? |
| --- | --- | --- |
| Sen (Geliştirici) | SD kart hazırlar, donanımı kargolar, Master VPS'i kurar, şubeleri sisteme tanımlar, teknik sorunları uzaktan çözer. | Müşterinin anonsunu ayarlamaz, günlük operasyona karışmaz. |
| Müşteri (Son Kullanıcı) | Dashboard'dan müzik yükler, anons zamanlar, ses ayarlar, mesai düzenler, acil durdurur. | Donanım ekleyemez/silemez. Teknik ayarlara erişemez. |


- Her müşteri kendi izole sisteminde çalışır. Müşteriler birbirinden tamamen habersizdir.

- Kurulum bitince işin biter. Teknik sorun çıkarsa müşteri seni arar, sen SSH/Alpemix ile uzaktan halledersin.


### Auth Mimarisi — Single Admin JWT (RBAC YOK)

> ✓ KURAL: Tek rol tipi. Authorization middleware yok. Backend (FastAPI) tamamen lean kalır.

**Güncellenmiş: users Tablosu (Basit ve Doğru)**

| Sütun | Tip | Açıklama |
| --- | --- | --- |
| id | Integer (PK) | Primary Key |
| username | String | Kullanıcı adı |
| password_hash | String | Argon2 ile hash'lenmiş şifre |
| is_vendor_admin | Boolean | True = Sen (geliştirici). False = Müşteri. /admin/* route'larını korur. RBAC değil — Feature Flag Pattern. |
| is_active | Boolean | Hesap aktif mi? Sözleşme bitince False. |


- Kurulumda 2 hesap: Müşterinin tek sorumlu çalışanı (is_vendor_admin=False) + Senin teknik hesabın (is_vendor_admin=True).

- JWT Claim: { 'sub': user_id, 'is_vendor_admin': true/false, 'exp': timestamp }

- Backend Guard (tek satır, RBAC değil): if not current_user.is_vendor_admin: raise HTTPException(403)

- FastAPI Best Practice — Dependency Injection Pattern:

    - async def verify_vendor_admin(current_user = Depends(get_current_user)):

    - if not current_user.is_vendor_admin: raise HTTPException(status_code=403, detail='Yetersiz yetki')

    - return current_user

    - @router.get('/admin/branches') async def list_branches(admin = Depends(verify_vendor_admin)): ...

- Bu pattern tüm /admin/* route'larına eklenir. Tek tanım, her yerde kullanım (DRY). AI editöre açık talimat: tüm /admin router'larına Depends(verify_vendor_admin) ekle.

- Müşteri /admin URL'ini bilse bile 403 alır. Middleware yok, rol tablosu yok — sadece 1 boolean, 1 satır kontrol.

- clients tablosu: YOK. client_id FK'ları: YOK. Authorization middleware: YOK.


### Dashboard Mimarisi — Tek Panel, İki Kullanım Amacı

> ✓ KURAL: Tek bir FastAPI + Jinja2 paneli. Ayrı URL/site yok. Kullanım amacı ayrışıyor, teknik mimari değil.

**Dashboard Katmanları**

| Katman | Kim Kullanır? | İçerik |
| --- | --- | --- |
| Operational Plane (Müşteri) | Müşteri çalışanı | Müzik/anons yükle, zamanlama, ses seviyesi, mesai saati, kill switch. Altyapı görünmez. |
| Infrastructure & Observability Plane (Sen) | Sen (teknik erişim) | Şube provisioning (branches tablosuna ekleme + token üretme), Fleet telemetri, Log Viewer, cihaz sağlık izleme. |


- Müşteri Operational Plane'e girince: Şubeler listesi, ses ayarları, anons yönetimi, zamanlama. Teknik detay yok.

- Sen Infrastructure Plane'e girince: Yeni Raspberry Pi tanımlama, Device Token üretme, MQTT heartbeat verileri (disk %, CPU temp, bağlantı durumu), JSON Log Viewer, Yeşil/Sarı/Kırmızı durum ışıkları.

- Ayrım nasıl sağlanır? URL prefix ile: /dashboard/* müşteri ekranları, /admin/* teknik ekranlar. Aynı JWT, aynı uygulama — sadece sayfalar ayrı.

- Over-engineering değil: Bu SSR (Jinja2) ile basitçe iki farklı template klasörü demek. Ekstra middleware veya rol sistemi gerektirmez.


### Müşterinin Dashboard'dan Yapabileceği İşlemler (Tam Liste)

**Operational Control Plane — Müşteri Yetkileri**

| İşlem | Teknik Karşılığı |
| --- | --- |
| Müzik / Anons Yükle | Media Ingestion Pipeline: Chunked Upload → FFmpeg -14 LUFS normalize → Manifest sync ile şubelere dağıtım. |
| Anons Zamanlama | schedules tablosuna kayıt: cron_expression veya tek seferlik play_at. Agent'ın APScheduler'ı otomatik programlanır. |
| Ses Seviyesi Ayarla | branches.volume_music / volume_announce güncellenir. MQTT Configuration Payload anında şubeye iletilir. |
| Mesai Saati Düzenle | branch_settings.work_start / work_end güncellenir. Agent'ın lokal SQLite'ına sync edilir — offline'da da çalışır. |
| Kill Switch / Acil Durdur | MQTT QoS 2 broadcast: announceflow/{city}/{branch_id}/killswitch. Agent State Machine tüm sesi keser, kill_active=true yazar. |


### Şube Provisioning — Zero-Touch Provisioning (4 Adım)

> ✓ KURAL: Müşteri sisteme yeni şube (cihaz) ekleyemez. Her şube fiziksel bir Pi'ye karşılık gelir. HaaS modelinin temel kuralı: Donanım yoksa şube yok.

**Zero-Touch Provisioning Akışı**

| Adım | Kim? | İşlem | Teknik Karşılık |
| --- | --- | --- | --- |
| 1 — Infrastructure Management | Sen | /admin/branches/new'den şubeyi sisteme eklersin. | branches tablosuna kayıt + benzersiz Device Token (UUID) üretimi. |
| 2 — Factory Injection | Sen | Gold Image yüklü SD karta device_token.txt + CPU Serial Lock gömersin. | Hardware Binding — o SD kart başka Pi'de çalışmaz. |
| 3 — Zero-Touch Deploy | Mağaza Personeli | Pi'yi fişe ve internete takar. Başka bir şey yapmaz. | Pi Outbound MQTT/HTTP ile Merkeze 'Ben geldim, token'ım bu' der. Handshake otomatik. |
| 4 — Operational Control | Müşteri | Dashboard'da şubenin ışığı 🔴'dan 🟢'e döner. | Müşteri artık o şubeye müzik, anons, ses ayarı yapabilir. |


- 🔴→🟢 geçişi otomatiktir. Handshake başarılı olana kadar şube 'Beklemede' görünür, içerik gönderilemez.

- Kargo senaryosu: Sen Gaziantep'teki masanda SD kartı hazırlarsın, kargolarsın. Mağaza personeli takıp çalıştırır. Bitti.


### Media Ingestion Pipeline — 4 Adımlı Teknik Akış

> ✓ KURAL: Sistemin ticari HaaS değerini yaratan ana motor: Müşteri dosya yükler, 100 şube alır. Tamamen otomatik.

**Media Ingestion Pipeline**

| Adım | Süreç Adı | İşlem |
| --- | --- | --- |
| 1 | Memory-Safe Ingestion | Müşteri dashboard'dan MP3/WAV/vb. yükler. FastAPI, RAM şişmesini (Memory Bloat) önlemek için Chunked Upload ile dosyayı doğrudan diske yazar (spool_max_size). |
| 2 | Audio Normalization | Dosya diske iner inmez arka planda (async) FFmpeg tetiklenir. Ses seviyesi profesyonel standart olan -14 LUFS'a normalize edilir. Şubede şarkı kısık anons gürültülü olmaz — hepsi dengeli. |
| 3 | Entity Creation | İşlenen dosyanın adı, süresi, hash ve yolu PostgreSQL'deki media_files tablosuna kaydedilir. manifest.json güncellenir. |
| 4 | Manifest-Based Sync | Müşteri 'Gaziantep şubelerine gönder' dediğinde hedef şubelere MQTT trigger gider. Agent diff alır, sadece yeni/değişen dosyayı HTTP ile çeker (Differential Pull). SD karta yazar. |


- Kural: Tüm bu akış arka planda (async) çalışır. Müşteri upload'ı tamamladıktan sonra dashboard'da dosyayı görür, şubeler arka planda eşitlenir.


## 3C.5 Kill Switch — Acil Durdurma Sistemi

> ✓ KURAL: Kill Switch: Deprem, yangın veya acil durumda tüm şubelerin (veya seçili şubelerin) sesini anında kesmek için.

**Kill Switch MQTT Topic'leri**

| Topic | Hedef | Payload |
| --- | --- | --- |
| announceflow/ALL/killswitch | Tüm şubeler (Global) | {"action": "kill", "reason": "emergency"} |
| announceflow/{city}/killswitch | Tek şehir | {"action": "kill", "reason": "emergency"} |
| announceflow/{city}/{branch_id}/killswitch | Tek şube | {"action": "kill", "reason": "manual"} |
| announceflow/ALL/killswitch/resume | Global devam | {"action": "resume"} |


- Agent Davranışı (Kill Switch geldiğinde):

    - Müzik anında STOP (PAUSE değil — acil durum).

    - Aktif anons varsa anında STOP.

    - 'kill_active: true' bayrağını SQLite'a yaz (Reboot sonrası da sessiz kalmak için).

    - Status heartbeat'e 'status: KILLED' ekle.

- QoS: Kill switch mesajları QoS 2 (Exactly Once) ile gönderilir — kayıp kabul edilemez.

- Resume: 'resume' komutu gelene kadar sistem sessiz kalır. Resume sonrası normal işleyişe döner.

- Dashboard: Kırmızı 'ACİL DURDUR' butonu (tüm şubeler) + şube kartı üzerinde tekil durdurma.


## 3C.6 Playlist Mantığı ve Scheduler

> ✓ KURAL: V1'deki scheduler mantığı prod'da çalışıyor — korunarak DB-driven hale getirilecek. playlists/playlist_items tabloları KALDIRILDI (over-engineering).

### Playlist Modları

**Playlist Modları (schedules + branch_settings ile yönetilir)**

| Mod | Nasıl Çalışır? | Nerede Tutulur? |
| --- | --- | --- |
| Sıralı (Default) | media_files listesindeki dosyaları created_at sırasına göre çalar. | media_files tablosu + Agent lokal SQLite. |
| Shuffle | Her döngüde listeyi karıştırır. Fisher-Yates. Aynı şarkı üst üste gelmez. | branch_settings.loop_mode = 'shuffle' |
| Loop | Liste bitince başa döner. Shuffle ile birlikte çalışır. | branch_settings.loop_mode = 'shuffle_loop' |
| Zaman Bazlı | Sabah 08-12 belirli dosyalar, öğleden sonra başkaları. | schedules tablosunda cron_expression + target_type ile yönetilir. |


- branch_settings tablosuna eklenen sütun: loop_mode ENUM ('sequential', 'shuffle', 'loop', 'shuffle_loop') DEFAULT 'shuffle_loop'

- Shuffle state persistent: Agent lokal SQLite'a çalma sırası hash'ini yazar. Reboot sonrası aynı noktadan devam eder.

> ⚠ ÇÖZÜLEN ÇAKIŞMA: playlists + playlist_items tabloları KALDIRILDI. V1'de yoktu, gereksiz karmaşıklık yaratıyordu. schedules + media_files + branch_settings.loop_mode yeterli.

### Scheduler — V1 Mantığının DB-Driven Karşılığı

**Scheduler Senaryoları ve DB Karşılıkları**

| V1'deki Senaryo | schedules Tablosunda Nasıl? |
| --- | --- |
| Tek seferlik (3 Mart 14:00'da bir kez) | play_at = '2025-03-03 14:00:00', cron_expression = NULL |
| Her gün 09:00'da | play_at = NULL, cron_expression = '0 9 * * *' |
| Her Pazartesi 09:00'da | play_at = NULL, cron_expression = '0 9 * * 1' |
| Hafta içi her gün 08:30 | play_at = NULL, cron_expression = '30 8 * * 1-5' |
| Mesai açılışında (work_start saatinde) | play_at = NULL, cron_expression otomatik üretilir: branch_settings.work_start okunarak |


- Backend Kütüphanesi: APScheduler (AsyncIOScheduler). V1'deki zamanlama mantığı bu kütüphaneye migrate edilir.

- Çakışma Kuralı: Aynı anda birden fazla anons tetiklenirse — önce schedule oluşturulma zamanı, sonra hedef kapsam (ALL > GROUP > BRANCH) sıralaması uygulanır.


## 3C.7 Ses Formatı ve Media Pipeline

> ✓ KURAL: Kural: Her format kabul edilir (MP3, WAV, OGG, FLAC, AAC vb.). FFmpeg ile MP3'e normalize edilir. Şubeye sadece MP3 gider.

**Media Upload Pipeline (Master Tarafı)**

| Adım | İşlem | Araç / Detay |
| --- | --- | --- |
| 1 | Client upload isteği başlatır | HTTP POST /api/v1/media/upload — Chunked (streaming) |
| 2 | FastAPI dosyayı /data/media/temp/{uuid}/ dizinine yazar | spool_max_size ile RAM'e değil diske buffer'lanır |
| 3 | Format ve bütünlük kontrolü | ffprobe ile dosyanın geçerli bir ses dosyası olup olmadığı kontrol edilir |
| 4 | FFmpeg normalizasyonu (async kuyruk) | ffmpeg -i input -af loudnorm=I=-14:TP=-1.5:LRA=11 -ar 44100 -ab 192k output.mp3 |
| 5 | SHA256 hash hesaplanır | Manifest sync için hash değeri üretilir |
| 6 | Hedef dizine taşınır | /data/media/{client_id}/{media_id}.mp3 |
| 7 | media_files tablosuna yazılır | file_path, hash, duration, size_bytes kaydedilir |
| 8 | Manifest güncellenir | Hedeflenen şubelerin bir sonraki sync'te bu dosyayı alması sağlanır |


- Normalizasyon Standardı: -14 LUFS (EBU R128). Tüm ses dosyaları aynı ses seviyesinde çalır — şarkılar arasında 'bir sessiz bir gürültülü' problemi olmaz.

- Geçici Dosya Temizliği: /data/media/temp/ dizini her gece 02:00'da temizlenir (cron job).

- Maksimum Dosya Boyutu: 500MB (ham format). Normalize sonrası MP3 genellikle çok daha küçük olur.


# BÖLÜM 4 — GELİŞTİRME FAZLARI VE ROADMAP


## 🟢 FAZ 1 — KURULUM VE TEMEL (SETUP & FOUNDATION)

### Adım 0: Mimari ve Repo Kurulumu

- [ ] Klasör: announceflow-v2 oluştur.

- [ ] Git: git init ve .gitignore (Python/FastAPI template).

- [ ] Monorepo Yapısı: /backend, /agent, /shared klasörleri.

- [ ] Migration: V1'den player.py, scheduler.py → legacy_reference/ içine kopyala (Sadece referans!).

- [ ] Vision: PROJECT_VISION_PROMPT.md oluştur.

- [ ] Auditor: AUDITOR_PROMPT.md oluştur (İçerik Bölüm 6'da).

### Adım 1: Veri Katmanı (Data Layer)

- [ ] Infra (Dev): docker-compose.dev.yml (PostgreSQL + Mosquitto).

- [ ] Schema: SQLAlchemy Models (Bölüm 3'teki tüm tablolar).

- [ ] Migration: Alembic kurulumu ve ilk şemanın dondurulması.


## 🔵 FAZ 2 — MERKEZİ BEYİN (BACKEND)

### Adım 2: Güvenlik (Auth)

- [ ] JWT & Handshake: Token tabanlı şube girişi.

- [ ] Code Review: Auth modülü AUDITOR_PROMPT.md ile denetlenir.

- [ ] Test (Kritik Yol): Auth modülü için pytest.

### Adım 3: İş Mantığı (Core Services)

- [ ] Media Engine: Chunked Upload + FFmpeg Normalization (-14 LUFS).

- [ ] TTS Service: Coqui XTTS v2 — asenkron kuyruk ile metinden anons üretme.

- [ ] Voice Engine Abstraction Layer: voice_engine modülü oluşturulur.

- [ ] Log Ingestion: Şubelerden gelen logları veritabanına yazan API.

- [ ] Heartbeat Monitor: MQTT LWT + 1 dakikalık Ping takibi ile cihaz sağlık izleme.

- [ ] Sync Engine: Manifest (Hash) tabanlı dosya senkronizasyon mantığı.

- [ ] Scheduler: V1 mantığının DB destekli (PostgreSQL + Cron) hale getirilmesi.

- [ ] Code Review: Tüm servisler AUDITOR_PROMPT.md ile denetlenir.

- [ ] Test (Kritik Yol): Priority Manager ve Sync Engine unit testleri.

"🟠 FAZ 3 — UÇ BİRİM (AGENT)" eski olan, artık aşağıdaki değil bunun dönüştürülmüş ve projede somut olarak faz 3'e gelindikten sonra güncellenerek yeniden hazırlanmış ve güncel olarak aşağıya konulmuş faz 3 dikkate alınacaktır:
"
## 🟠 FAZ 3 — UÇ BİRİM (AGENT)

### Adım 4: Ajan (The Player)

- [ ] Headless Player: legacy_reference mantığıyla modern agent/player.py (sıfırdan yazım).

- [ ] Priority Manager: Ezan/Anons/Müzik durum makinesi (State Machine).

- [ ] Local DB: SQLite (WAL Mode) — Offline Ezan ve Schedule verisi için.

- [ ] Centralized Logging: Logları yerelde (Disk/30MB limit) biriktirip Merkeze (API) atan yapı.

- [ ] Code Review: Agent kodları AUDITOR_PROMPT.md (özellikle IoT kısıtları) ile denetlenir.

### Adım 5: Sağlamlık

- [ ] Offline Mod: İnternet yoksa yerel cache kullanımı (Graceful Degradation).

- [ ] Watchdog: Docker restart:unless-stopped + Linux Hardware Watchdog."

---

"🟠 FAZ 3 — UÇ BİRİM (AGENT) - RASPBERRY PI 4 (1GB RAM)" güncel olan:

🟠 FAZ 3 — UÇ BİRİM (AGENT) - RASPBERRY PI 4 (1GB RAM)
(Not: Performans, mimari kalite veya kritik özelliklerden ödün verilmesi gerekecek bir darboğaz yaşanırsa, donanım 2GB RAM'e yükseltilecektir. Kod 1GB sınırlarına göre, RAM şişmesini önleyecek şekilde optimize yazılacaktır.)

[ ⏳ ŞU AN ] Adım 1: Foundation (Hafıza + Sinir Sistemi + Zamanlayıcı İskeleti)
  * agent.db: aiosqlite, WAL Mode, idempotent init_db(), Alembic YASAK.
    - Tablolar: config (schema_version dahil), local_media, local_schedules, prayer_times
  * AgentLogger: JSON format, stdout, flood protection (aynı hata saniyede >10 kez ise durdur).
  * APScheduler İskeleti: AsyncIOScheduler + SQLAlchemyJobStore (sadece başlatılır, job eklenmez).
  * Boot Sequence (Adım 1-3): CPU Serial oku -> token oku -> DB init.

[ 🔒 KİLİTLİ ] Adım 2: Sync Client & Handshake (Veri Boru Hattı)
  * Boot Sequence (Adım 4-6): HTTP Register -> Manifest Diff -> aiofiles ile asenkron MP3 indir.
  * SHA256 Doğrulama ve Sync Confirm API çağrısı.
  * I/O Darboğaz Önlemi (Chunking): Büyük MP3'ler inerken Player'ı (sesi) kilitlememek ve SD kart veri yolunu boğmamak için indirme işlemi parçalı (chunked) yapılacak ve döngü aralarına 'await asyncio.sleep(0.01)' eklenecektir.

[ 🔒 KİLİTLİ ] Adım 3: The Brain (Priority Manager & Ezan)
  * Boot Sequence (Adım 7): Diyanet API cache (<7 gün ise yenile).
  * State Machine (P0'dan P4'e): Kesin hiyerarşi (Kill Switch > Ezan > Mesai > Planlı > Fon).
  * Legacy Business Logic: 'legacy_reference/player.py' ve 'scheduler.py' içindeki karar alma mantığı (if/else), modern ve asenkron State Machine'e dönüştürülerek kullanılacaktır (Kopyala-yapıştır yasak).
  * APScheduler: local_schedules'dan job'ları register/deregister etme.

[ 🔒 KİLİTLİ ] Adım 4: The Muscle (Player & Voice Engine)
  * agent/voice_engine entegrasyonu (LibVLCBackend).
  * Priority Manager'ın PAUSE/RESUME emirlerini donanıma iletme.
  * SQLite'a persistent shuffle hash yazılması (reboot sonrası kaldığı yerden devam).

[ 🔒 KİLİTLİ ] Adım 5: Control Plane (MQTT Telemetry)
  * Boot Sequence (Adım 8-10): MQTT bağlantısı, LWT tanımlaması.
  * Heartbeat loop (1 dakika) ve Kill Switch / Config Update QoS 2 dinleyicileri.

[ 🔒 KİLİTLİ ] Adım 6: Sağlamlık (Watchdog & Offline Test)
  * Graceful Degradation: İnternetsiz açılış simülasyonları ve donanım watchdog entegrasyonu.

---

## 🔴 FAZ 4 — DAĞITIM (DEPLOYMENT)

### Adım 6: Paketleme

- [ ] Docker: Dockerfile.backend ve Dockerfile.agent (Multi-stage build, agent imajında Dashboard kodu yok).

- [ ] CI/CD: GitHub Actions (GHCR'a otomatik push).

- [ ] OTA: Watchtower konfigürasyonu (Jitter: 03:00–04:00 rastgele).

- [ ] Ticari Koruma: Nuitka ile Python kaynak kodlarının derlenmesi (Katman 1 — IP Koruması).

- [ ] Donanım Kilidi: CPU Serial locking entegrasyonu (Katman 2).

- [ ] Uzaktan Müdahale: Tailscale kurulumu (Katman 1 Admin) + Alpemix kurulumu (Katman 2 Stakeholder).

### Adım 7: İzleme ve Dashboard Tamamlama

- [ ] Fleet Dashboard: Grid View + Data Table (Faz 1 MVP).

- [ ] Log Viewer: Dashboard üzerinde tek bakışta teşhis ekranı.

- [ ] Telegram Alerting: Kırmızı/Sarı durum bildirimleri.

- [ ] Map View: (FAZ 2 HEDEFİ — Nominatim geocoding + LeafletJS + canlı MQTT marker).

- [ ] Desktop Agent (System Tray App): FAZ 2 HEDEFİ. Müşterinin ofis bilgisayarında (Windows/Mac) çalışan hafif uygulama. System tray'de logo, tıklayınca mini panel: 'Panele Bağlan', temel şube durumu, ses seviyesi kısayolu. Teknoloji: Python + PyQt6 veya Electron (karar Faz 2'de). MVP'ye dahil değil.


# BÖLÜM 5 — AUDITOR_PROMPT.md İÇERİĞİ


Bu dosya, her özellik tamamlandığında Main Branch'e geçmeden önce uygulanır.


## ROLE

Senior Security & IoT Quality Engineer (Auditor Mode)

## CONTEXT

Bu kod, 'AnnounceFlow V2' (Offline-First IoT Audio System — Statek Sound) projesine aittir. Donanım kısıtlıdır: Raspberry Pi 4, 1GB RAM (Agent), 8GB RAM (Master).

## DENETİM KURALLARI

- 1. Güvenlik: SQL Injection, Hardcoded Secret, Yetki Aşımı var mı?

- 2. IoT & Performans: Gereksiz döngü, RAM şişirme, SD Kartı yorma riski var mı?

- 3. Resilience (Dayanıklılık): İnternet koparsa veya dosya bozuksa sistem çöker mi (Graceful Degradation)?

- 4. Clean Code: DRY ihlali veya spagetti kod var mı? SOLID prensiplerine uyuluyor mu?

- 5. Logging Uyumu: print() kullanılmış mı? Merkezi Logger kullanılıyor mu? JSON format var mı?

- 6. Repository Pattern: Veri erişimi iş mantığından ayrılmış mı?

- 7. Type Hinting: Tüm fonksiyon imzaları tip belirtmiş mi?

- 8. Asyncio Tuzakları (Agent İçin Kritik): Async fonksiyon içinde blocking I/O var mı? (time.sleep(), senkron open(), requests.get() gibi çağrılar async bağlamda kullanılamaz — asyncio.sleep() ve httpx/aiofiles kullanılmalıdır.)

## ÇIKTI

Hataları maddeler halinde listele ve her hata için 'Refactored Code' öner.


# BÖLÜM 6 — PROJECT_VISION_PROMPT.md (Final Versiyon)

Bu dosya, her yeni modüle başlarken 'İşçi LLM'ye verilecek bağlam dosyasıdır. İki taslak versiyonu analiz edilmiş, nihai tek versiyon aşağıda derlenmiştir.


## Versiyon Analizi — Hangisi Daha İyi?

**İki Taslak Versiyonun Karşılaştırması**

| Kriter | Versiyon 1 (Uzun) | Versiyon 2 (Kısa/Güncel) |
| --- | --- | --- |
| Teknik Doğruluk | Bazı eski kararları içeriyor (örn. polling yasağı eksik) | Tüm güncel anayasa kararlarını (v12.20) yansıtıyor ✓ |
| Uzunluk | Uzun — LLM bağlamını şişirebilir | Kısa ve öz — token tasarrufu ✓ |
| Çalışma Protokolü | 3 aşama: Sorgula / Basitleştir / Eğit & Açıkla | 3 aşama: Sorgula / Basitleştir / Denetle ✓ (Auditor entegre) |
| voice_engine | Bahsedilmiyor | Açıkça tanımlanmış ✓ |
| IP Protection | Bahsedilmiyor | Nuitka + Hardware Binding belirtilmiş ✓ |
| Sonuç | Temel ruh iyi, teknik detay eksik | KAZANAN — Tüm anayasayı yansıtıyor ✓ |


> ⚠ ÇÖZÜLEN ÇAKIŞMA: Versiyon 1'in 'Eğit & Açıkla' (hoca gibi anlat) maddesi çok değerlidir. Versiyon 2'ye eksik. Final versiyona eklendi.


## PROJECT_VISION_PROMPT.md — NİHAİ VERSİYON


> ✓ KURAL: Bu dosyanın içeriği aşağıdaki kutudur. Yeni modül başlarken LLM'e bu bağlamı ver.


**ROLÜN (Sen Kimsin?):**

- Bu projede benim Kıdemli Teknoloji Ortağım (Senior Tech Partner) ve Danışmanımsın.

- Teknik kararlar alırken Best Practices, Sektör Standartları ve Modern Çözümler merceğinden bak.

- Beni 'Over-engineering' tuzağından koru. Solo Dev'im, bakımı basit olan çözümler sun.


**HEDEFİMİZ (Ne Yapıyoruz?):**

- Perakende zincirleri (100+ şube) için merkezi yönetilen, Offline-First, 'Statek Sound' markalı bir IoT Ses ve Anons sistemi kuruyoruz.

- Problem: Mağazalar ya çok pahalı sistemler ya da USB ile manuel müzik/anons yönetiyor.

- Çözümümüz: Tek merkezden tüm şubelerin müziğini/anonsunu/ses seviyesini yönet; şube internetsiz kalsa da çalışmaya devam etsin.


**TEKNİK ANAYASA ÖZETI (Source of Truth — FINAL):**

- Mimari: Monorepo. /backend (FastAPI), /agent (Python), /shared (Ortak Modeller).

- Donanım: Merkez (8GB Pi 4 / Cloud), Şube (1GB Pi 4 — düşük kaynak kullanımı kritik).

- İletişim: Control Plane=MQTT (Push-to-Trigger), Data Plane=HTTP (Lazy Sync). Polling YASAKTIR.

- Ses Mantığı (voice_engine Abstraction Layer):

    - Pause & Resume: Anons gelince müzik PAUSE, bitince RESUME. Ducking YOK, Mixing YOK.

    - Merkezi TTS: Coqui XTTS v2 merkezde üretir, şube MP3 indirir.

    - Öncelik: Ezan/Mesai Dışı > Anons > Fon Müziği.

- Güvenlik & IP Koruma:

    - Kodlar Nuitka ile Binary (.so) olarak derlenir. SD kartta okunabilir kod olmaz.

    - Hardware Binding: Yazılım CPU Serial numarasına kilitlenir. Kopyalanmış SD kart başka Pi'de çalışmaz.

    - Ağ: Şubeler dışarıdan erişilemez. Tüm bağlantılar Outbound (Şube→Merkez) yönünde.

- Loglama: JSON (Structured). Cihazda 30MB rotasyonlu, merkezde sınırsız. print() YASAKTIR.

- Ezan & Mesai: Diyanet API tabanlı 30 günlük offline cache. Ezan/Mesai Dışı = Priority 1 (Sessizlik).

- Design Patterns: Repository Pattern (Zorunlu), Singleton (DB), Modüler Monolit.


**ÇALIŞMA PROTOKOLÜ (Kod vermeden önce 4 aşama uygula):**

- SORGULA (The 'Why'): Mimari darboğaz veya gereksiz karmaşıklık var mı?

- BASİTLEŞTİR (KISS): Solo Dev'im. Bakımı kolay, Over-engineering olmayan çözüm sun.

- EĞİT & AÇIKLA: Sadece 'çalışan kodu' verme. Neden bu kütüphaneyi seçtiğini, alternatifini ve projeye katkısını anlat.

- DENETLE: Kodu vermeden önce zihninde AUDITOR_PROMPT kriterlerini çalıştır (Güvenlik, IoT kısıtları, SD Kart ömrü, Repository Pattern, Type Hinting).


**MÜHENDİSLİK PRENSİBİ (GOLDEN RULE):**

- Her çözümü Design Patterns ve Best Practices merceğinden değerlendir.

- Eğer istediğim yöntem bir Anti-Pattern ise veya 'Tekerleği yeniden icat etmek' anlamına geliyorsa (Auth, Loglama, DB bağlantısı için sıfırdan yazmak gibi) beni DURDUR ve sektör standardı kütüphaneyi öner.


# BÖLÜM 7 — AĞ GÜVENLİĞİ (v12.22) ve RTC NOTU


## 7.1 Port Açma vs Port Dinleme — Teknik Açıklama

Bu bölüm, 'Şubede neden port açmıyoruz?' sorusunu teknik ve ticari boyutlarıyla netleştirmek için anayasaya eklenmiştir.


### Şubede (Mağazada) Durum

> ✓ KURAL: Kural: Şube tarafında Port Forwarding (Port Yönlendirme) ASLA yapılmaz.

- Mağaza modeminin arayüzüne girip 'Dışarıdan gelen 80. port isteklerini Raspberry Pi'ye yönlendir' ayarı yapılmaz.

- Neden? İki kritik sebep:

    - Güvenlik: Port açmak, internetteki her saldırgana 'gel beni tara' demektir. (Detay aşağıda.)

    - Maliyet: Port açmak Statik IP gerektirir. 100 şubede bu devasa aylık ek maliyettir.

- Doğru Yöntem: Agent (Şube), başlatıldığında Merkeze (Broker) doğru Outbound bağlantı açar. Dışarıdan hiç kimse şubeye doğrudan bağlanamaz.


### Merkezde (Sunucuda) Durum

> ✓ KURAL: Kural: Merkez sunucusunda yalnızca 80 (HTTP), 443 (HTTPS) ve 1883 (MQTT) portları yetkili erişime açıktır.

- Merkez, 100 şubenin gelip bağlandığı 'Ev'dir. Bu kapıların açık olması zorunludur.

- Diğer tüm portlar UFW kuralı ile DROP edilir.


### Port Açılırsa Ne Olur? (Risk Analizi)

**Şubede Port Açmanın Riskleri**

| Saldırı Türü | Ne Olur? | Kritiklik |
| --- | --- | --- |
| Brute Force | Hacker, giriş kapısını bulur. admin/admin, pi/raspberry gibi binlerce şifre dener. İçeri girirse POS cihazlarına, ağ trafiğine sızabilir. | 🔴 KRİTİK |
| DDoS | Pi saniyede 1 milyon istek alıp kilitlenir. Müzik susar, sistem çevrimdışı olur. | 🔴 KRİTİK |
| Zombi Ağı (Botnet) | Hacker cihaza Mining Script yükler. Cihaz müzik yerine Bitcoin kazar. Devlet sitelerine saldırı yapar, yasal sorumluluk sana ait olur. | 🔴 KRİTİK |
| Statik IP Maliyeti | 100 şubede her biri için aylık Statik IP ücreti — büyük işletme maliyeti. | 🟡 MALİ |


### MQTT Tünel Mantığı — Merkez Şubeye Nasıl Ulaşır?

**'Şubenin kapısı kapalıysa, Merkez ona nasıl Sesi Kıs diyecek?' sorusunun cevabı:**

- Şube açılır açılmaz Merkeze (MQTT Broker) gider ve Persistent Connection (Sürekli Bağlantı) kurar. (Outbound)

- Bu TCP bağlantısı koparılmaz, açık tutulur.

- Merkez, şubeye emir göndermek istediğinde zaten açık olan bu hattı kullanır. Yeni bağlantı kurmak gerekmez.

- Telefon Analojisi: Sen (Şube) arkadaşını (Merkez) aradın. Hat açık. Arkadaşın sana 'Sesi kıs' dediğinde telefonu kapatıp seni tekrar aramasına gerek yok — açık hattan konuşur. MQTT budur.


**📂 03_CONSTITUTION.md — v12.22 Ekleme (Ağ ve Port Güvenlik Standartları):**

- Şube (Agent) Güvenliği: Mağaza/Şube tarafındaki modemlerde asla Port Yönlendirme (Port Forwarding) yapılmayacaktır. Şubeler 'Dışarıdan Erişilemez' (Invisible) kalacaktır.

- Bağlantı Yönü (Outbound Only): Tüm bağlantılar Şube → Merkez (Outbound) yönünde başlatılacaktır.

- MQTT Tünel Mantığı: Merkez, şubeye emir göndermek için Agent'ın açtığı Persistent Connection hattını kullanacaktır.

- Merkez (Master) Kapıları: Sadece 80 (HTTP), 443 (HTTPS) ve 1883 (MQTT) portları açık. Diğerleri DROP.


## 7.2 RTC (Gerçek Zamanlı Saat) Notu — Raspberry Pi 4

> ✓ KURAL: Raspberry Pi 4'te fabrikasyon RTC (Real-Time Clock) yoktur. Ticari bir üründe bu kritik bir zafiyettir. Çözüm: DS3231 modülü.

### Sorun: Pi 4'te RTC Neden Yok?

- Raspberry Pi 4'te pil yuvası veya kristal destekli saat çipi (RTC) yoktur.

- Cihaz saati NTP (Network Time Protocol) üzerinden internet bağlantısıyla çeker.

- İnternet yoksa: En son kapatıldığı zamanı sistem dosyalarından okur. Uzun süre güçsüz kalırsa saat sapıtır veya Epoch'a (1 Ocak 1970) döner.

### Neden Projemiz İçin Kritik?

- Ezan Vakti Hatası: İnternet yokken elektrik gidip geldiyse Pi saati yanlış sanabilir. Öğle ezanı vaktinde anons patlatabilir veya mesai dışında müzik çalabilir.

- Log Güvenilirliği: Tüm loglar '1 Ocak 1970' tarihli olursa hangi hatanın ne zaman yaşandığını anlamak imkansız olur.

- Offline-First İlkemizle Çelişki: Sistemimizin kalbi 'Offline-First'. Saati internete bağımlı olan bir donanım bu ilkeyi zayıflatır.

### Kanıtlama Deneyi

- 1. İnterneti kes (Ethernet çıkar, Wi-Fi kapat).

- 2. Pi'nin fişini çek, 5–10 dakika bekle.

- 3. İnternet hala kapalıyken cihazı başlat.

- 4. Terminale 'date' yaz. Saatin doğru olmadığını göreceksin.

### Çözüm: DS3231 RTC Modülü

**DS3231 Modülü Özellikleri**

| Özellik | Değer |
| --- | --- |
| Maliyet | ~1–2 USD (donanım başına) |
| Bağlantı | I2C (2 kablo, kolay entegrasyon) |
| Hassasiyet | Ayda ±2 saniye sapma — ticari kullanım için yeterli |
| Bağımsızlık | Kendi piliyle çalışır. İnternet ve elektrik kesilse bile saati tutar. |
| Raspberry Pi 5 Farkı | Pi 5'te bu ihtiyaç için fabrikasyon pil girişi var. Pi 4'te harici modül zorunlu. |


> ✓ KURAL: Fabrika Protokolü Güncellemesi: Her SD karta device_token.txt enjekte edilirken, her cihaza DS3231 modülü de takılmalı ve Linux RTC servisi aktif edilmelidir.


# BÖLÜM 10 — BAŞLANGIÇ REHBERİ (Legacy Reference + İlk Mesaj)


## 10.1 Legacy Reference — Ne Almalı, Ne Bırakmalı?

> ✓ KURAL: Tavsiye: legacy_reference/ yaklaşımını YAP. V1'in çalışan ses mantığı çok değerli. Ama ne aldığına dikkat et.


**V1'den Ne Alınır, Ne Alınmaz?**

| Dosya / Bileşen | Al mı? | Neden / Nasıl Kullanılır? |
| --- | --- | --- |
| player.py | ✅ Al | Pause/Resume mantığı, öncelik yönetimi (Ezan>Anons>Müzik) — sıfırdan yazmak hata riski. Mantığını oku, modern async yapıyla yeniden yaz. |
| scheduler.py | ✅ Al | Zamanlama ve cron mantığı. V2'de DB-driven olacak ama temel logic aynı. Referans al. |
| prayer / ezan modülü | ✅ Al | Diyanet API bağlantısı ve yerel cache mantığı çalışıyorsa altın değerinde. |
| Flask/FastAPI routes | ❌ Bırak | Mimari tamamen değişti. Eski route yapısı V2'ye aktarılamaz. |
| Eski DB bağlantıları | ❌ Bırak | SQLite'tan PostgreSQL'e geçiş var. Eski connection kodu işe yaramaz. |
| Hardcoded config / secrets | ❌ Bırak | Bunları almak, güvenlik açığını da almak demektir. |
| requirements.txt | ⚠️ İncele | Kütüphane listesine bak, güncel versiyonları araştır. Direkt kopyalama. |


- Komut: Eski projeyi aç → Sadece player.py, scheduler.py ve ezan modülünü announceflow-v2/legacy_reference/ içine kopyala → Geri kalanını açma.

- AI Editöre söylenecek: 'Bu dosyaları oku ve mantığını anla, ama buradan tek satır import etme. Amacı referans.'


## 10.2 Hangi Editör? (Cursor vs Claude Code vs Codex)

**Editör Karşılaştırması — Bu Proje İçin**

| Editör | Güçlü Yanı | Bu Proje İçin Notu |
| --- | --- | --- |
| Cursor | Dosya ağacını görür, bağlam hafızası güçlü, multi-file edit | ✅ TAVSİYE EDİLEN. Monorepo yapısını anlayıp /backend ve /agent arasında geçiş yapar. |
| Claude Code | Terminal entegrasyonu, komut çalıştırabilir, Docker ile konuşur | ✅ İYİ SEÇENEK. docker-compose.dev.yml'i çalıştırması gerektiğinde güçlü. |
| GitHub Copilot | Satır tamamlama | ❌ Bu proje için zayıf. Mimari kararlar veremez, sadece satır tamamlar. |
| ChatGPT/Codex | Tek seferlik kod üretimi | ⚠️ Proje bağlamını tutamaz. Her mesajda context kaybı yaşanır. |


## 10.3 İlk Mesaj Stratejisi — Adım Adım

> ✓ KURAL: Tam belgeyi ATMA. Bağlamı şişirir, AI editör boğulur. Parçalı ve sıralı ver.


### Mesaj 1 — Bağlam Kurma (PROJECT_VISION_PROMPT.md'yi ver)

- Şunu at: Bölüm 6'daki 'PROJECT_VISION_PROMPT.md — NİHAİ VERSİYON' başlığından itibaren tüm içerik.

- Son soru olarak şunu ekle: 'Bu projeyi anladın mı? Şimdi Raspberry Pi 1GB RAM kısıtlarını göz önünde bulundurarak Monorepo klasör yapısını oluşturalım mı?'

- Beklenen çıktı: Klasör yapısı + her klasörün amacının açıklaması.


### Mesaj 2 — Veri Katmanı (Adım 1)

- Şunu at: Bölüm 3 (Veritabanı Şeması) + ilgili Anayasa maddeleri (Repository Pattern, Type Hinting).

- İstek: 'SQLAlchemy modellerini yaz. Önce Pydantic şemalarını (API sözleşmesi) oluştur, sonra modelleri.'


### Her Modülde Kullanılacak Şablon

- 1. İlgili belge bölümünü ver (sadece o modülle ilgili kısım).

- 2. 'AUDITOR_PROMPT.md kriterlerini (Bölüm 5) bu koda da uygula' de.

- 3. Legacy referans varsa: 'legacy_reference/player.py içindeki şu mantığa bak: [satır X-Y]. Bunu modern async yapıyla yeniden yaz.' de.


# BÖLÜM 11 — OPSİYONEL KARARLAR (FAZ 4'TE AÇILACAK)


Aşağıdaki maddeler Faz 1-2-3 sürecinde geliştirmeyi engellemez. Dağıtım aşamasında değerlendirilir.


## 1. Uzaktan Müdahale — Final Karar

- Seçim: SSH (Port 22) her zaman açık — backbone.

- Admin Erişimi: Tailscale VPN (öncelikli).

- Stakeholder Erişimi: Alpemix (opsiyonel, Faz 4). RAM etkisi Heartbeat ile izlenir.


## 2. Sunucu Altyapısı

- Seçenek: Herhangi bir VPS (Hetzner, DigitalOcean, yerli firmalar) — ~5$/ay.

- Kod Docker ile yazıldığı için provider değişikliği kod değişikliği gerektirmez.


## 3. Ticari Koruma Uygulaması

- İşlem: Nuitka ile derleme.

- Zamanlama: Kodlar tamamen bittiğinde, SD karta yüklemeden hemen önce.


## 4. Map View (Harita Modu)

- Teknoloji: LeafletJS veya Google Maps API.

- Zamanlama: FAZ 2 HEDEFİ. MVP'de yok. 100 şubeyi haritaya koymak Solo Dev için Nice-to-have.


# BÖLÜM 12 — ÇAKIŞMA VE TUTARSIZLIK ÖZETİ (Tüm Kararlar)


**Çözülen Tüm Tutarsızlıklar**

| Konu | Eski/Çakışan Değer | Final Karar |
| --- | --- | --- |
| Heartbeat Aralığı | v12.4: 5 dakika / v12.9: 1 dakika | 1 dakika (v12.9 — daha güncel) |
| TTS Gecikme | v12.3: 5-10 sn / v12.5: 1-5 sn | 1-10 saniye (birleştirilmiş aralık) |
| Volume Sütunu | v12.6: volume_level (tek) / v12.11: iki ayrı slider | volume_music + volume_announce (v12.11) |
| Master Log Rotasyon | v12.20: disk dolana dek sakla / v12.21: tüm servisler 10m/3file | Agent=30MB tavan, Master=esnek disk izleme |
| Remote Access Önceliği | Tailscale önce mi, Alpemix önce mi? | SSH=backbone, Tailscale=admin, Alpemix=opsiyonel stakeholder |
| Ezan Çakışma Kararı | Merkez planla mı, Agent karar ver mi? | Agent kendi karar verir (Offline dayanıklılık) |
| Map View Zamanlaması | MVP'de mi, sonra mı? | Faz 2 hedefi — MVP'ye dahil değil |
| Overlay FS | Bazı versiyonlarda belirsiz | KULLANILMAZ (tüm versiyonlarda tutarlı — onaylandı) |
| Log Numara Çakışması | Anayasada '5' numarası iki kez kullanılmış | Düzeltildi: Tekrarlanan madde numaraları düzgün sıralandı |
| PROJECT_VISION_PROMPT | İki farklı versiyon mevcuttu (uzun vs kısa) | Birleştirildi: Kısa versiyonun doğruluğu + uzunun 'Eğit&Açıkla' maddesi |
| Şube Port Güvenliği | v12.22 öncesi açıkça belgelenmemişti | Outbound-Only + MQTT Persistent Connection — resmi kural olarak eklendi |
| RTC (Saat Modülü) | Fabrika protokolünde hiç bahsedilmiyordu | DS3231 modülü her cihaza zorunlu — Fabrika Protokolüne eklendi |
| MQTT Topic Yapısı | Hiç tanımlanmamıştı — sistemin kalp damarı eksikti | Formal topic convention tablosu + QoS seviyeleri eklendi (Bölüm 3B.1) |
| Boot Sequence | Yüksek seviyede bahsediliyordu, adım adım yoktu | 10 adımlı Boot Sequence tablosu eklendi (Bölüm 3B.2) |
| Manifest Sync Detayı | 'Manifest Sync' kural olarak vardı, implementasyon yoktu | JSON formatı + 6 adımlı diff algoritması eklendi (Bölüm 3B.3) |
| Dosya Depolama | file_path sütunu vardı ama fiziksel yol tanımsızdı | /data/media/{branch_id}/{file_id}.mp3 standardı tanımlandı (Bölüm 3B.4) |
| AUDITOR_PROMPT Asyncio | Async tuzakları denetim listesinde yoktu | 8. madde eklendi: Agent'ta blocking I/O kontrolü |
| Auth Mimarisi — KRİTİK | Yanlışlıkla 'super_admin + client_admin + clients tablosu' eklenmişti | TAMAMEN KALDIRILDI. HaaS modeli: Single Admin JWT, RBAC yok, lean backend. |
| Dashboard Mimarisi | 'İki ayrı panel' düşünülmüştü | Tek panel, iki sayfa: /dashboard/* müşteri, /admin/* teknik. Aynı JWT, ayrı template. |
| Uzaktan Müdahale — KRİTİK | Tailscale öncelikli yazılmıştı (ücretli) | DÜZELTILDI: Alpemix birincil (ücretsiz), Tailscale/ZeroTier ücretsiz tier not olarak eklendi. |
| Audio Backend | Hiç belgelenmemişti | python-vlc (LibVLC) seçildi. Pi 3.5mm jack + Pause/Resume güvenilirliği |
| Ezan API Detayı | Sadece 'Diyanet API' yazıyordu | Endpoint, retry, failover, SQLite tablo yapısı eklendi |
| Playlist Tablosu | Veri modeli yoktu | playlists + playlist_items tabloları eklendi |
| Kill Switch | Belirtilmemişti | QoS 2 MQTT broadcast + kill_active SQLite bayrağı |
| Media Pipeline | FFmpeg söylenmişti, adımlar yoktu | 8 adımlı upload pipeline tanımlandı |
| Müşteri Operasyonel Yetkileri | Belirsizdi | 5 işlem netleştirildi: yükleme, zamanlama, ses, mesai, kill switch |
| Şube Provisioning | Belirsizdi | Sadece sen eklersin. HaaS: donanım yoksa şube olmaz. |
| Dashboard Dili | Belirtilmemişti | Sadece Türkçe |


# BÖLÜM 13 — CURSOR BAŞLANGIÇ REHBERİ


## MD Formatı Sorusu — Net Cevap

> ✓ KURAL: Bu DOCX senin referansın. Cursor'a TAMAMINI verme. Parçalı, amaçlı ve sıralı ver.

> ⚠ ÇÖZÜLEN ÇAKIŞMA: 'Tüm dokümanı MD olarak atayım mı?' → HAYIR. Cursor'un context window'u sınırlı. 150 sayfalık belgeyi bir seferde verirsen AI ilk bölümleri hatırlar, geri kalanı unutur. Kritik kararlar kaybolur.


## Doğru Yöntem: 3 Dosya Stratejisi

**Cursor'a Verilecek 3 Dosya**

| Dosya | İçeriği | Ne Zaman? |
| --- | --- | --- |
| PROJECT_VISION_PROMPT.md | Bölüm 6 içeriği (kısa, öz — 1-2 sayfa) | Her oturumda @mention et. Her zaman açık. |
| AUDITOR_PROMPT.md | Bölüm 5'teki 8 maddelik denetim listesi | Modül bitiminde '@AUDITOR_PROMPT.md bu kodu denetle' ile çağır. |
| docs/module_context.md | O anki modüle ait belge bölümleri | Her yeni modülde içeriği değiştir, ilgili bölümleri yapıştır. |


## Modül Başında Hangi Belge Bölümü Verilir?

**Modül → Belge Bölümü Eşleştirmesi**

| Modül | module_context.md'ye Eklenecek Bölümler |
| --- | --- |
| Auth + Users | Bölüm 2 (JWT maddeleri) + Bölüm 3C.4 (Rol yapısı, yetki matrisi) |
| Player / Agent | Bölüm 3C.1 (Audio backend) + 3C.3 (Legacy ref) + 3D.1 (Çakışma) + 2.8 (Audio Engine) |
| Scheduler | Bölüm 3C.6 (Playlist + Scheduler) + 3D.1 (end_time) + 3D.4 (APScheduler notu) |
| Ezan Modülü | Bölüm 3C.2 (Diyanet API) + 3B.2 (Boot Sequence 7. adım) |
| Sync Engine | Bölüm 3B.3 (Manifest Sync) + 3B.4 (Dosya yolları) + 3D.4 (SQLite migration) |
| Media Upload | Bölüm 3C.7 (Media Pipeline) + 3D.4 (Dosya yolu standardı) |
| Dashboard | Bölüm 2.14 (Frontend stack) + 2.5 (Heartbeat payload) + 3D.3 (Harita) |
| Kill Switch | Bölüm 3C.5 (Kill switch MQTT) + 3B.1 (MQTT topic tablosu) |


## İlk Oturum — Adım Adım

### Adım 1 — Repo Kur (Terminal'de)

- mkdir announceflow-v2 && cd announceflow-v2 && git init

- mkdir backend agent shared legacy_reference docs

- Bu DOCX'teki Bölüm 5 → docs/AUDITOR_PROMPT.md

- Bu DOCX'teki Bölüm 6 → docs/PROJECT_VISION_PROMPT.md


### Adım 2 — Legacy Reference

- V1 projesini aç → player.py + scheduler.py + ezan modülünü legacy_reference/ içine kopyala.

- Her dosyanın başına: # LEGACY REFERENCE — SADECE OKUMA. IMPORT YASAK.


### Adım 3 — Cursor'da İlk Mesaj

"@PROJECT_VISION_PROMPT.md Bu projeyi anladın mı? Raspberry Pi 1GB RAM kısıtlarını ve Monorepo yapısını göz önünde bulundurarak klasör yapısını ve docker-compose.dev.yml dosyasını oluşturalım. PostgreSQL ve Mosquitto (MQTT Broker) servislerini içermeli."


### Adım 4 — Her Modülde

- İlgili bölümleri docs/module_context.md'ye yapıştır.

- '@PROJECT_VISION_PROMPT.md @module_context.md [MODÜL ADI] modülünü yazalım.' diyerek başla.

- Modül bitince: '@AUDITOR_PROMPT.md Bu kodu denetle.'

- Denetimden geçen kodu commit et.


## Belge Final Durum Özeti

> ✓ KURAL: Bu belge TAMAMDIR. Artık hiçbir major belirsizlik, çakışma veya eksik madde kalmamıştır.

**Tüm Kararların Durumu**

| Kategori | Durum |
| --- | --- |
| İş Modeli | ✅ HaaS — Altyapı sende, Operasyonel Kontrol müşteride |
| Mimari | ✅ Monorepo, Modüler Monolit, Hub & Spoke, Standalone per Client |
| Donanım | ✅ Pi 4, 3.5mm Jack, python-vlc, DS3231 RTC zorunlu |
| Veritabanı Şeması | ✅ 9 tablo (clients KALDIRILDI), tüm ilişkiler tanımlı |
| Auth | ✅ Single Admin JWT, RBAC YOK, lean backend, iki hesap (sen + müşteri) |
| Dashboard | ✅ Tek panel (Türkçe): /dashboard müşteri, /admin teknik — aynı JWT |
| Müşteri Yetkileri | ✅ 5 operasyonel işlem: yükleme, zamanlama, ses, mesai, kill switch |
| Şube Provisioning | ✅ Sadece sen — HaaS kuralı |
| Uzaktan Müdahale | ✅ SSH backbone + Alpemix birincil + Tailscale/ZeroTier ücretsiz opsiyonel |
| Audio Engine | ✅ Pause/Resume, Kill Switch (QoS 2), Playlist modları, Çakışma engeli |
| Ezan Entegrasyonu | ✅ Diyanet API, 30 günlük cache, failover |
| Sync Engine | ✅ Manifest format, diff algoritması, konfirmasyon akışı |
| Media Pipeline | ✅ Her format kabul, FFmpeg -14 LUFS, dosya yolu standardı |
| Anons Çakışma | ✅ Upload anında slot kilitleme (V1 mantığı korundu) |
| TTS | ✅ Faz 2. voice_engine abstraction MVP'de yazılır. |
| Harita | ✅ Faz 2. Nominatim geocoding + LeafletJS + canlı Marker. |
| IP Koruması | ✅ 3 katmanlı savunma, Nuitka Faz 4 |
| Deployment & OTA | ✅ GitHub Actions, GHCR, Watchtower, Jitter, Kargo (tak-çalıştır) |
| Loglama | ✅ JSON, 30MB rotation (agent), sınırsız (master), flood protection |
| Güvenlik | ✅ UFW, Fail2Ban, SSH, Alpemix, ücretsiz VPN opsiyonel |
| SQLite Migration | ✅ schema_version tablosu + gömülü idempotent SQL'ler |
| APScheduler Persistence | ✅ SQLAlchemyJobStore → agent SQLite |
| Cursor Başlangıç | ✅ 3 dosya stratejisi + 4 adımlı modül protokolü |

