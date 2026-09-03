"""
Deterministic pytest suite for the ShopDemo site, built on the actions.py
library. This is the "traditional" automation layer -- fixed steps, fixed
assertions. Contrast this with agent/agent.py, which achieves the same kind
of outcomes but lets an LLM decide the steps dynamically.

Run with (site must already be running on http://127.0.0.1:5000):
    pytest -v --headed          # see the browser
    pytest -v                   # headless
"""
import os
import pytest
from playwright.sync_api import sync_playwright

from actions import login, add_to_cart, remove_from_cart, get_cart_total, checkout, go_to_cart

USERNAME = "admin"
PASSWORD = "admin123"

# Use an already-installed system browser (Edge/Chrome) instead of Playwright's
# own downloaded Chromium -- avoids needing "playwright install chromium" at
# all, which matters on machines without permission to download binaries.
# Set PW_CHANNEL=chrome in the environment if you'd rather use Chrome.
CHANNEL = os.environ.get("PW_CHANNEL", "msedge")


@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=CHANNEL, headless=True)
        pg = browser.new_page()
        yield pg
        browser.close()


def test_login_success(page):
    login(page, USERNAME, PASSWORD)
    assert "/products" in page.url


def test_login_failure(page):
    page.goto("http://127.0.0.1:5000/login")
    page.fill("#username", "admin")
    page.fill("#password", "wrong-password")
    page.click("#login-btn")
    assert "/login" in page.url  # stays on login page


def test_add_to_cart(page):
    login(page, USERNAME, PASSWORD)
    add_to_cart(page, "Wireless Mouse")
    total = get_cart_total(page)
    assert "799" in total


def test_add_multiple_and_remove(page):
    login(page, USERNAME, PASSWORD)
    add_to_cart(page, "Wireless Mouse")
    add_to_cart(page, "Mechanical Keyboard")
    total_before = get_cart_total(page)
    assert "4298" in total_before  # 799 + 3499

    remove_from_cart(page, "Wireless Mouse")
    total_after = get_cart_total(page)
    assert "3499" in total_after


def test_full_checkout_flow(page):
    login(page, USERNAME, PASSWORD)
    add_to_cart(page, "USB-C Hub")
    order_id = checkout(
        page,
        card_name="Test User",
        card_number="4111111111111111",
        expiry="12/28",
        cvv="123",
    )
    assert order_id  # non-empty order id was generated
    assert page.locator("#order-confirmation").is_visible()


def test_empty_cart_redirects_from_checkout(page):
    login(page, USERNAME, PASSWORD)
    page.goto("http://127.0.0.1:5000/checkout")
    assert "/products" in page.url  # redirected because cart is empty
