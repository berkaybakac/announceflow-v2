"""Kritik Yol Testi: FloodFilter Token Bucket Algoritmasi.

Bu test, SD kartın dolmasını engelleyen flood protection
mekanizmasının doğru çalıştığını kanıtlar.

Test senaryoları:
1. İlk 10 mesaj → hepsi geçer
2. 11. mesaj → bastırılır (suppressed)
3. 1 sn sonra → sayaç sıfırlanır, mesaj tekrar geçer
"""

from __future__ import annotations

import logging
import threading
from unittest.mock import patch

import pytest

from agent.core.logger import FloodFilter


@pytest.fixture()
def flood_filter() -> FloodFilter:
    """Her test icin temiz bir FloodFilter instance'i."""
    return FloodFilter()


def _make_record(msg: str, level: int = logging.ERROR) -> logging.LogRecord:
    """Test icin sahte LogRecord olusturur."""
    return logging.LogRecord(
        name="test",
        level=level,
        pathname="test.py",
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )


class TestFloodFilterThreshold:
    """Eşik değeri testleri: ilk 10 geçer, 11. bastırılır."""

    def test_first_10_messages_pass(self, flood_filter: FloodFilter) -> None:
        """Aynı mesaj ilk 10 kez gönderildiğinde hepsi geçmeli."""
        record = _make_record("tekrar eden hata mesaji")

        passed = 0
        for _ in range(10):
            if flood_filter.filter(record):
                passed += 1

        assert passed == 10, f"10 mesajın hepsi geçmeliydi, {passed} geçti"

    def test_11th_message_suppressed(self, flood_filter: FloodFilter) -> None:
        """11. aynı mesaj bastırılmalı (suppress edilmeli)."""
        record = _make_record("tekrar eden hata mesaji")

        # İlk 10'u gönder
        for _ in range(10):
            flood_filter.filter(record)

        # 11. mesaj
        result = flood_filter.filter(record)
        assert result is False, "11. mesaj bastırılmalıydı"

    def test_multiple_suppressed_messages(self, flood_filter: FloodFilter) -> None:
        """Eşik aşıldıktan sonra gelen mesajlar da bastırılmalı."""
        record = _make_record("tekrar eden hata mesaji")

        results = [flood_filter.filter(record) for _ in range(15)]

        passed = sum(results)
        suppressed = len(results) - passed

        assert passed == 10, f"Sadece 10 mesaj geçmeliydi, {passed} geçti"
        assert suppressed == 5, f"5 mesaj bastırılmalıydı, {suppressed} bastırıldı"


class TestFloodFilterWindowReset:
    """Zaman penceresi sıfırlama testleri."""

    def test_counter_resets_after_window(self, flood_filter: FloodFilter) -> None:
        """1 saniye sonra sayaç sıfırlanmalı ve mesaj tekrar geçmeli."""
        record = _make_record("tekrar eden hata mesaji")

        # İlk 10'u doldur
        for _ in range(10):
            flood_filter.filter(record)

        # 11. → bastırılmalı
        assert flood_filter.filter(record) is False

        # Pencereyi süresi dolmuş gibi simüle et:
        # window_start'ı 1.1 sn geçmişe çekerek monotonic farkını büyütüyoruz.
        with flood_filter._lock:
            for key in flood_filter._state:
                flood_filter._state[key][0] -= 1.1

        # Sayaç sıfırlanmış olmalı — yeni mesaj geçmeli
        result = flood_filter.filter(record)
        assert result is True, "Pencere sonrası mesaj geçmeliydi"


class TestFloodFilterDifferentMessages:
    """Farklı mesajlar birbirini etkilememeli."""

    def test_different_messages_independent(self, flood_filter: FloodFilter) -> None:
        """Her mesaj kendi sayacına sahip olmalı."""
        record_a = _make_record("hata tipi A")
        record_b = _make_record("hata tipi B")

        # A'yı 10 kez gönder — doldur
        for _ in range(10):
            flood_filter.filter(record_a)

        # A'nın 11.'si bastırılmalı
        assert flood_filter.filter(record_a) is False

        # B'nin 1.'si geçmeli — bağımsız sayaç
        assert flood_filter.filter(record_b) is True

    def test_different_levels_independent(self, flood_filter: FloodFilter) -> None:
        """Aynı mesaj farklı seviyelerde bağımsız sayılmalı."""
        record_error = _make_record("ayni mesaj", level=logging.ERROR)
        record_warn = _make_record("ayni mesaj", level=logging.WARNING)

        # ERROR 10 kez
        for _ in range(10):
            flood_filter.filter(record_error)

        # ERROR'un 11.'si bastırılmalı
        assert flood_filter.filter(record_error) is False

        # WARNING aynı metin ama farklı seviye → geçmeli
        assert flood_filter.filter(record_warn) is True


class TestFloodFilterSummaryEmission:
    """Pencere sonunda bastırılan mesaj özeti loglanmalı."""

    def test_summary_emitted_on_window_expiry(self, flood_filter: FloodFilter) -> None:
        """Bastırılan mesajlar varsa, pencere sonunda özet logu basılmalı."""
        record = _make_record("flood mesaji")

        # 12 mesaj gönder (10 geçer, 2 bastırılır)
        for _ in range(12):
            flood_filter.filter(record)

        # Pencereyi süresi dolmuş gibi yap
        with flood_filter._lock:
            for key in flood_filter._state:
                flood_filter._state[key][0] -= 1.1

        # _emit_summary çağrılmalı
        with patch.object(flood_filter, "_emit_summary") as mock_emit:
            flood_filter.filter(record)
            mock_emit.assert_called_once()
            # suppressed_count = 2
            args = mock_emit.call_args
            assert args[0][2] == 2, "2 bastırılan mesaj rapor edilmeliydi"


class TestFloodFilterConcurrency:
    """Eşzamanlı çağrılarda filter güvenli çalışmalı."""

    def test_filter_is_thread_safe_under_high_load(
        self, flood_filter: FloodFilter
    ) -> None:
        """Çok thread altında filter() exception fırlatmamalı."""
        errors: list[Exception] = []

        def worker(thread_id: int) -> None:
            try:
                for i in range(5000):
                    record = _make_record(f"thread-{thread_id}-msg-{i}")
                    flood_filter.filter(record)
            except Exception as exc:  # pragma: no cover - negatif senaryo
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == [], f"filter() thread-safe olmaliydi, hata: {errors}"

    def test_state_size_is_capped_for_unique_messages(
        self, flood_filter: FloodFilter
    ) -> None:
        """Benzersiz mesaj yukunde state boyutu _MAX_ENTRIES ustune cikmamali."""
        for i in range(5000):
            flood_filter.filter(_make_record(f"unique-msg-{i}"))

        with flood_filter._lock:
            assert len(flood_filter._state) <= 256
