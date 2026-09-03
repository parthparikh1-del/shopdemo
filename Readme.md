# ShopDemo — Local E-commerce + Automation + LLM Agent

A 3-part project for practicing test automation and agentic execution:

1. **`app/`** — A local Flask e-commerce site: login, product catalog, add/remove cart, mock checkout/payment.
2. **`automation/`** — A traditional Playwright + pytest suite: fixed, deterministic steps.
3. **`agent/`** — A Claude-powered agent: given a goal in plain English, it reads the page and decides each click/fill/navigate action itself, dynamically.

All 3 pieces run **locally**. Nothing is deployed anywhere.

---

## 1. Set up the site (`app/`)

```bash
cd app
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
python app.py
```

Visit **http://127.0.0.1:5000**. Test logins:
- `admin` / `admin123`
- `testuser` / `password1`

Leave this running in its own terminal — both automation and the agent talk to it over HTTP.

---

## 2. Run the deterministic automation (`automation/`)

Open a **second terminal**:

```bash
cd automation
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
pytest -v            # headless
pytest -v --headed   # watch the browser do it
```

`actions.py` has small reusable functions (`login`, `add_to_cart`, `remove_from_cart`,
`checkout`, `get_cart_total`) — both the pytest suite and the agent below share these
same building blocks, so you can compare "fixed script" vs "agent-driven" using the
exact same underlying browser actions.

---

## 3. Run the LLM agent (`agent/`)

Open a **third terminal**:

```bash
cd agent
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Set your Anthropic API key (get one at https://console.anthropic.com):

```bash
export ANTHROPIC_API_KEY=sk-ant-...        # macOS/Linux
$env:ANTHROPIC_API_KEY="sk-ant-..."        # Windows PowerShell
```

Then give it a goal in plain English:

```bash
python agent.py --headed --goal "Log in as admin/admin123, add a Wireless Mouse and a Mechanical Keyboard to the cart, remove the Wireless Mouse, then complete checkout with any mock card details."
```

What happens on each step:
1. The agent reads the live page (buttons, links, inputs + their selectors).
2. It sends that state + your goal + the action history so far to Claude.
3. Claude returns ONE next action as JSON: `click`, `fill`, `navigate`, or `finish`.
4. The agent executes that action with Playwright and loops.
5. It stops when Claude reports `finish` (or after `AGENT_MAX_STEPS`, default 20).

Try changing the goal without touching any code, e.g.:
- `"Log in as testuser/password1 and add every product to the cart"`
- `"Log in as admin/admin123, try to check out with an empty cart, and report what happens"`

---

## Project structure

```
shopdemo/
├── app/                    # Flask e-commerce site
│   ├── app.py
│   ├── requirements.txt
│   ├── templates/
│   └── static/style.css
├── automation/              # Deterministic Playwright + pytest suite
│   ├── actions.py            # shared action library
│   ├── test_ecommerce.py
│   └── requirements.txt
├── agent/                   # Claude-powered dynamic agent
│   ├── agent.py
│   └── requirements.txt
└── README.md
```

## Restricted / corporate machine setup (no admin rights, SSL proxy errors)

If `pip install` fails with an **SSL certificate error**, your network likely has a
proxy that intercepts HTTPS. Add trusted-host flags to every pip install command:

```cmd
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org -r requirements.txt
```

If you **don't have permission to download the Playwright browser** (the
`playwright install chromium` step), skip it entirely — `actions.py`,
`test_ecommerce.py`, and `agent.py` are already set up to launch your
**already-installed Edge or Chrome** instead, via Playwright's `channel` option.
Just don't run `playwright install chromium` at all; nothing else changes.

- Uses Edge by default.
- To use Chrome instead, set an environment variable before running:
  ```cmd
  set PW_CHANNEL=chrome
  ```

## Notes
- All "payment" is mock — no real card is charged, no external gateway is called.
- Cart/orders are stored in memory; restarting `app.py` resets all data.
- Element IDs used by both automation layers: `#username`, `#password`, `#login-btn`,
  `#add-to-cart-<id>` (per product), `.remove-btn` (in cart rows), `#checkout-btn`,
  `#card_name`, `#card_number`, `#expiry`, `#cvv`, `#pay-btn`, `#order-id`.
- If you extend the site (new pages, new fields), give new interactive elements
  stable `id` attributes — the agent's `extract_page_state()` targets ids first.
