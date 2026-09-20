"""Analyse de portefeuille et conseils de positionnement basés sur le scoring Crazus."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from crazus.screening import DISCLAIMER, STYLE_WEIGHTS, score_one, screen_tickers


def _parse_french_number(value: str) -> float | None:
    """Parse a French-formatted number string (comma decimal, dot thousands)."""
    if not value or not isinstance(value, str):
        return None
    try:
        # Replace dots and spaces (thousands separator) and comma (decimal separator)
        normalized = value.strip().replace(".", "").replace(" ", "").replace(",", ".")
        return float(normalized)
    except (ValueError, TypeError):
        return None


def _parse_french_integer(value: str) -> int | None:
    """Parse a French-formatted integer string (may contain dots as thousands separator)."""
    if not value or not isinstance(value, str):
        return None
    try:
        normalized = value.strip().replace(".", "").replace(" ", "").replace(",", ".")
        return int(float(normalized))
    except (ValueError, TypeError):
        return None


def parse_boursobank_csv(file_path: str | Path) -> list[dict[str, Any]]:
    """Parse a Boursobank positions CSV export file.
    
    Expected columns:
    - name: Company name
    - isin: ISIN code
    - quantity: Number of shares
    - buyingPrice: Purchase price per share
    - lastPrice: Current price per share
    - intradayVariation: Daily price variation percentage
    - amount: Total current value
    - amountVariation: Daily value variation
    - variation: Total portfolio percentage variation
    
    Returns a list of position dictionaries with parsed numeric values.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {file_path}")
    
    positions = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            position = {
                "name": row.get("name", "").strip(),
                "isin": row.get("isin", "").strip(),
                "quantity": _parse_french_integer(row.get("quantity", "0")) or 0,
                "buying_price": _parse_french_number(row.get("buyingPrice", "0")) or 0.0,
                "last_price": _parse_french_number(row.get("lastPrice", "0")) or 0.0,
                "intraday_variation": _parse_french_number(row.get("intradayVariation", "0")) or 0.0,
                "amount": _parse_french_number(row.get("amount", "0")) or 0.0,
                "amount_variation": _parse_french_number(row.get("amountVariation", "0")) or 0.0,
                "variation": _parse_french_number(row.get("variation", "0")) or 0.0,
            }
            # Calculate additional useful metrics
            if position["buying_price"] > 0 and position["quantity"] > 0:
                position["total_cost"] = position["buying_price"] * position["quantity"]
                position["current_value"] = position["last_price"] * position["quantity"]
                if position["total_cost"] > 0:
                    position["unrealized_pnl"] = position["current_value"] - position["total_cost"]
                    position["unrealized_pnl_pct"] = (
                        (position["unrealized_pnl"] / position["total_cost"]) * 100
                        if position["total_cost"] != 0
                        else 0.0
                    )
                else:
                    position["unrealized_pnl"] = 0.0
                    position["unrealized_pnl_pct"] = 0.0
            else:
                position["total_cost"] = 0.0
                position["current_value"] = 0.0
                position["unrealized_pnl"] = 0.0
                position["unrealized_pnl_pct"] = 0.0
            
            positions.append(position)
    
    return positions


def get_yahoo_ticker_from_isin(isin: str) -> str | None:
    """Map ISIN to Yahoo Finance ticker symbol.
    
    This is a simplified mapping. For a complete solution, you would need
    a comprehensive ISIN-to-symbol mapping or use an API.
    """
    # Known mappings from the user's portfolio
    isin_to_ticker = {
        "FR0012757854": "SPIE.PA",      # SPIE
        "LU1829219390": None,           # AMUNDI EURO STOXX BANKS ETF ACC - ETF, no direct ticker
        "NL0000235190": "AIR.PA",      # AIRBUS
        "FR0000120628": "CS.PA",       # AXA
        "NL00150001Q9": "STLAP.PA",    # STELLANTIS
    }
    return isin_to_ticker.get(isin.upper())


def get_ticker_from_position(position: dict[str, Any]) -> str | None:
    """Extract Yahoo Finance ticker from a position."""
    # Try ISIN mapping first
    ticker = get_yahoo_ticker_from_isin(position.get("isin", ""))
    if ticker:
        return ticker
    
    # Try to infer from name
    name = position.get("name", "").upper()
    name_to_ticker = {
        "SPIE": "SPIE.PA",
        "AIRBUS": "AIR.PA",
        "AXA": "CS.PA",
        "STELLANTIS": "STLA.PA",
    }
    return name_to_ticker.get(name)


