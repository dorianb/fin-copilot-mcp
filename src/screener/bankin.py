"""Analyse des transactions bancaires Bankin et recommandations de placement."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from screener.screening import DISCLAIMER


class TransactionType(Enum):
    """Type de transaction bancaire."""
    INCOME = "income"      # Entrées d'argent (salaire, loyer, remboursement, etc.)
    EXPENSE = "expense"    # Dépenses
    TRANSFER_IN = "transfer_in"  # Virement entrant
    TRANSFER_OUT = "transfer_out"  # Virement sortant
    LOAN = "loan"          # Emprunt/remboursement
    SAVING = "saving"      # Épargne/investissement
    UNKNOWN = "unknown"    # Non classé


class InvestmentRecommendation(Enum):
    """Niveau de recommandation d'investissement."""
    AGGRESSIVE = "aggressive"  # Investir fortement (PEA, actions)
    MODERATE = "moderate"      # Investissement modéré (mix PEA/PER/Livret A)
    CONSERVATIVE = "conservative"  # Sécurité (Livret A, LDDS)
    NONE = "none"              # Pas de recommandation (solde négatif ou instable)


@dataclass
class Transaction:
    """Représente une transaction bancaire."""
    date: datetime
    description: str
    account: str
    amount: float
    category: str
    subcategory: str
    note: str
    is_reconciled: bool
    transaction_type: TransactionType = TransactionType.UNKNOWN

    def is_income(self) -> bool:
        return self.amount > 0 and self.transaction_type in [TransactionType.INCOME, TransactionType.TRANSFER_IN]

    def is_expense(self) -> bool:
        return self.amount < 0 and self.transaction_type in [TransactionType.EXPENSE, TransactionType.TRANSFER_OUT, TransactionType.LOAN]
    
    def is_internal_transfer(self) -> bool:
        """Check if this is an internal transfer that should be excluded from analysis."""
        return (
            "virement interne" in self.subcategory.lower() or
            "virements internes" in self.subcategory.lower() or
            ("virement" in self.category.lower() and "interne" in self.description.lower()) or
            (self.category == "Retraits, Chq. et Vir." and self.transaction_type in [TransactionType.TRANSFER_IN, TransactionType.TRANSFER_OUT]) or
            # Relevé Différé / Débit mensuel carte are duplicates of internal transfers in Bankin exports
            "relevé différé" in self.description.lower() or
            "débit mensuel carte" in self.subcategory.lower()
        )
    
    def is_real_income(self) -> bool:
        """Check if this is real income (not internal transfer)."""
        return self.is_income() and not self.is_internal_transfer()
    
    def is_real_expense(self) -> bool:
        """Check if this is real expense (not internal transfer)."""
        return self.is_expense() and not self.is_internal_transfer()


@dataclass
class MonthlySummary:
    """Résumé mensuel des flux financiers."""
    month: str  # Format: YYYY-MM
    total_income: float = 0.0
    total_expense: float = 0.0
    net_flow: float = 0.0  # total_income - abs(total_expense)
    savings_rate: float = 0.0  # (net_flow / total_income) * 100
    transactions: list[Transaction] = field(default_factory=list)
    income_by_category: dict[str, float] = field(default_factory=dict)
    expense_by_category: dict[str, float] = field(default_factory=dict)


@dataclass
class FinancialAnalysis:
    """Analyse financière complète avec recommandations."""
    disclaimer: str = DISCLAIMER
    period_start: datetime | None = None
    period_end: datetime | None = None
    total_transactions: int = 0
    total_income: float = 0.0
    total_expense: float = 0.0
    net_flow: float = 0.0
    average_monthly_income: float = 0.0
    average_monthly_expense: float = 0.0
    average_monthly_net: float = 0.0
    savings_rate: float = 0.0
    monthly_summaries: list[MonthlySummary] = field(default_factory=list)
    
    # Statistiques par catégorie
    income_by_category: dict[str, float] = field(default_factory=dict)
    expense_by_category: dict[str, float] = field(default_factory=dict)
    
    # Solde et tendance
    current_balance_estimate: float = 0.0
    balance_trend: str = "stable"  # stable, increasing, decreasing
    
    # Recommandations
    investable_amount: float = 0.0
    emergency_fund_needed: float = 0.0
    recommended_investment: InvestmentRecommendation = InvestmentRecommendation.NONE
    investment_suggestions: list[dict[str, Any]] = field(default_factory=list)
    risk_profile: str = "unknown"  # conservative, moderate, aggressive
    
    # Conseils spécifiques
    advice: list[str] = field(default_factory=list)


