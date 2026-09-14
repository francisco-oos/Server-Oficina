"""Pruebas del dominio de Transporte.

Cubre el apartado 5 del encargo. Las garantías centrales que se verifican:

* una unidad es un activo del Asset Core con capacidad ``transport``: no hay un
  registro paralelo de vehículos;
* reasignar NO sobrescribe la asignación anterior, la cierra con fecha;
* reportar una incidencia y resolverla son actos de áreas distintas;
* un checklist con falla no inmoviliza la unidad automáticamente.
"""

from __future__ import annotations

from tests.helpers import setup_admin


def _crear_unidad(client, code, tipo='VEHICLE'):
    r = client.post('/api/assets', json={
        'type_code': tipo, 'technology_code': 'GENERIC', 'internal_code': code,
        'serial_number': f'VIN-{code}', 'status_code': 'AVAILABLE',
        'identifiers': [{'kind': 'ECONOMIC_NUMBER', 'value': f'ECO-{code}', 'is_primary': True}],
    })
    assert r.status_code == 200, r.text
    return r.json()['id']


def _crear_persona(client, nombre, employment_id):
    r = client.post('/api/persons', json={
        'full_name': nombre, 'employment_id': employment_id, 'position': 'Conductor',
        'employer_type': 'DIRECT', 'start_date': '2026-01-15',
    })
    assert r.status_code == 200, r.text
    return r.json()['id']


def test_unit_must_declare_transport_capability(client, db):
    """La comprobación es por capacidad del tipo, no por su nombre."""
    setup_admin(client)
    nodo = client.post('/api/assets', json={
        'type_code': 'NODE', 'technology_code': 'SERCEL', 'internal_code': 'NODO-TR-1',
        'serial_number': 'SN-NODO-TR-1', 'status_code': 'AVAILABLE', 'identifiers': [],
    })
    assert nodo.status_code == 200
    nodo_id = nodo.json()['id']

    rechazo = client.post(f'/api/transport/units/{nodo_id}/assignments', json={'availability': 'ASSIGNED'})
    assert rechazo.status_code == 422
    assert 'transport' in rechazo.json()['detail']

    # Un tipo NUEVO con la capacidad correcta debe funcionar sin tocar código.
    creado = client.post('/api/asset-types', json={
        'code': 'PICKUP_4X4', 'name': 'Pick-up 4x4',
        'capabilities': ['transport', 'custody', 'maintenance'], 'metadata': {},
    })
    assert creado.status_code in (200, 409), creado.text
    pickup = _crear_unidad(client, 'PU-001', tipo='PICKUP_4X4')
    ok = client.post(f'/api/transport/units/{pickup}/assignments', json={'availability': 'AVAILABLE'})
    assert ok.status_code == 200, ok.text


def test_assignment_closes_previous_without_overwriting_history(client, db):
    """Estado actual ≠ historial: quién conducía antes sigue siendo consultable."""
    setup_admin(client)
    unidad = _crear_unidad(client, 'UN-100')
    primero = _crear_persona(client, 'Conductor Primero', 'EMP-TR-100')
    segundo = _crear_persona(client, 'Conductor Segundo', 'EMP-TR-101')

    r1 = client.post(f'/api/transport/units/{unidad}/assignments', json={
        'driver_person_id': primero, 'availability': 'ASSIGNED', 'note': 'Asignación inicial',
    })
    assert r1.status_code == 200, r1.text

    r2 = client.post(f'/api/transport/units/{unidad}/assignments', json={
        'driver_person_id': segundo, 'availability': 'ASSIGNED', 'note': 'Relevo de conductor',
    })
    assert r2.status_code == 200, r2.text

    ficha = client.get(f'/api/transport/units/{unidad}').json()
    assert ficha['current_assignment']['driver'] == 'Conductor Segundo'
    assert len(ficha['assignments']) == 2

    anteriores = [a for a in ficha['assignments'] if not a['current']]
    assert len(anteriores) == 1
    assert anteriores[0]['driver'] == 'Conductor Primero', "La asignación previa no puede perderse"
    assert anteriores[0]['end_at'] is not None, "La asignación previa debe cerrarse con fecha"


