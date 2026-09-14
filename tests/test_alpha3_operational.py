from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.db.models import (
    Asset, AssetHealthObservation, AssetIdentifier, AssetMovement, EmploymentEngagement,
    EmploymentLifecycleEvent, EngagementOrganizationLink, EvidenceRecord, InventorySession, MaintenancePart, NodeOperationItem, Organization, Person,
    PersonHRProfile, ProjectCloseout, Role, User,
)
from tests.helpers import setup_admin


def _project_group_location(client, suffix="A3"):
    pr = client.post('/api/projects', json={'code': f'P-{suffix}', 'name': f'Proyecto {suffix}', 'start_date': '2026-09-01'})
    assert pr.status_code in (200, 409), pr.text
    projects = client.get('/api/projects').json()
    pid = next(x['id'] for x in projects if x['code'] == f'P-{suffix}')
    gr = client.post('/api/groups', json={'code': f'G-{suffix}', 'name': f'Grupo {suffix}', 'project_id': pid})
    assert gr.status_code in (200, 409), gr.text
    # No hay listado heredado de grupos; si se creó usamos su id, y si ya existía
    # lo recuperamos directamente de DB en las pruebas que lo requieran.
    gid = gr.json()['id'] if gr.status_code == 200 else None
    loc = client.post('/api/locations', json={'code': f'CAMP-{suffix}', 'name': f'Campamento {suffix}', 'location_type': 'CAMP', 'project_id': pid})
    assert loc.status_code in (200, 409), loc.text
    locations = client.get('/api/locations', params={'project_id': pid}).json()
    lid = next(x['id'] for x in locations if x['code'] == f'CAMP-{suffix}')
    return pid, gid, lid


def _create_asset(client, code, type_code='NODE', tech='SERCEL', status='AVAILABLE', identifiers=None, **kw):
    payload = {
        'type_code': type_code, 'technology_code': tech, 'internal_code': code,
        'serial_number': kw.get('serial_number', f'SN-{code}'), 'status_code': status,
        'identifiers': identifiers or [], 'metadata': kw.get('metadata', {}),
    }
    for k in ('project_id','group_id','location_id','custodian_person_id','notes'):
        if kw.get(k) is not None: payload[k] = kw[k]
    r = client.post('/api/assets', json=payload)
    assert r.status_code == 200, r.text
    return r.json()['id']


def test_dynamic_profiles_catalogs_and_future_technology(client, db):
    setup_admin(client)
    role = client.post('/api/roles', json={
        'name': 'ADMIN_NODOS_B', 'description': 'Perfil configurable de prueba',
        'permissions': ['dashboard.view','assets.view','assets.create','assets.move','nodes.view','nodes.operate'],
    })
    assert role.status_code in (200, 409), role.text
    roles = client.get('/api/roles').json()
    assert any(x['name'] == 'ADMIN_NODOS_B' for x in roles)

    # Catálogos y tecnologías nuevas se agregan sin tocar Python.
    c = client.post('/api/catalogs/ASSET_STATUS', json={'code':'QUARANTINED','name':'Cuarentena','metadata':{'critical': True}})
    assert c.status_code in (200,409), c.text
    m = client.post('/api/catalogs/ASSET_MOVEMENT', json={'code':'CUARENTENA','name':'Enviar a cuarentena','metadata':{'status_after':'QUARANTINED'}})
    assert m.status_code in (200,409), m.text
    t = client.post('/api/asset-types', json={'code':'SMART_SENSOR_FUTURE','name':'Sensor futuro','capabilities':['node_field','health','maintenance']})
    assert t.status_code in (200,409), t.text
    tech = client.post('/api/asset-technologies', json={'code':'TECH_X_FUTURE','name':'Tecnología X','vendor':'Proveedor futuro'})
    assert tech.status_code in (200,409), tech.text
    aid = _create_asset(client,'SSF-001','SMART_SENSOR_FUTURE','TECH_X_FUTURE')
    mv = client.post(f'/api/assets/{aid}/movements', json={'movement_type':'CUARENTENA','note':'Prueba de extensibilidad'})
    assert mv.status_code == 200, mv.text
    assert mv.json()['status'] == 'QUARANTINED'