def _parse_french_number(value: str) -> float | None:
    """Parse a number string in French or international format.
    
    Handles both:
    - French format: 1 234,56 or 1.234,56 (dot/space thousands, comma decimal)
    - International format: 1234.56 or -7.99 (dot as decimal separator)
    - Bankin format: 3706.38 (dot as decimal separator, no thousands)
    """
    if not value or not isinstance(value, str):
        return None
    try:
        value = value.strip()
        
        # Count separators
        has_comma = "," in value
        has_dot = "." in value
        
        # If it has both comma and dot (French format with thousands)
        # e.g., "1.234,56" or "1 234,56"
        if has_comma and has_dot:
            # Remove dots and spaces (thousands separators), replace comma with dot
            normalized = value.replace(".", "").replace(" ", "").replace(",", ".")
            return float(normalized)
        
        # If it has comma but no dot (French format without thousands)
        # e.g., "123,56"
        elif has_comma and not has_dot:
            normalized = value.replace(",", ".")
            return float(normalized)
        
        # If it has dot but no comma (International/Bankin format)
        # e.g., "1234.56" or "-7.99" or "3706.38"
        elif has_dot and not has_comma:
            # Assume dot is decimal separator (Bankin/International format)
            return float(value)
        
        # No separators, just a plain number
        else:
            return float(value)
            
    except (ValueError, TypeError):
        return None


def _parse_date(date_str: str) -> datetime | None:
    """Parse French date format (DD/MM/YYYY or DD/MM/YY)."""
    if not date_str or not isinstance(date_str, str):
        return None
    try:
        date_str = date_str.strip().strip('"')
        # Try DD/MM/YYYY first
        try:
            return datetime.strptime(date_str, "%d/%m/%Y")
        except ValueError:
            # Try DD/MM/YY
            return datetime.strptime(date_str, "%d/%m/%y")
    except (ValueError, TypeError):
        return None


def _parse_boolean(value: str) -> bool:
    """Parse French boolean (Oui/Non, Yes/No, 1/0)."""
    if not value or not isinstance(value, str):
        return False
    value_lower = value.strip().lower()
    return value_lower in ["oui", "yes", "1", "true"]


def _classify_transaction(transaction: Transaction) -> TransactionType:
    """Classify transaction based on category and amount."""
    category = transaction.category.lower()
    subcategory = transaction.subcategory.lower()
    amount = transaction.amount
    
    # Entrées d'argent
    if amount > 0:
        if "salaire" in category or "salaire" in subcategory:
            return TransactionType.INCOME
        elif "loyer" in category and "reçu" in subcategory.lower():
            return TransactionType.INCOME
        elif "remboursement" in category or "remboursement" in subcategory.lower():
            return TransactionType.INCOME
        elif "entrée" in category or "rentrée" in subcategory.lower():
            return TransactionType.INCOME
        elif "virement" in category and "reçu" in subcategory.lower():
            return TransactionType.TRANSFER_IN
        return TransactionType.INCOME
    
    # Dépenses
    elif amount < 0:
        if "banque" in category and ("virement" in subcategory.lower() or "prélèvement" in subcategory.lower()):
            # Vérifier si c'est un virement interne (sortant)
            if "interne" in subcategory.lower():
                return TransactionType.TRANSFER_OUT
        elif "banque" in category and "remboursement emprunt" in subcategory.lower():
            return TransactionType.LOAN
        elif "impôt" in category or "taxe" in category:
            return TransactionType.EXPENSE
        elif category in ["logement", "auto & transports", "loisirs & sorties", 
                         "abonnements", "alimentation", "santé", 
                         "esthétique & soins", "divers", "impôts & taxes"]:
            return TransactionType.EXPENSE
        elif "virement" in category or "virement" in subcategory.lower():
            return TransactionType.TRANSFER_OUT
        elif "remboursement" in subcategory.lower() and amount < 0:
            # Remboursement de carte bancaire
            return TransactionType.EXPENSE
        return TransactionType.EXPENSE
    
    return TransactionType.UNKNOWN


