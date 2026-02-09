"""
ヘルパー関数のテスト
"""
import pytest
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from app import ensure_aware, parse_local_datetime, format_local_form_value, ensure_valid_range, fmt_dt, fmt_hms, fmt_date_ja

class TestDateTimeHelpers:
    """日時ヘルパー関数のテスト"""
    
    def test_ensure_aware_with_naive(self):
        """ナイーブなdatetimeをawareに変換"""
        naive_dt = datetime(2024, 1, 1, 12, 0, 0)
        aware_dt = ensure_aware(naive_dt)
        
        assert aware_dt.tzinfo is not None
    
    def test_ensure_aware_with_aware(self):
        """既にawareなdatetimeはそのまま"""
        aware_dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = ensure_aware(aware_dt)
        
        assert result.tzinfo is not None
        assert result == aware_dt
    
    def test_ensure_aware_with_none(self):
        """Noneの場合はNoneを返す"""
        assert ensure_aware(None) is None
    
    def test_parse_local_datetime_valid(self):
        """有効なローカル時刻文字列をパース"""
        dt_str = '2024-01-01T12:00'
        result = parse_local_datetime(dt_str)
        
        assert result is not None
        assert result.tzinfo is not None
    
    def test_parse_local_datetime_invalid(self):
        """無効な時刻文字列でエラー"""
        with pytest.raises(ValueError):
            parse_local_datetime('invalid-date')
    
    def test_parse_local_datetime_none(self):
        """Noneの場合はNoneを返す"""
        assert parse_local_datetime(None) is None
    
    def test_format_local_form_value(self):
        """datetime-local形式にフォーマット"""
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = format_local_form_value(dt)
        
        assert '2024-01-01T' in result
        # タイムゾーン変換により時刻が変わる可能性があるため、形式のみ確認
        assert 'T' in result
        assert len(result) > 0
    
    def test_format_local_form_value_none(self):
        """Noneの場合は空文字列を返す"""
        assert format_local_form_value(None) == ''
    
    def test_ensure_valid_range_valid(self):
        """有効な日付範囲"""
        start = datetime(2024, 1, 1).date()
        end = datetime(2024, 1, 10).date()
        
        result_start, result_end = ensure_valid_range(start, end)
        assert result_start == start
        assert result_end == end
    
    def test_ensure_valid_range_invalid_order(self):
        """開始日が終了日より後の場合はエラー"""
        start = datetime(2024, 1, 10).date()
        end = datetime(2024, 1, 1).date()
        
        with pytest.raises(ValueError):
            ensure_valid_range(start, end)
    
    def test_ensure_valid_range_too_long(self):
        """期間が長すぎる場合はエラー"""
        from app import CSV_EXPORT_MAX_DAYS
        start = datetime(2024, 1, 1).date()
        end = datetime(2024, 1, 1).date() + timedelta(days=CSV_EXPORT_MAX_DAYS + 1)
        
        with pytest.raises(ValueError):
            ensure_valid_range(start, end)

class TestFormatHelpers:
    """フォーマット関数のテスト"""
    
    def test_fmt_dt_with_datetime(self):
        """日時フォーマット（短縮版）"""
        dt = datetime(2024, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        result = fmt_dt(dt)
        
        assert '01月15日' in result or '1月15日' in result
        # タイムゾーン変換により時刻が変わる可能性があるため、形式のみ確認
        assert ':' in result
    
    def test_fmt_dt_full(self):
        """日時フォーマット（完全版）"""
        dt = datetime(2024, 1, 15, 14, 30, 45, tzinfo=timezone.utc)
        result = fmt_dt(dt, full=True)
        
        assert '2024年' in result
        assert '01月15日' in result or '1月15日' in result
        # タイムゾーン変換により時刻が変わる可能性があるため、形式のみ確認
        assert ':' in result
    
    def test_fmt_dt_none(self):
        """Noneの場合は'-'を返す"""
        assert fmt_dt(None) == '-'
    
    def test_fmt_hms(self):
        """時分秒フォーマット"""
        seconds = 3661  # 1時間1分1秒
        result = fmt_hms(seconds)
        
        assert '1:01' in result or '01:01' in result
    
    def test_fmt_hms_precise(self):
        """時分秒フォーマット（秒まで表示）"""
        seconds = 3661  # 1時間1分1秒
        result = fmt_hms(seconds, precise=True)
        
        assert '01:01:01' in result
    
    def test_fmt_hms_zero(self):
        """0秒の場合"""
        assert fmt_hms(0) is not None
    
    def test_fmt_date_ja(self):
        """日本語日付フォーマット"""
        date = datetime(2024, 1, 15).date()
        result = fmt_date_ja(date)
        
        assert '01月15日' in result
    
    def test_fmt_date_ja_full(self):
        """日本語日付フォーマット（完全版）"""
        date = datetime(2024, 1, 15).date()
        result = fmt_date_ja(date, full=True)
        
        assert '2024年01月15日' in result
    
    def test_fmt_date_ja_none(self):
        """Noneの場合は'-'を返す"""
        assert fmt_date_ja(None) == '-'