def test_hr_license_category_rotation_attendance_and_lifecycle(client, db):
    setup_admin(client)
    pid, gid, lid = _project_group_location(client, 'HR3')
    supervisor = client.post('/api/persons', json={'full_name':'Supervisor Alpha3','employment_id':'SUP-A3','position':'Supervisor','start_date':'2026-09-01','project_id':pid})
    assert supervisor.status_code == 200, supervisor.text
    sup_id = supervisor.json()['id']
    person = client.post('/api/persons', json={'full_name':'Operador Alpha3','employment_id':'OP-A3-1','position':'Operador de nodos','employer_type':'OUTSOURCING','provider':'Proveedor Campo','start_date':'2026-09-01','project_id':pid})
    assert person.status_code == 200, person.text
    person_id = person.json()['id']

    prof = client.put(f'/api/persons/{person_id}/hr-profile', json={
        'category':'ADMINISTRADOR_NODOS_B','license_number':'LIC-A3-998','license_type':'CONDUCIR',
        'license_expiry':'2027-09-11','rotation_on_days':30,'rotation_off_days':15,'phone':'5550001111'
    })
    assert prof.status_code == 200, prof.text
    db.expire_all(); hp = db.get(PersonHRProfile, person_id)
    assert hp.category == 'ADMINISTRADOR_NODOS_B' and hp.rotation_on_days == 30 and hp.rotation_off_days == 15

    # Unidad, radio y nodo bajo la misma persona.
    vehicle = _create_asset(client,'UNIT-A3','VEHICLE','GENERIC',identifiers=[{'kind':'ECONOMIC_NUMBER','value':'ECO-A3','is_primary':True}])
    radio = _create_asset(client,'RAD-A3','RADIO','GENERIC',identifiers=[{'kind':'SERIAL','value':'RADIO-SERIAL-A3','is_primary':True}])
    node = _create_asset(client,'NODE-A3-HR','NODE','SERCEL')
    ass = client.post(f'/api/persons/{person_id}/assignments', json={'project_id':pid,'group_id':gid,'location_id':lid,'supervisor_person_id':sup_id,'unit_asset_id':vehicle,'role_name':'Administrador de nodos B'})
    assert ass.status_code == 200, ass.text
    for aid in (vehicle, radio, node):
        r = client.post(f'/api/assets/{aid}/movements', json={'movement_type':'ASSIGN','project_id':pid,'group_id':gid,'location_id':lid,'responsible_person_id':person_id})
        assert r.status_code == 200, r.text

    att = client.post('/api/attendance', json={'person_id':person_id,'attendance_date':'2026-09-11','status':'PRESENT'})
    assert att.status_code == 200, att.text
    found = client.get('/api/locate', params={'q':'OP-A3-1'})
    assert found.status_code == 200, found.text
    p = found.json()['persons'][0]
    assert p['unit_asset_id'] == vehicle and {x['id'] for x in p['assets']} >= {vehicle, radio, node}

    eng = db.scalar(select(EmploymentEngagement).where(EmploymentEngagement.person_id == person_id, EmploymentEngagement.end_date.is_(None)))
    quit_ev = client.post(f'/api/engagements/{eng.id}/lifecycle', json={'event_type':'RESIGNATION','occurred_on':'2026-10-01','reason':'Renuncia voluntaria'})
    assert quit_ev.status_code == 200, quit_ev.text
    db.expire_all(); assert db.get(Person, person_id).active is False
    assert db.scalar(select(EmploymentLifecycleEvent).where(EmploymentLifecycleEvent.engagement_id == eng.id, EmploymentLifecycleEvent.event_type == 'RESIGNATION'))

    rehire = client.post(f'/api/persons/{person_id}/rehire', json={'employment_id':'OP-A3-2','position':'Operador de nodos','employer_type':'OUTSOURCING','provider':'Proveedor Campo','start_date':'2026-11-01','project_id':pid})
    assert rehire.status_code == 200, rehire.text
    fire = client.post(f"/api/engagements/{rehire.json()['id']}/lifecycle", json={'event_type':'DISMISSAL','occurred_on':'2026-12-01','reason':'Baja administrativa de prueba'})
    assert fire.status_code == 200, fire.text


