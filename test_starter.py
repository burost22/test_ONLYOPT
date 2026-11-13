import asyncio
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock

from starter import recommend_price, sample_fetch_offers


class RecommendPriceTests(unittest.IsolatedAsyncioTestCase):
    def assert_result(self, result, price, decision):
        self.assertEqual(set(result), {"price", "decision", "reason"})
        self.assertIsInstance(result["price"], Decimal)
        self.assertEqual(result["price"], Decimal(price))
        self.assertEqual(result["decision"], decision)
        self.assertIsInstance(result["reason"], str)
        self.assertTrue(result["reason"].strip())

    def make_source(self, price, status="success"):
        return AsyncMock(return_value={
            "status": status,
            "offers": [
                {"seller": "PARTS", "price": Decimal(price), "delivery_days": 6}
            ],
        })

    async def test_sample(self):
        result = await recommend_price(
            sample_fetch_offers, Decimal("4900.00"), Decimal("4500.00")
        )
        self.assert_result(result, "4728.00", "APPLY")

    async def test_source_exception(self):
        source = AsyncMock(side_effect=RuntimeError("Source unavailable"))
        result = await recommend_price(source, Decimal("100.00"), Decimal("120.00"))
        self.assert_result(result, "100.00", "HOLD")

    async def test_source_timeout(self):
        async def slow_source():
            await asyncio.sleep(60)
            return {"status": "success", "offers": []}

        result = await recommend_price(
            slow_source, Decimal("100.00"), Decimal("120.00"), timeout_s=0.01
        )
        self.assert_result(result, "100.00", "HOLD")

    async def test_unsuccessful_status(self):
        for status in ("partial", "error"):
            with self.subTest(status=status):
                result = await recommend_price(
                    self.make_source("150.00", status),
                    Decimal("100.00"),
                    Decimal("120.00"),
                )
                self.assert_result(result, "100.00", "HOLD")

    async def test_empty_offers_preserve_price_below_minimum(self):
        source = AsyncMock(return_value={"status": "success", "offers": []})
        result = await recommend_price(source, Decimal("100.00"), Decimal("120.00"))
        self.assert_result(result, "100.00", "HOLD")

    async def test_ineligible_offers(self):
        for seller, delivery_days in (
            ("MYSHOP", 2),
            ("myshop", 2),
            ("MyShOp", 2),
            ("PARTS", None),
            ("PARTS", 7),
        ):
            with self.subTest(seller=seller, delivery_days=delivery_days):
                source = AsyncMock(return_value={
                    "status": "success",
                    "offers": [{
                        "seller": seller,
                        "price": Decimal("110.00"),
                        "delivery_days": delivery_days,
                    }],
                })
                result = await recommend_price(
                    source, Decimal("100.00"), Decimal("120.00")
                )
                self.assert_result(result, "100.00", "HOLD")

    async def test_lowest_eligible_price_and_rounding_down(self):
        source = AsyncMock(return_value={
            "status": "success",
            "offers": [
                {"seller": "PARTS", "price": Decimal("110.00"), "delivery_days": 6},
                {"seller": "OTHER", "price": Decimal("100.01"), "delivery_days": 0},
            ],
        })
        result = await recommend_price(source, Decimal("100.00"), Decimal("90.00"))
        self.assert_result(result, "98.50", "APPLY")

    async def test_minimum_price(self):
        result = await recommend_price(
            self.make_source("100.00"), Decimal("100.00"), Decimal("105.00")
        )
        self.assert_result(result, "105.00", "APPLY")

    async def test_change_threshold_in_both_directions(self):
        for current_price, min_price, expected_price, decision in (
            ("197.00", "1.00", "137.90", "APPLY"),
            ("197.01", "1.00", "137.90", "REVIEW"),
            ("197.00", "256.10", "256.10", "APPLY"),
            ("197.00", "256.11", "256.11", "REVIEW"),
        ):
            with self.subTest(current_price=current_price, min_price=min_price):
                result = await recommend_price(
                    self.make_source("140.00"),
                    Decimal(current_price),
                    Decimal(min_price),
                )
                self.assert_result(result, expected_price, decision)


if __name__ == "__main__":
    unittest.main()