def test_unit_links_radio_and_phone_from_asset_core(client, db):
    """Radio y teléfono se referencian del Asset Core, no se duplican."""
    setup_admin(client)
    unidad = _crear_unidad(client, 'UN-200')
    radio = client.post('/api/assets', json={
        'type_code': 'RADIO', 'technology_code': 'GENERIC', 'internal_code': 'RAD-200',
        'serial_number': 'SN-RAD-200', 'status_code': 'AVAILABLE', 'identifiers': [],
    }).json()['id']
    telefono = client.post('/api/assets', json={
        'type_code': 'PHONE', 'technology_code': 'GENERIC', 'internal_code': 'TEL-200',
        'serial_number': 'SN-TEL-200', 'status_code': 'AVAILABLE',
        'identifiers': [{'kind': 'IMEI', 'value': '350000000000200', 'is_primary': True}],
    }).json()['id']
    conductor = _crear_persona(client, 'Conductor Radio', 'EMP-TR-200')

    r = client.post(f'/api/transport/units/{unidad}/assignments', json={
        'driver_person_id': conductor, 'radio_asset_id': radio, 'phone_asset_id': telefono,
        'availability': 'ASSIGNED',
    })
    assert r.status_code == 200, r.text

    ficha = client.get(f'/api/transport/units/{unidad}').json()
    assert ficha['current_assignment']['radio'] == 'RAD-200'
    assert ficha['current_assignment']['phone'] == 'TEL-200'

    # El listado de flota resuelve el vínculo para que la pantalla sea usable.
    flota = client.get('/api/transport/units').json()
    fila = next(u for u in flota if u['id'] == unidad)
    assert fila['driver'] == 'Conductor Radio'
    assert fila['radio'] == 'RAD-200' and fila['phone'] == 'TEL-200'

    # El radio sigue siendo un activo propio, con su ficha y su identidad.
    radio_ficha = client.get(f'/api/dossier/asset/{radio}').json()
    assert radio_ficha['kind'] == 'asset'
    assert radio_ficha['header']['internal_code'] == 'RAD-200'


def test_checklist_with_failure_does_not_immobilize_unit(client, db):
    """Un hallazgo se registra; la disponibilidad la decide Transporte."""
    setup_admin(client)
    unidad = _crear_unidad(client, 'UN-300')
    client.post(f'/api/transport/units/{unidad}/assignments', json={'availability': 'AVAILABLE'})

    r = client.post(f'/api/transport/units/{unidad}/checklists', json={
        'result': 'FAIL', 'odometer_km': 148230, 'fuel_level': '1/4',
        'items': [
            {'code': 'LLANTAS', 'label': 'Llantas', 'ok': False, 'note': 'Refacción sin aire'},
            {'code': 'LUCES', 'label': 'Luces', 'ok': True},
        ],
        'note': 'Revisión de salida',
    })
    assert r.status_code == 200, r.text

    ficha = client.get(f'/api/transport/units/{unidad}').json()
    assert ficha['current_assignment']['availability'] == 'AVAILABLE', \
        "Un checklist con falla no cambia la disponibilidad por sí solo"
    assert ficha['checklists'][0]['result'] == 'FAIL'
    hallazgos = [i for i in ficha['checklists'][0]['items'] if not i['ok']]
    assert len(hallazgos) == 1 and hallazgos[0]['code'] == 'LLANTAS'
    # occurred_at y recorded_at se conservan por separado.
    assert ficha['checklists'][0]['occurred_at'] and ficha['checklists'][0]['recorded_at']

    invalido = client.post(f'/api/transport/units/{unidad}/checklists', json={'result': 'QUIZA'})
    assert invalido.status_code == 422