def test_all_asset_technologies_identifiers_and_search(client, db):
    setup_admin(client)
    samples = [
        ('PHONE-A3','PHONE','GENERIC',[{'kind':'IMEI','value':'865000000000001','is_primary':True}]),
        ('PC-A3','COMPUTER','GENERIC',[{'kind':'SERIAL','value':'PC-SERIAL-A3','is_primary':True}]),
        ('DRONE-A3','DRONE','DJI',[{'kind':'SERIAL','value':'DJI-A3-SN','is_primary':True}]),
        ('RADIO-A3-X','RADIO','GENERIC',[{'kind':'SERIAL','value':'RAD-A3-X-SN','is_primary':True}]),
        ('NODE-SERCEL-A3','NODE','SERCEL',[{'kind':'QR','value':'QR-SERCEL-A3','is_primary':True}]),
        ('NODE-INOVA-A3','NODE','INOVA',[{'kind':'QR','value':'QR-INOVA-A3','is_primary':True}]),
    ]
    for code, typ, tech, ids in samples:
        _create_asset(client,code,typ,tech,identifiers=ids)
    assert client.get('/api/assets', params={'q':'865000000000001'}).json()[0]['type_code'] == 'PHONE'
    assert client.get('/api/assets', params={'q':'QR-INOVA-A3'}).json()[0]['technology'] == 'INOVA'


def test_node_tracking_full_flow_and_exception_matrix(client, db):
    setup_admin(client)
    pid, gid, lid = _project_group_location(client, 'NODE3')
    worker = client.post('/api/persons', json={'full_name':'Tendedor Alpha3','employment_id':'TEND-A3','position':'Tendedor','start_date':'2026-09-01','project_id':pid}).json()['id']
    node = _create_asset(client,'NODE-FLOW-A3','NODE','SERCEL')
    flows = [
        ('TENDIDO','1001','1001'),('ROTACION','1001','1051'),('LEVANTADO','1051','1051'),('RETORNO','1051','1051')
    ]
    for op, fr, to in flows:
        r=client.post('/api/node-operations',json={'operation_type':op,'project_id':pid,'group_id':gid,'location_id':lid,'line_code':'L-100',
            'participant_person_ids':[worker],'items':[{'asset_id':node,'stake_from':fr,'stake_to':to,'responsible_person_id':worker,'result_code':'OK'}]})
        assert r.status_code==200,r.text
    detail=client.get(f'/api/assets/{node}').json()
    types=[x['movement_type'] for x in detail['movements']]
    for needed in ('TENDIDO','ROTACION','LEVANTADO','RETORNO'): assert needed in types
    rotate=next(x for x in detail['movements'] if x['movement_type']=='ROTACION')
    assert rotate['metadata']['stake_from']=='1001' and rotate['metadata']['stake_to']=='1051'
    assert worker in rotate['participants']

    exceptions = {
        'DAMAGED':'DAMAGED','BURNED':'BURNED','MISSING':'MISSING','LOST':'LOST','STOLEN':'STOLEN',
        'SEIZED':'SEIZED','MAINTENANCE':'MAINTENANCE','HIBERNATED':'HIBERNATED','NO_INFO':'NO_INFO'
    }
    for result, expected in exceptions.items():
        aid=_create_asset(client,f'NODE-{result}-A3','NODE','INOVA')
        r=client.post('/api/node-operations',json={'operation_type':'INCIDENT','project_id':pid,'location_id':lid,'line_code':'L-EX',
            'participant_person_ids':[worker],'items':[{'asset_id':aid,'stake_from':'2000','result_code':result,'responsible_person_id':worker}]})
        assert r.status_code==200,r.text
        detail = client.get(f'/api/assets/{aid}').json()
        assert detail['asset']['status_code']==expected
        expected_move = {
            'DAMAGED':'DAMAGE','BURNED':'BURNED','MISSING':'MISSING','LOST':'LOST','STOLEN':'STOLEN',
            'SEIZED':'SEIZED','MAINTENANCE':'MAINTENANCE_IN','HIBERNATED':'HIBERNATE','NO_INFO':'NO_INFO'
        }[result]
        assert detail['movements'][0]['movement_type'] == expected_move
        if result in {'LOST','SEIZED','HIBERNATED'}:
            recover_move = 'WAKE' if result=='HIBERNATED' else 'RECOVER'
            rr=client.post(f'/api/assets/{aid}/movements',json={'movement_type':recover_move,'responsible_person_id':worker,'location_id':lid})
            assert rr.status_code==200,rr.text
            assert rr.json()['status']=='AVAILABLE'


