"""Read the real generated workbook when available; these tests do not create files."""
from pathlib import Path
import pytest
from analista.excel import read_tracking,TRACKING_HEADERS
from analista.settings import ROOT


def test_generated_workbook_is_importable_without_tracking_changes():
    path=ROOT/'outputs/cadmo/seguimiento.xlsx'
    if not path.exists():
        pytest.skip('Ejecutar una exportación para verificar el round-trip real')
    records=read_tracking(path)
    assert records
    assert {'ID','Negocio','Estado','Notas','No contactar','Revisión'} <= set(records[0])
    assert all(r['Estado'] in ('Nuevo','Revisar','Contactado','Respondió','Reunión','Propuesta','Cliente','Descartado') for r in records)


def test_tracking_all_or_nothing_validation(tmp_path):
    from analista.database import Database
    from analista.models import Business
    db=Database(tmp_path/'test.sqlite3')
    try:
        bid,_=db.upsert(Business('x','Negocio','Zona','Rubro'))
        good={'ID':bid,'Estado':'Contactado','Notas':'Nota válida','Revisión':0}
        bad={'ID':'desconocido','Estado':'Nuevo','Revisión':0}
        with pytest.raises(ValueError):db.import_tracking([good,bad])
        assert db.conn.execute('SELECT state FROM tracking').fetchone()[0]=='Nuevo'
    finally:db.close()
