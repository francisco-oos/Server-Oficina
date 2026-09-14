"""Pruebas de expedientes por dominio y búsqueda transversal.

Cubren los apartados 2, 3, 4 y 10 del encargo. La garantía que estas pruebas
protegen es la que motivó toda la revisión:

    Tracking Core es común por debajo, pero la ficha de una persona, un nodo, un
    activo genérico y una unidad de transporte NO son intercambiables.

Si alguien volviera a unificarlas en una ficha universal, estas pruebas fallan.
"""

from __future__ import annotations

from tests.helpers import setup_admin


def _persona(client, nombre, employment_id, **kw):
    r = client.post('/api/persons', json={
        'full_name': nombre, 'employment_id': employment_id,
        'position': kw.get('position', 'Ayudante'), 'employer_type': kw.get('employer_type', 'DIRECT'),
        'provider': kw.get('provider'), 'start_date': kw.get('start_date', '2026-02-01'),
        'project_id': kw.get('project_id'),
    })
    assert r.status_code == 200, r.text
    return r.json()['id']


def test_person_dossier_keeps_identity_across_rehire(client, db):
    """Persona ≠ contratación: una recontratación conserva el mismo expediente."""
    setup_admin(client)
    persona = _persona(client, 'Martina Ríos Salgado', 'EMP-DOS-1', start_date='2026-01-10')

    detalle = client.get(f'/api/persons/{persona}').json()
    engagement = detalle['engagements'][0]['id']
    baja = client.post(f'/api/engagements/{engagement}/end',
                       json={'end_date': '2026-03-31', 'reason': 'Fin de contrato'})
    assert baja.status_code == 200, baja.text

    recontratacion = client.post(f'/api/persons/{persona}/rehire', json={
        'employment_id': 'EMP-DOS-1-B', 'position': 'Operador', 'employer_type': 'OUTSOURCING',
        'provider': 'Servicios del Norte', 'start_date': '2026-06-01',
    })
    assert recontratacion.status_code == 200, recontratacion.text

    dossier = client.get(f'/api/dossier/person/{persona}')
    assert dossier.status_code == 200, dossier.text
    d = dossier.json()

    # El expediente sigue siendo el mismo person_id.
    assert d['summary']['person_id'] == persona
    # Y muestra las DOS contrataciones, con IDs laborales distintos.
    ids = {e['employment_id'] for e in d['engagements']}
    assert ids == {'EMP-DOS-1', 'EMP-DOS-1-B'}
    vigente = [e for e in d['engagements'] if e['end_date'] is None]
    assert len(vigente) == 1 and vigente[0]['employment_id'] == 'EMP-DOS-1-B'
    cerrada = [e for e in d['engagements'] if e['end_date'] is not None]
    assert len(cerrada) == 1, "La contratación anterior no puede desaparecer del expediente"
    assert d['summary']['estado'] == 'Activo'