def test_maintenance_parts_and_health_do_not_auto_retire(client, db):
    setup_admin(client)
    aid=_create_asset(client,'NODE-MAINT-A3','NODE','SERCEL')
    op=client.post('/api/maintenance',json={'asset_id':aid,'priority':'HIGH','symptom':'No enciende','fault_code':'BAT-LOW'})
    assert op.status_code==200,op.text; oid=op.json()['id']
    part=client.post(f'/api/maintenance/{oid}/parts',json={'component_type':'BATTERY','serial_removed':'BAT-OLD-A3','serial_installed':'BAT-NEW-A3','quantity':1})
    assert part.status_code==200,part.text
    h=client.post(f'/api/assets/{aid}/health',json={'source':'NodeHealthAnalyzer','soh_percent':41,'rul_days':45,'health_score':38,'confidence':'MEDIUM','cycles':320})
    assert h.status_code==200,h.text and h.json()['asset_status_unchanged']=='MAINTENANCE'
    close=client.put(f'/api/maintenance/{oid}',json={'diagnosis':'Batería degradada','action_taken':'Cambio de batería y prueba','result':'PASS','close':True,'status_after':'AVAILABLE','downtime_minutes':180})
    assert close.status_code==200,close.text
    db.expire_all(); assert db.get(Asset,aid).status_code=='AVAILABLE'
    assert db.scalar(select(MaintenancePart).where(MaintenancePart.maintenance_order_id==oid)).serial_installed=='BAT-NEW-A3'
    assert db.scalar(select(AssetHealthObservation).where(AssetHealthObservation.asset_id==aid)).rul_days==45


def test_inventory_missing_and_material_traceability(client, db):
    setup_admin(client)
    pid, gid, lid = _project_group_location(client, 'INV3')
    a1=_create_asset(client,'INV-RADIO-A3','RADIO','GENERIC',project_id=pid,location_id=lid)
    a2=_create_asset(client,'INV-NODE-A3','NODE','SERCEL',project_id=pid,location_id=lid)
    s=client.post('/api/inventory/sessions',json={'name':'Inventario quincenal A3','project_id':pid,'location_id':lid})
    assert s.status_code==200,s.text; sid=s.json()['id']
    assert client.post(f'/api/inventory/sessions/{sid}/count',json={'asset_id':a1,'found':True,'location_id':lid}).status_code==200
    closed=client.post(f'/api/inventory/sessions/{sid}/close')
    assert closed.status_code==200,closed.text
    missing={x['asset_id'] for x in closed.json()['missing']}
    assert a2 in missing and a1 not in missing
    db.expire_all(); assert db.get(InventorySession,sid).status=='CLOSED'


def test_bulk_asset_import_preserves_informative_metadata(client, db):
    setup_admin(client)
    csv_data = "TYPE,TECHNOLOGY,INTERNAL_CODE,SERIAL,STATUS,IMEI,EXTRA_COLOR,AREA_ORIGEN\nPHONE,GENERIC,BULK-PHONE-A3,BULK-SN-A3,AVAILABLE,865000000000777,NEGRO,OFICINA\n"
    p=client.post('/api/assets/bulk/preview',files={'file':('assets.csv',csv_data.encode(),'text/csv')})
    assert p.status_code==200,p.text and p.json()['can_commit'] is True
    c=client.post(f"/api/assets/bulk/{p.json()['batch_id']}/commit")
    assert c.status_code==200,c.text and c.json()['created']==1
    asset=db.get(Asset,c.json()['asset_ids'][0]); assert asset.metadata_json['EXTRA_COLOR']=='NEGRO' and asset.metadata_json['AREA_ORIGEN']=='OFICINA'
    assert db.scalar(select(AssetIdentifier).where(AssetIdentifier.asset_id==asset.id,AssetIdentifier.kind=='IMEI')).value=='865000000000777'


