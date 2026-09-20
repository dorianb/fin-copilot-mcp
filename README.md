# Screener

Serveur MCP (Model Context Protocol) qui s'appuie sur [yfinance](https://github.com/ranaroussi/yfinance) pour classer des valeurs boursières selon un score composite.

Ce n'est **pas** un conseil en investissement. Le score agrège du momentum, de la qualité fondamentale, de la croissance, de la valorisation et le consensus analystes Yahoo. Les données peuvent être incomplètes ou retardées.

## Outils MCP

| Outil | Rôle |
| --- | --- |
| `screen_promising` | Top N d'un univers (`cac40`, `sp100`, `nasdaq_mega`) ou d'une liste custom |
| `analyze_ticker` | Score détaillé d'un symbole |
| `compare_tickers` | Classement d'une liste fournie |
| `get_quote` | Cours et fiche courte |
| `get_news` | Actualités Yahoo |
| `search_ticker` | Recherche de symbole |
| `list_universes` | Univers et styles disponibles |
| `analyze_my_portfolio` | **Analyse de portefeuille Boursobank avec conseils achat/vente/conservation** |
| `analyze_my_bankin` | **Analyse des flux bancaires Bankin avec recommandations de placement (PEA, PER, Livret A)** |

Styles de pondération : `balanced`, `momentum`, `quality`, `growth`, `value`.

Ressource : `screener://methodology`.

## Analyse de portefeuille

L'outil `analyze_my_portfolio` permet d'importer vos positions depuis un export CSV Boursobank et de recevoir des **conseils personnalisés** (ACHAT / CONSERVATION / VENTE) basés sur :

- **Le score composite** (momentum, qualité, croissance, valorisation, consensus analystes)
- **Votre P&L non réalisé** (plus-value ou moins-value)
- **Les composantes du score** (momentum fort/faible, qualité fondamentale, etc.)

### Format du CSV attendu
Le fichier doit contenir les colonnes suivantes (format Boursobank standard) :
```
name;isin;quantity;buyingPrice;lastPrice;intradayVariation;amount;amountVariation;variation
```

### Exemple de résultat
Pour chaque position, vous obtiendrez :
- Score composite (0-100)
- Recommandation (BUY / HOLD / SELL)
- Raisonnement détaillé
- Niveau de confiance
- Métriques de P&L

## Analyse Bankin

L'outil `analyze_my_bankin` permet d'importer vos transactions depuis un export CSV Bankin et de recevoir des **recommandations de placement personnalisées** (PEA, PER, Livret A) basées sur :

- **Votre flux net mensuel** (revenus - dépenses)
- **Votre taux d'épargne**
- **Votre profil de risque** (conservateur, modéré, agressif)
- **Vos besoins en fonds d'urgence**

### Format du CSV attendu
Le fichier doit contenir les colonnes suivantes (format Bankin standard) :
```
Date;Description;Compte;Montant;Catégorie;Sous-Catégorie;Note;Pointée
```

### Recommandations proposées
- **Fonds d'urgence** (Livret A) : Priorité absolue si pas de liquidités de sécurité
- **PEA** (Plan d'Épargne en Actions) : Pour investir en actions européennes avec avantages fiscaux
- **PER** (Plan d'Épargne Retraite) : Pour préparer sa retraite avec réductions d'impôt
- **SCPI** : Pour diversification immobilière
- **Conseils spécifiques** selon votre situation financière

## Installation

Python 3.11+ (le projet est testé avec 3.13).

```bash
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Lancer le serveur

stdio (c'est ce que Cursor utilise) :

```bash
.venv/bin/python -m screener
```

## Brancher dans Cursor

Le fichier `.cursor/mcp.json` pointe déjà vers l'interpréteur du `.venv`. Dans Cursor : Settings → MCP, puis activer le serveur **screener**. Relancer MCP si le venv vient d'être créé.

Ensuite, dans le chat :

- « Quelles sont les 8 valeurs les plus prometteuses du CAC 40 en style quality ? »
- « Compare MC.PA, RMS.PA, OR.PA et KER.PA »
- « Analyse NVDA en style growth »
- **« Analyse mon portefeuille exports/boursobank/export-positions-20-09-2026.csv »**
- **« Analyse mes flux bancaires exports/bankin/export_banks_2026-01-01_2026-09-30.csv »**

## Tests

```bash
.venv/bin/pytest
```
