from analista.providers import OSMProvider,read_csv
from analista.settings import Settings
import json


def test_osm_contact_mapping_and_cache(tmp_path):
    class HTTP:
        calls=0
        def request(self,*args,**kwargs):
            self.calls+=1
            assert 'AR-C' in kwargs['params']['data']
            return '',json.dumps({'elements':[{'type':'node','id':1,'lat':-34.5,'lon':-58.4,'tags':{'name':'Prueba','shop':'hairdresser','phone':'+541145678900','contact:instagram':'@prueba','opening_hours':'Mo-Fr 09:00-18:00'}}]}),'application/json'
    s=Settings()
    # Override path resolution only for this isolated cache.
    class Config:
        overpass_url=s.overpass_url;max_candidates=500;overpass_cache_hours=24
        def path(self,p):return tmp_path/p
    http=HTTP();provider=OSMProvider(Config(),http)
    records,_=provider.discover('Villa Urquiza','peluquerias')
    assert records[0].details['Horarios publicados (OSM)']=='Mo-Fr 09:00-18:00'
    assert {c.kind for c in records[0].contacts}=={'phone','instagram'}
    provider.discover('Villa Urquiza','peluquerias')
    assert http.calls==1


def test_csv_separate_contacts_and_zone_filter(tmp_path):
    f=tmp_path/'negocios.csv'
    f.write_text('nombre;zona;telefono;instagram;web\nUno;Palermo;+541145678900;@uno;uno.com\nDos;Recoleta;;;\n',encoding='utf-8-sig')
    rows=read_csv(f,'Palermo')
    assert len(rows)==1 and rows[0].website=='https://uno.com/'
    assert {c.kind for c in rows[0].contacts}=={'phone','instagram'}
