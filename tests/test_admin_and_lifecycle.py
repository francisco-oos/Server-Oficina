from sqlalchemy import select

from app.db.models import EmploymentEngagement, Person, User
from tests.helpers import setup_admin


def test_first_admin_is_one_time(client):
    setup_admin(client)
    r = client.post('/api/setup/first-admin', json={
        'username':'otheradmin','display_name':'Other Admin','password':'AnotherPass123!'
    })
    assert r.status_code == 409


def test_admin_can_create_role_scoped_user(client, db):
    setup_admin(client)
    r = client.post('/api/users', json={
        'username':'rh-test','display_name':'RRHH Test','password':'StrongPass123!','roles':['HR']
    })
    assert r.status_code in (200,409), r.text
    user = db.scalar(select(User).where(User.username=='rh-test'))
    assert user is not None
    assert 'HR' in {role.name for role in user.roles}


def test_end_engagement_then_rehire_through_api(client, db):
    setup_admin(client)
    p = client.post('/api/persons', json={
        'full_name':'Ciclo Laboral','employment_id':'EMP-CYCLE-1','position':'Operador',
        'employer_type':'OUTSOURCING','provider':'Proveedor Demo','start_date':'2026-01-01'
    })
    assert p.status_code == 200, p.text
    pid = p.json()['id']
    eng = db.scalar(select(EmploymentEngagement).where(EmploymentEngagement.person_id==pid, EmploymentEngagement.employment_id=='EMP-CYCLE-1'))
    end = client.post(f'/api/engagements/{eng.id}/end', json={'end_date':'2026-02-28','reason':'Fin temporal'})
    assert end.status_code == 200, end.text
    db.expire_all()
    assert db.get(Person,pid).active is False
    rehire = client.post(f'/api/persons/{pid}/rehire', json={
        'employment_id':'EMP-CYCLE-2','position':'Operador','employer_type':'OUTSOURCING',
        'provider':'Proveedor Demo','start_date':'2026-04-01'
    })
    assert rehire.status_code == 200, rehire.text
    db.expire_all()
    assert db.get(Person,pid).active is True
    ids = {x.employment_id for x in db.scalars(select(EmploymentEngagement).where(EmploymentEngagement.person_id==pid)).all()}
    assert {'EMP-CYCLE-1','EMP-CYCLE-2'}.issubset(ids)
