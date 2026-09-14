import io
from sqlalchemy import select
from openpyxl import Workbook

from app.core.security import hash_password
from app.db.models import CaseRecord, Person, Role, TrainingRecord, User, ImportBatch, AttendanceRecord
from tests.helpers import setup_admin


def make_xlsx():
    wb=Workbook();ws=wb.active
    ws.append(['CLAVE','NOMBRE','PUESTO','GRUPO','10/09/2026'])
    ws.append(['EMP-TEST-01','Import Persona','Operador','G-01','T'])
    b=io.BytesIO();wb.save(b);return b.getvalue()


def test_import_preview_then_commit(client, db):
    setup_admin(client)
    content=make_xlsx()
    r=client.post('/api/imports/attendance/preview',files={'file':('asistencia.xlsx',content,'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
    assert r.status_code==200,r.text; out=r.json();assert out['summary']['rows']==1
    assert db.scalar(select(Person).where(Person.normalized_name=='IMPORT PERSONA')) is None
    c=client.post(f"/api/imports/{out['batch_id']}/commit");assert c.status_code==200,c.text
    p=db.scalar(select(Person).where(Person.normalized_name=='IMPORT PERSONA'));assert p is not None
    assert db.scalar(select(AttendanceRecord).where(AttendanceRecord.person_id==p.id)) is not None
    batch=db.get(ImportBatch,out['batch_id']);assert batch.sha256 and batch.status=='COMMITTED'


def test_training_hr_to_hse(client, db):
    setup_admin(client)
    person=Person(full_name='Curso Persona',normalized_name='CURSO PERSONA');db.add(person);db.commit()
    course=client.post('/api/training/courses',json={'code':'HSE-01','name':'Curso HSE'});assert course.status_code==200
    rec=client.post('/api/training/records',json={'person_id':person.id,'course_id':course.json()['id']});assert rec.status_code==200;rid=rec.json()['id']
    role=db.scalar(select(Role).where(Role.name=='HSE'));hse=User(username='hse',display_name='HSE',password_hash=hash_password('StrongPass123!'),roles=[role]);db.add(hse);db.commit()
    client.post('/api/auth/logout');assert client.post('/api/auth/login',json={'username':'hse','password':'StrongPass123!'}).status_code==200
    done=client.post(f'/api/training/records/{rid}/complete');assert done.status_code==200,done.text
    db.expire_all();assert db.get(TrainingRecord,rid).state=='COMPLETED'


def test_case_records_fact_not_automatic_sanction(client, db):
    setup_admin(client)
    person=Person(full_name='Caso Persona',normalized_name='CASO PERSONA');db.add(person);db.commit()
    c=client.post('/api/cases',json={'person_id':person.id,'case_type':'CONSUMO_DATOS','summary':'Consumo anómalo documentado'});assert c.status_code==200
    db.expire_all();item=db.get(CaseRecord,c.json()['id']);assert item.status=='OPEN' and item.resolution is None
    r=client.post(f'/api/cases/{item.id}/resolve',json={'resolution':'Revisado por área competente; sin acción automática.'});assert r.status_code==200
    db.expire_all();assert db.get(CaseRecord,item.id).status=='RESOLVED'


def test_import_does_not_guess_rehire_when_id_changes(client, db):
    setup_admin(client)
    person=Person(full_name='Nombre Recontratable', normalized_name='NOMBRE RECONTRATABLE')
    db.add(person); db.flush()
    from app.db.models import EmploymentEngagement, ImportIssue
    from datetime import date
    db.add(EmploymentEngagement(person_id=person.id, employment_id='OLD-ID', employer_type='OUTSOURCING', provider='P', start_date=date(2026,1,1), end_date=date(2026,2,1), status='ENDED'))
    db.commit()
    wb=Workbook(); ws=wb.active
    ws.append(['CLAVE','NOMBRE','PUESTO']); ws.append(['NEW-ID','Nombre Recontratable','Operador'])
    b=io.BytesIO(); wb.save(b)
    r=client.post('/api/imports/personnel/preview',files={'file':('personal.xlsx',b.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})
    assert r.status_code==200,r.text
    out=r.json(); assert out['summary']['review']>=1
    issues=client.get(f"/api/imports/{out['batch_id']}/issues").json()
    assert any(x['issue_type']=='POSSIBLE_ID_CHANGE' for x in issues)
    c=client.post(f"/api/imports/{out['batch_id']}/commit"); assert c.status_code==200,c.text
    ids={x.employment_id for x in db.scalars(select(EmploymentEngagement).where(EmploymentEngagement.person_id==person.id)).all()}
    assert 'NEW-ID' not in ids
