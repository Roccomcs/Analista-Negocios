import pytest
from analista import pipeline, ai
from analista.database import Database
from analista.models import Business, Page, Contact
from analista.settings import Settings


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path/'db.sqlite3')
    yield database
    database.close()


def business(i, kind=None, website=''):
    contacts = [Contact(kind, 'valor-publicado', f'https://fuente.example/{i}')] if kind else []
    return Business(f'osm:{i}', f'Negocio {i:03}', 'Villa Urquiza', 'shop', str(i),
                    website, f'https://fuente.example/{i}', contacts=contacts)


def discover(monkeypatch, businesses, warnings=None):
    monkeypatch.setattr(pipeline.OSMProvider, 'discover', lambda *a: (businesses, warnings or []))
    # The collection path must work even when Ollama is unavailable.
    def forbidden(*a, **k):
        raise AssertionError('El flujo de contactos no debe llamar a la IA')
    monkeypatch.setattr(ai, 'analyze', forbidden)
    monkeypatch.setattr(ai, 'doctor', forbidden)


def run(db, **kwargs):
    return pipeline.run(db, Settings(), zone='Villa Urquiza', category='todos',
                        limit=kwargs.pop('limit', 2), log=lambda m: None, **kwargs)


def test_target_counts_contacts_not_scanned_businesses(db, monkeypatch):
    records = [business(i, website=f'https://negocio{i}.example/') for i in range(110)]
    discover(monkeypatch, records)
    visits=[]
    def research(url, http, max_pages, **kwargs):
        visits.append(url)
        i=int(url.split('negocio')[1].split('.')[0])
        return [], [Contact('email', 'info@local.example', url)] if i%2 else [], []
    monkeypatch.setattr(pipeline, 'research', research)
    result=run(db, limit=50)
    assert result['qualified']==50 and result['processed']==100
    assert len(visits)==100 and result['target_met']
    assert db.conn.execute('SELECT qualified FROM runs').fetchone()[0]==50
    assert db.conn.execute('SELECT count(*) FROM proposals').fetchone()[0]==50


def test_published_messages_skip_web_and_previous_proposals(db, monkeypatch):
    records=[business(i,'instagram', 'https://local.example/') for i in range(4)]
    discover(monkeypatch, records)
    def forbidden(*a,**k):raise AssertionError('No visitar webs si ya hay Instagram')
    monkeypatch.setattr(pipeline,'research',forbidden)
    assert run(db)['qualified']==2
    second=run(db)
    assert second['qualified']==2 and second['skipped']==2
    monkeypatch.setattr(pipeline,'research',lambda *a,**k:([],[],[]))
    third=run(db, refresh=True)
    assert third['qualified']==0 and third['processed']==4 and third['errors']==0
    assert third['status']=='fuente agotada'


def test_only_phone_is_a_proposal_and_web_failure_does_not_lose_it(db, monkeypatch):
    discover(monkeypatch,[business(1,'phone','https://local.example/')])
    monkeypatch.setattr(pipeline,'research',lambda *a,**k: (_ for _ in ()).throw(RuntimeError('Caído')))
    result=run(db,limit=1)
    assert result['qualified']==1 and result['errors']==1
    assert [c.kind for c in db.current_contacts(db.conn.execute('SELECT id FROM businesses').fetchone()[0])]==['phone']


def test_website_facebook_candidate_and_historical_are_not_proposals(db, monkeypatch):
    records=[business(1,'facebook'),business(2,'email'),business(3,'instagram'),business(4,website='https://vacia.example/')]
    records[1].contacts[0].verification='candidato de búsqueda; identidad sin verificar'
    records[2].contacts[0].verification='histórico; no vuelto a encontrar'
    discover(monkeypatch,records)
    monkeypatch.setattr(pipeline,'research',lambda *a,**k:([],[],[]))
    result=run(db)
    assert result['qualified']==0 and result['processed']==4
    assert result['status']=='fuente agotada' and not result['target_met']