def parse_bankin_csv(file_path: str | Path) -> list[Transaction]:
    """Parse a Bankin CSV export file.
    
    Expected columns (Bankin format):
    - Date: Transaction date (DD/MM/YYYY)
    - Description: Transaction description
    - Compte: Account name
    - Montant: Amount (positive for income, negative for expense)
    - Catégorie: Main category
    - Sous-Catégorie: Sub-category
    - Note: Optional note
    - Pointée: Whether transaction is reconciled (Oui/Non)
    
    Returns a list of Transaction objects.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {file_path}")
    
    transactions = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            date = _parse_date(row.get("Date", ""))
            amount = _parse_french_number(row.get("Montant", "0")) or 0.0
            
            transaction = Transaction(
                date=date or datetime.min,
                description=row.get("Description", "").strip().strip('"'),
                account=row.get("Compte", "").strip().strip('"'),
                amount=amount,
                category=row.get("Catégorie", "").strip().strip('"'),
                subcategory=row.get("Sous-Catégorie", "").strip().strip('"'),
                note=row.get("Note", "").strip().strip('"'),
                is_reconciled=_parse_boolean(row.get("Pointée", "Non")),
            )
            
            # Classify transaction
            transaction.transaction_type = _classify_transaction(transaction)
            transactions.append(transaction)
    
    # Sort by date
    transactions.sort(key=lambda t: t.date)
    return transactions


def analyze_monthly_flows(transactions: list[Transaction]) -> list[MonthlySummary]:
    """Analyze transactions by month."""
    monthly_data: dict[str, MonthlySummary] = {}
    
    for transaction in transactions:
        if transaction.date == datetime.min:
            continue
        
        # Skip internal transfers
        if transaction.is_internal_transfer():
            continue
            
        month_key = transaction.date.strftime("%Y-%m")
        
        if month_key not in monthly_data:
            monthly_data[month_key] = MonthlySummary(month=month_key)
        
        summary = monthly_data[month_key]
        summary.transactions.append(transaction)
        
        if transaction.is_real_income():
            summary.total_income += transaction.amount
            summary.income_by_category[transaction.category] = \
                summary.income_by_category.get(transaction.category, 0.0) + transaction.amount
        elif transaction.is_real_expense():
            summary.total_expense += transaction.amount  # Already negative
            summary.expense_by_category[transaction.category] = \
                summary.expense_by_category.get(transaction.category, 0.0) + transaction.amount
    
    # Calculate derived metrics for each month
    for summary in monthly_data.values():
        summary.net_flow = summary.total_income + summary.total_expense
        if summary.total_income > 0:
            summary.savings_rate = (summary.net_flow / summary.total_income) * 100
    
    # Sort by month
    return sorted(monthly_data.values(), key=lambda s: s.month)


def calculate_savings_analysis(transactions: list[Transaction]) -> dict[str, Any]:
    """Calculate savings and investment capacity."""
    total_income = sum(t.amount for t in transactions if t.is_income())
    total_expense = sum(t.amount for t in transactions if t.is_expense())
    net_flow = total_income + total_expense
    
    # Calculer le taux d'épargne
    savings_rate = (net_flow / total_income * 100) if total_income > 0 else 0.0
    
    # Estimer le solde courant (simplifié : somme de tous les flux)
    current_balance = net_flow
    
    # Déterminer la tendance
    monthly_summaries = analyze_monthly_flows(transactions)
    if len(monthly_summaries) >= 2:
        last_net = monthly_summaries[-1].net_flow
        prev_net = monthly_summaries[-2].net_flow
        if last_net > prev_net:
            balance_trend = "increasing"
        elif last_net < prev_net:
            balance_trend = "decreasing"
        else:
            balance_trend = "stable"
    else:
        balance_trend = "stable"
    
    return {
        "total_income": total_income,
        "total_expense": total_expense,
        "net_flow": net_flow,
        "savings_rate": savings_rate,
        "current_balance_estimate": current_balance,
        "balance_trend": balance_trend,
        "monthly_summaries": monthly_summaries,
    }


def determine_risk_profile(savings_rate: float, net_flow: float, 
                          expense_by_category: dict[str, float]) -> str:
    """Determine the user's risk profile based on financial behavior."""
    # Si taux d'épargne élevé et flux net positif
    if savings_rate >= 30 and net_flow > 0:
        return "aggressive"
    # Si taux d'épargne modéré
    elif savings_rate >= 15 and net_flow > 0:
        return "moderate"
    # Si flux net positif mais taux d'épargne faible
    elif net_flow > 0:
        return "conservative"
    else:
        return "unknown"


