"""Read-only SQL helper for the latest portfolio-construction backtest snapshot."""

from __future__ import annotations

from quantis.db.engine import session_scope
from quantis.db.models import PortfolioSnapshot


def latest_portfolio() -> dict | None:
    with session_scope() as session:
        row = session.query(PortfolioSnapshot).order_by(PortfolioSnapshot.id.desc()).first()
    if row is None:
        return None
    return {
        "period_start": row.period_start.isoformat() if row.period_start else None,
        "period_end": row.period_end.isoformat() if row.period_end else None,
        "trading_days": row.trading_days,
        "total_return": float(row.total_return),
        "cagr": float(row.cagr),
        "ann_vol": float(row.ann_vol),
        "sharpe": float(row.sharpe),
        "max_drawdown": float(row.max_drawdown),
        "avg_names_long": float(row.avg_names_long),
        "avg_exposure": float(row.avg_exposure),
        "annualized_turnover": float(row.annualized_turnover),
        "max_sector_weight": float(row.max_sector_weight) if row.max_sector_weight else None,
        "reallocated": row.reallocated,
        "vol_target": float(row.vol_target) if row.vol_target else None,
        "avg_leverage": float(row.avg_leverage),
        "computed_at": row.computed_at.isoformat() if row.computed_at else None,
    }
