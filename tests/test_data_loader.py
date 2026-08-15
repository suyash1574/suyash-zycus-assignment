"""
Unit tests for DataLoader and 90-day ticket historical query engine.
"""

import pytest
from src.data_loader import data_loader


def test_data_loader_initialization():
    tickets = data_loader.get_all_tickets()
    accounts = data_loader.get_all_accounts()
    assert len(tickets) >= 500, f"Expected >= 500 tickets, got {len(tickets)}"
    assert len(accounts) >= 50, f"Expected >= 50 accounts, got {len(accounts)}"


def test_get_account_by_id():
    acc = data_loader.get_account("ACC-4654")
    assert acc is not None
    assert acc["company"] == "Initech"
    assert "arr_usd" in acc
    assert acc["arr_usd"] > 0


def test_get_account_tickets_90d():
    tickets_90d = data_loader.get_account_tickets_90d("ACC-3336")
    assert isinstance(tickets_90d, list)
    assert len(tickets_90d) > 0
    # Verify tickets belong to this account
    for t in tickets_90d:
        assert t["account_id"] == "ACC-3336"


def test_get_nonexistent_account():
    acc = data_loader.get_account("ACC-UNKNOWN-999")
    assert acc is None
    tickets = data_loader.get_account_tickets_90d("ACC-UNKNOWN-999")
    assert tickets == []