def test_person_summary_exposes_localisation_block(client, db):
    """El resumen debe responder los campos que pide el apartado 2 del encargo."""
    setup_admin(client)
    proyecto = client.post('/api/projects', json={'code': 'P-DOS', 'name': 'Proyecto Expedientes'})
    assert proyecto.status_code in (200, 409)
    pid = next(p['id'] for p in client.get('/api/projects').json() if p['code'] == 'P-DOS')
    grupo = client.post('/api/groups', json={'code': 'G-DOS', 'name': 'Cuadrilla Expedientes', 'project_id': pid})
    gid = grupo.json()['id']
    ubicacion = client.post('/api/locations', json={
        'code': 'CAMP-DOS', 'name': 'Campamento Expedientes', 'location_type': 'CAMP', 'project_id': pid})
    lid = ubicacion.json()['id']

    supervisor = _persona(client, 'Supervisora Ana Beltrán', 'EMP-DOS-SUP')
    trabajador = _persona(client, 'Julián Pacheco Ortiz', 'EMP-DOS-2')
    conductor = _persona(client, 'Conductor Esteban Ruiz', 'EMP-DOS-CON')

    unidad = client.post('/api/assets', json={
        'type_code': 'VEHICLE', 'technology_code': 'GENERIC', 'internal_code': 'ECO-770',
        'serial_number': 'VIN-770', 'status_code': 'AVAILABLE', 'identifiers': [],
    }).json()['id']
    radio = client.post('/api/assets', json={
        'type_code': 'RADIO', 'technology_code': 'GENERIC', 'internal_code': 'RAD-770',
        'serial_number': 'SN-RAD-770', 'status_code': 'AVAILABLE', 'identifiers': [],
    }).json()['id']

    client.post(f'/api/transport/units/{unidad}/assignments', json={
        'driver_person_id': conductor, 'group_id': gid, 'project_id': pid,
        'radio_asset_id': radio, 'availability': 'ASSIGNED',
    })
    client.put(f'/api/persons/{trabajador}/hr-profile', json={
        'category': 'Ayudante de línea', 'phone': '555-0101',
        'license_type': 'B', 'license_number': 'LIC-4455', 'license_expiry': '2027-01-31',
        'rotation_on_days': 21, 'rotation_off_days': 7,
    })
    asignacion = client.post(f'/api/persons/{trabajador}/assignments', json={
        'project_id': pid, 'group_id': gid, 'location_id': lid,
        'supervisor_person_id': supervisor, 'unit_asset_id': unidad, 'role_name': 'Ayudante',
    })
    assert asignacion.status_code == 200, asignacion.text

    s = client.get(f'/api/dossier/person/{trabajador}/summary').json()
    assert s['estado'] == 'Activo'
    assert s['grupo'] == 'Cuadrilla Expedientes'
    assert s['responsable'] == 'Supervisora Ana Beltrán'
    assert s['unidad'] == 'ECO-770'
    assert s['conductor'] == 'Conductor Esteban Ruiz'
    assert s['es_conductor'] is False, "Esta persona va en la unidad, no la conduce"
    assert s['radio'] == 'RAD-770'
    assert s['telefono'] == '555-0101'
    assert s['ubicacion'] == 'Campamento Expedientes'
    assert s['proyecto'] == 'Proyecto Expedientes'
    assert s['categoria'] == 'Ayudante de línea'

    # Un campo no capturado se devuelve como None, no como cadena inventada.
    otro = _persona(client, 'Persona Sin Datos', 'EMP-DOS-3')
    vacio = client.get(f'/api/dossier/person/{otro}/summary').json()
    assert vacio['grupo'] is None and vacio['unidad'] is None and vacio['radio'] is None


def test_node_dossier_shows_operational_cycle_not_just_status(client, db):
    """Un nodo no se reduce a un campo ``estado``: su ficha muestra el ciclo."""
    setup_admin(client)
    pid = next((p['id'] for p in client.get('/api/projects').json() if p['code'] == 'P-DOS'), None)
    nodo = client.post('/api/assets', json={
        'type_code': 'NODE', 'technology_code': 'SERCEL', 'internal_code': 'NODO-DOS-1',
        'serial_number': 'SN-NODO-DOS-1', 'status_code': 'AVAILABLE',
        'identifiers': [{'kind': 'QR', 'value': 'QR-NODO-DOS-1'}],
    }).json()['id']
    operador = _persona(client, 'Operador Nodo Díaz', 'EMP-DOS-NODO')

    tendido = client.post('/api/node-operations', json={
        'operation_type': 'TENDIDO', 'project_id': pid, 'line_code': 'L-1200',
        'participant_person_ids': [operador],
        'items': [{'asset_id': nodo, 'stake_from': '1010', 'stake_to': '1010',
                   'responsible_person_id': operador}],
    })
    assert tendido.status_code == 200, tendido.text

    levantado = client.post('/api/node-operations', json={
        'operation_type': 'LEVANTADO', 'project_id': pid, 'line_code': 'L-1200',
        'items': [{'asset_id': nodo, 'stake_from': '1010', 'result_code': 'DAMAGED',
                   'responsible_person_id': operador, 'note': 'Carcasa fracturada'}],
    })
    assert levantado.status_code == 200, levantado.text

    d = client.get(f'/api/dossier/asset/{nodo}').json()
    assert d['kind'] == 'node', "Un activo con capacidad node_field abre la ficha de nodo"

    # El estado actual se presenta junto a su derivación, para poder auditarlo.
    assert d['current_state']['status_code'] == 'DAMAGED'
    assert d['current_state']['derived_from'] is not None
    assert d['current_state']['derived_from']['line_code'] == 'L-1200'
    assert d['current_state']['derived_from']['responsible'] == 'Operador Nodo Díaz'

    # El ciclo operacional completo, no sólo el último estado.
    assert len(d['operations']) == 2
    tipos = {o['operation_type'] for o in d['operations']}
    assert tipos == {'TENDIDO', 'LEVANTADO'}
    assert d['operations'][0]['occurred_at'] >= d['operations'][1]['occurred_at']

    # Las excepciones se separan para que salten a la vista.
    assert len(d['exceptions']) == 1
    assert d['exceptions'][0]['result_code'] == 'DAMAGED'
    assert d['exceptions'][0]['note'] == 'Carcasa fracturada'

    # Secciones propias del dominio de nodo.
    for seccion in ('operations', 'exceptions', 'movements', 'custody', 'maintenance',
                    'health', 'inventory', 'evidence', 'timeline'):
        assert seccion in d, f"La ficha de nodo debe incluir la sección {seccion}"

    # Y la persona responsable ve la excepción reflejada en SU expediente,
    # etiquetada como trazabilidad y no como imputación.
    expediente = client.get(f'/api/dossier/person/{operador}').json()
    assert any(x['asset_id'] == nodo and x['result_code'] == 'DAMAGED'
               for x in expediente['node_exceptions'])


