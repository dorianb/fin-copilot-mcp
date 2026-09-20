from screener.screening import composite_score, score_growth, score_momentum, score_quality, score_valuation


def test_momentum_rewards_positive_returns():
    strong = score_momentum(0.08, 0.15, 0.25, 0.40)
    weak = score_momentum(-0.08, -0.15, -0.20, -0.30)
    assert strong > weak
    assert 0 <= strong <= 100
    assert 0 <= weak <= 100


def test_quality_penalizes_high_leverage():
    healthy = score_quality(0.25, 0.18, 0.22, 30)
    leveraged = score_quality(0.25, 0.18, 0.22, 250)
    assert healthy > leveraged


def test_growth_and_valuation_bounds():
    assert 0 <= score_growth(0.4, 0.5) <= 100
    cheap = score_valuation(12, 11, 0.8, 1.5)
    expensive = score_valuation(90, 85, 4.0, 20)
    assert cheap > expensive


def test_composite_style_changes_ranking():
    quality_stock = {
        "momentum": 40.0,
        "quality": 90.0,
        "growth": 50.0,
        "valuation": 80.0,
        "analyst": 60.0,
    }
    momentum_stock = {
        "momentum": 95.0,
        "quality": 40.0,
        "growth": 50.0,
        "valuation": 40.0,
        "analyst": 55.0,
    }
    assert composite_score(quality_stock, "quality") > composite_score(momentum_stock, "quality")
    assert composite_score(momentum_stock, "momentum") > composite_score(quality_stock, "momentum")