def test_incident_reported_by_any_area_resolved_by_transport(client, db):
    """Proponer ≠ confirmar, aplicado al dominio de Transporte."""
    setup_admin(client)
    unidad = _crear_unidad(client, 'UN-400')

    # Perfil que puede reportar (cases.create) pero no administrar transporte.
    client.post('/api/roles', json={
        'name': 'OBSERVADOR_CAMPO', 'description': 'Puede reportar, no resolver',
        'permissions': ['dashboard.view', 'cases.create', 'transport.view'],
    })
    client.post('/api/users', json={
        'username': 'observador', 'display_name': 'Observador', 'password': 'OtraClave123!',
        'roles': ['OBSERVADOR_CAMPO'],
    })

    client.post('/api/auth/login', json={'username': 'observador', 'password': 'OtraClave123!'})
    reporte = client.post(f'/api/transport/units/{unidad}/incidents', json={
        'incident_type': 'PONCHADURA', 'severity': 'NORMAL',
        'summary': 'Llanta trasera derecha ponchada en el kilómetro 12',
    })
    assert reporte.status_code == 200, reporte.text
    incidencia = reporte.json()['id']
    assert reporte.json()['status'] == 'OPEN'

    # El mismo perfil NO puede resolverla: no es autoridad del dominio.
    negado = client.post(f'/api/transport/incidents/{incidencia}/resolve',
                         json={'resolution': 'Ya quedó'})
    assert negado.status_code == 403
    assert 'transport.manage' in negado.json()['detail']

    setup_admin(client)
    resuelto = client.post(f'/api/transport/incidents/{incidencia}/resolve', json={
        'resolution': 'Llanta reparada y refacción repuesta',
    })
    assert resuelto.status_code == 200 and resuelto.json()['status'] == 'RESOLVED'

    # Resolver dos veces no debe permitirse.
    repetido = client.post(f'/api/transport/incidents/{incidencia}/resolve', json={'resolution': 'otra vez'})
    assert repetido.status_code == 409

    ficha = client.get(f'/api/transport/units/{unidad}').json()
    assert ficha['incidents'][0]['status'] == 'RESOLVED'
    assert 'refacción' in ficha['incidents'][0]['resolution']


def test_incident_link_to_workshop_order_is_validated(client, db):
    """Enlazar una incidencia a una orden no la convierte en esa orden."""
    setup_admin(client)
    unidad = _crear_unidad(client, 'UN-500')
    otra_unidad = _crear_unidad(client, 'UN-501')

    incidencia = client.post(f'/api/transport/units/{unidad}/incidents', json={
        'incident_type': 'FALLA_MOTOR', 'severity': 'HIGH', 'summary': 'Sobrecalentamiento',
    }).json()['id']

    orden_otra = client.post('/api/maintenance', json={
        'asset_id': otra_unidad, 'symptom': 'Orden de otra unidad', 'priority': 'NORMAL',
    }).json()['id']
    cruzado = client.post(f'/api/transport/incidents/{incidencia}/resolve', json={
        'resolution': 'Enviada a taller', 'maintenance_order_id': orden_otra,
    })
    assert cruzado.status_code == 422, "No debe aceptarse una orden de otro activo"

    orden = client.post('/api/maintenance', json={
        'asset_id': unidad, 'symptom': 'Sobrecalentamiento reportado', 'priority': 'HIGH',
    }).json()['id']
    ok = client.post(f'/api/transport/incidents/{incidencia}/resolve', json={
        'resolution': 'Enviada a taller para diagnóstico', 'maintenance_order_id': orden,
    })
    assert ok.status_code == 200, ok.text

    ficha = client.get(f'/api/transport/units/{unidad}').json()
    assert ficha['incidents'][0]['maintenance_order_id'] == orden
    # La orden existe como hecho separado, con su propia historia.
    assert any(o['id'] == orden for o in ficha['maintenance'])


def test_transport_permissions_are_enforced(client, db):
    setup_admin(client)
    unidad = _crear_unidad(client, 'UN-600')
    client.post('/api/roles', json={
        'name': 'SIN_TRANSPORTE', 'description': 'No consulta transporte',
        'permissions': ['dashboard.view', 'assets.view'],
    })
    client.post('/api/users', json={
        'username': 'sintransporte', 'display_name': 'Sin Transporte', 'password': 'OtraClave123!',
        'roles': ['SIN_TRANSPORTE'],
    })
    client.post('/api/auth/login', json={'username': 'sintransporte', 'password': 'OtraClave123!'})
    assert client.get('/api/transport/units').status_code == 403
    assert client.get(f'/api/transport/units/{unidad}').status_code == 403
    assert client.post(f'/api/transport/units/{unidad}/assignments', json={}).status_code == 403
    setup_admin(client)
