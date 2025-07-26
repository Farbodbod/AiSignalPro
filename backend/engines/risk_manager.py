"""
advanced_risk_manager.py

ماژول مدیریت ریسک پیشرفته و افسانه‌ای:
- پوزیشن سایزینگ دقیق با ATR، ریسک درصدی و لوریج
- استراتژی Long/Short، Compound/Fix Risk، و ریسک داینامیک
- ابزارهای: Kelly، Sharpe، Sortino، Max Drawdown، CVaR، Expectancy
- مدیریت چند پوزیشن با ماتریس کوواریانس و همبستگی
- اتصال به مدل ML برای بهینه‌سازی ریسک
Author: farbodbod1990
"""

import math
import numpy as np
from typing import List, Dict, Any, Optional

# -------------------- پایه‌ای --------------------
def calc_position_size(balance: float, risk_pct: float, entry: float, stop: float, leverage: float = 1.0) -> float:
    risk_amount = balance * risk_pct
    risk_per_unit = abs(entry - stop)
    if risk_per_unit == 0:
        return 0
    return (risk_amount / risk_per_unit) * leverage

def calc_risk_reward(entry: float, stop: float, target: float) -> float:
    risk = abs(entry - stop)
    reward = abs(target - entry)
    return reward / risk if risk != 0 else float('inf')

def kelly_criterion(win_rate: float, win_loss_ratio: float) -> float:
    return max(0, win_rate - (1 - win_rate) / win_loss_ratio) if win_loss_ratio != 0 else 0

def max_drawdown(equity_curve: List[float]) -> float:
    peak = equity_curve[0]
    max_dd = 0
    for x in equity_curve:
        peak = max(peak, x)
        dd = (peak - x) / peak
        max_dd = max(max_dd, dd)
    return max_dd

# -------------------- پیشرفته --------------------
def atr_based_position_size(balance: float, risk_pct: float, atr: float, leverage: float = 1.0) -> float:
    risk_amount = balance * risk_pct
    if atr == 0:
        return 0
    return (risk_amount / atr) * leverage

def sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
    mean_return = np.mean(returns)
    std_dev = np.std(returns)
    return (mean_return - risk_free_rate) / std_dev if std_dev != 0 else 0

def sortino_ratio(returns: List[float], target: float = 0.0) -> float:
    downside = [r for r in returns if r < target]
    std_dev = np.std(downside) if downside else 1e-9
    mean_return = np.mean(returns)
    return (mean_return - target) / std_dev

def expectancy(win_rate: float, avg_win: float, avg_loss: float) -> float:
    return (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

def value_at_risk(returns: List[float], confidence_level: float = 0.95) -> float:
    return np.percentile(returns, (1 - confidence_level) * 100)

def conditional_var(returns: List[float], confidence_level: float = 0.95) -> float:
    var = value_at_risk(returns, confidence_level)
    tail_losses = [r for r in returns if r <= var]
    return np.mean(tail_losses) if tail_losses else var

# -------------------- پرتفوی و چند پوزیشن --------------------
def correlation_matrix(returns_dict: Dict[str, List[float]]) -> np.ndarray:
    return np.corrcoef([returns_dict[k] for k in returns_dict])

def portfolio_var(weights: List[float], cov_matrix: np.ndarray) -> float:
    weights_np = np.array(weights)
    return float(np.sqrt(weights_np.T @ cov_matrix @ weights_np))

def multi_position_risk(positions: List[Dict[str, float]], balance: float) -> float:
    total_risk = 0
    for p in positions:
        size = calc_position_size(balance, p['risk_pct'], p['entry'], p['stop'], p.get('leverage', 1.0))
        total_risk += size * abs(p['entry'] - p['stop'])
    return total_risk

# -------------------- مدیریت هوشمند و داینامیک --------------------
def dynamic_risk_adjustment(volatility: float, base_risk: float = 0.01, max_risk: float = 0.03) -> float:
    scaled = base_risk * (1.0 / (volatility + 1e-6))
    return min(scaled, max_risk)

def compound_balance(balance: float, returns: List[float]) -> float:
    for r in returns:
        balance *= (1 + r)
    return balance

# -------------------- اتصال به مدل یادگیری ماشین --------------------
def ml_optimized_risk_adjustment(features: Dict[str, Any], model: Any) -> float:
    """
    مدل ML باید خروجی ریسک پیشنهادی (risk_pct) را برگرداند.
    """
    X = np.array([features[k] for k in sorted(features.keys())]).reshape(1, -1)
    predicted_risk = model.predict(X)[0]
    return max(0.001, min(predicted_risk, 0.05))  # محدود به 0.1 تا 5٪

# -------------------- آنالیز جامع --------------------
def advanced_risk_analysis(balance: float,
                           entry: float,
                           stop: float,
                           targets: List[float],
                           risk_pct: float,
                           leverage: float = 1.0,
                           win_rate: float = 0.5,
                           atr: Optional[float] = None,
                           ml_model: Optional[Any] = None,
                           ml_features: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    results = {}
    if ml_model and ml_features:
        risk_pct = ml_optimized_risk_adjustment(ml_features, ml_model)

    for target in targets:
        size = atr_based_position_size(balance, risk_pct, atr, leverage) if atr else calc_position_size(balance, risk_pct, entry, stop, leverage)
        rr = calc_risk_reward(entry, stop, target)
        kelly = kelly_criterion(win_rate, rr)
        results[target] = {
            'position_size': size,
            'risk_reward': rr,
            'kelly_fraction': kelly
        }
    return results
