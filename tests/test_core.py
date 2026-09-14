from datetime import date
from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import EmploymentEngagement, Person, Role, User, EppHistory
from tests.helpers import setup_admin


def test_health(client):
    r=client.get('/api/health'); assert r.status_code==200; assert r.json()['ok'] is True


def test_identity_survives_rehire(client, db):
    setup_admin(client)
    p=client.post('/api/persons',json={'full_name':'Persona Prueba','employment_id':'EMP-OLD','position':'Auxiliar','employer_type':'OUTSOURCING','provider':'Proveedor X','start_date':'2026-01-01'})
    assert p.status_code==200,p.text; person_id=p.json()['id']
    eng=db.scalar(select(EmploymentEngagement).where(EmploymentEngagement.person_id==person_id,EmploymentEngagement.employment_id=='EMP-OLD'))
    eng.end_date=date(2026,2,1);eng.status='ENDED';db.commit()
    r=client.post(f'/api/persons/{person_id}/rehire',json={'employment_id':'EMP-NEW','position':'Auxiliar','employer_type':'OUTSOURCING','provider':'Proveedor X','start_date':'2026-03-01'})
    assert r.status_code==200,r.text
    engagements=db.scalars(select(EmploymentEngagement).where(EmploymentEngagement.person_id==person_id)).all()
    assert {x.employment_id for x in engagements}=={'EMP-OLD','EMP-NEW'}
    assert len({x.person_id for x in engagements})==1


def test_epp_only_hr_or_admin_can_validate(client, db):
    setup_admin(client)
    role=db.scalar(select(Role).where(Role.name=='SUPERVISOR'))
    user=User(username='supervisor',display_name='Supervisor',password_hash=hash_password('StrongPass123!'),roles=[role]);db.add(user)
    person=Person(full_name='EPP Persona',normalized_name='EPP PERSONA');db.add(person);db.commit()
    client.post('/api/auth/logout');assert client.post('/api/auth/login',json={'username':'supervisor','password':'StrongPass123!'}).status_code==200
    req=client.post('/api/epp/requests',json={'person_id':person.id,'item_type':'Overol','reason':'Deterioro'});assert req.status_code==200,req.text
    denied=client.post(f"/api/epp/requests/{req.json()['id']}/review",json={'decision':'APPROVED','note':'x'});assert denied.status_code==403
    client.post('/api/auth/logout');setup_admin(client)
    ok=client.post(f"/api/epp/requests/{req.json()['id']}/review",json={'decision':'APPROVED','note':'Validado por RRHH/admin'});assert ok.status_code==200
    assert db.scalar(select(EppHistory).where(EppHistory.request_id==req.json()['id'])) is not None
