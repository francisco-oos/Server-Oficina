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
        browser = p.chromium.launch(headless=True, executable_path=BROWSER, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(viewport={"width": 1500, "height": 1050})
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

        # RRHH: alta de persona real desde UI.
        page.locator('nav button[data-view="people"]').click()
        expect(page.locator("#title")).to_have_text("Personal")
        page.locator('#newPerson input[name="full_name"]').fill("Persona Prueba E2E")
        page.locator('#newPerson input[name="employment_id"]').fill("E2E-001")
        page.locator('#newPerson input[name="position"]').fill("Administrador de nodos")
        page.locator('#newPerson input[name="start_date"]').fill("2026-09-11")
        page.locator("#newPerson button").click()
        expect(page.locator("#newPerson .msg")).to_contain_text("Registrado", timeout=10_000)
        expect(page.locator("#personDetail")).to_contain_text("Persona Prueba E2E")

        # Inventario/Asset Core: alta de nodo y tracking básico.
        page.locator('nav button[data-view="assets"]').click()
        expect(page.locator("#title")).to_have_text("Activos y Nodos")
        page.locator('#assetForm select[name="type_code"]').select_option("NODE")
        page.locator('#assetForm select[name="technology_code"]').select_option("SERCEL")
        page.locator('#assetForm input[name="internal_code"]').fill("NODE-E2E-001")
        page.locator('#assetForm input[name="serial_number"]').fill("SN-E2E-001")
        page.locator("#assetForm button").click()
        expect(page.locator("#assetForm .msg")).to_contain_text("Activo registrado", timeout=10_000)
        expect(page.locator("#assetDetail")).to_contain_text("NODE-E2E-001")

        page.locator('nav button[data-view="nodes"]').click()
        expect(page.locator("#title")).to_have_text("Tracking Nodes")
        page.locator('#nodeOp select[name="operation_type"]').select_option("TENDIDO")
        page.locator('#nodeOp select[name="asset_id"]').select_option(label="NODE-E2E-001 · SERCEL")
        page.locator('#nodeOp input[name="line_code"]').fill("L-E2E")
        page.locator('#nodeOp input[name="stake_to"]').fill("1001")
        page.locator("#nodeOp button").click()
        expect(page.locator("#nodeOp .msg")).to_contain_text("Operación registrada", timeout=10_000)
        expect(page.locator("#nodeHistory")).to_contain_text("TENDIDO")

        page.locator("#logout").click()
        expect(page.locator("#login")).to_be_visible(timeout=10_000)
        browser.close()

    print("FRONTEND_E2E_OK")


if __name__ == "__main__":
    main()
