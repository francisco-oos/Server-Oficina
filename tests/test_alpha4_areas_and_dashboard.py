"""Pruebas de áreas, autoridad del dato y vista resumen configurable.

Cubren los apartados 7, 9 y 11 del encargo. El énfasis está en las garantías
que NO deben romperse nunca:

* la configuración del dashboard puede restringir, jamás ampliar privilegios;
* un widget roto no deja al operador sin vista resumen;
* la siembra de arranque no pisa lo que el administrador configuró.
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.areas import AREAS, DATA_DOMAINS, authority_matrix
from app.core.rbac import PERMISSIONS
from app.db.models import DashboardDefinition, DashboardWidgetPlacement
from app.services import widgets as widget_registry
from app.services import dashboards as dashboard_service
from tests.helpers import setup_admin


def _login(client, username, password):
    r = client.post('/api/auth/login', json={'username': username, 'password': password})
    assert r.status_code == 200, r.text


def _create_user(client, username, role_names, password='OtraClave123!'):
    """Crea un usuario con perfiles concretos, reutilizándolo si ya existe."""
    r = client.post('/api/users', json={
        'username': username, 'display_name': username.title(),
        'password': password, 'roles': role_names,
    })
    assert r.status_code in (200, 409), r.text
    return username, password


def test_widget_registry_is_coherent():
    """El catálogo de widgets debe ser consistente con RBAC y con las áreas.

    Es una prueba de integridad del registro: un widget que declare un permiso
    inexistente nunca se mostraría, y uno con un área desconocida rompería la
    navegación por departamento. Vale más detectarlo aquí que en producción.
    """
    assert widget_registry.REGISTRY, "El registro de widgets no puede estar vacío"
    for key, definition in widget_registry.REGISTRY.items():
        assert definition.key == key
        assert definition.permission in PERMISSIONS, f"{key} declara un permiso inexistente"
        assert definition.area in AREAS, f"{key} declara un área desconocida"
        assert definition.default_size in widget_registry.SIZES
        assert definition.description, f"{key} debe documentar qué responde"
        assert callable(definition.resolver)

    # Debe haber al menos un widget por área operativa: si un área no tiene
    # ninguno, su vista resumen nace vacía y no sirve para nada.
    areas_con_widget = {w.area for w in widget_registry.REGISTRY.values()}
    for code in AREAS:
        assert code in areas_con_widget, f"El área {code} no tiene ningún widget"


def test_authority_matrix_is_declared_for_every_domain():
    """Cada dominio declara autoridad y ésta debe ser un área real."""
    matrix = authority_matrix()
    assert len(matrix) == len(DATA_DOMAINS)
    for domain in matrix:
        assert domain["authority"] in AREAS
        assert domain["confirm"], f"{domain['code']} debe declarar quién confirma"
        for area in domain["consult"] + domain["propose"] + domain["confirm"]:
            assert area in AREAS, f"{domain['code']} referencia un área inexistente: {area}"
        # El área autoridad no necesita aparecer en 'consult': consultar su propio
        # dato es implícito. Lo que sí debe cumplirse es que pueda confirmarlo.
        assert domain["authority"] in domain["confirm"]


def test_dashboards_are_seeded_per_area(client, db):
    setup_admin(client)
    rows = client.get('/api/dashboards')
    assert rows.status_code == 200, rows.text
    keys = {d['key'] for d in rows.json()}
    assert 'general' in keys
    for code in AREAS:
        if code == 'GENERAL':
            continue
        assert code.lower() in keys, f"Falta la vista resumen del área {code}"

    payload = client.get('/api/dashboards/general').json()
    assert payload['dashboard']['key'] == 'general'
    assert payload['widgets'], "El dashboard general se siembra con widgets"
    # Todos deben resolver sin error: un widget que lance excepción se aísla,
    # pero en una instalación limpia ninguno debería fallar.
    fallidos = [w['key'] for w in payload['widgets'] if not w['ok']]
    assert not fallidos, f"Widgets que fallaron al resolver: {fallidos}"


def test_dashboard_render_filters_widgets_by_permission(client, db):
    """La configuración NO puede otorgar visibilidad que el permiso niega.

    Se coloca en el dashboard general un widget que exige ``maintenance.view`` y
    se comprueba que un usuario sin ese permiso simplemente no lo recibe,
    mientras que el administrador sí.
    """
    setup_admin(client)
    client.post('/api/roles', json={
        'name': 'SOLO_LECTURA_RRHH', 'description': 'Perfil mínimo de prueba',
        'permissions': ['dashboard.view', 'person.view'],
    })
    _create_user(client, 'consulta_rrhh', ['SOLO_LECTURA_RRHH'])

    layout = client.get('/api/dev/dashboards/general').json()
    placements = [
        {'widget_key': p['widget_key'], 'visible': p['visible'], 'position': p['position'],
         'size': p['size'], 'title_override': p['title_override'], 'role_names': p['role_names'],
         'options': p['options']}
        for p in layout['placements']
    ]
    if not any(p['widget_key'] == 'taller_ordenes_abiertas' for p in placements):
        placements.append({'widget_key': 'taller_ordenes_abiertas', 'visible': True, 'position': 500,
                           'size': 'SMALL', 'title_override': None, 'role_names': [], 'options': {}})
    if not any(p['widget_key'] == 'hr_personal_activo' for p in placements):
        placements.append({'widget_key': 'hr_personal_activo', 'visible': True, 'position': 20,
                           'size': 'SMALL', 'title_override': None, 'role_names': [], 'options': {}})
    saved = client.put('/api/dev/dashboards/general', json={'placements': placements})
    assert saved.status_code == 200, saved.text

    admin_keys = {w['key'] for w in client.get('/api/dashboards/general').json()['widgets']}
    assert 'taller_ordenes_abiertas' in admin_keys

    _login(client, 'consulta_rrhh', 'OtraClave123!')
    limited = client.get('/api/dashboards/general')
    assert limited.status_code == 200, limited.text
    limited_keys = {w['key'] for w in limited.json()['widgets']}
    assert 'taller_ordenes_abiertas' not in limited_keys, \
        "Un widget colocado no puede mostrarse a quien carece de su permiso"
    assert 'hr_personal_activo' in limited_keys, "Sí debe ver aquello para lo que tiene permiso"

    # El mismo usuario no puede entrar al modo DEV.
    assert client.get('/api/dev/widgets').status_code == 403
    assert client.put('/api/dev/dashboards/general', json={'placements': []}).status_code == 403

    setup_admin(client)


def test_dev_can_show_hide_reorder_and_retitle(client, db):
    setup_admin(client)
    client.post('/api/dev/dashboards', json={
        'key': 'prueba-dev', 'name': 'Panel de prueba', 'area_code': 'MATERIAL',
        'description': 'Dashboard creado por la prueba', 'sort_order': 900,
    })
    placements = [
        {'widget_key': 'material_activos_total', 'visible': True, 'position': 10, 'size': 'MEDIUM',
         'title_override': 'Material en custodia', 'role_names': [], 'options': {}},
        {'widget_key': 'material_criticos', 'visible': False, 'position': 20, 'size': 'SMALL',
         'title_override': None, 'role_names': [], 'options': {}},
        {'widget_key': 'material_por_estado', 'visible': True, 'position': 5, 'size': 'LARGE',
         'title_override': None, 'role_names': [], 'options': {}},
    ]
    saved = client.put('/api/dev/dashboards/prueba-dev', json={'placements': placements})
    assert saved.status_code == 200, saved.text
    assert saved.json()['placements'] == 3

    rendered = client.get('/api/dashboards/prueba-dev').json()
    keys = [w['key'] for w in rendered['widgets']]
    # Ocultar funciona.
    assert 'material_criticos' not in keys
    # Ordenar funciona: position 5 va antes que position 10.
    assert keys == ['material_por_estado', 'material_activos_total']
    # Retitular funciona.
    titulo = next(w['title'] for w in rendered['widgets'] if w['key'] == 'material_activos_total')
    assert titulo == 'Material en custodia'
    # Redimensionar funciona.
    assert next(w['size'] for w in rendered['widgets'] if w['key'] == 'material_activos_total') == 'MEDIUM'

    # El modo DEV sí debe seguir viendo lo oculto, para poder volver a mostrarlo.
    admin_view = client.get('/api/dev/dashboards/prueba-dev').json()
    assert any(p['widget_key'] == 'material_criticos' and not p['visible'] for p in admin_view['placements'])


def test_dev_layout_validation_rejects_bad_input(client, db):
    setup_admin(client)
    base = {'visible': True, 'position': 10, 'size': 'SMALL', 'title_override': None,
            'role_names': [], 'options': {}}

    unknown = client.put('/api/dev/dashboards/general',
                         json={'placements': [{**base, 'widget_key': 'widget_que_no_existe'}]})
    assert unknown.status_code == 422 and 'desconocido' in unknown.json()['detail']

    duplicated = client.put('/api/dev/dashboards/general', json={'placements': [
        {**base, 'widget_key': 'hr_personal_activo'},
        {**base, 'widget_key': 'hr_personal_activo', 'position': 20},
    ]})
    assert duplicated.status_code == 422 and 'repetido' in duplicated.json()['detail']

    bad_size = client.put('/api/dev/dashboards/general',
                          json={'placements': [{**base, 'widget_key': 'hr_personal_activo', 'size': 'GIGANTE'}]})
    assert bad_size.status_code == 422 and 'Tamaño' in bad_size.json()['detail']

    bad_role = client.put('/api/dev/dashboards/general', json={'placements': [
        {**base, 'widget_key': 'hr_personal_activo', 'role_names': ['PERFIL_INEXISTENTE']}]})
    assert bad_role.status_code == 422 and 'inexistente' in bad_role.json()['detail']

    # Una validación fallida no debe dejar media composición aplicada.
    still_there = client.get('/api/dashboards/general').json()['widgets']
    assert still_there, "Un guardado rechazado no puede vaciar el dashboard"


def test_placement_role_restriction_narrows_only(client, db):
    """Restringir por perfil acota; nunca concede permisos que no se tienen."""
    setup_admin(client)
    client.post('/api/dev/dashboards', json={
        'key': 'prueba-perfiles', 'name': 'Panel por perfil', 'area_code': 'GENERAL', 'sort_order': 901,
    })
    client.post('/api/roles', json={
        'name': 'PERFIL_RESTRINGIDO', 'description': 'Prueba de restricción',
        'permissions': ['dashboard.view', 'person.view'],
    })
    _create_user(client, 'restringido', ['PERFIL_RESTRINGIDO'])

    client.put('/api/dev/dashboards/prueba-perfiles', json={'placements': [
        # Visible sólo para ADMIN aunque el permiso lo tengan ambos.
        {'widget_key': 'hr_personal_activo', 'visible': True, 'position': 10, 'size': 'SMALL',
         'title_override': None, 'role_names': ['ADMIN'], 'options': {}},
        # Sin restricción de perfil: lo ve quien tenga el permiso.
        {'widget_key': 'hr_personal_descanso', 'visible': True, 'position': 20, 'size': 'SMALL',
         'title_override': None, 'role_names': [], 'options': {}},
    ]})
    admin_keys = {w['key'] for w in client.get('/api/dashboards/prueba-perfiles').json()['widgets']}
    assert admin_keys == {'hr_personal_activo', 'hr_personal_descanso'}

    _login(client, 'restringido', 'OtraClave123!')
    keys = {w['key'] for w in client.get('/api/dashboards/prueba-perfiles').json()['widgets']}
    assert keys == {'hr_personal_descanso'}, "La restricción por perfil debe acotar la visibilidad"
    setup_admin(client)


def test_seed_does_not_overwrite_administrator_configuration(client, db):
    """Rearrancar la aplicación no debe deshacer lo que configuró el operador.

    Es la garantía que permite actualizar la release sin que los dashboards
    vuelvan a su composición de fábrica.
    """
    setup_admin(client)
    client.put('/api/dev/dashboards/taller', json={'placements': [
        {'widget_key': 'taller_espera_pieza', 'visible': True, 'position': 10, 'size': 'FULL',
         'title_override': 'Sólo esto', 'role_names': [], 'options': {}},
    ]})
    antes = client.get('/api/dev/dashboards/taller').json()['placements']
    assert len(antes) == 1

    # Se vuelve a ejecutar la siembra, tal como haría un reinicio del servicio.
    dashboard_service.ensure_dashboards(db)

    despues = client.get('/api/dev/dashboards/taller').json()['placements']
    assert len(despues) == 1, "La siembra no debe reinsertar widgets en un dashboard ya configurado"
    assert despues[0]['title_override'] == 'Sólo esto'


def test_orphan_placement_does_not_break_rendering(client, db):
    """Un widget retirado por una release no debe romper la vista resumen.

    Se simula insertando directamente una colocación cuya clave no existe en el
    registro, que es exactamente lo que quedaría tras desplegar una versión que
    eliminó ese widget.
    """
    setup_admin(client)
    dashboard = db.scalar(select(DashboardDefinition).where(DashboardDefinition.key == 'operacion'))
    db.add(DashboardWidgetPlacement(
        dashboard_id=dashboard.id, widget_key='widget_retirado_en_v5', position=1, size='SMALL', visible=True,
    ))
    db.commit()

    rendered = client.get('/api/dashboards/operacion')
    assert rendered.status_code == 200, "Una colocación huérfana no puede tumbar el dashboard"
    assert all(w['key'] != 'widget_retirado_en_v5' for w in rendered.json()['widgets'])

    # El modo DEV sí debe verla, marcada, para poder limpiarla.
    admin_view = client.get('/api/dev/dashboards/operacion').json()
    huerfanas = [p for p in admin_view['placements'] if p['orphan']]
    assert any(p['widget_key'] == 'widget_retirado_en_v5' for p in huerfanas)


def test_widget_failure_is_isolated(client, db, monkeypatch):
    """Si un resolver lanza una excepción, se aísla esa tarjeta y no la pantalla."""
    setup_admin(client)

    def explota(_db, _ctx):
        raise RuntimeError('fallo simulado de un widget')

    # WidgetDefinition es un dataclass frozen a propósito: una definición del
    # catálogo no debe mutarse en caliente. Por eso se sustituye la ENTRADA
    # completa del registro en lugar de reasignarle el resolver.
    definicion = widget_registry.REGISTRY['hr_personal_activo']
    monkeypatch.setitem(
        widget_registry.REGISTRY, 'hr_personal_activo',
        widget_registry.WidgetDefinition(
            key=definicion.key, title=definicion.title, area=definicion.area, kind=definicion.kind,
            permission=definicion.permission, description=definicion.description, resolver=explota,
            default_size=definicion.default_size, default_position=definicion.default_position,
        ),
    )
    client.put('/api/dev/dashboards/rrhh', json={'placements': [
        {'widget_key': 'hr_personal_activo', 'visible': True, 'position': 10, 'size': 'SMALL',
         'title_override': None, 'role_names': [], 'options': {}},
        {'widget_key': 'hr_epp_pendiente', 'visible': True, 'position': 20, 'size': 'SMALL',
         'title_override': None, 'role_names': [], 'options': {}},
    ]})
    payload = client.get('/api/dashboards/rrhh')
    assert payload.status_code == 200
    cards = {w['key']: w for w in payload.json()['widgets']}
    assert cards['hr_personal_activo']['ok'] is False
    assert cards['hr_personal_activo']['error']
    assert cards['hr_epp_pendiente']['ok'] is True, "El resto de la vista resumen debe seguir funcionando"


def test_areas_and_role_area_assignment(client, db):
    setup_admin(client)
    areas = client.get('/api/areas')
    assert areas.status_code == 200
    codes = {a['code'] for a in areas.json()}
    assert codes == set(AREAS)

    matrix = client.get('/api/areas/authority').json()
    assert len(matrix['domains']) == len(DATA_DOMAINS)
    assert 'my_areas' in matrix

    # Un perfil nuevo toma área GENERAL hasta que se declare la suya.
    client.post('/api/roles', json={
        'name': 'PERFIL_CON_AREA', 'description': 'Prueba de área',
        'permissions': ['dashboard.view', 'transport.view'],
    })
    inicial = client.get('/api/roles/PERFIL_CON_AREA/area').json()
    assert inicial['area_code'] == 'GENERAL' and inicial['explicit'] is False

    puesto = client.put('/api/roles/PERFIL_CON_AREA/area', json={'area_code': 'TRANSPORTE'})
    assert puesto.status_code == 200
    despues = client.get('/api/roles/PERFIL_CON_AREA/area').json()
    assert despues['area_code'] == 'TRANSPORTE' and despues['explicit'] is True

    invalida = client.put('/api/roles/PERFIL_CON_AREA/area', json={'area_code': 'NO_EXISTE'})
    assert invalida.status_code == 422

    contexto = client.get('/api/me/context').json()
    assert 'permissions' in contexto and 'areas' in contexto and 'domains' in contexto


def test_system_dashboard_cannot_be_deleted_but_can_be_deactivated(client, db):
    setup_admin(client)
    borrado = client.delete('/api/dev/dashboards/general')
    assert borrado.status_code == 409, "Una vista resumen del sistema no se borra"

    apagado = client.patch('/api/dev/dashboards/general', json={'active': False})
    assert apagado.status_code == 200
    assert client.get('/api/dashboards/general').status_code == 404
    assert 'general' not in {d['key'] for d in client.get('/api/dashboards').json()}

    client.patch('/api/dev/dashboards/general', json={'active': True})
    assert client.get('/api/dashboards/general').status_code == 200


def test_node_lifecycle_catalog_covers_every_required_event(client, db):
    """Los eventos del apartado 3 del encargo deben existir como catálogo.

    Se comprueba que están *configurados*, no codificados: viven en
    ``catalog_items`` y un operador puede añadir más sin desplegar nada.
    """
    setup_admin(client)
    estados = {x['code'] for x in client.get('/api/catalogs/ASSET_STATUS').json()}
    operaciones = {x['code'] for x in client.get('/api/catalogs/NODE_OPERATION').json()}
    resultados = {x['code'] for x in client.get('/api/catalogs/NODE_RESULT').json()}
    movimientos = {x['code'] for x in client.get('/api/catalogs/ASSET_MOVEMENT').json()}

    # TENDIDO, PLANTADO, ROTACIÓN, LEVANTADO y RETORNO son operaciones de campo.
    for code in ('TENDIDO', 'PLANTADO', 'ROTACION', 'LEVANTADO', 'RETORNO'):
        assert code in operaciones, f'Falta la operación de campo {code}'
        assert code in movimientos, f'Falta el movimiento {code}'

    # El resto son situaciones en las que puede acabar un nodo.
    for code in ('DAMAGED', 'BURNED', 'MISSING', 'LOST', 'STOLEN', 'SEIZED',
                 'MAINTENANCE', 'HIBERNATED', 'STORED', 'NO_INFO'):
        assert code in estados, f'Falta el estado {code}'
        assert code in resultados, f'Falta el resultado de campo {code}'

    # Y un estado nuevo sigue pudiendo agregarse sin tocar Python.
    nuevo = client.post('/api/catalogs/ASSET_STATUS', json={
        'code': 'EN_TRANSITO', 'name': 'En tránsito', 'metadata': {'critical': False, 'transferable': False},
    })
    assert nuevo.status_code in (200, 409), nuevo.text
    assert 'EN_TRANSITO' in {x['code'] for x in client.get('/api/catalogs/ASSET_STATUS').json()}
