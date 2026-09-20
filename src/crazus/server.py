"""Serveur MCP stdio : outils yfinance pour le screening de valeurs prometteuses."""

from __future__ import annotations

import json
from typing import Any

from mcp.server import MCPServer

from crazus.screening import (
    DISCLAIMER,
    STYLE_WEIGHTS,
    fetch_news,
    fetch_quote,
    score_one,
    screen_tickers,
    search_tickers,
)
from crazus.universes import UNIVERSES, resolve_universe
from crazus.portfolio import analyze_portfolio, parse_boursobank_csv

mcp = MCPServer("crazus")


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


@mcp.tool()
def list_universes() -> str:
    """Liste les univers de tickers prédéfinis (CAC 40, S&P 100, Nasdaq mega-caps)."""
    return _json(
        {
            "disclaimer": DISCLAIMER,
            "universes": {name: {"size": len(tickers), "tickers": tickers} for name, tickers in UNIVERSES.items()},
            "styles": sorted(STYLE_WEIGHTS),
        }
    )


@mcp.tool()
def search_ticker(query: str, limit: int = 8) -> str:
    """Recherche un ticker Yahoo Finance à partir d'un nom ou d'un symbole.

    Args:
        query: Nom d'entreprise ou symbole (ex. LVMH, NVIDIA, MC.PA).
        limit: Nombre maximum de résultats (1-15).
    """
    limit = max(1, min(limit, 15))
    return _json({"query": query, "results": search_tickers(query, limit), "disclaimer": DISCLAIMER})


@mcp.tool()
def get_quote(ticker: str) -> str:
    """Cours, variation du jour et fiche courte d'une valeur.

    Args:
        ticker: Symbole Yahoo Finance (ex. MC.PA, AAPL, NVDA).
    """
    return _json(fetch_quote(ticker.strip().upper()))


@mcp.tool()
def get_news(ticker: str, limit: int = 8) -> str:
    """Dernières actualités Yahoo Finance pour un ticker.

    Args:
        ticker: Symbole Yahoo Finance.
        limit: Nombre d'articles (1-15).
    """
    limit = max(1, min(limit, 15))
    symbol = ticker.strip().upper()
    return _json({"ticker": symbol, "news": fetch_news(symbol, limit), "disclaimer": DISCLAIMER})


@mcp.tool()
def analyze_ticker(ticker: str, style: str = "balanced") -> str:
    """Score détaillé d'une valeur (momentum, qualité, croissance, valorisation, analystes).

    Args:
        ticker: Symbole Yahoo Finance.
        style: Pondération du score: balanced, momentum, quality, growth ou value.
    """
    return _json(score_one(ticker.strip().upper(), style=style.strip().lower()))


@mcp.tool()
def compare_tickers(tickers: list[str], style: str = "balanced") -> str:
    """Compare et classe plusieurs tickers selon le même score.

    Args:
        tickers: Liste de symboles Yahoo Finance.
        style: Pondération: balanced, momentum, quality, growth ou value.
    """
    cleaned = [t.strip().upper() for t in tickers if t and t.strip()]
    if not cleaned:
        return _json({"error": "Aucun ticker fourni", "disclaimer": DISCLAIMER})
    payload = screen_tickers(cleaned, style=style.strip().lower(), top_n=len(cleaned), fundamental_pool=len(cleaned))
    return _json(payload)


@mcp.tool()
def screen_promising(
    universe: str = "cac40",
    tickers: list[str] | None = None,
    style: str = "balanced",
    top_n: int = 10,
    min_market_cap: float | None = None,
) -> str:
    """Identifie les valeurs les plus prometteuses d'un univers selon un score composite.

    Le score n'est pas une prédiction. Il classe des titres liquides selon momentum
    (1m/3m/6m/1y), qualité (ROE, marges, dette), croissance (CA et résultats),
    valorisation (PE, PEG, P/B) et consensus analystes Yahoo.

    Args:
        universe: Univers prédéfini si tickers est vide: cac40, sp100, nasdaq_mega.
        tickers: Liste optionnelle de symboles. Si fournie, elle remplace l'univers.
        style: balanced, momentum, quality, growth ou value.
        top_n: Nombre de valeurs à renvoyer (1-20).
        min_market_cap: Capitalisation minimale en devise locale (ex. 1e10).
    """
    try:
        symbols = resolve_universe(universe, tickers)
    except ValueError as exc:
        return _json({"error": str(exc), "disclaimer": DISCLAIMER})
    top_n = max(1, min(top_n, 20))
    payload = screen_tickers(
        symbols,
        style=style.strip().lower(),
        top_n=top_n,
        min_market_cap=min_market_cap,
    )
    payload["universe"] = universe if not tickers else "custom"
    return _json(payload)


@mcp.resource("crazus://methodology")
def methodology() -> str:
    """Explique le score et ses limites."""
    return _json(
        {
            "disclaimer": DISCLAIMER,
            "styles": STYLE_WEIGHTS,
            "components": {
                "momentum": "Rendements 1 mois, 3 mois, 6 mois et 1 an.",
                "quality": "ROE, marge nette, marge opérationnelle, dette/capitaux propres.",
                "growth": "Croissance du chiffre d'affaires et des résultats.",
                "valuation": "PE (forward prioritaire), PEG, price-to-book.",
                "analyst": "Note moyenne Yahoo (1 = strong buy) et upside vs cours cible.",
            },
            "process": [
                "Téléchargement des historiques de clôture (1 an) pour tout l'univers.",
                "Pré-classement par momentum.",
                "Enrichissement fondamental des meilleures valeurs du pré-classement.",
                "Score composite selon le style choisi, puis top N.",
            ],
        }
    )


@mcp.tool()
def analyze_my_portfolio(
    file_path: str,
    style: str = "balanced",
    benchmark_universe: str | None = None,
) -> str:
    """Analyse un portefeuille Boursobank et donne des conseils achat/vente/conservation.

    Args:
        file_path: Chemin vers le fichier CSV d'export Boursobank
                   (ex: exports/boursobank/export-positions-20-09-2026.csv).
        style: Style de scoring: balanced, momentum, quality, growth ou value.
        benchmark_universe: Univers de référence optionnel pour comparaison
                          (ex: cac40, sp100, nasdaq_mega).
    """
    import os
    from pathlib import Path
    
    # Convert relative path to absolute if needed
    path = Path(file_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    
    if not path.exists():
        return _json({
            "error": f"Fichier introuvable: {path}",
            "disclaimer": DISCLAIMER,
        })
    
    try:
        result = analyze_portfolio(path, style=style, benchmark_universe=benchmark_universe)
        return _json(result)
    except Exception as exc:
        return _json({
            "error": str(exc),
            "disclaimer": DISCLAIMER,
        })


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
