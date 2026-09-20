"""Tests for Bankin analysis functionality."""

import pytest
from datetime import datetime
from pathlib import Path

from screener.bankin import (
    Transaction,
    TransactionType,
    MonthlySummary,
    FinancialAnalysis,
    parse_bankin_csv,
    analyze_bankin_file,
    _parse_french_number,
    _parse_date,
    _parse_boolean,
    _classify_transaction,
)


class TestParsing:
    """Test parsing functions."""

    def test_parse_french_number(self):
        """Test French number parsing."""
        assert _parse_french_number("123,45") == 123.45
        assert _parse_french_number("1234,56") == 1234.56
        assert _parse_french_number("1.234,56") == 1234.56
        assert _parse_french_number("-10.000,00") == -10000.0
        assert _parse_french_number("0") == 0.0
        assert _parse_french_number("") is None
        assert _parse_french_number(None) is None

    def test_parse_date(self):
        """Test French date parsing."""
        assert _parse_date("01/01/2026") == datetime(2026, 1, 1)
        assert _parse_date("31/12/2025") == datetime(2025, 12, 31)
        assert _parse_date("") is None
        assert _parse_date(None) is None
        # Test with quotes
        assert _parse_date('"01/01/2026"') == datetime(2026, 1, 1)

    def test_parse_boolean(self):
        """Test French boolean parsing."""
        assert _parse_boolean("Oui") is True
        assert _parse_boolean("oui") is True
        assert _parse_boolean("OUI") is True
        assert _parse_boolean("Non") is False
        assert _parse_boolean("non") is False
        assert _parse_boolean("Yes") is True
        assert _parse_boolean("No") is False
        assert _parse_boolean("") is False
        assert _parse_boolean(None) is False


class TestTransactionClassification:
    """Test transaction classification."""

    def test_classify_income_salary(self):
        """Test salary classification."""
        t = Transaction(
            date=datetime(2026, 1, 1),
            description="Salaire",
            account="Compte",
            amount=3000.0,
            category="Entrées d'argent",
            subcategory="Salaires",
            note="",
            is_reconciled=True,
        )
        assert _classify_transaction(t) == TransactionType.INCOME

    def test_classify_income_rent(self):
        """Test rent received classification."""
        t = Transaction(
            date=datetime(2026, 1, 1),
            description="Loyer reçu",
            account="Compte",
            amount=1000.0,
            category="Entrées d'argent",
            subcategory="Loyers reçus",
            note="",
            is_reconciled=True,
        )
        assert _classify_transaction(t) == TransactionType.INCOME

    def test_classify_expense_food(self):
        """Test food expense classification."""
        t = Transaction(
            date=datetime(2026, 1, 1),
            description="Supermarché",
            account="Compte",
            amount=-100.0,
            category="Alimentation",
            subcategory="Supermarché",
            note="",
            is_reconciled=True,
        )
        assert _classify_transaction(t) == TransactionType.EXPENSE

    def test_classify_loan(self):
        """Test loan repayment classification."""
        t = Transaction(
            date=datetime(2026, 1, 1),
            description="Remboursement emprunt",
            account="Compte",
            amount=-500.0,
            category="Banque",
            subcategory="Remboursement emprunt",
            note="",
            is_reconciled=True,
        )
        assert _classify_transaction(t) == TransactionType.LOAN

    def test_classify_transfer_out(self):
        """Test outgoing transfer classification."""
        t = Transaction(
            date=datetime(2026, 1, 1),
            description="Virement interne",
            account="Compte",
            amount=-1000.0,
            category="Retraits, Chq. et Vir.",
            subcategory="Virements internes",
            note="",
            is_reconciled=True,
        )
        assert _classify_transaction(t) == TransactionType.TRANSFER_OUT


class TestBankinParsing:
    """Test Bankin CSV parsing."""

    def test_parse_bankin_csv(self):
        """Test parsing a real Bankin CSV file."""
        csv_path = Path(__file__).parent.parent / "exports" / "bankin" / "export_banks_2026-01-01_2026-09-30.csv"
        
        if not csv_path.exists():
            pytest.skip(f"Test file not found: {csv_path}")
        
        transactions = parse_bankin_csv(csv_path)
        
        assert len(transactions) > 0
        assert all(isinstance(t, Transaction) for t in transactions)
        
        # Check that transactions are sorted by date
        for i in range(len(transactions) - 1):
            assert transactions[i].date <= transactions[i + 1].date


class TestFinancialAnalysis:
    """Test financial analysis."""

    def test_analyze_bankin_file(self):
        """Test complete Bankin file analysis."""
        csv_path = Path(__file__).parent.parent / "exports" / "bankin" / "export_banks_2026-01-01_2026-09-30.csv"
        
        if not csv_path.exists():
            pytest.skip(f"Test file not found: {csv_path}")
        
        analysis = analyze_bankin_file(csv_path)
        
        assert isinstance(analysis, FinancialAnalysis)
        assert analysis.total_transactions > 0
        assert analysis.period_start is not None
        assert analysis.period_end is not None
        assert analysis.total_income >= 0
        assert analysis.total_expense <= 0
        # Check net_flow with floating point tolerance
        assert abs(analysis.net_flow - (analysis.total_income + analysis.total_expense)) < 0.01
        
        # Check that we have investment suggestions
        assert len(analysis.investment_suggestions) > 0
        assert analysis.risk_profile in ["conservative", "moderate", "aggressive", "unknown"]
        assert analysis.recommended_investment is not None

    def test_analyze_with_parameters(self):
        """Test analysis with custom parameters."""
        csv_path = Path(__file__).parent.parent / "exports" / "bankin" / "export_banks_2026-01-01_2026-09-30.csv"
        
        if not csv_path.exists():
            pytest.skip(f"Test file not found: {csv_path}")
        
        analysis = analyze_bankin_file(
            csv_path,
            existing_investments=50000.0,
            emergency_fund=10000.0,
            initial_balance=10000.0
        )
        
        assert isinstance(analysis, FinancialAnalysis)
        assert analysis.emergency_fund_needed > 0
