"""Serveur Gradio : outils yfinance pour le screening de valeurs prometteuses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import gradio as gr
import spaces

from screener.screening import (
    DISCLAIMER,
    STYLE_WEIGHTS,
    fetch_news,
    fetch_quote,
    get_dividends as screening_get_dividends,
    score_one,
    screen_tickers,
    search_tickers,
)
from screener.universes import UNIVERSES, resolve_universe
from screener.portfolio import analyze_portfolio
from screener.bankin import analyze_bankin_file

STYLES = sorted(STYLE_WEIGHTS)
UNIVERSE_NAMES = sorted(UNIVERSES)


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _resolve_path(file_obj: Any) -> Path | None:
    """Accepte un chemin str ou un fichier Gradio (objet avec .name ou str)."""
    if file_obj is None:
        return None
    if isinstance(file_obj, str):
        path = Path(file_obj)
    elif hasattr(file_obj, "name"):
        path = Path(file_obj.name)
    else:
        return None
    return path if path.exists() else None


@spaces.GPU
def screen_promising(
    universe: str,
    custom_tickers: str,
    style: str,
    top_n: int,
    min_market_cap: float | None,
) -> str:
    """Identifie les valeurs les plus prometteuses d'un univers selon un score composite."""
    tickers = [t.strip().upper() for t in (custom_tickers or "").split(",") if t.strip()] or None
    try:
        symbols = resolve_universe(universe, tickers)
    except ValueError as exc:
        return _json({"error": str(exc), "disclaimer": DISCLAIMER})
    top_n = max(1, min(int(top_n), 20))
    cap = min_market_cap if min_market_cap else None
    payload = screen_tickers(symbols, style=style.strip().lower(), top_n=top_n, min_market_cap=cap)
    payload["universe"] = universe if not tickers else "custom"
    return _json(payload)


@spaces.GPU
def analyze_ticker(ticker: str, style: str) -> str:
    """Score détaillé d'une valeur (momentum, qualité, croissance, valorisation, analystes)."""
    return _json(score_one(ticker.strip().upper(), style=style.strip().lower()))


@spaces.GPU
def compare_tickers(tickers: str, style: str) -> str:
    """Compare et classe plusieurs tickers selon le même score."""
    cleaned = [t.strip().upper() for t in (tickers or "").split(",") if t.strip()]
    if not cleaned:
        return _json({"error": "Aucun ticker fourni", "disclaimer": DISCLAIMER})
    payload = screen_tickers(cleaned, style=style.strip().lower(), top_n=len(cleaned), fundamental_pool=len(cleaned))
    return _json(payload)


def get_quote(ticker: str) -> str:
    """Cours, variation du jour et fiche courte d'une valeur."""
    return _json(fetch_quote(ticker.strip().upper()))


def get_news(ticker: str, limit: int) -> str:
    """Dernières actualités Yahoo Finance pour un ticker."""
    limit = max(1, min(int(limit), 15))
    symbol = ticker.strip().upper()
    return _json({"ticker": symbol, "news": fetch_news(symbol, limit), "disclaimer": DISCLAIMER})


def get_dividends(ticker: str) -> str:
    """Dividendes passés et futurs pour un ticker."""
    return _json(screening_get_dividends(ticker.strip().upper()))


def search_ticker(query: str, limit: int) -> str:
    """Recherche un ticker Yahoo Finance à partir d'un nom ou d'un symbole."""
    limit = max(1, min(int(limit), 15))
    return _json({"query": query, "results": search_tickers(query, limit), "disclaimer": DISCLAIMER})


@spaces.GPU
def analyze_my_portfolio(file_obj: Any, style: str, benchmark_universe: str | None) -> str:
    """Analyse un portefeuille Boursobank et donne des conseils achat/vente/conservation."""
    path = _resolve_path(file_obj)
    if path is None:
        return _json({"error": "Aucun fichier fourni ou introuvable", "disclaimer": DISCLAIMER})
    benchmark = benchmark_universe or None
    try:
        result = analyze_portfolio(path, style=style.strip().lower(), benchmark_universe=benchmark)
        return _json(result)
    except Exception as exc:
        return _json({"error": str(exc), "disclaimer": DISCLAIMER})


@spaces.GPU
def analyze_my_bankin(
    file_obj: Any,
    existing_investments: float,
    emergency_fund: float,
    initial_balance: float,
) -> str:
    """Analyse les transactions bancaires Bankin et propose des recommandations de placement."""
    path = _resolve_path(file_obj)
    if path is None:
        return _json({"error": "Aucun fichier fourni ou introuvable", "disclaimer": DISCLAIMER})
    try:
        result = analyze_bankin_file(
            path,
            existing_investments=float(existing_investments or 0.0),
            emergency_fund=float(emergency_fund or 0.0),
            initial_balance=float(initial_balance or 0.0),
        )
        return _json(result, default=str)
    except Exception as exc:
        return _json({"error": str(exc), "disclaimer": DISCLAIMER})


