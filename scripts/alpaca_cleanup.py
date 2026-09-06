"""Inspect and (optionally) clean up the Alpaca PAPER account.

Safety: this ALWAYS uses the paper endpoint (`paper=True`), so it can never act on a
live account even if a live key were supplied.

Usage:
    uv run python scripts/alpaca_cleanup.py            # report only, changes nothing
    uv run python scripts/alpaca_cleanup.py --execute  # cancel all orders + close all positions
"""

from __future__ import annotations

import argparse

from quantis.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Cancel all open orders and close all positions (otherwise report only).",
    )
    args = parser.parse_args()

    s = get_settings()
    if not (s.alpaca_api_key and s.alpaca_secret_key):
        print("No ALPACA_API_KEY / ALPACA_SECRET_KEY in .env — add them first.")
        return 1

    from alpaca.trading.client import TradingClient

    # paper=True forces the paper endpoint — never touches a live account.
    client = TradingClient(s.alpaca_api_key, s.alpaca_secret_key, paper=True)

    acct = client.get_account()
    masked = f"****{str(acct.account_number)[-4:]}"
    print("Alpaca PAPER account")
    print("-" * 48)
    print(f"  account     {masked}")
    print(f"  status      {acct.status}")
    print(f"  cash        ${float(acct.cash):,.2f}")
    print(f"  equity      ${float(acct.equity):,.2f}")
    print(f"  buying_pwr  ${float(acct.buying_power):,.2f}")

    orders = client.get_orders()
    positions = client.get_all_positions()
    print(f"\n  open orders   {len(orders)}")
    for o in orders[:20]:
        print(f"    {o.side.value:<4} {o.qty} {o.symbol:<6} {o.type.value} [{o.status.value}]")
    print(f"  open positions {len(positions)}")
    for p in positions[:40]:
        print(
            f"    {p.side.value:<5} {p.qty:>8} {p.symbol:<6} "
            f"mv=${float(p.market_value):>12,.2f}  uPnL=${float(p.unrealized_pl):>10,.2f}"
        )

    if not args.execute:
        print("\n(report only — pass --execute to cancel orders and close positions)")
        return 0

    if not orders and not positions:
        print("\nNothing to clean up — account already flat.")
        return 0

    print("\nExecuting cleanup on the PAPER account...")
    if orders:
        client.cancel_orders()
        print(f"  cancelled {len(orders)} open order(s)")
    if positions:
        client.close_all_positions(cancel_orders=True)
        print(f"  submitted close for {len(positions)} position(s)")
    print("Done. Re-run without --execute to confirm the account is flat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
