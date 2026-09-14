from __future__ import annotations

from sqlalchemy import select

from app.db.models import EmploymentEngagement, Person
from tests.helpers import setup_admin
from tests.test_alpha3_operational import _create_asset, _project_group_location


def test_acceptance_story_personnel_material_nodes_maintenance_and_closeout(client, db):
    """Historia de aceptación transversal solicitada para alpha.3.

    No busca cubrir cada validación unitaria (eso vive en otras pruebas), sino
    demostrar que las áreas comparten identidad e historial sin duplicar una
    persona o un activo al cambiar de etapa operacional.
    """
    setup_admin(client)
    project_id, group_id, location_id = _project_group_location(client, "ACC3")

    person = client.post('/api/persons', json={
        'full_name': 'Operador Aceptacion Alpha3', 'employment_id': 'ACC-EMP-01',
        'position': 'Administrador de nodos', 'employer_type': 'OUTSOURCING',
        'provider': 'Proveedor Aceptacion', 'start_date': '2026-09-01', 'project_id': project_id,
    })
    assert person.status_code == 200, person.text
    person_id = person.json()['id']
    assert client.put(f'/api/persons/{person_id}/hr-profile', json={
        'category': 'ADMIN_NODOS_B', 'license_number': 'LIC-ACC-01', 'license_type': 'CONDUCIR',
        'license_expiry': '2027-09-01', 'rotation_on_days': 30, 'rotation_off_days': 15,
    }).status_code == 200
    assert client.post('/api/attendance', json={
        'person_id': person_id, 'attendance_date': '2026-09-11', 'status': 'PRESENT'
    }).status_code == 200

    course = client.post('/api/training/courses', json={'code': 'ACC-HSE', 'name': 'Curso HSE aceptación'})
    assert course.status_code == 200, course.text
    training = client.post('/api/training/records', json={'person_id': person_id, 'course_id': course.json()['id']})
    assert training.status_code == 200, training.text
    assert client.post(f"/api/training/records/{training.json()['id']}/complete").status_code == 200

    unit = _create_asset(client, 'ACC-UNIT-01', 'VEHICLE', 'GENERIC', project_id=project_id, location_id=location_id,
                         identifiers=[{'kind': 'ECONOMIC_NUMBER', 'value': 'ECO-ACC-01', 'is_primary': True}])
    radio = _create_asset(client, 'ACC-RADIO-01', 'RADIO', 'GENERIC', project_id=project_id, location_id=location_id)
    node_good = _create_asset(client, 'ACC-NODE-GOOD', 'NODE', 'SERCEL', project_id=project_id, location_id=location_id)
    node_burned = _create_asset(client, 'ACC-NODE-BURN', 'NODE', 'INOVA', project_id=project_id, location_id=location_id)
    node_seized = _create_asset(client, 'ACC-NODE-SEIZED', 'NODE', 'SERCEL', project_id=project_id, location_id=location_id)

    assert client.post(f'/api/persons/{person_id}/assignments', json={
        'project_id': project_id, 'group_id': group_id, 'location_id': location_id,
        'unit_asset_id': unit, 'role_name': 'Administrador de nodos B',
    }).status_code == 200
    for asset_id in (unit, radio, node_good):
        r = client.post(f'/api/assets/{asset_id}/movements', json={
            'movement_type': 'ASSIGN', 'project_id': project_id, 'group_id': group_id,
            'location_id': location_id, 'responsible_person_id': person_id,
        })
        assert r.status_code == 200, r.text

    for op, stake_from, stake_to in (
        ('TENDIDO', '3001', '3001'), ('ROTACION', '3001', '3051'),
        ('LEVANTADO', '3051', '3051'), ('RETORNO', '3051', '3051'),
    ):
        r = client.post('/api/node-operations', json={
            'operation_type': op, 'project_id': project_id, 'group_id': group_id,
            'location_id': location_id, 'line_code': 'L-ACC', 'participant_person_ids': [person_id],
            'items': [{'asset_id': node_good, 'stake_from': stake_from, 'stake_to': stake_to,
                       'responsible_person_id': person_id, 'result_code': 'OK'}],
        })
        assert r.status_code == 200, r.text

    for asset_id, result in ((node_burned, 'BURNED'), (node_seized, 'SEIZED')):
        r = client.post('/api/node-operations', json={
            'operation_type': 'INCIDENT', 'project_id': project_id, 'location_id': location_id,
            'line_code': 'L-ACC', 'participant_person_ids': [person_id],
            'items': [{'asset_id': asset_id, 'stake_from': '3999', 'responsible_person_id': person_id,
                       'result_code': result}],
        })
        assert r.status_code == 200, r.text

    maint = client.post('/api/maintenance', json={
        'asset_id': node_good, 'priority': 'HIGH', 'symptom': 'Bateria degradada', 'fault_code': 'BAT-ACC'
    })
    assert maint.status_code == 200, maint.text
    assert client.post(f"/api/maintenance/{maint.json()['id']}/parts", json={
        'component_type': 'BATTERY', 'serial_removed': 'BAT-ACC-OLD', 'serial_installed': 'BAT-ACC-NEW', 'quantity': 1
    }).status_code == 200
    assert client.put(f"/api/maintenance/{maint.json()['id']}", json={
        'diagnosis': 'Bateria degradada', 'action_taken': 'Cambio y prueba', 'result': 'PASS',
        'close': True, 'status_after': 'AVAILABLE', 'downtime_minutes': 120,
    }).status_code == 200

    inv = client.post('/api/inventory/sessions', json={
        'name': 'Corte aceptación', 'project_id': project_id, 'location_id': location_id
    })
    assert inv.status_code == 200, inv.text
    inv_id = inv.json()['id']
    for asset_id in (unit, radio, node_good, node_burned):
        assert client.post(f'/api/inventory/sessions/{inv_id}/count', json={
            'asset_id': asset_id, 'found': True, 'location_id': location_id
        }).status_code == 200
    closed_inventory = client.post(f'/api/inventory/sessions/{inv_id}/close')
    assert closed_inventory.status_code == 200, closed_inventory.text
    assert node_seized in {x['asset_id'] for x in closed_inventory.json()['missing']}

    locator = client.get('/api/locate', params={'q': 'ACC-RADIO-01'})
    assert locator.status_code == 200 and locator.json()['assets']
    node_detail = client.get(f'/api/assets/{node_good}').json()
    assert {'TENDIDO', 'ROTACION', 'LEVANTADO', 'RETORNO'} <= {x['movement_type'] for x in node_detail['movements']}

    engagement = db.scalar(select(EmploymentEngagement).where(
        EmploymentEngagement.person_id == person_id, EmploymentEngagement.end_date.is_(None)))
    assert client.post(f'/api/engagements/{engagement.id}/lifecycle', json={
        'event_type': 'RESIGNATION', 'occurred_on': '2026-10-15', 'reason': 'Fin de prueba de aceptación'
    }).status_code == 200
    db.expire_all(); assert db.get(Person, person_id).active is False

    closeout = client.post(f'/api/projects/{project_id}/material-closeout', json={
        'end_date': '2026-10-31', 'note': 'Cierre integral de aceptación alpha.3'
    })
    assert closeout.status_code == 200, closeout.text
    snap = closeout.json()['snapshot']
    assert snap['assets_total'] >= 5
    assert node_burned in {x['asset_id'] for x in snap['critical_assets']}
    assert node_seized in {x['asset_id'] for x in snap['critical_assets']}