def test_evidence_repository_local_upload_and_smb_fail_closed(client, tmp_path):
    setup_admin(client)
    local=tmp_path/'evidence-local'
    r=client.post('/api/evidence/repositories',json={'code':'LOCAL_A3','name':'Local test','repository_type':'LOCAL','mount_point':str(local)})
    assert r.status_code==200,r.text
    repo_id=r.json()['id']
    payload=(b'evidencia-alpha3-' * 180000)  # > 1 MiB para ejercer escritura/hash por bloques.
    up=client.post('/api/evidence/upload',data={'repository_id':repo_id,'entity_type':'ASSET','entity_id':'asset-test-a3'},files={'file':('evidencia.bin',payload,'application/octet-stream')})
    assert up.status_code==200,up.text
    stored=local/up.json()['relative_path']
    assert stored.exists() and stored.stat().st_size == len(payload)
    import hashlib
    assert up.json()['sha256'] == hashlib.sha256(payload).hexdigest()

    smb=client.post('/api/evidence/repositories',json={'code':'SMB_A3','name':'NAS no montado','repository_type':'SMB','mount_point':str(tmp_path/'fake-mount'),'canonical_uri':'\\\\nas\\evidencias'})
    assert smb.status_code==200,smb.text
    denied=client.post('/api/evidence/upload',data={'repository_id':smb.json()['id'],'entity_type':'ASSET','entity_id':'x'},files={'file':('x.txt',b'x','text/plain')})
    assert denied.status_code==503,denied.text


def test_dashboard_includes_operational_asset_summary(client):
    setup_admin(client)
    d=client.get('/api/dashboard')
    assert d.status_code==200,d.text
    body=d.json()
    for key in ('assets_total','critical_assets','maintenance_open','assets_by_status','active_persons','recent_events'):
        assert key in body


def test_normalized_organization_links_on_engagement(client, db):
    setup_admin(client)
    person = client.post('/api/persons', json={
        'full_name':'Persona Outsourcing Alpha3','employment_id':'OUT-A3-001','position':'Operador',
        'employer_type':'OUTSOURCING','provider':'Texto legado compatible','start_date':'2026-09-01'
    })
    assert person.status_code == 200, person.text
    person_id = person.json()['id']
    org = client.post('/api/organizations', json={
        'code':'PROV-A3','name':'Proveedor Normalizado Alpha3','organization_type':'OUTSOURCING',
        'metadata':{'source':'acceptance-test'}
    })
    assert org.status_code == 200, org.text
    eng = db.scalar(select(EmploymentEngagement).where(EmploymentEngagement.person_id == person_id, EmploymentEngagement.end_date.is_(None)))
    link = client.post(f'/api/engagements/{eng.id}/organizations', json={
        'organization_id':org.json()['id'],'relation_type':'OUTSOURCING','start_date':'2026-09-01'
    })
    assert link.status_code == 200, link.text
    listing = client.get(f'/api/engagements/{eng.id}/organizations')
    assert listing.status_code == 200, listing.text
    assert listing.json()[0]['organization_name'] == 'Proveedor Normalizado Alpha3'
    db.expire_all()
    assert db.scalar(select(EngagementOrganizationLink).where(EngagementOrganizationLink.engagement_id == eng.id))
    assert db.scalar(select(Organization).where(Organization.code == 'PROV-A3')).organization_type == 'OUTSOURCING'


def test_register_existing_evidence_without_moving_original(client, db, tmp_path):
    setup_admin(client)
    root = tmp_path / 'nas-like-repository'
    source = root / 'ProyectoA' / 'Nodos' / 'NODE-001' / 'foto_original.txt'
    source.parent.mkdir(parents=True)
    source.write_bytes(b'evidencia copiada previamente por Windows')
    repo = client.post('/api/evidence/repositories', json={
        'code':'EXISTING_A3','name':'Repositorio existente','repository_type':'LOCAL','mount_point':str(root),
        'canonical_uri':r'\\nas-configurable\evidencias'
    })
    assert repo.status_code == 200, repo.text
    reg = client.post('/api/evidence/register-existing', json={
        'repository_id':repo.json()['id'],'entity_type':'ASSET','entity_id':'NODE-001',
        'relative_path':'ProyectoA/Nodos/NODE-001/foto_original.txt','metadata':{'indexed_from':'windows-organizer'}
    })
    assert reg.status_code == 200, reg.text
    assert reg.json()['already_registered'] is False
    assert source.exists() and source.read_bytes() == b'evidencia copiada previamente por Windows'
    again = client.post('/api/evidence/register-existing', json={
        'repository_id':repo.json()['id'],'entity_type':'ASSET','entity_id':'NODE-001',
        'relative_path':'ProyectoA/Nodos/NODE-001/foto_original.txt'
    })
    assert again.status_code == 200 and again.json()['already_registered'] is True
    rows = client.get('/api/evidence/records', params={'entity_type':'ASSET','entity_id':'NODE-001'}).json()
    assert len(rows) == 1 and rows[0]['source'] == 'EXISTING_FILE'
    db.expire_all(); assert db.scalar(select(EvidenceRecord).where(EvidenceRecord.entity_id == 'NODE-001'))