def generate_investment_recommendations(
    analysis: FinancialAnalysis, 
    existing_investments: float = 0.0,
    emergency_fund: float = 0.0
) -> tuple[InvestmentRecommendation, list[dict[str, Any]]]:
    """Generate investment recommendations based on financial analysis.
    
    Args:
        analysis: The financial analysis object
        existing_investments: Current amount already invested (default 0)
        emergency_fund: Current emergency fund amount (default 0)
    
    Returns:
        Tuple of (recommendation_level, list of specific suggestions)
    """
    suggestions = []
    net_flow = analysis.net_flow
    savings_rate = analysis.savings_rate
    avg_monthly_net = analysis.average_monthly_net
    
    # Calculer le montant investissable (estimation)
    # On considère qu'on peut investir une partie de l'épargne mensuelle
    if avg_monthly_net > 0:
        investable_amount = avg_monthly_net * 0.7  # 70% de l'épargne mensuelle moyenne
    else:
        investable_amount = 0.0
    
    # Calculer le fonds d'urgence nécessaire (3-6 mois de dépenses)
    avg_monthly_expense = abs(analysis.average_monthly_expense)
    emergency_fund_needed = avg_monthly_expense * 4  # 4 mois de dépenses
    
    # Si pas de fonds d'urgence, priorité à la constitution
    if emergency_fund < emergency_fund_needed:
        missing_emergency = emergency_fund_needed - emergency_fund
        suggestions.append({
            "type": "emergency_fund",
            "priority": "HIGH",
            "description": f"Constituer un fonds d'urgence de {missing_emergency:.0f}€ (4 mois de dépenses)",
            "recommended_product": "Livret A",
            "amount": missing_emergency,
            "reason": "Le fonds d'urgence est essentiel avant d'investir",
        })
    
    # Recommandations selon le profil de risque
    risk_profile = analysis.risk_profile
    
    if net_flow > 0 and savings_rate >= 10:
        # Bonne capacité d'épargne
        
        # PEA (Plan d'Épargne en Actions) - pour actions européennes
        if risk_profile in ["aggressive", "moderate"]:
            pea_allocation = min(investable_amount * 0.6, 150000 - existing_investments)
            if pea_allocation > 0:
                suggestions.append({
                    "type": "investment",
                    "priority": "HIGH",
                    "description": f"Investir {pea_allocation:.0f}€ dans un PEA",
                    "recommended_product": "PEA",
                    "amount": pea_allocation,
                    "allocations": {
                        "ETF CAC 40": 0.4,
                        "ETF MSCI Europe": 0.3,
                        "Actions individuelles": 0.3,
                    },
                    "reason": f"Taux d'épargne élevé ({savings_rate:.1f}%) et profil {risk_profile}",
                })
        
        # PER (Plan d'Épargne Retraite)
        if risk_profile in ["aggressive", "moderate", "conservative"]:
            per_allocation = investable_amount * 0.3
            if per_allocation > 0:
                suggestions.append({
                    "type": "investment",
                    "priority": "MEDIUM",
                    "description": f"Investir {per_allocation:.0f}€ dans un PER",
                    "recommended_product": "PER",
                    "amount": per_allocation,
                    "allocations": {
                        "ETF Monde": 0.5,
                        "Obligations": 0.3,
                        "Actions": 0.2,
                    },
                    "reason": "Avantage fiscal du PER pour la retraite",
                })
        
        # Livret A pour la sécurité
        if risk_profile == "conservative":
            livret_allocation = investable_amount * 0.8
            suggestions.append({
                "type": "investment",
                "priority": "MEDIUM",
                "description": f"Placer {livret_allocation:.0f}€ sur Livret A",
                "recommended_product": "Livret A",
                "amount": livret_allocation,
                "reason": "Profil conservateur privilégiant la sécurité",
            })
        else:
            # Même avec profil modéré/agressif, garder une partie en sécurité
            livret_allocation = investable_amount * 0.2
            suggestions.append({
                "type": "investment",
                "priority": "LOW",
                "description": f"Placer {livret_allocation:.0f}€ sur Livret A (sécurité)",
                "recommended_product": "Livret A",
                "amount": livret_allocation,
                "reason": "Diversification et sécurité",
            })
        
        # Suggestions spécifiques par catégorie de dépenses
        if "logement" in analysis.expense_by_category:
            # Si dépenses de logement élevées, suggérer investissement immobilier
            suggestions.append({
                "type": "advice",
                "priority": "INFO",
                "description": "Dépenses de logement identifiées - considérer SCPI pour diversification immobilière",
                "recommended_product": "SCPI",
                "amount": investable_amount * 0.1,
                "reason": "Diversification du patrimoine immobilier",
            })
    
    elif net_flow > 0:
        # Faible épargne mais flux positif
        suggestions.append({
            "type": "advice",
            "priority": "MEDIUM",
            "description": f"Flux net positif mais taux d'épargne faible ({savings_rate:.1f}%)",
            "recommended_product": "Livret A",
            "amount": investable_amount,
            "reason": "Commencer par sécuriser l'épargne avant d'investir",
        })
    else:
        # Flux net négatif
        suggestions.append({
            "type": "warning",
            "priority": "HIGH",
            "description": "Flux net négatif - pas d'investissement recommandé",
            "recommended_product": "Aucun",
            "amount": 0.0,
            "reason": "Les dépenses dépassent les revenus",
        })
    
    # Déterminer le niveau de recommandation global
    if len([s for s in suggestions if s["type"] == "investment" and s["priority"] == "HIGH"]) > 0:
        recommendation = InvestmentRecommendation.AGGRESSIVE
    elif len([s for s in suggestions if s["type"] == "investment"]) > 0:
        recommendation = InvestmentRecommendation.MODERATE
    elif len([s for s in suggestions if s["type"] == "emergency_fund" and s["priority"] == "HIGH"]) > 0:
        recommendation = InvestmentRecommendation.CONSERVATIVE
    else:
        recommendation = InvestmentRecommendation.NONE
    
    return recommendation, suggestions