def analyze_position(portfolio_position: dict[str, Any], style: str = "balanced") -> dict[str, Any]:
    """Analyze a single portfolio position and provide advice.
    
    Returns a dict with score, recommendation, and reasoning.
    """
    ticker = get_ticker_from_position(portfolio_position)
    
    if not ticker:
        return {
            "ticker": None,
            "name": portfolio_position.get("name", "Unknown"),
            "isin": portfolio_position.get("isin", ""),
            "error": "Ticker Yahoo Finance introuvable",
            "recommendation": "UNKNOWN",
            "confidence": 0,
            "disclaimer": DISCLAIMER,
        }
    
    try:
        # Get the Crazus score for this ticker
        score_data = score_one(ticker, style=style)
        
        if "error" in score_data:
            return {
                "ticker": ticker,
                "name": portfolio_position.get("name", "Unknown"),
                "isin": portfolio_position.get("isin", ""),
                "error": score_data.get("error", "Données introuvables"),
                "recommendation": "UNKNOWN",
                "confidence": 0,
                "disclaimer": DISCLAIMER,
            }
        
        score = score_data.get("score", 0)
        components = score_data.get("components", {})
        
        # Calculate position metrics
        unrealized_pnl_pct = portfolio_position.get("unrealized_pnl_pct", 0)
        intraday_variation = portfolio_position.get("intraday_variation", 0)
        
        # Determine recommendation based on score and P&L
        recommendation, reasoning = _determine_recommendation(
            score, components, unrealized_pnl_pct, portfolio_position
        )
        
        return {
            "ticker": ticker,
            "name": portfolio_position.get("name", "Unknown"),
            "isin": portfolio_position.get("isin", ""),
            "quantity": portfolio_position.get("quantity", 0),
            "buying_price": portfolio_position.get("buying_price", 0),
            "last_price": portfolio_position.get("last_price", 0),
            "current_value": portfolio_position.get("current_value", 0),
            "total_cost": portfolio_position.get("total_cost", 0),
            "unrealized_pnl": portfolio_position.get("unrealized_pnl", 0),
            "unrealized_pnl_pct": unrealized_pnl_pct,
            "intraday_variation": intraday_variation,
            "score": score,
            "components": components,
            "style": style,
            "recommendation": recommendation,
            "reasoning": reasoning,
            "confidence": _calculate_confidence(score, components),
            "disclaimer": DISCLAIMER,
        }
        
    except Exception as e:
        return {
            "ticker": ticker,
            "name": portfolio_position.get("name", "Unknown"),
            "isin": portfolio_position.get("isin", ""),
            "error": str(e),
            "recommendation": "UNKNOWN",
            "confidence": 0,
            "disclaimer": DISCLAIMER,
        }


def _determine_recommendation(
    score: float, 
    components: dict[str, float], 
    unrealized_pnl_pct: float,
    position: dict[str, Any]
) -> tuple[str, list[str]]:
    """Determine buy/hold/sell recommendation based on score and position data.
    
    Returns (recommendation, list of reasoning strings)
    """
    reasoning = []
    
    # Score-based recommendation
    if score >= 80:
        score_advice = "BUY"
        reasoning.append(f"Score élevé ({score:.1f}/100) - Fundamentaux solides")
    elif score >= 65:
        score_advice = "HOLD"
        reasoning.append(f"Score correct ({score:.1f}/100) - Fundamentaux satisfaisants")
    elif score >= 50:
        score_advice = "HOLD"
        reasoning.append(f"Score moyen ({score:.1f}/100) - À surveiller")
    else:
        score_advice = "SELL"
        reasoning.append(f"Score faible ({score:.1f}/100) - Fundamentaux préoccupants")
    
    # P&L-based modulation
    if unrealized_pnl_pct >= 20:
        pnl_advice = "SELL"
        reasoning.append(f"Plus-value importante (+{unrealized_pnl_pct:.1f}%) - Prendre des bénéfices")
    elif unrealized_pnl_pct >= 10:
        pnl_advice = "HOLD"
        reasoning.append(f"Plus-value significative (+{unrealized_pnl_pct:.1f}%)")
    elif unrealized_pnl_pct >= 5:
        pnl_advice = "HOLD"
        reasoning.append(f"Légère plus-value (+{unrealized_pnl_pct:.1f}%)")
    elif unrealized_pnl_pct >= -5:
        pnl_advice = "HOLD"
        reasoning.append(f"Position proche de l'équilibre ({unrealized_pnl_pct:+.1f}%)")
    elif unrealized_pnl_pct >= -15:
        pnl_advice = "HOLD"
        reasoning.append(f"Légère moins-value ({unrealized_pnl_pct:.1f}%) - Attendre rebond")
    else:
        pnl_advice = "SELL"
        reasoning.append(f"Moins-value importante ({unrealized_pnl_pct:.1f}%) - Couper les pertes")
    
    # Component-based insights
    momentum = components.get("momentum", 50)
    quality = components.get("quality", 50)
    valuation = components.get("valuation", 50)
    
    if momentum >= 80:
        reasoning.append("Momentum très fort - Tendance haussière marquée")
    elif momentum <= 30:
        reasoning.append("Momentum faible - Tendance baissière")
    
    if quality >= 80:
        reasoning.append("Qualité fondamentale excellente")
    elif quality <= 30:
        reasoning.append("Qualité fondamentale médiocre")
    
    if valuation >= 80:
        reasoning.append("Valorisation attractive - Sous-évalué")
    elif valuation <= 30:
        reasoning.append("Valorisation chère - Sur-évalué")
    
    # Combine recommendations
    if score_advice == "SELL" or pnl_advice == "SELL":
        recommendation = "SELL"
    elif score_advice == "BUY" and unrealized_pnl_pct < 15:
        recommendation = "BUY"
    else:
        recommendation = "HOLD"
    
    return recommendation, reasoning