def test_project_material_closeout_snapshot_survives_later_transfer(client, db):
    setup_admin(client)
    pid, gid, lid = _project_group_location(client, 'CLOSE3')
    good = _create_asset(client, 'CLOSE-GOOD-A3', 'RADIO', 'GENERIC', project_id=pid, location_id=lid)
    lost = _create_asset(client, 'CLOSE-LOST-A3', 'NODE', 'SERCEL', project_id=pid, location_id=lid)
    assert client.post(f'/api/assets/{lost}/movements', json={'movement_type':'LOST','project_id':pid,'location_id':lid}).status_code == 200
    preview = client.get(f'/api/projects/{pid}/material-closeout')
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body['assets_total'] == 2
    assert lost in {x['asset_id'] for x in body['critical_assets']}
    assert good in {x['asset_id'] for x in body['transferable_assets']}
    closed = client.post(f'/api/projects/{pid}/material-closeout', json={'end_date':'2026-09-30','note':'Cierre de prueba Alpha3'})
    assert closed.status_code == 200, closed.text
    closeout_id = closed.json()['id']
    db.expire_all(); saved = db.get(ProjectCloseout, closeout_id)
    assert saved and saved.snapshot_json['status_counts']['LOST'] == 1

    # Un activo sano puede continuar al proyecto siguiente, sin reescribir el corte anterior.
    pr2 = client.post('/api/projects', json={'code':'P-CLOSE3-NEXT','name':'Proyecto siguiente','start_date':'2026-10-01'})
    assert pr2.status_code == 200, pr2.text
    next_pid = pr2.json()['id']
    moved = client.post(f'/api/assets/{good}/movements', json={'movement_type':'TRANSFER','project_id':next_pid,'status_after':'AVAILABLE'})
    assert moved.status_code == 200, moved.text
    history = client.get(f'/api/projects/{pid}/material-closeouts').json()
    old = next(x for x in history if x['id'] == closeout_id)
    old_good = next(x for x in old['snapshot']['assets'] if x['asset_id'] == good)
    assert old_good['current_project_id'] == pid
    assert client.get(f'/api/assets/{good}').json()['asset']['project_id'] == next_pid


