import pytest
from analista.database import Database
from analista.models import Business


@pytest.fixture
def db(tmp_path):
    instance=Database(tmp_path/'test.sqlite3')
    yield instance
    instance.close()


def business(source='osm:node:1',address='Calle 123'):
    return Business(source,'Café Prueba','Villa Urquiza','cafe',address,'https://prueba.com/')


def test_dedup_source_and_name_address(db):
    bid,new=db.upsert(business())
    assert new
    assert db.upsert(business())[0]==bid
    assert db.upsert(business('csv:otra'))[0]==bid
    assert db.conn.execute('SELECT count(*) FROM businesses').fetchone()[0]==1


def test_shared_website_does_not_merge_branches(db):
    a,_=db.upsert(business())
    b,_=db.upsert(business('osm:node:2','Calle 456'))
    assert a!=b


def record(bid,revision=0,notes='nota'):
    return {'ID':bid,'Estado':'Contactado','Responsable':'Socio','Notas':notes,'Próxima acción':'Revisar',
            'Próxima fecha':'2026-09-01','No contactar':'No','Revisión':revision}


def test_tracking_survives_research_and_import_is_idempotent(db):
    bid,_=db.upsert(business())
    row=record(bid)
    assert db.import_tracking([row])==1
    assert db.import_tracking([row])==0
    db.upsert(business())
    saved=db.conn.execute('SELECT * FROM tracking WHERE business_id=?',(bid,)).fetchone()
    assert saved['notes']=='nota' and saved['revision']==1


def test_old_excel_and_duplicate_rows_are_rejected_atomically(db):
    bid,_=db.upsert(business())
    db.import_tracking([record(bid)])
    with pytest.raises(ValueError,match='desactualizado'):
        db.import_tracking([record(bid,notes='conflicto')])
    with pytest.raises(ValueError,match='duplicado'):
        db.import_tracking([record(bid),record(bid)])
    assert db.conn.execute('SELECT notes FROM tracking').fetchone()[0]=='nota'


def test_invalid_date_and_unknown_id_rejected(db):
    bid,_=db.upsert(business())
    row=record(bid);row['Próxima fecha']='mañana'
    with pytest.raises(ValueError):db.import_tracking([row])
    with pytest.raises(ValueError):db.import_tracking([record('no-existe')])


def test_old_contact_retained_only_as_history(db):
    from analista.models import Page,Contact
    bid,_=db.upsert(business())
    page=Page('https://prueba.com/','Prueba','Contacto anterior')
    db.save_research(bid,[page],[Contact('email','antes@prueba.com',page.url)],[])
    db.save_research(bid,[page],[],[])
    assert db.conn.execute('SELECT verification FROM contacts').fetchone()[0].startswith('histórico')


def test_simple_tracking_preserves_legacy_owner_and_next_action(db):
    bid,_=db.upsert(business())
    db.import_tracking([record(bid)])
    db.import_tracking([{'ID':bid,'Estado':'Respondió','Notas':'Nueva nota','No contactar':'No','Revisión':1}])
    row=db.conn.execute('SELECT * FROM tracking').fetchone()
    assert row['owner']=='Socio' and row['next_action']=='Revisar' and row['next_date']=='2026-09-01'
    assert row['notes']=='Nueva nota'


def test_v1_migration_preserves_contacts_and_marks_old_proposals(tmp_path):
    from analista.models import Contact
    path=tmp_path/'legacy.sqlite3'
    db=Database(path)
    b=business();b.contacts=[Contact('phone','45458899','fuente')]
    bid,_=db.upsert(b)
    db.import_tracking([record(bid)])
    db.conn.execute('PRAGMA user_version=1');db.conn.commit();db.close()
    db=Database(path)
    try:
        assert db.was_proposed(bid)
        assert db.row(bid)['state']=='Contactado'
        assert len(db.current_contacts(bid))==1
        assert path.with_suffix('.v1-backup.sqlite3').exists()
        assert db.conn.execute('PRAGMA user_version').fetchone()[0]==2
    finally:db.close()