def test_duplicates_exclusions_and_contacted_never_count(db, monkeypatch):
    original=business(1,'email')
    duplicate=business(1,'email');duplicate.source_id='csv:duplicate'
    blocked=business(2,'phone');contacted=business(3,'email')
    a,_=db.upsert(blocked);b,_=db.upsert(contacted)
    db.conn.execute('UPDATE tracking SET do_not_contact=1 WHERE business_id=?',(a,))
    db.conn.execute("UPDATE tracking SET state='Contactado' WHERE business_id=?",(b,));db.conn.commit()
    discover(monkeypatch,[original,duplicate,blocked,contacted])
    result=run(db,refresh=True)
    assert result['qualified']==1 and result['processed']==1 and result['skipped']==3


def test_incomplete_source_and_stop_are_distinct_from_success(db, monkeypatch):
    discover(monkeypatch,[business(1)],['Se alcanzó el máximo de candidatos: consulta parcial'])
    assert run(db)['status']=='límite de candidatos'
    result=run(db,should_stop=lambda:True)
    assert result['status']=='detenido' and result['processed']==0


def test_new_csv_contact_can_rescue_a_previously_empty_record(db, monkeypatch):
    record=business(1)
    discover(monkeypatch,[record])
    assert run(db,limit=1)['qualified']==0
    record.contacts=[Contact('phone','45454545',record.source_url)]
    assert run(db,limit=1)['qualified']==1


def test_contact_collection_preserves_previous_analysis(db, monkeypatch):
    record=business(1,'email')
    bid,_=db.upsert(record)
    db.finish(bid,'analizado',{'summary':'análisis anterior'},'modelo')
    discover(monkeypatch,[record])
    assert run(db,limit=1)['qualified']==1
    assert 'análisis anterior' in db.row(bid)['analysis_json']


def test_social_website_qualifies_without_http(db, monkeypatch):
    discover(monkeypatch,[business(1,website='https://instagram.com/local/')])
    assert run(db,limit=1)['qualified']==1


def test_finite_exhaustion_and_invalid_target(db, monkeypatch):
    discover(monkeypatch,[business(1)])
    assert run(db)['processed']==1
    assert run(db)['processed']==0
    with pytest.raises(ValueError):run(db,limit=0)
    with pytest.raises(ValueError):run(db,use_ai=True)


def test_cli_exports_partial_results_and_uses_no_ai(tmp_path,monkeypatch):
    import json
    from analista import cli
    csv=tmp_path/'input.csv'
    csv.write_text('nombre,zona,telefono\nLocal,Villa Urquiza,45458899\n',encoding='utf-8')
    config=tmp_path/'config.json'
    config.write_text(json.dumps({'database':str(tmp_path/'cli.sqlite3'),'output':str(tmp_path/'out.xlsx')}),encoding='utf-8')
    exported=[]
    monkeypatch.setattr(cli,'synchronize',lambda *a:None)
    monkeypatch.setattr(cli.excel,'export',lambda db,s,*a:exported.append(db.export_data()) or s.path(s.output))
    discover(monkeypatch,[])
    code=cli.main(['--config',str(config),'ejecutar','--zona','Villa Urquiza','--csv',str(csv),'--cantidad','50'])
    assert code==3 and exported[0]['runs'][0]['qualified']==1
    assert len(exported[0]['proposals'])==1


def test_cli_stop_request_still_exports(tmp_path,monkeypatch):
    import json
    from analista import cli
    csv=tmp_path/'input.csv'
    csv.write_text('nombre,zona,telefono\nLocal,Villa Urquiza,45458899\n',encoding='utf-8')
    flag=tmp_path/'stop';flag.touch()
    config=tmp_path/'config.json'
    config.write_text(json.dumps({'database':str(tmp_path/'cli.sqlite3'),'output':str(tmp_path/'out.xlsx')}),encoding='utf-8')
    exported=[]
    monkeypatch.setattr(cli,'synchronize',lambda *a:None)
    monkeypatch.setattr(cli.excel,'export',lambda db,s,*a:exported.append(db.export_data()) or s.path(s.output))
    code=cli.main(['--config',str(config),'ejecutar','--zona','Villa Urquiza','--csv',str(csv),'--detener-archivo',str(flag)])
    assert code==3 and exported[0]['runs'][0]['status']=='detenido'
    assert exported[0]['runs'][0]['processed']==0
