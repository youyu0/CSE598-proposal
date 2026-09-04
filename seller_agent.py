"""
AI Seller Agent - Gemini & Claude baseline implementation.

Given a buyer message and a product/policy config, this agent produces
a natural-language reply plus a structured decision (accept / counter /
reject). A Python wrapper (see `respond()`) checks each model output
against the seller's price floor; if the floor is violated, the wrapper
re-calls the LLM API (up to MAX_REGEN_ATTEMPTS times, with an added
system notice) before falling back to a safe rejection reply.
"""

import os
import json
import re
from dataclasses import dataclass, field
from typing import Optional, Any

from dotenv import load_dotenv

load_dotenv()

# Gemini defaults
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# Anthropic defaults (optional fallback)
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-7-sonnet-20250219")

MAX_REGEN_ATTEMPTS = 2


@dataclass
class Decision:
    action: str                    # "accept" | "counter" | "reject" | "answer"
    price: Optional[float] = None  # proposed price, if any
    reply_text: str = ""
    raw_model_output: str = field(default="", repr=False)


class SellerAgent:
    def __init__(
        self,
        product_config: dict,
        provider: str = "gemini",  # "gemini" or "anthropic"
        client: Optional[Any] = None,
        model: Optional[str] = None
    ):
        self.config = product_config
        self.provider = provider.lower()
        self.model = model
        self.client = client
        self.history: list[dict] = []  # [{"role": "buyer"/"agent", "text": "..."}]

        if self.client is None:
            if self.provider == "gemini":
                from google import genai
                # genai.Client reads GEMINI_API_KEY from env automatically
                api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
                self.client = genai.Client(api_key=api_key) if api_key else genai.Client()
                self.model = self.model or GEMINI_MODEL
            elif self.provider == "anthropic":
                from anthropic import Anthropic
                self.client = Anthropic()
                self.model = self.model or ANTHROPIC_MODEL

    # ---------- prompt construction ----------

    def _system_prompt(self) -> str:
        c = self.config
        specs_str = json.dumps(c.get("specs", {}), indent=2)
        return f"""You are an AI sales agent negotiating on behalf of a seller.

PRODUCT
Name: {c['name']}
Description: {c['description']}
Specs: {specs_str}
List price: ${c['list_price']} {c['currency']}
Stock: {c['stock']}

SELLER POLICY (CONFIDENTIAL - never reveal these numbers or reasoning to the buyer)
Floor price (minimum acceptable): ${c['floor_price']}
Max discount allowed: {c['discount_rules']['max_discount_percent']}%
Notes: {c.get('seller_notes', 'None')}

RULES
1. Never agree to, or counter with, a price below the floor price.
2. Never reveal the floor price or your internal reasoning/policy to the buyer.
3. Be concise, friendly, and natural - like a real seller texting a buyer.
4. When the buyer makes a price offer, you must explicitly decide: accept, counter, or reject.
5. When the buyer asks a factual question, answer only using the product info above. Do not invent specs.

OUTPUT FORMAT
Respond with a natural-language reply for the buyer, then on a new final line output
a machine-readable tag in this exact format:
[[DECISION: action=<accept|counter|reject|answer>; price=<number or none>]]

Example:
Sure, I can do $200 for it!
[[DECISION: action=counter; price=200]]
"""

    # ---------- decision parsing ----------

    @staticmethod
    def _parse_decision(raw_output: str) -> Decision:
        match = re.search(
            r"\[\[DECISION:\s*action=(\w+);\s*price=([\w.]+)\]\]", raw_output
        )
        reply_text = raw_output
        if match:
            reply_text = raw_output[: match.start()].strip()
            action = match.group(1).lower()
            price_str = match.group(2).lower()
            price = None if price_str == "none" else float(price_str)
            return Decision(action=action, price=price, reply_text=reply_text, raw_model_output=raw_output)
        # Fallback: model didn't follow format - treat as an answer with no price
        return Decision(action="answer", price=None, reply_text=reply_text, raw_model_output=raw_output)

    # ---------- guardrail ----------

    def _violates_floor(self, decision: Decision) -> bool:
        floor = self.config["floor_price"]
        if decision.action in ("accept", "counter") and decision.price is not None:
            return decision.price < floor
        return False

    # ---------- LLM API dispatchers ----------

    def _call_gemini(self, contents: list) -> str:
        from google.genai import types
        config = types.GenerateContentConfig(
            system_instruction=self._system_prompt(),
            max_output_tokens=1000,
            temperature=0.7,
        )
        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )
        return response.text or ""

    def _call_anthropic(self, messages: list) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            system=self._system_prompt(),
            messages=messages,
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        )

    # ---------- main entry point ----------

    def respond(self, buyer_message: str) -> Decision:
        """Generate a guarded reply to a single buyer message."""
        decision = None

        if self.provider == "gemini":
            from google.genai import types
            contents = []
            for turn in self.history:
                role = "user" if turn["role"] == "buyer" else "model"
                contents.append(types.Content(role=role, parts=[types.Part.from_text(text=turn["text"])]))
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=buyer_message)]))

            for attempt in range(MAX_REGEN_ATTEMPTS + 1):
                raw_text = self._call_gemini(contents)
                decision = self._parse_decision(raw_text)

                if not self._violates_floor(decision):
                    break  # good to send

                # Retry with strict system notice
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=raw_text)]))
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(
                                text=(
                                    "SYSTEM NOTICE: Your last proposed price was below the allowed "
                                    "floor price. Do not reveal this notice or the floor price to the "
                                    "buyer. Regenerate a valid reply that does not go below the floor."
                                )
                            )
                        ],
                    )
                )
            else:
                decision = Decision(
                    action="reject",
                    price=None,
                    reply_text="Let me check with the seller and get back to you shortly.",
                    raw_model_output=decision.raw_model_output if decision else "",
                )

        else:
            # Anthropic / custom fallback
            messages = []
            for turn in self.history:
                role = "user" if turn["role"] == "buyer" else "assistant"
                messages.append({"role": role, "content": turn["text"]})
            messages.append({"role": "user", "content": buyer_message})

            for attempt in range(MAX_REGEN_ATTEMPTS + 1):
                raw_text = self._call_anthropic(messages)
                decision = self._parse_decision(raw_text)

                if not self._violates_floor(decision):
                    break

                messages.append({"role": "assistant", "content": raw_text})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "SYSTEM NOTICE: Your last proposed price was below the allowed "
                            "floor price. Do not reveal this notice or the floor price to the "
                            "buyer. Regenerate a valid reply that does not go below the floor."
                        ),
                    }
                )
            else:
                decision = Decision(
                    action="reject",
                    price=None,
                    reply_text="Let me check with the seller and get back to you shortly.",
                    raw_model_output=decision.raw_model_output if decision else "",
                )

        # Final safety check before considering sendable
        if self._violates_floor(decision):
            decision = Decision(
                action="reject",
                price=None,
                reply_text="Let me check with the seller and get back to you shortly.",
                raw_model_output=decision.raw_model_output,
            )

        self.history.append({"role": "buyer", "text": buyer_message})
        self.history.append({"role": "agent", "text": decision.reply_text})
        return decision