def _calculate_confidence(score: float, components: dict[str, float]) -> int:
    """Calculate confidence level (0-100) based on score quality."""
    if score <= 0:
        return 0
    
    # Higher confidence when score is extreme (very high or very low)
    # and when components are well-distributed
    component_values = list(components.values())
    if not component_values:
        return 50
    
    avg_component = sum(component_values) / len(component_values)
    score_diff = abs(score - avg_component)
    
    # Confidence is higher when score is consistent with components
    consistency = 100 - min(score_diff * 2, 50)
    
    # Also factor in how extreme the score is
    extremeness = min(abs(score - 50) * 0.4, 20)
    
    confidence = min(100, consistency + extremeness + 30)
    return int(confidence)


def analyze_portfolio(
    file_path: str | Path, 
    style: str = "balanced",
    benchmark_universe: str | None = None
) -> dict[str, Any]:
    """Analyze a complete portfolio from a Boursobank CSV export.
    
    Args:
        file_path: Path to the Boursobank CSV export file
        style: Scoring style (balanced, momentum, quality, growth, value)
        benchmark_universe: Optional universe to compare against (e.g., "cac40")
    
    Returns:
        Dict with portfolio summary, individual position analyses, 
        and overall recommendations.
    """
    positions = parse_boursobank_csv(file_path)
    
    if not positions:
        return {
            "error": "Aucune position trouvée dans le fichier",
            "disclaimer": DISCLAIMER,
        }
    
    # Analyze each position
    analyses = []
    total_value = 0.0
    total_cost = 0.0
    total_pnl = 0.0
    
    for position in positions:
        analysis = analyze_position(position, style=style)
        analyses.append(analysis)
        
        if "current_value" in analysis:
            total_value += analysis["current_value"]
        if "total_cost" in analysis:
            total_cost += analysis["total_cost"]
        if "unrealized_pnl" in analysis:
            total_pnl += analysis["unrealized_pnl"]
    
    # Calculate portfolio-level metrics
    portfolio_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0
    
    # Count recommendations
    buy_count = sum(1 for a in analyses if a.get("recommendation") == "BUY")
    hold_count = sum(1 for a in analyses if a.get("recommendation") == "HOLD")
    sell_count = sum(1 for a in analyses if a.get("recommendation") == "SELL")
    unknown_count = sum(1 for a in analyses if a.get("recommendation") == "UNKNOWN")
    
    # Calculate average score (only for analyzed positions)
    valid_scores = [a.get("score", 0) for a in analyses if a.get("score", 0) > 0]
    avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
    
    # Get benchmark comparison if requested
    benchmark_data = None
    if benchmark_universe:
        try:
            from crazus.universes import resolve_universe
            benchmark_tickers = resolve_universe(benchmark_universe, None)
            if benchmark_tickers:
                benchmark_data = screen_tickers(
                    benchmark_tickers, 
                    style=style, 
                    top_n=5,
                    fundamental_pool=10
                )
        except Exception:
            pass
    
    return {
        "disclaimer": DISCLAIMER,
        "file_path": str(file_path),
        "portfolio_summary": {
            "total_positions": len(positions),
            "total_value": round(total_value, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(portfolio_pnl_pct, 2),
            "average_score": round(avg_score, 1),
            "recommendations": {
                "BUY": buy_count,
                "HOLD": hold_count,
                "SELL": sell_count,
                "UNKNOWN": unknown_count,
            },
        },
        "style": style,
        "positions": analyses,
        "benchmark": benchmark_data,
    }
