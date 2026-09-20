"""Tests for portfolio analysis module."""

from pathlib import Path
import tempfile

from screener.portfolio import (
    parse_boursobank_csv,
    _parse_french_number,
    _parse_french_integer,
    get_yahoo_ticker_from_isin,
    get_ticker_from_position,
)


class TestFrenchNumberParsing:
    """Test parsing of French-formatted numbers."""

    def test_parse_french_number_basic(self):
        assert _parse_french_number("123,45") == 123.45
        assert _parse_french_number("1 234,56") == 1234.56
        assert _parse_french_number("1.234,56") == 1234.56

    def test_parse_french_number_negative(self):
        assert _parse_french_number("-123,45") == -123.45

    def test_parse_french_number_zero(self):
        assert _parse_french_number("0,00") == 0.0

    def test_parse_french_number_none(self):
        assert _parse_french_number("") is None
        assert _parse_french_number(None) is None

    def test_parse_french_integer_basic(self):
        assert _parse_french_integer("123") == 123
        assert _parse_french_integer("1.234") == 1234
        assert _parse_french_integer("123,00") == 123


class TestBoursobankCSVParsing:
    """Test parsing of Boursobank CSV exports."""

    def test_parse_csv(self):
        csv_content = """name;isin;quantity;buyingPrice;lastPrice;intradayVariation;amount;amountVariation;variation
TESTCORP;FR0000000001;100,00;10,00;12,50;-0,50;1250,00;250,00;25,00
DEMO SA;NL0000000002;50,00;20,00;22,00;-1,00;1100,00;100,00;10,00
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_content)
            f.flush()
            
            positions = parse_boursobank_csv(f.name)
            
            assert len(positions) == 2
            
            # Check first position
            first = positions[0]
            assert first["name"] == "TESTCORP"
            assert first["isin"] == "FR0000000001"
            assert first["quantity"] == 100
            assert first["buying_price"] == 10.0
            assert first["last_price"] == 12.5
            assert first["intraday_variation"] == -0.5
            assert first["current_value"] == 12.5 * 100
            assert first["total_cost"] == 10.0 * 100
            
            # Check second position
            second = positions[1]
            assert second["name"] == "DEMO SA"
            assert second["isin"] == "NL0000000002"
            assert second["quantity"] == 50
            assert second["buying_price"] == 20.0
            assert second["last_price"] == 22.0

    def test_parse_csv_with_etf(self):
        csv_content = """name;isin;quantity;buyingPrice;lastPrice;intradayVariation;amount;amountVariation;variation
SYNTHETIC ETF;LU0000000003;10,00;50,00;55,00;-1,00;550,00;50,00;10,00
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_content)
            f.flush()
            
            positions = parse_boursobank_csv(f.name)
            
            assert len(positions) == 1
            assert positions[0]["name"] == "SYNTHETIC ETF"


class TestTickerMapping:
    """Test ISIN to ticker mapping."""

    def test_known_isins(self):
        assert get_yahoo_ticker_from_isin("FR0012757854") == "SPIE.PA"
        assert get_yahoo_ticker_from_isin("NL0000235190") == "AIR.PA"
        assert get_yahoo_ticker_from_isin("FR0000120628") == "CS.PA"
        assert get_yahoo_ticker_from_isin("NL00150001Q9") == "STLAP.PA"

    def test_unknown_isin(self):
        assert get_yahoo_ticker_from_isin("UNKNOWN123") is None

    def test_ticker_from_position(self):
        position = {
            "name": "SPIE",
            "isin": "FR0012757854",
        }
        assert get_ticker_from_position(position) == "SPIE.PA"
        
        position_no_isin = {
            "name": "AIRBUS",
            "isin": "",
        }
        assert get_ticker_from_position(position_no_isin) == "AIR.PA"