def test_all_seeded_asset_types_can_be_registered_and_traced(client, db):
    """El inventario base no debe dejar categorías 'de segunda'.

    Además de los casos de trabajo más frecuentes, comprobamos que ANTENNA,
    SERVER y NAS comparten la misma identidad, identificadores y timeline que
    nodos/radios/teléfonos.  Añadir una categoría futura sigue cubierto por la
    prueba de extensibilidad; esta prueba protege las semillas actuales.
    """
    setup_admin(client)
    pid, gid, lid = _project_group_location(client, 'TYPES3')
    worker = client.post('/api/persons', json={
        'full_name':'Custodio Tipos Alpha3','employment_id':'TYPE-A3-EMP','position':'Materiales',
        'start_date':'2026-09-01','project_id':pid,
    })
    assert worker.status_code == 200, worker.text
    person_id = worker.json()['id']
    samples = [
        ('TYPE-NODE-A3','NODE','SERCEL','SERIAL','SER-NODE-A3'),
        ('TYPE-RADIO-A3','RADIO','GENERIC','SERIAL','SER-RADIO-A3'),
        ('TYPE-ANT-A3','ANTENNA','GENERIC','SERIAL','SER-ANT-A3'),
        ('TYPE-PHONE-A3','PHONE','GENERIC','IMEI','865000000001234'),
        ('TYPE-PC-A3','COMPUTER','GENERIC','SERIAL','SER-PC-A3'),
        ('TYPE-DRONE-A3','DRONE','DJI','SERIAL','SER-DRONE-A3'),
        ('TYPE-VEH-A3','VEHICLE','GENERIC','ECONOMIC_NUMBER','ECO-TYPE-A3'),
        ('TYPE-SERVER-A3','SERVER','GENERIC','SERIAL','SER-SERVER-A3'),
        ('TYPE-NAS-A3','NAS','GENERIC','SERIAL','SER-NAS-A3'),
    ]
    ids=[]
    for code, typ, tech, kind, value in samples:
        aid = _create_asset(client, code, typ, tech, project_id=pid, location_id=lid,
                            identifiers=[{'kind':kind,'value':value,'is_primary':True}])
        ids.append(aid)
        moved = client.post(f'/api/assets/{aid}/movements', json={
            'movement_type':'ASSIGN','project_id':pid,'group_id':gid,'location_id':lid,
            'responsible_person_id':person_id,
        })
        assert moved.status_code == 200, moved.text
        detail = client.get(f'/api/assets/{aid}')
        assert detail.status_code == 200, detail.text
        assert detail.json()['asset']['custodian_person_id'] == person_id
        assert detail.json()['movements'][0]['movement_type'] == 'ASSIGN'
    assert len(ids) == 9
    assert client.get('/api/assets', params={'q':'SER-NAS-A3'}).json()[0]['type_code'] == 'NAS'
    assert client.get('/api/assets', params={'q':'ECO-TYPE-A3'}).json()[0]['type_code'] == 'VEHICLE'


def test_custom_role_can_be_edited_and_assigned_without_touching_base_roles(client, db):
    """El desarrollador/admin diseña perfiles de negocio sin hardcodear roles."""
    setup_admin(client)
    created = client.post('/api/roles', json={
        'name':'OPERACION_CAMPO_CUSTOM','description':'Perfil inicial',
        'permissions':['dashboard.view','assets.view'],
    })
    assert created.status_code == 200, created.text
    updated = client.put('/api/roles/OPERACION_CAMPO_CUSTOM', json={
        'name':'OPERACION_CAMPO_CUSTOM','description':'Perfil ampliado',
        'permissions':['dashboard.view','assets.view','nodes.view','nodes.operate','evidence.view'],
    })
    assert updated.status_code == 200, updated.text
    assert 'nodes.operate' in updated.json()['permissions']
    user_resp = client.post('/api/users', json={
        'username':'campo-custom','display_name':'Campo Custom','password':'StrongPass123!',
        'roles':['OFFICE'],
    })
    assert user_resp.status_code == 200, user_resp.text
    changed = client.put(f"/api/users/{user_resp.json()['id']}/roles", json={'roles':['OPERACION_CAMPO_CUSTOM']})
    assert changed.status_code == 200, changed.text
    assert changed.json()['roles'] == ['OPERACION_CAMPO_CUSTOM']
    # Los perfiles base permanecen protegidos para evitar degradar el bootstrap.
    denied = client.put('/api/roles/ADMIN', json={
        'name':'ADMIN','description':'no debe cambiar','permissions':['dashboard.view'],
    })
    assert denied.status_code == 409


def test_evidence_existing_path_cannot_escape_repository(client, tmp_path):
    """Una ruta relativa manipulada nunca puede indexar archivos fuera del repositorio."""
    setup_admin(client)
    root = tmp_path / 'repo'
    root.mkdir()
    outside = tmp_path / 'fuera.txt'
    outside.write_text('fuera del repositorio')
    repo = client.post('/api/evidence/repositories', json={
        'code':'SAFE_PATH_A3','name':'Repositorio seguro','repository_type':'LOCAL','mount_point':str(root)
    })
    assert repo.status_code == 200, repo.text
    denied = client.post('/api/evidence/register-existing', json={
        'repository_id':repo.json()['id'],'entity_type':'ASSET','entity_id':'x','relative_path':'../fuera.txt'
    })
    assert denied.status_code == 422, denied.text