def list_universes() -> str:
    """Liste les univers de tickers prédéfinis et les styles de pondération."""
    return _json(
        {
            "disclaimer": DISCLAIMER,
            "universes": {name: {"size": len(tickers), "tickers": tickers} for name, tickers in UNIVERSES.items()},
            "styles": STYLES,
        }
    )


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


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="Screener") as demo:
        gr.Markdown("# Screener\n" + DISCLAIMER)

        with gr.Tab("Screening"):
            gr.Markdown("### Valeurs prometteuses d'un univers")
            with gr.Row():
                universe_in = gr.Dropdown(choices=UNIVERSE_NAMES, value="cac40", label="Univers")
                style_in = gr.Dropdown(choices=STYLES, value="balanced", label="Style")
            with gr.Row():
                custom_in = gr.Textbox(label="Tickers custom (optionnel, séparés par virgules)", placeholder="MC.PA, RMS.PA, OR.PA")
                top_n_in = gr.Slider(1, 20, value=10, step=1, label="Top N")
                min_cap_in = gr.Number(label="Cap. min. (devise locale)", value=None)
            screen_out = gr.Textbox(label="Résultat (JSON)", lines=20)
            screen_btn = gr.Button("Lancer le screening")
            screen_btn.click(
                screen_promising,
                inputs=[universe_in, custom_in, style_in, top_n_in, min_cap_in],
                outputs=screen_out,
            )

        with gr.Tab("Analyser un ticker"):
            gr.Markdown("### Score détaillé d'une valeur")
            with gr.Row():
                ticker_in = gr.Textbox(label="Ticker", placeholder="MC.PA, AAPL, NVDA")
                style_a_in = gr.Dropdown(choices=STYLES, value="balanced", label="Style")
            analyze_out = gr.Textbox(label="Résultat (JSON)", lines=20)
            analyze_btn = gr.Button("Analyser")
            analyze_btn.click(analyze_ticker, inputs=[ticker_in, style_a_in], outputs=analyze_out)

        with gr.Tab("Comparer"):
            gr.Markdown("### Classement de plusieurs tickers")
            with gr.Row():
                compare_in = gr.Textbox(label="Tickers (séparés par virgules)", placeholder="MC.PA, RMS.PA, OR.PA, KER.PA")
                style_c_in = gr.Dropdown(choices=STYLES, value="balanced", label="Style")
            compare_out = gr.Textbox(label="Résultat (JSON)", lines=20)
            compare_btn = gr.Button("Comparer")
            compare_btn.click(compare_tickers, inputs=[compare_in, style_c_in], outputs=compare_out)

        with gr.Tab("Cours / Actu / Dividendes"):
            gr.Markdown("### Données de marché Yahoo Finance")
            md_ticker = gr.Textbox(label="Ticker", placeholder="MC.PA, AAPL, NVDA")
            with gr.Row():
                quote_out = gr.Textbox(label="Cours (JSON)", lines=12)
                news_out = gr.Textbox(label="Actualités (JSON)", lines=12)
                div_out = gr.Textbox(label="Dividendes (JSON)", lines=12)
            news_limit = gr.Slider(1, 15, value=8, step=1, label="Nb d'articles")
            with gr.Row():
                quote_btn = gr.Button("Cours")
                news_btn = gr.Button("Actualités")
                div_btn = gr.Button("Dividendes")
            quote_btn.click(get_quote, inputs=md_ticker, outputs=quote_out)
            news_btn.click(get_news, inputs=[md_ticker, news_limit], outputs=news_out)
            div_btn.click(get_dividends, inputs=md_ticker, outputs=div_out)

        with gr.Tab("Rechercher"):
            gr.Markdown("### Recherche de symbole Yahoo Finance")
            with gr.Row():
                search_q = gr.Textbox(label="Requête", placeholder="LVMH, NVIDIA, MC.PA")
                search_limit = gr.Slider(1, 15, value=8, step=1, label="Nb de résultats")
            search_out = gr.Textbox(label="Résultat (JSON)", lines=12)
            search_btn = gr.Button("Rechercher")
            search_btn.click(search_ticker, inputs=[search_q, search_limit], outputs=search_out)

        with gr.Tab("Portefeuille Boursobank"):
            gr.Markdown("### Analyse d'un portefeuille (conseils BUY / HOLD / SELL)")
            with gr.Row():
                portfolio_file = gr.File(label="Export CSV Boursobank", file_types=[".csv"])
                style_p_in = gr.Dropdown(choices=STYLES, value="balanced", label="Style")
                benchmark_in = gr.Dropdown(choices=[""] + UNIVERSE_NAMES, value="", label="Univers de référence (optionnel)")
            portfolio_out = gr.Textbox(label="Résultat (JSON)", lines=20)
            portfolio_btn = gr.Button("Analyser le portefeuille")
            portfolio_btn.click(
                analyze_my_portfolio,
                inputs=[portfolio_file, style_p_in, benchmark_in],
                outputs=portfolio_out,
            )

        with gr.Tab("Flux Bankin"):
            gr.Markdown("### Recommandations de placement (PEA, PER, Livret A, SCPI)")
            bankin_file = gr.File(label="Export CSV Bankin", file_types=[".csv"])
            with gr.Row():
                existing_inv = gr.Number(label="Investissements existants", value=0.0)
                emergency = gr.Number(label="Fonds d'urgence existant", value=0.0)
                initial_bal = gr.Number(label="Solde initial", value=0.0)
            bankin_out = gr.Textbox(label="Résultat (JSON)", lines=20)
            bankin_btn = gr.Button("Analyser les flux")
            bankin_btn.click(
                analyze_my_bankin,
                inputs=[bankin_file, existing_inv, emergency, initial_bal],
                outputs=bankin_out,
            )

        with gr.Tab("Méthodologie"):
            gr.Markdown("### Score composite et univers")
            with gr.Row():
                meth_out = gr.Textbox(label="Méthodologie (JSON)", lines=20)
                univ_out = gr.Textbox(label="Univers & styles (JSON)", lines=20)
            with gr.Row():
                meth_btn = gr.Button("Afficher la méthodologie")
                univ_btn = gr.Button("Lister les univers")
            meth_btn.click(methodology, outputs=meth_out)
            univ_btn.click(list_universes, outputs=univ_out)

    return demo


def main() -> None:
    build_demo().launch(theme=gr.themes.Soft(), mcp_server=True)


if __name__ == "__main__":
    main()
