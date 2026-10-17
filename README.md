---
title: Screener
emoji: 📈
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: "6.30.0"
app_file: src/screener/server.py
pinned: false
---

# Screener

Application web [Gradio](https://gradio.app) qui s'appuie sur [yfinance](https://github.com/ranaroussi/yfinance) pour classer des valeurs boursières selon un score composite, analyser un portefeuille Boursobank et recommander des placements a partir d'un export Bankin.

> **Avertissement.** Ceci n'est pas un conseil en investissement. Le score agrège du momentum, de la qualité fondamentale, de la croissance, de la valorisation et le consensus analystes Yahoo. Les donnees peuvent être incomplètes, retardées ou erronées. Les performances passées ne préjugent pas des performances futures.

## Outils (onglets Gradio)

| Onglet | Rôle |
| --- | --- |
| `screen_promising` | Top N d'un univers (`cac40`, `sp100`, `nasdaq_mega`) ou d'une liste custom |
| `analyze_ticker` | Score détaillé d'un symbole |
| `compare_tickers` | Classement d'une liste fournie |
| `get_quote` | Cours, variation du jour et fiche courte |
| `get_news` | Dernières actualités Yahoo Finance |
| `get_dividends` | Historique des dividendes passés |
| `search_ticker` | Recherche de symbole Yahoo Finance |
| `list_universes` | Univers et styles disponibles |
| `analyze_my_portfolio` | Analyse d'un portefeuille Boursobank avec conseils achat/vente/conservation |
| `analyze_my_bankin` | Analyse des flux bancaires Bankin avec recommandations de placement (PEA, PER, Livret A) |

Ressource : onglet **Méthodologie** — décrit le score, ses composantes et ses limites.

## Score composite

Chaque titre reçoit un score de 0 à 100 combinant cinq composantes pondérées selon le style choisi.

| Composante | Métriques utilisées |
| --- | --- |
| **Momentum** | Rendements 1 mois, 3 mois, 6 mois et 1 an |
| **Qualité** | ROE, marge nette, marge opérationnelle, dette/capitaux propres |
| **Croissance** | Croissance du chiffre d'affaires et des résultats |
| **Valorisation** | PE (forward prioritaire), PEG, price-to-book |
| **Analystes** | Note moyenne Yahoo (1 = strong buy) et upside vs cours cible |

### Styles de pondération

| Style | Momentum | Qualité | Croissance | Valorisation | Analystes |
| --- | --- | --- | --- | --- | --- |
| `balanced` | 0,30 | 0,25 | 0,20 | 0,15 | 0,10 |
| `momentum` | 0,55 | 0,15 | 0,15 | 0,05 | 0,10 |
| `quality` | 0,15 | 0,40 | 0,15 | 0,20 | 0,10 |
| `growth` | 0,20 | 0,15 | 0,40 | 0,10 | 0,15 |
| `value` | 0,10 | 0,25 | 0,10 | 0,45 | 0,10 |

### Processus de screening

1. Téléchargement des historiques de clôture (1 an) pour tout l'univers.
2. Pré-classement par momentum.
3. Enrichissement fondamental des meilleures valeurs du pré-classement.
4. Score composite selon le style choisi, puis top N.

### Univers prédéfinis

| Univers | Taille | Description |
| --- | --- | --- |
| `cac40` | 40 | CAC 40 (Euronext Paris) |
| `sp100` | 100 | S&P 100 (grandes capitalisations US) |
| `nasdaq_mega` | 48 | Mega-caps Nasdaq |

## Analyse de portefeuille (Boursobank)

L'outil `analyze_my_portfolio` importe vos positions depuis un export CSV Boursobank et délivre des **conseils personnalisés** (BUY / HOLD / SELL) pour chaque position, en croisant :

- Le score composite (momentum, qualité, croissance, valorisation, consensus)
- Votre P&L non réalisé (plus-value ou moins-value)
- Les composantes du score (momentum fort/faible, qualité fondamentale, etc.)

Le résultat inclut pour chaque position : score composite, recommandation, raisonnement détaillé, niveau de confiance et métriques de P&L. Un résumé global du portefeuille (valeur totale, P&L global, répartition des recommandations) est également fourni, avec option de comparaison à un univers de référence.

### Format CSV attendu

Format Boursobank standard, séparateur `;` :

```
name;isin;quantity;buyingPrice;lastPrice;intradayVariation;amount;amountVariation;variation
```

Les nombres au format français (virgule décimale, point pour les milliers) sont pris en charge.

## Analyse des flux bancaires (Bankin)

L'outil `analyze_my_bankin` importe vos transactions depuis un export CSV Bankin et génère des **recommandations de placement personnalisées** (PEA, PER, Livret A, SCPI) basées sur :

- Votre flux net mensuel (revenus - dépenses)
- Votre taux d'épargne
- Votre profil de risque (conservateur, modéré, agressif)
- Vos besoins en fonds d'urgence (4 mois de dépenses)

Les virements internes et doublons (relevé différé, débit mensuel carte) sont automatiquement filtrés.

### Format CSV attendu

Format Bankin standard, séparateur `;` :

```
Date;Description;Compte;Montant;Catégorie;Sous-Catégorie;Note;Pointée
```

### Paramètres optionnels

| Paramètre | Description |
| --- | --- |
| `existing_investments` | Montant déjà investi (pour calculer le plafond PEA restant) |
| `emergency_fund` | Montant déjà sur votre fonds d'urgence (Livret A, etc.) |
| `initial_balance` | Solde initial au début de la période (pour estimation du solde courant) |

## Installation

Python 3.11+ (testé avec 3.13).

```bash
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Lancer l'application

Localement (CPU) :

```bash
.venv/bin/python -m screener
```

L'interface Gradio est servie sur http://127.0.0.1:7860.

# Exemples de requêtes

- « Quelles sont les 8 valeurs les plus prometteuses du CAC 40 en style quality ? »
- « Compare MC.PA, RMS.PA, OR.PA et KER.PA »
- « Analyse NVDA en style growth »
- « Analyse mon portefeuille exports/boursobank/export-positions-20-09-2026.csv »
- « Analyse mes flux bancaires exports/bankin/export_banks_2026-01-01_2026-09-30.csv »

## Tests

```bash
.venv/bin/pytest
```

## Structure du projet

```
src/screener/
├── __main__.py        # Point d'entrée (python -m screener)
├── server.py          # Application Gradio : déclaration des onglets/outils
├── screening.py       # Scoring quantitatif (momentum, qualité, croissance, valorisation, consensus)
├── universes.py       # Univers de tickers prédéfinis (CAC 40, S&P 100, Nasdaq mega)
├── portfolio.py       # Analyse de portefeuille Boursobank et conseils BUY/HOLD/SELL
└── bankin.py          # Analyse des flux bancaires Bankin et recommandations de placement
```
