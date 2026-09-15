"""Regresiones de la revisión OpenAI R1 sobre Server Oficina alpha.4."""
from pathlib import Path

from tests.helpers import setup_admin


def _person(client, name: str, employment_id: str) -> str:
    response = client.post("/api/persons", json={
        "full_name": name,
        "employment_id": employment_id,
        "position": "Operador",
        "employer_type": "DIRECT",
        "start_date": "2026-09-01",
    })
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _asset(client, code: str, type_code: str, technology: str = "GENERIC") -> str:
    response = client.post("/api/assets", json={
        "type_code": type_code,
        "technology_code": technology,
        "internal_code": code,
        "serial_number": f"SN-{code}",
        "status_code": "AVAILABLE",
        "identifiers": [],
    })
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_transport_assignment_validates_radio_and_phone_capabilities(client, db):
    setup_admin(client)
    unit = _asset(client, "UNIT-OAI-R1", "VEHICLE")
    node = _asset(client, "NODE-OAI-R1", "NODE", "SERCEL")
    computer = _asset(client, "PC-OAI-R1", "COMPUTER")

    wrong_radio = client.post(
        f"/api/transport/units/{unit}/assignments",
        json={"radio_asset_id": node, "availability": "ASSIGNED"},
    )
    assert wrong_radio.status_code == 422
    assert "radio" in wrong_radio.json()["detail"].lower()

    wrong_phone = client.post(
        f"/api/transport/units/{unit}/assignments",
        json={"phone_asset_id": computer, "availability": "ASSIGNED"},
    )
    assert wrong_phone.status_code == 422
    assert "phone" in wrong_phone.json()["detail"].lower() or \
           "teléfono" in wrong_phone.json()["detail"].lower()

    for code, name, capability in (
        ("RADIO_SAT_OAI", "Radio satelital OAI", "radio"),
        ("TERMINAL_OAI", "Terminal de campo OAI", "phone"),
    ):
        created = client.post("/api/asset-types", json={
            "code": code,
            "name": name,
            "capabilities": ["custody", capability],
            "metadata": {},
        })
        assert created.status_code in (200, 409), created.text

    sat_radio = _asset(client, "SAT-RAD-OAI", "RADIO_SAT_OAI")
    field_phone = _asset(client, "PHONE-OAI", "TERMINAL_OAI")

    valid = client.post(
        f"/api/transport/units/{unit}/assignments",
        json={
            "radio_asset_id": sat_radio,
            "phone_asset_id": field_phone,
            "availability": "ASSIGNED",
        },
    )
    assert valid.status_code == 200, valid.text


def test_person_summary_driver_flag_uses_identity_not_name(client, db):
    setup_admin(client)
    passenger = _person(client, "José Operador Homónimo", "OAI-HOMO-01")
    actual_driver = _person(client, "José Operador Homónimo", "OAI-HOMO-02")
    unit = _asset(client, "UNIT-HOMO-OAI", "VEHICLE")

    assigned_person = client.post(
        f"/api/persons/{passenger}/assignments",
        json={"unit_asset_id": unit, "role_name": "Operador trasladado"},
    )
    assert assigned_person.status_code == 200, assigned_person.text

    transport = client.post(
        f"/api/transport/units/{unit}/assignments",
        json={"driver_person_id": actual_driver, "availability": "ASSIGNED"},
    )
    assert transport.status_code == 200, transport.text

    summary = client.get(f"/api/dossier/person/{passenger}/summary")
    assert summary.status_code == 200, summary.text
    payload = summary.json()
    assert payload["conductor"] == "José Operador Homónimo"
    assert payload["es_conductor"] is False


def test_nodes_view_without_assets_view_can_open_node_found_by_search(client, db):
    setup_admin(client)
    node = _asset(client, "NODE-PERM-OAI", "NODE", "SERCEL")
    generic = _asset(client, "RAD-PERM-OAI", "RADIO")

    role = client.post("/api/roles", json={
        "name": "SOLO_NODOS_OAI",
        "description": "Consulta nodos sin Asset Core genérico",
        "permissions": ["dashboard.view", "nodes.view"],
    })
    assert role.status_code in (200, 409), role.text

    user = client.post("/api/users", json={
        "username": "solonodosoai",
        "display_name": "Sólo Nodos OAI",
        "password": "OtraClave123!",
        "roles": ["SOLO_NODOS_OAI"],
    })
    assert user.status_code in (200, 409), user.text

    login = client.post("/api/auth/login", json={
        "username": "solonodosoai",
        "password": "OtraClave123!",
    })
    assert login.status_code == 200, login.text

    search = client.get("/api/search", params={"q": "NODE-PERM-OAI"})
    assert search.status_code == 200, search.text
    assert any(row["id"] == node for row in search.json()["results"])

    opened = client.get(f"/api/dossier/asset/{node}")
    assert opened.status_code == 200

    generic_denied = client.get(f"/api/dossier/asset/{generic}")
    assert generic_denied.status_code == 403
    setup_admin(client)


def test_admin_management_extension_is_loaded_and_uses_existing_safe_endpoints():
    index = Path("app/static/index.html").read_text(encoding="utf-8")
    script = Path("app/static/admin-management.js").read_text(encoding="utf-8")
    assert "/static/admin-management.css" in index
    assert "/static/admin-management.js" in index
    assert "VIEWS.roles = rolesAdminEnhanced" in script
    assert "VIEWS.users = usersAdminEnhanced" in script
    assert "/api/users/" in script
    assert "method: 'PUT'" in script
