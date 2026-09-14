"""Recorrido E2E de navegador sobre la interfaz real.

No sustituye a la suite de backend: comprueba lo que sólo se puede comprobar
dibujando la página —que la navegación por área se construya según permisos,
que cada dominio abra SU ficha y que el modo DEV cambie de verdad la vista
resumen del operador—.

Recorrido:

    primer admin → login → vista resumen configurable → alta de persona →
    expediente de persona → alta de nodo → tendido → ficha de nodo →
    alta de unidad → asignación de conductor → ficha de unidad →
    búsqueda transversal → modo DEV (ocultar/renombrar/guardar) →
    verificación del cambio en la vista resumen → responsive → logout
"""

from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE_URL = os.getenv("SERVER_OFICINA_E2E_URL", "http://127.0.0.1:18081")
BROWSER = os.getenv("SERVER_OFICINA_E2E_BROWSER", "/usr/bin/chromium")

ADMIN_USER = "admin_e2e"
ADMIN_PASSWORD = "E2E-Password-2026!"


def main() -> None:
    if not Path(BROWSER).exists():
        raise SystemExit(f"E2E_BLOCKED: navegador no encontrado: {BROWSER}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, executable_path=BROWSER,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page(viewport={"width": 1500, "height": 1050})

        # Los errores de consola se vigilan: una excepción de JavaScript deja la
        # pantalla a medias sin que ninguna aserción de contenido lo note.
        errores: list[str] = []
        page.on("pageerror", lambda e: errores.append(str(e)))

        page.goto(BASE_URL, wait_until="networkidle")

        # --- Primer administrador y sesión ---------------------------------
        expect(page.locator("#setup")).to_be_visible()
        page.locator('#setupForm input[name="display_name"]').fill("Administrador E2E")
        page.locator('#setupForm input[name="username"]').fill(ADMIN_USER)
        page.locator('#setupForm input[name="password"]').fill(ADMIN_PASSWORD)
        page.locator("#setupForm button").click()
        expect(page.locator("#login")).to_be_visible(timeout=10_000)
        page.locator('#loginForm input[name="username"]').fill(ADMIN_USER)
        page.locator('#loginForm input[name="password"]').fill(ADMIN_PASSWORD)
        page.locator("#loginForm button").click()
        expect(page.locator("#app")).to_be_visible(timeout=10_000)

        # --- Vista resumen configurable ------------------------------------
        expect(page.locator("#title")).to_have_text("Vista resumen general", timeout=10_000)
        expect(page.locator(".widget").first).to_be_visible()
        # La navegación se construyó por permisos, agrupada por área.
        expect(page.locator('.nav-group:has-text("RECURSOS HUMANOS")')).to_be_visible()
        expect(page.locator('.nav-group:has-text("TRANSPORTE")')).to_be_visible()
        expect(page.locator('.nav-group:has-text("TALLER")')).to_be_visible()
        # Existe un selector de dashboards por departamento.
        expect(page.locator('.dashboard-switch .chip')).to_have_count(7)
        page.locator('.dashboard-switch .chip:has-text("Transporte")').click()
        expect(page.locator("#title")).to_contain_text("Transporte", timeout=10_000)

        # --- RRHH: alta de persona y expediente ----------------------------
        page.locator('nav button[data-view="people"]').click()
        expect(page.locator("#title")).to_have_text("Personal", timeout=10_000)
        page.locator('#newPerson input[name="full_name"]').fill("Persona Prueba E2E")
        page.locator('#newPerson input[name="employment_id"]').fill("E2E-001")
        page.locator('#newPerson input[name="position"]').fill("Administrador de nodos")
        page.locator('#newPerson input[name="start_date"]').fill("2026-09-11")
        page.locator("#newPerson button").click()
        # El alta navega directamente al expediente de la persona creada.
        expect(page.locator(".dossier-head h2")).to_have_text("Persona Prueba E2E", timeout=10_000)
        expect(page.locator(".eyebrow").first).to_contain_text("PERSONA")
        # El bloque de localización que exige el encargo está presente.
        localizacion = page.locator('.summary-card:has-text("Localización")')
        expect(localizacion).to_be_visible()
        # Se acota al bloque de localización: etiquetas como "Proyecto" también
        # aparecen en la historia laboral, y sin acotar el selector sería ambiguo.
        for etiqueta in ("Grupo", "Responsable / supervisor", "Unidad", "Conductor",
                         "Radio", "Teléfono", "Ubicación / campamento", "Proyecto"):
            expect(localizacion.locator(f'.field-label:text-is("{etiqueta}")')).to_have_count(1)
        # La ficha de persona tiene historia laboral, no custodia de almacén.
        expect(page.locator('.tab:has-text("Historia laboral")')).to_be_visible()
        expect(page.locator('.tab:has-text("Asistencia")')).to_be_visible()

        # --- Material: alta de nodo ----------------------------------------
        page.locator('nav button[data-view="assets"]').click()
        expect(page.locator("#title")).to_have_text("Activos y material", timeout=10_000)
        page.locator('#assetForm select[name="type_code"]').select_option("NODE")
        page.locator('#assetForm input[name="technology_code"]').fill("SERCEL")
        page.locator('#assetForm input[name="internal_code"]').fill("NODE-E2E-001")
        page.locator('#assetForm input[name="serial_number"]').fill("SN-E2E-001")
        page.locator('#assetForm input[name="qr"]').fill("QR-E2E-001")
        page.locator("#assetForm button").click()
        # Un activo con capacidad node_field abre la FICHA DE NODO, no la genérica.
        expect(page.locator(".dossier-head h2")).to_have_text("NODE-E2E-001", timeout=10_000)
        expect(page.locator('.summary-card:has-text("Situación actual")')).to_be_visible()

        # --- Operación: registrar un TENDIDO --------------------------------
        page.locator('nav button[data-view="nodes"]').click()
        expect(page.locator("#title")).to_have_text("Tracking Nodes", timeout=10_000)
        page.locator('#nodeOp select[name="operation_type"]').select_option("TENDIDO")
        page.locator('#nodeOp select[name="asset_id"]').select_option(label="NODE-E2E-001 · AVAILABLE")
        page.locator('#nodeOp input[name="line_code"]').fill("L-E2E")
        page.locator('#nodeOp input[name="stake_to"]').fill("1001")
        page.locator("#nodeOp button").click()
        expect(page.locator('td:has-text("TENDIDO")').first).to_be_visible(timeout=10_000)

        # La ficha del nodo debe reflejar el ciclo operacional y su derivación.
        page.locator('button.link:has-text("NODE-E2E-001")').first.click()
        expect(page.locator(".dossier-head h2")).to_have_text("NODE-E2E-001", timeout=10_000)
        expect(page.locator('.summary-card:has-text("Situación actual")')).to_contain_text("DEPLOYED")
        expect(page.locator('.summary-card:has-text("Situación actual")')).to_contain_text("L-E2E")
        expect(page.locator('.tab:has-text("Operaciones y lotes")')).to_be_visible()

        # --- Transporte: unidad, conductor y ficha propia -------------------
        page.locator('nav button[data-view="assets"]').click()
        expect(page.locator("#title")).to_have_text("Activos y material", timeout=10_000)
        page.locator('#assetForm select[name="type_code"]').select_option("VEHICLE")
        page.locator('#assetForm input[name="internal_code"]').fill("ECO-E2E-900")
        page.locator('#assetForm input[name="serial_number"]').fill("VIN-E2E-900")
        page.locator("#assetForm button").click()
        # Un activo con capacidad transport abre la FICHA DE UNIDAD.
        expect(page.locator(".dossier-head h2")).to_have_text("ECO-E2E-900", timeout=10_000)
        expect(page.locator('.summary-card:has-text("Asignación vigente")')).to_be_visible()
        page.locator('#assignForm select[name="driver_person_id"]').select_option(label="Persona Prueba E2E · E2E-001")
        page.locator('#assignForm select[name="availability"]').select_option("ASSIGNED")
        page.locator("#assignForm button").click()
        expect(page.locator('.summary-card:has-text("Asignación vigente")')).to_contain_text(
            "Persona Prueba E2E", timeout=10_000)

        # El listado de flota resuelve el vínculo unidad ↔ conductor.
        page.locator('nav button[data-view="transport"]').click()
        expect(page.locator("#title")).to_have_text("Unidades de transporte", timeout=10_000)
        expect(page.locator('td:has-text("Persona Prueba E2E")').first).to_be_visible()

        # --- Búsqueda transversal -------------------------------------------
        page.locator("#globalSearchInput").fill("E2E-001")
        page.locator("#globalSearch button").click()
        expect(page.locator("#title")).to_have_text("Resultados de búsqueda", timeout=10_000)
        expect(page.locator('.result:has-text("Persona Prueba E2E")')).to_be_visible()

        page.locator("#globalSearchInput").fill("QR-E2E-001")
        page.locator("#globalSearch button").click()
        # El QR localiza el nodo y la respuesta explica por qué coincidió.
        expect(page.locator('.result:has-text("NODE-E2E-001")')).to_be_visible(timeout=10_000)
        expect(page.locator('.result:has-text("NODE-E2E-001")')).to_contain_text("QR")
        # Y al pulsarlo abre la ficha de NODO, no una ficha universal.
        page.locator('.result:has-text("NODE-E2E-001")').click()
        expect(page.locator('.summary-card:has-text("Situación actual")')).to_be_visible(timeout=10_000)

        # --- Modo DEV: la vista resumen deja de estar hardcodeada -----------
        page.locator('nav button[data-view="devDashboard"]').click()
        expect(page.locator("#title")).to_have_text("Modo DEV · Vista resumen", timeout=10_000)
        page.locator('.dashboard-switch .chip:has-text("Vista resumen general")').click()
        expect(page.locator(".dev-row").first).to_be_visible(timeout=10_000)

        # Se renombra el primer widget y se oculta otro; luego se guarda.
        fila_personal = page.locator('.dev-row:has-text("Personal activo")')
        expect(fila_personal).to_be_visible()
        fila_personal.locator('input[data-title]').fill("Plantilla vigente E2E")
        page.locator('.dev-row:has-text("Activos registrados") input[data-visible]').uncheck()
        page.locator("#devSave").click()
        expect(page.locator("#devMsg")).to_contain_text("Composición guardada", timeout=10_000)

        # El operador ve el cambio inmediatamente en su vista resumen.
        page.locator('nav button[data-view="resumen"]').click()
        expect(page.locator("#title")).to_have_text("Vista resumen general", timeout=10_000)
        expect(page.locator('.widget h3:text-is("Plantilla vigente E2E")')).to_be_visible()
        expect(page.locator('.widget h3:text-is("Activos registrados")')).to_have_count(0)

        # --- Responsive ------------------------------------------------------
        page.set_viewport_size({"width": 390, "height": 844})
        expect(page.locator("#menuToggle")).to_be_visible()
        page.locator("#menuToggle").click()
        expect(page.locator("#sidebar")).to_have_class(__import__("re").compile(r"open"))
        page.locator('nav button[data-view="people"]').click()
        expect(page.locator("#title")).to_have_text("Personal", timeout=10_000)
        # Al navegar, el panel se cierra solo: en teléfono no debe tapar el contenido.
        expect(page.locator("#scrim")).to_be_hidden()
        # La página no debe desbordarse horizontalmente en 390 px.
        desborde = page.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        assert desborde <= 1, f"La interfaz desborda horizontalmente en 390px: {desborde}px"
        page.set_viewport_size({"width": 1500, "height": 1050})

        # --- Cierre de sesión -----------------------------------------------
        page.locator("#logout").click()
        expect(page.locator("#login")).to_be_visible(timeout=10_000)

        if errores:
            raise SystemExit("E2E_FAIL: errores de JavaScript en consola:\n  " + "\n  ".join(errores))
        browser.close()

    print("FRONTEND_E2E_OK")


if __name__ == "__main__":
    main()