def test_dossier_structures_differ_per_domain(client, db):
    """La prueba que impide volver a una ficha universal."""
    setup_admin(client)
    persona = _persona(client, 'Comparativa Pérez', 'EMP-DOS-CMP')
    nodo = client.post('/api/assets', json={
        'type_code': 'NODE', 'technology_code': 'INOVA', 'internal_code': 'NODO-CMP',
        'serial_number': 'SN-NODO-CMP', 'status_code': 'AVAILABLE', 'identifiers': [],
    }).json()['id']
    radio = client.post('/api/assets', json={
        'type_code': 'RADIO', 'technology_code': 'GENERIC', 'internal_code': 'RAD-CMP',
        'serial_number': 'SN-RAD-CMP', 'status_code': 'AVAILABLE', 'identifiers': [],
    }).json()['id']
    unidad = client.post('/api/assets', json={
        'type_code': 'VEHICLE', 'technology_code': 'GENERIC', 'internal_code': 'ECO-CMP',
        'serial_number': 'VIN-CMP', 'status_code': 'AVAILABLE', 'identifiers': [],
    }).json()['id']

    ficha_persona = client.get(f'/api/dossier/person/{persona}').json()
    ficha_nodo = client.get(f'/api/dossier/asset/{nodo}').json()
    ficha_radio = client.get(f'/api/dossier/asset/{radio}').json()
    ficha_unidad = client.get(f'/api/transport/units/{unidad}').json()

    assert ficha_nodo['kind'] == 'node'
    assert ficha_radio['kind'] == 'asset'
    assert ficha_unidad['kind'] == 'transport-unit'

    # La persona tiene vida laboral; ningún activo la tiene.
    assert 'engagements' in ficha_persona and 'attendance' in ficha_persona
    for ficha in (ficha_nodo, ficha_radio, ficha_unidad):
        assert 'engagements' not in ficha
        assert 'attendance' not in ficha

    # El nodo tiene ciclo operacional; el radio y la unidad NO.
    assert 'operations' in ficha_nodo and 'current_state' in ficha_nodo
    assert 'operations' not in ficha_radio
    assert 'current_state' not in ficha_unidad

    # La unidad tiene conductor y checklist; ni el nodo ni el radio.
    assert 'current_assignment' in ficha_unidad and 'checklists' in ficha_unidad
    assert 'checklists' not in ficha_nodo and 'checklists' not in ficha_radio

    # La persona no tiene custodia propia: tiene activos ENTREGADOS.
    assert 'assets_current' in ficha_persona and 'custody' not in ficha_persona
    assert 'custody' in ficha_radio


