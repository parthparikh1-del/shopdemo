"""
LLM-powered browsing agent for the ShopDemo site.

Unlike automation/test_ecommerce.py (fixed steps, fixed assertions), this
agent is given a GOAL in plain English. On every turn it:
  1. Reads the current page (extracts visible interactive elements)
  2. Sends that state + the goal + history to Claude
  3. Claude replies with ONE next action as JSON (click / fill / navigate / finish)
  4. The agent executes that action with Playwright
  5. Repeat until Claude says "finish" or a step limit is hit

Setup:
    pip install -r requirements.txt
    playwright install chromium
    export ANTHROPIC_API_KEY=sk-ant-...     (Windows PowerShell: $env:ANTHROPIC_API_KEY="sk-ant-...")

Run (site must already be running on http://127.0.0.1:5000):
    python agent.py --goal "Log in as admin/admin123, add a Wireless Mouse and a Mechanical Keyboard to the cart, then remove the Wireless Mouse, then complete checkout with any mock card details."
"""
import argparse
import json
import os
import sys

from playwright.sync_api import sync_playwright, Page
from anthropic import Anthropic

BASE_URL = "http://127.0.0.1:5000"
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
MAX_STEPS = int(os.environ.get("AGENT_MAX_STEPS", "20"))

# Use an already-installed system browser (Edge/Chrome) instead of Playwright's
# own downloaded Chromium -- avoids needing "playwright install chromium" at
# all. Set PW_CHANNEL=chrome in the environment if you'd rather use Chrome.
CHANNEL = os.environ.get("PW_CHANNEL", "msedge")

SYSTEM_PROMPT = """You are a browser automation agent controlling a real web page \
via Playwright. You are given a GOAL, the current page's URL, and a list of \
interactive elements visible on the page (buttons, links, inputs, and forms), \
each with a CSS selector you can act on.

On every turn, choose exactly ONE next action and respond with ONLY a JSON \
object (no prose, no markdown fences) in one of these shapes:

  {"action": "click", "selector": "#some-id", "reason": "why"}
  {"action": "fill", "selector": "#some-id", "value": "text to type", "reason": "why"}
  {"action": "navigate", "url": "http://127.0.0.1:5000/products", "reason": "why"}
  {"action": "finish", "success": true, "reason": "goal achieved, e.g. order id XYZ"}
  {"action": "finish", "success": false, "reason": "why you are stuck"}

Rules:
- Only ever return ONE action per turn.
- Prefer elements that are actually listed in the current page state; do not \
invent selectors that were not shown to you.
- To submit a login form, first fill username and password fields, THEN click \
the login button on a separate turn (one action per turn).
- Payment fields on checkout can contain any mock values (this is a demo site, \
no real payment is processed) -- e.g. card number "4111111111111111", \
expiry "12/28", cvv "123", any name.
- When the goal has been fully completed (e.g. you see an order confirmation \
element), respond with {"action": "finish", "success": true, ...}.
- If you have repeated the same failing action twice, try a different approach \
or finish with success:false and explain why.
"""


def extract_page_state(page: Page) -> dict:
    """Pull a lightweight, LLM-friendly summary of interactive elements."""
    state = page.evaluate(
        """
        () => {
          const out = [];
          const els = document.querySelectorAll(
            'button, a[href], input, select, textarea'
          );
          els.forEach(el => {
            if (el.offsetParent === null && el.tagName !== 'INPUT') return; // skip hidden
            const rect = el.getBoundingClientRect();
            const item = {
              tag: el.tagName.toLowerCase(),
              id: el.id || null,
              text: (el.innerText || el.value || el.placeholder || '').trim().slice(0, 60),
              type: el.type || null,
              name: el.name || null,
            };
            if (item.id || item.text || item.name) out.push(item);
          });
          return out;
        }
        """
    )
    # Build CSS selectors for anything that has an id (preferred, unambiguous)
    elements = []
    for el in state:
        if el["id"]:
            selector = f"#{el['id']}"
        elif el["name"]:
            selector = f"[name='{el['name']}']"
        else:
            continue  # skip elements we can't reliably target
        elements.append(
            {
                "selector": selector,
                "tag": el["tag"],
                "text": el["text"],
                "type": el["type"],
            }
        )
    return {"url": page.url, "elements": elements}


def call_claude(client: Anthropic, goal: str, history: list, page_state: dict) -> dict:
    user_content = (
        f"GOAL: {goal}\n\n"
        f"CURRENT PAGE STATE:\n{json.dumps(page_state, indent=2)}\n\n"
        f"ACTION HISTORY SO FAR:\n{json.dumps(history, indent=2)}\n\n"
        "What is the single next action?"
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"action": "finish", "success": False, "reason": f"Could not parse model output: {text}"}


def run_agent(goal: str, headless: bool = False):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: set the ANTHROPIC_API_KEY environment variable first.")
        sys.exit(1)

    client = Anthropic(api_key=api_key)
    history = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel=CHANNEL, headless=headless)
        page = browser.new_page()
        page.goto(f"{BASE_URL}/login")

        for step in range(1, MAX_STEPS + 1):
            state = extract_page_state(page)
            print(f"\n--- Step {step} | URL: {state['url']} ---")

            decision = call_claude(client, goal, history, state)
            print(f"Agent decision: {decision}")

            action = decision.get("action")

            if action == "finish":
                print(f"\nFINISHED. success={decision.get('success')} reason={decision.get('reason')}")
                break

            try:
                if action == "click":
                    page.click(decision["selector"], timeout=5000)
                elif action == "fill":
                    page.fill(decision["selector"], decision["value"], timeout=5000)
                elif action == "navigate":
                    page.goto(decision["url"])
                else:
                    raise ValueError(f"Unknown action type: {action}")
                page.wait_for_load_state("networkidle", timeout=5000)
                decision["result"] = "ok"
            except Exception as e:
                decision["result"] = f"error: {e}"
                print(f"Action failed: {e}")

            history.append(decision)
        else:
            print("\nStopped: reached MAX_STEPS without finishing.")

        browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Claude-powered ShopDemo agent.")
    parser.add_argument("--goal", required=True, help="Plain-English task for the agent to accomplish.")
    parser.add_argument("--headed", action="store_true", help="Show the browser window (default: headless).")
    args = parser.parse_args()
    run_agent(args.goal, headless=not args.headed)
