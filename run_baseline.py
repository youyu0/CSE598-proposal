"""
Entry point for the AI Seller Agent baseline (supports Gemini and Claude).

Usage:
    python run_baseline.py --input examples/test1.txt --config config/product_001.json
    python run_baseline.py --input examples/test1.txt --config config/product_001.json --provider gemini
"""

import argparse
import json
import os
from dataclasses import asdict

from seller_agent import SellerAgent


def main():
    parser = argparse.ArgumentParser(description="Run the AI Seller Agent baseline.")
    parser.add_argument("--input", required=True, help="Path to buyer message .txt file")
    parser.add_argument("--config", required=True, help="Path to product/policy .json config")
    parser.add_argument(
        "--provider",
        choices=["gemini", "anthropic"],
        default=os.getenv("DEFAULT_PROVIDER", "gemini"),
        help="LLM provider: 'gemini' (default) or 'anthropic'"
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Where to write the JSON output (default: outputs/<input_name>_output.json)",
    )
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        buyer_message = f.read().strip()

    with open(args.config, "r", encoding="utf-8") as f:
        product_config = json.load(f)

    agent = SellerAgent(product_config, provider=args.provider)
    decision = agent.respond(buyer_message)

    result = {
        "buyer_message": buyer_message,
        "product": product_config["name"],
        "floor_price": product_config["floor_price"],
        "agent_reply": decision.reply_text,
        "decision_action": decision.action,
        "decision_price": decision.price,
        "provider": args.provider,
    }

    print("=" * 60)
    print(f"PROVIDER: {args.provider.upper()}")
    print(f"BUYER:    {buyer_message}")
    print(f"AGENT:    {decision.reply_text}")
    print(f"DECISION: action={decision.action}, price={decision.price}")
    print("=" * 60)

    out_path = args.output
    if out_path is None:
        os.makedirs("outputs", exist_ok=True)
        base_name = os.path.splitext(os.path.basename(args.input))[0]
        out_path = os.path.join("outputs", f"{base_name}_output.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"Saved output to {out_path}")


if __name__ == "__main__":
    main()
