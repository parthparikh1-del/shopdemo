"""
Reusable Playwright action library for the ShopDemo site.

Each function wraps one user-level action (login, add to cart, remove from
cart, checkout) so both the deterministic test suite AND the LLM agent can
call the same, well-tested building blocks.

Usage:
    from playwright.sync_api import sync_playwright
    from actions import login, add_to_cart, remove_from_cart, checkout

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        login(page, "admin", "admin123")
        add_to_cart(page, "Wireless Mouse")
        checkout(page, card_name="Jane Doe", card_number="4111111111111111",
                  expiry="12/28", cvv="123")
        browser.close()
"""
from playwright.sync_api import Page

BASE_URL = "http://127.0.0.1:5000"


def goto_login(page: Page):
    page.goto(f"{BASE_URL}/login")


def login(page: Page, username: str, password: str):
    """Log in and land on the products page."""
    goto_login(page)
    page.fill("#username", username)
    page.fill("#password", password)
    page.click("#login-btn")
    page.wait_for_url(f"{BASE_URL}/products")


def logout(page: Page):
    page.click("#nav-logout")
    page.wait_for_url(f"{BASE_URL}/login")


def add_to_cart(page: Page, product_name: str):
    """Add a product to the cart by its visible name."""
    page.goto(f"{BASE_URL}/products")
    card = page.locator(".product-card", has_text=product_name)
    card.locator(".add-to-cart-btn").click()
    page.wait_for_load_state("networkidle")


def go_to_cart(page: Page):
    page.goto(f"{BASE_URL}/cart")


def remove_from_cart(page: Page, product_name: str):
    """Remove one unit of a product from the cart by its visible name."""
    go_to_cart(page)
    row = page.locator("tr", has_text=product_name)
    row.locator(".remove-btn").click()
    page.wait_for_load_state("networkidle")


def get_cart_total(page: Page) -> str:
    go_to_cart(page)
    total_el = page.locator("#cart-total")
    if total_el.count() == 0:
        return "0"
    return total_el.inner_text()


def checkout(page: Page, card_name: str, card_number: str, expiry: str, cvv: str) -> str:
    """Complete checkout with mock payment details. Returns the order id."""
    page.goto(f"{BASE_URL}/checkout")
    page.fill("#card_name", card_name)
    page.fill("#card_number", card_number)
    page.fill("#expiry", expiry)
    page.fill("#cvv", cvv)
    page.click("#pay-btn")
    page.wait_for_selector("#order-confirmation")
    order_id = page.locator("#order-id").inner_text()
    return order_id