def test_cross_search_finds_every_identifier_and_routes_to_the_right_dossier(client, db):
    """Buscar un mismo término debe localizar entidades de dominios distintos."""
    setup_admin(client)
    _persona(client, 'Buscable Nayeli Cruz', 'EMP-778899')
    nodo = client.post('/api/assets', json={
        'type_code': 'NODE', 'technology_code': 'SERCEL', 'internal_code': 'NODO-778899',
        'serial_number': 'SN-778899', 'status_code': 'AVAILABLE',
        'identifiers': [{'kind': 'QR', 'value': 'QR-778899'}],
    }).json()['id']
    telefono = client.post('/api/assets', json={
        'type_code': 'PHONE', 'technology_code': 'GENERIC', 'internal_code': 'TEL-778899',
        'serial_number': 'SNTEL-778899', 'status_code': 'AVAILABLE',
        'identifiers': [{'kind': 'IMEI', 'value': '350000000778899', 'is_primary': True}],
    }).json()['id']
    unidad = client.post('/api/assets', json={
        'type_code': 'VEHICLE', 'technology_code': 'GENERIC', 'internal_code': 'ECO-778899',
        'serial_number': 'VIN-778899', 'status_code': 'AVAILABLE',
        'identifiers': [{'kind': 'ECONOMIC_NUMBER', 'value': 'ECON-778899'}],
    }).json()['id']

    resultado = client.get('/api/search', params={'q': '778899'})
    assert resultado.status_code == 200, resultado.text
    data = resultado.json()
    por_id = {r['id']: r for r in data['results']}

    assert any(r['dossier'] == 'person' for r in data['results']), 'Debe encontrar a la persona por ID laboral'
    assert por_id[nodo]['dossier'] == 'node'
    assert por_id[telefono]['dossier'] == 'asset'
    assert por_id[unidad]['dossier'] == 'transport-unit'
    # Cada resultado explica POR QUÉ coincidió.
    assert all(r['matched_on'] for r in data['results'])

    # Búsqueda por IMEI exacto.
    por_imei = client.get('/api/search', params={'q': '350000000778899'}).json()
    assert any(r['id'] == telefono for r in por_imei['results'])
    assert next(r for r in por_imei['results'] if r['id'] == telefono)['matched_on'] == 'IMEI'

    # Búsqueda por QR.
    por_qr = client.get('/api/search', params={'q': 'QR-778899'}).json()
    assert next(r for r in por_qr['results'] if r['id'] == nodo)['matched_on'] == 'QR'

    # Búsqueda por nombre.
    por_nombre = client.get('/api/search', params={'q': 'Nayeli'}).json()
    assert any(r['dossier'] == 'person' and 'Nayeli' in r['label'] for r in por_nombre['results'])

    # Un término demasiado corto se rechaza en lugar de devolver el padrón.
    assert client.get('/api/search', params={'q': 'a'}).status_code == 422


def test_search_hides_results_the_user_cannot_open(client, db):
    """La búsqueda no ofrece lo que después daría 403, pero avisa de que existe."""
    setup_admin(client)
    client.post('/api/roles', json={
        'name': 'SOLO_PERSONAS', 'description': 'Sólo consulta personal',
        'permissions': ['dashboard.view', 'person.view'],
    })
    client.post('/api/users', json={
        'username': 'solopersonas', 'display_name': 'Solo Personas',
        'password': 'OtraClave123!', 'roles': ['SOLO_PERSONAS'],
    })
    client.post('/api/auth/login', json={'username': 'solopersonas', 'password': 'OtraClave123!'})

    data = client.get('/api/search', params={'q': '778899'}).json()
    assert all(r['dossier'] == 'person' for r in data['results']), \
        'Sin assets.view no deben aparecer activos en los resultados'
    assert data['hidden_by_permissions'] > 0, \
        'El usuario debe saber que hay coincidencias fuera de su alcance'

    setup_admin(client)


