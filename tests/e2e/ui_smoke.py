from __future__ import annotations

import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE_URL = os.getenv("SERVER_OFICINA_E2E_URL", "http://127.0.0.1:18081")
BROWSER = os.getenv("SERVER_OFICINA_E2E_BROWSER", "/usr/bin/chromium")


def main() -> None:
    if not Path(BROWSER).exists():
        raise SystemExit(f"E2E_BLOCKED: navegador no encontrado: {BROWSER}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=BROWSER,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(BASE_URL, wait_until="networkidle")

        expect(page.locator("#setup")).to_be_visible()
        page.locator('#setupForm input[name="display_name"]').fill("Administrador E2E")
        page.locator('#setupForm input[name="username"]').fill("admin_e2e")
        page.locator('#setupForm input[name="password"]').fill("E2E-Password-2026!")
        page.locator("#setupForm button").click()

        expect(page.locator("#login")).to_be_visible(timeout=10_000)
        page.locator('#loginForm input[name="username"]').fill("admin_e2e")
        page.locator('#loginForm input[name="password"]').fill("E2E-Password-2026!")
        page.locator("#loginForm button").click()

        expect(page.locator("#app")).to_be_visible(timeout=10_000)
        expect(page.locator("#title")).to_have_text("Dashboard de Oficina")
        expect(page.locator("text=Personal activo")).to_be_visible()

        page.locator('nav button[data-view="people"]').click()
        expect(page.locator("#title")).to_have_text("Personal")
        expect(page.locator("#newPerson")).to_be_visible()

        page.locator('#newPerson input[name="full_name"]').fill("Persona Prueba E2E")
        page.locator('#newPerson input[name="employment_id"]').fill("E2E-001")
        page.locator('#newPerson input[name="position"]').fill("Prueba QA")
        page.locator('#newPerson input[name="start_date"]').fill("2026-09-11")
        page.locator("#newPerson button").click()

        expect(page.locator("#newPerson .msg")).to_contain_text("Registrado", timeout=10_000)
        expect(page.locator("#personDetail")).to_contain_text("Persona Prueba E2E")
        expect(page.locator("#personDetail")).to_contain_text("E2E-001")

        page.locator("#logout").click()
        expect(page.locator("#login")).to_be_visible(timeout=10_000)
        browser.close()

    print("FRONTEND_E2E_OK")


if __name__ == "__main__":
    main()
