# AI Seller Agent

An intelligent, guardrailed sales negotiation agent powered by **Google Gemini** (with support for **Anthropic Claude**). 

The agent negotiates with buyers in natural language while strictly enforcing seller pricing policies, protecting confidential floor prices, and outputting both conversational responses and structured machine-readable decisions.

---

## Key Features

- **Multi-Model Support**: Native integration with Google Gemini (`google-genai` SDK) and Anthropic Claude.
- **Strict Price Floor Guardrails**: 
  - Prevents the agent from agreeing to or countering with prices below the confidential `floor_price`.
  - Implements an automated **retry loop** with system notices if the LLM proposes an invalid price.
  - Falls back to a safe rejection response if attempts are exhausted.
- **Confidentiality by Design**: Never discloses internal pricing rules, discount limits, or seller floor prices to buyers.
- **Structured Decision Extraction**: Automatically parses conversational outputs into typed decisions (`accept`, `counter`, `reject`, `answer`) with extracted price points.
- **Multi-Turn Negotiation Context**: Maintains conversation state and history across multiple back-and-forth messages.
- **Comprehensive Verification Suite**: Includes deterministic mock tests for CI/CD and live API testing capabilities.

---

## Project Structure

```text
.
├── config/
│   └── product_001.json      # Sample product specifications and pricing policy
├── outputs/                  # Saved JSON execution outputs
├── .env                      # Environment variables & API keys (do NOT commit)
├── run_agent.py              # Mock test suite & live verification runner
├── run_baseline.py           # CLI runner for file-based batch/single input
├── seller_agent.py           # Core agent implementation and guardrails
└── README.md                 # Project documentation
```

---

## Prerequisites

- **Python 3.10+** (Tested on Python 3.13)
- An active API key from:
  - [Google AI Studio](https://aistudio.google.com/) for Gemini (Default)
  - [Anthropic Console](https://console.anthropic.com/) for Claude (Optional)

---

## Installation

1. **Clone or navigate to the project directory**:
   ```bash
   cd "AI Seller Agent"
   ```

2. **Create and activate a virtual environment (optional but recommended)**:
   ```bash
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install google-genai anthropic python-dotenv
   ```

---

## Environment Setup

Create a `.env` file in the project root directory:

```ini
# Google Gemini Configuration
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.6-flash

# Optional: Anthropic Claude Configuration
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-3-7-sonnet-20250219

# Default Provider ("gemini" or "anthropic")
DEFAULT_PROVIDER=gemini
```

> [!WARNING]
> Never commit your `.env` file or expose your API keys in public repositories. Ensure `.env` is listed in your `.gitignore`.

---

## Usage Guide

### 1. Run Verification & Test Suite

Run the built-in runner to verify mock guardrail behaviors and test live API communication:

```bash
python run_agent.py
```

**What it tests**:
- **Test 1**: Buyer offers below floor price $\rightarrow$ Agent correctly counters above floor.
- **Test 2 (Guardrail Retry)**: Agent initially suggests a price below floor $\rightarrow$ Guardrail detects violation $\rightarrow$ Agent retries and adjusts price above floor.
- **Test 3 (Fallback)**: Agent exhausts retry attempts $\rightarrow$ Safe fallback reject response.
- **Live Test**: Runs a real negotiation turn against the Gemini API if `GEMINI_API_KEY` is configured.

---

### 2. Run Single Input via CLI (`run_baseline.py`)

You can run individual negotiation tests from buyer message text files:

```bash
# 1. Create a buyer message file (e.g. examples/test1.txt)
# "Would you take $200 for it?"

# 2. Execute with product config
python run_baseline.py --input examples/test1.txt --config config/product_001.json --provider gemini
```

**Output**:
- Prints negotiation results in the console.
- Saves structured JSON results to `outputs/<input_name>_output.json`.

---

### 3. Programmatic Python Usage

Integrate the `SellerAgent` directly into your application or service:

```python
import json
from seller_agent import SellerAgent

# Load product configuration
with open("config/product_001.json", "r", encoding="utf-8") as f:
    product_config = json.load(f)

# Initialize agent
agent = SellerAgent(product_config=product_config, provider="gemini")

# Round 1: Buyer asks a question
decision1 = agent.respond("Are the headphones scratch-free?")
print(f"Agent: {decision1.reply_text}")
print(f"Decision: {decision1.action}")

# Round 2: Buyer makes an offer
decision2 = agent.respond("Can you do $210?")
print(f"Agent: {decision2.reply_text}")
print(f"Decision: Action={decision2.action}, Price={decision2.price}")
```

---

## Product & Policy Configuration

Product catalogs and business rules are defined via JSON (e.g. [`config/product_001.json`](config/product_001.json)):

```json
{
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
  "floor_price": 220,
  "discount_rules": {
    "max_discount_percent": 21.4
  },
  "seller_notes": "Firm on floor price. Free shipping included."
}
```

### Configuration Fields

| Field | Type | Description |
|---|---|---|
| `name` | string | Product title |
| `description` | string | General product description |
| `specs` | object | Technical specifications (battery life, condition, color, etc.) |
| `list_price` | number | Public starting list price |
| `floor_price` | number | **Confidential minimum acceptable price** (strictly guarded) |
| `discount_rules` | object | Permitted discount constraints |
| `seller_notes` | string | Internal seller instructions or shipping policies |

---

## Decision Protocol

Every response produces a typed `Decision` dataclass:

```python
@dataclass
class Decision:
    action: str                    # "accept" | "counter" | "reject" | "answer"
    price: Optional[float] = None  # agreed or proposed price (float or None)
    reply_text: str = ""           # user-facing reply text
    raw_model_output: str = ""     # full model generation with metadata tags
```

### Action Types
- `accept`: The agent accepts the buyer's offered price.
- `counter`: The agent proposes a counter-offer above or equal to `floor_price`.
- `reject`: The agent declines the offer or defers to human seller.
- `answer`: The agent answers a factual question without negotiating price.