def test_asset_dossier_requires_the_permission_of_its_domain(client, db):
    """Abrir la ficha de un nodo exige nodes.view, no sólo assets.view."""
    setup_admin(client)
    nodo = client.post('/api/assets', json={
        'type_code': 'NODE', 'technology_code': 'SERCEL', 'internal_code': 'NODO-PERM',
        'serial_number': 'SN-NODO-PERM', 'status_code': 'AVAILABLE', 'identifiers': [],
    }).json()['id']
    radio = client.post('/api/assets', json={
        'type_code': 'RADIO', 'technology_code': 'GENERIC', 'internal_code': 'RAD-PERM',
        'serial_number': 'SN-RAD-PERM', 'status_code': 'AVAILABLE', 'identifiers': [],
    }).json()['id']

    client.post('/api/roles', json={
        'name': 'MATERIAL_SIN_NODOS', 'description': 'Ve activos pero no tracking de nodos',
        'permissions': ['dashboard.view', 'assets.view'],
    })
    client.post('/api/users', json={
        'username': 'materialsinnodos', 'display_name': 'Material Sin Nodos',
        'password': 'OtraClave123!', 'roles': ['MATERIAL_SIN_NODOS'],
    })
    client.post('/api/auth/login', json={'username': 'materialsinnodos', 'password': 'OtraClave123!'})

    assert client.get(f'/api/dossier/asset/{radio}').status_code == 200
    negado = client.get(f'/api/dossier/asset/{nodo}')
    assert negado.status_code == 403 and 'nodes.view' in negado.json()['detail']

    setup_admin(client)
    assert client.get(f'/api/dossier/asset/{nodo}').status_code == 200


def test_dossier_not_found_returns_404(client, db):
    setup_admin(client)
    assert client.get('/api/dossier/person/no-existe').status_code == 404
    assert client.get('/api/dossier/asset/no-existe').status_code == 404
    assert client.get('/api/transport/units/no-existe').status_code == 404


def test_radio_is_resolved_by_capability_not_by_type_name(client, db):
    """Un tipo nuevo con capacidad ``radio`` debe funcionar sin tocar código.

    Decidir por el código del tipo (``== "RADIO"``) rompería la regla de
    configurabilidad del sistema: una tecnología futura quedaría invisible.
    """
    setup_admin(client)
    creado = client.post('/api/asset-types', json={
        'code': 'RADIO_SATELITAL', 'name': 'Radio satelital',
        'capabilities': ['custody', 'maintenance', 'radio'], 'metadata': {},
    })
    assert creado.status_code in (200, 409), creado.text

    persona = _persona(client, 'Radiooperador Satelital', 'EMP-DOS-SAT')
    radio = client.post('/api/assets', json={
        'type_code': 'RADIO_SATELITAL', 'technology_code': 'GENERIC', 'internal_code': 'SAT-001',
        'serial_number': 'SN-SAT-001', 'status_code': 'AVAILABLE', 'identifiers': [],
    }).json()['id']
    entrega = client.post(f'/api/assets/{radio}/movements', json={
        'movement_type': 'ASSIGN', 'responsible_person_id': persona,
    })
    assert entrega.status_code == 200, entrega.text

    resumen = client.get(f'/api/dossier/person/{persona}/summary').json()
    assert resumen['radio'] == 'SAT-001', \
        'El radio debe resolverse por capacidad del tipo, no por su código'


def test_seeded_asset_types_gain_new_capabilities_on_upgrade(client, db):
    """Actualizar la release debe incorporar capacidades nuevas a tipos existentes.

    Sin esta unión, una instalación creada con una versión anterior tendría el
    tipo RADIO sin la capacidad ``radio`` y el resumen de localización dejaría
    de encontrar los radios entregados.
    """
    from sqlalchemy import select

    from app.db.models import AssetType
    from app.services.bootstrap import ensure_operational_catalogs

    setup_admin(client)
    radio_type = db.scalar(select(AssetType).where(AssetType.code == 'RADIO'))
    assert radio_type is not None

    # Se simula una instalación previa sin la capacidad y con una capacidad
    # añadida por el operador, que NO debe perderse.
    radio_type.capabilities = ['custody', 'maintenance', 'capacidad_del_operador']
    db.commit()

    ensure_operational_catalogs(db)
    db.refresh(radio_type)

    assert 'radio' in radio_type.capabilities, 'La actualización debe incorporar la capacidad nueva'
    assert 'capacidad_del_operador' in radio_type.capabilities, \
        'La siembra no puede borrar capacidades añadidas por el operador'
