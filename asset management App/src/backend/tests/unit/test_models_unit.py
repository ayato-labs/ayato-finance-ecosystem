from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.models import AssetType, Transaction, TransactionType


def test_transaction_validation():
    # Valid transaction
    tx = Transaction(ticker="AAPL", type="BUY", quantity=10, price=150.0)
    assert tx.ticker == "AAPL"
    assert tx.transaction_type == TransactionType.BUY
    assert tx.asset_type == AssetType.STOCK

    # Invalid type
    with pytest.raises(ValidationError):
        Transaction(ticker="AAPL", type="INVALID", quantity=10, price=150.0)

    # Missing required field
    with pytest.raises(ValidationError):
        Transaction(ticker="AAPL")


def test_transaction_alias():
    # Test that 'type' alias works for 'transaction_type'
    data = {
        "ticker": "BTC",
        "type": "BUY",
        "quantity": 1.0,
        "price": 50000.0,
        "asset_type": "CRYPTO",
    }
    tx = Transaction(**data)
    assert tx.transaction_type == TransactionType.BUY

    # Test serialization uses alias 'type'
    dump = tx.model_dump(by_alias=True)
    assert dump["type"] == "BUY"
    assert "transaction_type" not in dump