def analyze_bankin_file(
    file_path: str | Path,
    existing_investments: float = 0.0,
    emergency_fund: float = 0.0,
    initial_balance: float = 0.0
) -> FinancialAnalysis:
    """Analyze a Bankin CSV export file and provide investment recommendations.
    
    Args:
        file_path: Path to the Bankin CSV export file
        existing_investments: Current amount already invested (default 0)
        emergency_fund: Current emergency fund amount (default 0)
        initial_balance: Initial balance at the start of the period (default 0)
    
    Returns:
        FinancialAnalysis object with complete analysis and recommendations
    """
    # Parse transactions
    transactions = parse_bankin_csv(file_path)
    
    if not transactions:
        return FinancialAnalysis(
            error="Aucune transaction trouvée dans le fichier",
            disclaimer=DISCLAIMER,
        )
    
    # Sort transactions by date
    transactions.sort(key=lambda t: t.date)
    
    # Get period
    dates = [t.date for t in transactions if t.date != datetime.min]
    if dates:
        period_start = min(dates)
        period_end = max(dates)
    else:
        period_start = None
        period_end = None
    
    # Calculate totals (excluding internal transfers)
    total_income = sum(t.amount for t in transactions if t.is_real_income())
    total_expense = sum(t.amount for t in transactions if t.is_real_expense())
    net_flow = total_income + total_expense
    
    # Monthly summaries
    monthly_summaries = analyze_monthly_flows(transactions)
    
    # Calculate averages
    num_months = len(monthly_summaries) if monthly_summaries else 1
    average_monthly_income = total_income / num_months
    average_monthly_expense = total_expense / num_months
    average_monthly_net = net_flow / num_months
    
    # Savings rate
    savings_rate = (net_flow / total_income * 100) if total_income > 0 else 0.0
    
    # Aggregate by category (excluding internal transfers)
    income_by_category: dict[str, float] = defaultdict(float)
    expense_by_category: dict[str, float] = defaultdict(float)
    
    for t in transactions:
        if t.is_real_income():
            income_by_category[t.category] += t.amount
        elif t.is_real_expense():
            expense_by_category[t.category] += t.amount
    
    # Estimate current balance
    current_balance_estimate = initial_balance + net_flow
    
    # Determine balance trend
    if len(monthly_summaries) >= 2:
        recent_trend = [s.net_flow for s in monthly_summaries[-3:]]
        if all(recent_trend[i] > recent_trend[i-1] for i in range(1, len(recent_trend))):
            balance_trend = "increasing"
        elif all(recent_trend[i] < recent_trend[i-1] for i in range(1, len(recent_trend))):
            balance_trend = "decreasing"
        else:
            balance_trend = "stable"
    else:
        balance_trend = "stable"
    
    # Determine risk profile
    risk_profile = determine_risk_profile(savings_rate, net_flow, dict(expense_by_category))
    
    # Generate investment recommendations
    recommendation, investment_suggestions = generate_investment_recommendations(
        FinancialAnalysis(
            total_income=total_income,
            total_expense=total_expense,
            net_flow=net_flow,
            average_monthly_income=average_monthly_income,
            average_monthly_expense=average_monthly_expense,
            average_monthly_net=average_monthly_net,
            savings_rate=savings_rate,
            balance_trend=balance_trend,
            risk_profile=risk_profile,
        ),
        existing_investments=existing_investments,
        emergency_fund=emergency_fund,
    )
    
    # Calculate investable amount (70% of average monthly net)
    investable_amount = average_monthly_net * 0.7 if average_monthly_net > 0 else 0.0
    
    # Calculate emergency fund needed
    emergency_fund_needed = abs(average_monthly_expense) * 4
    
    # Generate advice messages
    advice = []
    
    if net_flow > 0:
        advice.append(f"Votre flux net sur la période est positif: +{net_flow:.2f}€")
        advice.append(f"Taux d'épargne: {savings_rate:.1f}%")
    else:
        advice.append(f"Votre flux net sur la période est négatif: {net_flow:.2f}€")
        advice.append("Pensez à réduire vos dépenses ou augmenter vos revenus")
    
    advice.append(f"Solde estimé: {current_balance_estimate:.2f}€")
    advice.append(f"Tendance: {balance_trend}")
    
    if risk_profile != "unknown":
        advice.append(f"Profil de risque: {risk_profile}")
    
    # Create the analysis object
    analysis = FinancialAnalysis(
        disclaimer=DISCLAIMER,
        period_start=period_start,
        period_end=period_end,
        total_transactions=len(transactions),
        total_income=round(total_income, 2),
        total_expense=round(total_expense, 2),
        net_flow=round(net_flow, 2),
        average_monthly_income=round(average_monthly_income, 2),
        average_monthly_expense=round(average_monthly_expense, 2),
        average_monthly_net=round(average_monthly_net, 2),
        savings_rate=round(savings_rate, 2),
        monthly_summaries=monthly_summaries,
        income_by_category=dict(income_by_category),
        expense_by_category=dict(expense_by_category),
        current_balance_estimate=round(current_balance_estimate, 2),
        balance_trend=balance_trend,
        investable_amount=round(investable_amount, 2),
        emergency_fund_needed=round(emergency_fund_needed, 2),
        recommended_investment=recommendation,
        investment_suggestions=investment_suggestions,
        risk_profile=risk_profile,
        advice=advice,
    )
    
    return analysis
