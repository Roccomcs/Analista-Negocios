"""Opt-in end-to-end check with an isolated database. Does not alter production notes."""
import json
import tempfile
from pathlib import Path
from analista.database import Database
from analista.models import Business,Contact
from analista.excel import export,read_tracking
from analista.settings import Settings

def main():
    with tempfile.TemporaryDirectory(prefix='cadmo-excel-') as temp:
        root=Path(temp)
        settings=Settings(database=str(root/'test.sqlite3'),output=str(root/'test.xlsx'))
        db=Database(root/'test.sqlite3')
        try:
            export(db,settings)
            assert read_tracking(root/'test.xlsx')==[]
            pending_id,_=db.upsert(Business('test:pending','Sin contacto','Zona prueba','prueba'))
            business=Business('test:1','=NO_EJECUTAR','Zona prueba','prueba',contacts=[Contact('phone','+541145678900','https://example.com/')])
            bid,_=db.upsert(business)
            export(db,settings)
            rows=read_tracking(root/'test.xlsx')
            assert len(rows)==2 and rows[0]['ID']==bid and rows[1]['ID']==pending_id
            rows[0]['Notas']='Revisión manual conservada'
            rows[0]['Estado']='Revisar'
            assert db.import_tracking(rows)==1
            export(db,settings)
            again=read_tracking(root/'test.xlsx')
            assert again[0]['Notas']=='Revisión manual conservada'
            assert again[0]['Revisión']=='1'
            assert db.import_tracking(again)==0
            rows[0]['Notas']='=NO_EJECUTAR'
            rows[0]['Revisión']='1'
            db.import_tracking(rows)
            export(db,settings)
            assert read_tracking(root/'test.xlsx')[0]['Notas']=='=NO_EJECUTAR'
            assert db.import_tracking(read_tracking(root/'test.xlsx'))==0
            import zipfile
            import xml.etree.ElementTree as ET
            with zipfile.ZipFile(root/'test.xlsx') as book:
                ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                main=ET.fromstring(book.read('xl/worksheets/sheet1.xml'))
                phone=main.find('.//m:c[@r="F5"]',ns)
                assert phone.get('t') in ('s','str','inlineStr'), 'El teléfono debe conservarse como texto, no como número.'
                for name in book.namelist():
                    if name.startswith('xl/worksheets/') and name.endswith('.xml'):
                        assert '<f>NO_EJECUTAR' not in book.read(name).decode('utf-8')
            print('Verificación OK: exportación, importación, notas, revisión e inyección de fórmula.')
        finally:db.close()

if __name__=='__main__':main()
