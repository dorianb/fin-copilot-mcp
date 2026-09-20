"""Tests for portfolio analysis module."""

from pathlib import Path
import tempfile

from crazus.portfolio import (
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
SPIE;FR0012757854;11,00;34,57;43,72;-0,91;480,92;100,60;26,45
AIRBUS;NL0000235190;2,00;170,43;193,38;-1,08;386,76;45,90;13,47
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_content)
            f.flush()
            
            positions = parse_boursobank_csv(f.name)
            
            assert len(positions) == 2
            
            # Check SPIE position
            spie = positions[0]
            assert spie["name"] == "SPIE"
            assert spie["isin"] == "FR0012757854"
            assert spie["quantity"] == 11
            assert spie["buying_price"] == 34.57
            assert spie["last_price"] == 43.72
            assert spie["intraday_variation"] == -0.91
            assert spie["current_value"] == 43.72 * 11
            assert spie["total_cost"] == 34.57 * 11
            
            # Check AIRBUS position
            airbus = positions[1]
            assert airbus["name"] == "AIRBUS"
            assert airbus["isin"] == "NL0000235190"
            assert airbus["quantity"] == 2
            assert airbus["buying_price"] == 170.43
            assert airbus["last_price"] == 193.38

    def test_parse_csv_with_etf(self):
        csv_content = """name;isin;quantity;buyingPrice;lastPrice;intradayVariation;amount;amountVariation;variation
AMUNDI EURO STOXX BANKS ETF ACC;LU1829219390;1,00;277,38;395,00;-2,31;395,00;117,62;42,40
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(csv_content)
            f.flush()
            
            positions = parse_boursobank_csv(f.name)
            
            assert len(positions) == 1
            assert positions[0]["name"] == "AMUNDI EURO STOXX BANKS ETF ACC"


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
