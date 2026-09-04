"""
Runner and Test Suite for AI Seller Agent (Gemini & Claude).
Supports Mock verification and Live API execution.
"""

import os
import sys
from unittest.mock import MagicMock
from seller_agent import SellerAgent, Decision

SAMPLE_PRODUCT = {
    "name": "Sony WH-1000XM5 Wireless Headphones",
    "description": "Premium noise-canceling wireless over-ear headphones, lightly used, mint condition with original box.",
    "specs": {
        "color": "Black",
        "battery_life": "30 hours",
        "connectivity": "Bluetooth 5.2 / 3.5mm jack",
        "condition": "Like New"
    },
    "list_price": 280,
    "currency": "USD",
    "stock": 1,
    "floor_price": 220,  # Cannot sell below $220
    "discount_rules": {
        "max_discount_percent": 21.4
    },
    "seller_notes": "Firm on floor price. Free shipping included."
}


class MockGeminiResponse:
    def __init__(self, text: str):
        self.text = text


class MockGeminiClient:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.call_history = []
        self.models = MagicMock()
        self.models.generate_content = self._generate_content

    def _generate_content(self, **kwargs):
        self.call_history.append(kwargs)
        if self.responses:
            return MockGeminiResponse(self.responses.pop(0))
        return MockGeminiResponse("Thank you for your interest.\n[[DECISION: action=answer; price=none]]")


def run_gemini_mock_tests():
    print("=" * 60)
    print(">>> Running Gemini Mock Verification Tests <<<")
    print("=" * 60)

    # Test 1: Counter Offer (Above Floor Price)
    print("\n[Test 1] Buyer offers $200 (Below floor $220) -> Gemini counters at $240")
    mock_client_1 = MockGeminiClient([
        "I can't do $200, but I could meet you at $240 with free shipping!\n[[DECISION: action=counter; price=240]]"
    ])
    agent_1 = SellerAgent(product_config=SAMPLE_PRODUCT, provider="gemini", client=mock_client_1)
    d1 = agent_1.respond("Would you take $200?")
    print(f"Agent Reply: {d1.reply_text}")
    print(f"Decision: Action={d1.action}, Price=${d1.price}")
    assert d1.action == "counter" and d1.price == 240.0
    print("[PASS] Test 1 passed.")

    # Test 2: Guardrail Retry (Floor price enforcement)
    print("\n[Test 2] Gemini Guardrail Retry: Proposes $190 first, retries with $230")
    mock_client_2 = MockGeminiClient([
        "Sure, I can do $190!\n[[DECISION: action=accept; price=190]]",
        "Sorry about that. The best I can offer is $230.\n[[DECISION: action=counter; price=230]]"
    ])
    agent_2 = SellerAgent(product_config=SAMPLE_PRODUCT, provider="gemini", client=mock_client_2)
    d2 = agent_2.respond("Can I buy this for $190?")
    print(f"Agent Reply: {d2.reply_text}")
    print(f"Decision: Action={d2.action}, Price=${d2.price}")
    print(f"API calls made: {len(mock_client_2.call_history)}")
    assert d2.action == "counter" and d2.price == 230.0 and len(mock_client_2.call_history) == 2
    print("[PASS] Test 2 passed.")

    # Test 3: Exhausted Retries Fallback
    print("\n[Test 3] Exhausted Retries Fallback")
    mock_client_3 = MockGeminiClient([
        "Sure, $180!\n[[DECISION: action=accept; price=180]]",
        "How about $185?\n[[DECISION: action=accept; price=185]]",
        "Fine, $190.\n[[DECISION: action=accept; price=190]]"
    ])
    agent_3 = SellerAgent(product_config=SAMPLE_PRODUCT, provider="gemini", client=mock_client_3)
    d3 = agent_3.respond("Can you do $180?")
    print(f"Agent Reply: {d3.reply_text}")
    print(f"Decision: Action={d3.action}, Price=${d3.price}")
    assert d3.action == "reject"
    print("[PASS] Test 3 passed.")

    print("\n" + "=" * 60)
    print("ALL GEMINI MOCK TESTS PASSED SUCCESSFULLY! (3/3)")
    print("=" * 60)


def run_live():
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if gemini_key:
        print("\n>>> Detected GEMINI_API_KEY! Running live Gemini test... <<<")
        agent = SellerAgent(product_config=SAMPLE_PRODUCT, provider="gemini")
        buyer_msg = "Can you do $230 for the headphones?"
        print(f"[Buyer]: {buyer_msg}")
        dec = agent.respond(buyer_msg)
        print(f"[Agent]: {dec.reply_text}")
        print(f"[Decision]: Action={dec.action}, Price={dec.price}")
    elif anthropic_key:
        print("\n>>> Detected ANTHROPIC_API_KEY! Running live Claude test... <<<")
        agent = SellerAgent(product_config=SAMPLE_PRODUCT, provider="anthropic")
        buyer_msg = "Can you do $230 for the headphones?"
        print(f"[Buyer]: {buyer_msg}")
        dec = agent.respond(buyer_msg)
        print(f"[Agent]: {dec.reply_text}")
        print(f"[Decision]: Action={dec.action}, Price={dec.price}")
    else:
        print("\n[Notice] Neither GEMINI_API_KEY nor ANTHROPIC_API_KEY is set.")
        print("To run with live API, set GEMINI_API_KEY in .env file.")


if __name__ == "__main__":
    run_gemini_mock_tests()
    run_live()
