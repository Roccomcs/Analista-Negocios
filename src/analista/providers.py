"""Fuentes intercambiables. No hay extractor masivo de Google Maps."""
import csv
import hashlib
import json
import os
import re
import time
from urllib.parse import quote_plus
from .models import Business, Contact, normalize, website_url
from .contacts import from_value, from_link, usable, MESSAGE_KINDS

ZONES = ("Villa Urquiza","Recoleta","Palermo","Belgrano","Chacarita","Colegiales","Villa Crespo","Caballito","Almagro","Villa Devoto","Núñez","Saavedra","Villa Pueyrredón","Flores","Boedo","San Telmo","Balvanera","Villa del Parque")
CATEGORIES = {
    "todos": ['["shop"]','["office"]','["craft"]','["amenity"~"^(restaurant|cafe|bar|fast_food|veterinary|clinic|dentist|doctors|school|language_school|gym)$"]'],
    "peluquerias": ['["shop"="hairdresser"]','["shop"="beauty"]'],
    "gastronomia": ['["amenity"~"^(restaurant|cafe|bar|fast_food|ice_cream)$"]'],
    "comercios": ['["shop"]'],
    "talleres": ['["shop"="car_repair"]','["craft"]'],
    "salud": ['["amenity"~"^(veterinary|clinic|dentist|doctors)$"]'],
    "educacion": ['["amenity"~"^(school|language_school|music_school|driving_school)$"]'],
    "profesionales": ['["office"]'],
}


def maps_link(name: str, address: str, zone: str) -> str:
    return "https://www.google.com/maps/search/?api=1&query="+quote_plus(f"{name} {address} {zone} Buenos Aires")


class OSMProvider:
    def __init__(self,settings,http):
        self.settings,self.http = settings,http

    def discover(self, zone: str, category: str, refresh=False) -> tuple[list[Business],list[str]]:
        # Fixed city boundary + escaped barrio name prevent accidental worldwide searches.
        if zone not in ZONES:
            raise ValueError("Barrio no configurado. Usá 'zonas' o importá un CSV para otras zonas.")
        selectors = CATEGORIES[category]
        name_pattern = re.escape(zone).replace('"','\\"')
        query = '[out:json][timeout:35];area["ISO3166-2"="AR-C"]->.ciudad;rel(area.ciudad)["boundary"="administrative"]["admin_level"="9"]["name"~"^'+name_pattern+'$",i];map_to_area->.barrio;('
        query += ''.join('nwr["name"]'+selector+'(area.barrio);' for selector in selectors)
        query += f');out center tags {self.settings.max_candidates+1};'
        key = hashlib.sha256((self.settings.overpass_url+query).encode()).hexdigest()
        cache = self.settings.path("data/cache") / (key+".json")
        if not refresh and cache.exists() and time.time()-cache.stat().st_mtime < self.settings.overpass_cache_hours*3600:
            payload = json.loads(cache.read_text("utf-8"))
        else:
            _,text,_ = self.http.request("GET",self.settings.overpass_url,params={"data":query},limit=8_000_000)
            payload = json.loads(text)
            if payload.get("remark"):
                raise RuntimeError("Overpass devolvió un resultado incompleto: "+payload["remark"][:300])
            cache.parent.mkdir(parents=True,exist_ok=True)
            cache.write_text(json.dumps(payload,ensure_ascii=False),encoding="utf-8")
        elements = payload.get("elements",[])
        warnings = ["Fuente: © OpenStreetMap contributors, ODbL. No equivale a un relevamiento completo de Google Maps."]
        if not elements:
            warnings.append("No hubo resultados: puede faltar cobertura del rubro o el límite administrativo del barrio en OSM.")
        if len(elements)>self.settings.max_candidates:
            warnings.append("Se alcanzó el máximo de candidatos: consulta parcial; elegí un rubro más específico.")
        businesses = []
        for element in elements[:self.settings.max_candidates]:
            tags = element.get("tags",{})
            if tags.get("disused") == "yes" or tags.get("abandoned") == "yes":
                continue
            source = f"https://www.openstreetmap.org/{element['type']}/{element['id']}"
            address = " ".join(filter(None,[tags.get("addr:street"),tags.get("addr:housenumber")]))
            center = element.get("center",element)
            website = website_url(tags.get("contact:website") or tags.get("website", ""))
            b = Business(f"osm:{element['type']}:{element['id']}",tags["name"],zone,
                         tags.get("shop") or tags.get("amenity") or tags.get("office") or tags.get("craft") or category,
                         address,website,source,center.get("lat"),center.get("lon"))
            b.details = {label: tags[key] for key,label in {
                "opening_hours":"Horarios publicados (OSM)","brand":"Marca","operator":"Operador",
                "description":"Descripción","cuisine":"Gastronomía","wheelchair":"Accesibilidad publicada",
                "delivery":"Entrega publicada","takeaway":"Retiro publicado"
            }.items() if tags.get(key)}
            for kind,keys in {
                "email":("contact:email","email"),"phone":("contact:phone","phone"),
                "whatsapp":("contact:whatsapp","whatsapp"),"instagram":("contact:instagram","instagram"),
                "facebook":("contact:facebook","facebook")
            }.items():
                for key_name in keys:
                    for value in tags.get(key_name,"").split(";"):
                        if value:
                            c=from_value(kind,value,source,"directorio público; corroborar identidad")
                            if c:
                                b.contacts.append(c)
            businesses.append(b)
        # Useful first, but stable order so repeated runs advance through the same cached list.
        businesses.sort(key=candidate_order)
        return businesses,warnings


def candidate_order(business):
    contacts = list(business.contacts)
    direct = from_link(business.website, business.source_url) if business.website else None
    if direct:
        contacts.append(direct)
    rank = (0 if any(usable(c, MESSAGE_KINDS) for c in contacts) else
            1 if any(usable(c) for c in contacts) else 2 if business.website else 3)
    return rank, normalize(business.name), business.source_id


def read_csv(path, zone: str = "", category: str = "importado") -> list[Business]:
    with open(path,"r",encoding="utf-8-sig",newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample,delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        rows = csv.DictReader(handle,dialect=dialect)
        if not rows.fieldnames or "nombre" not in rows.fieldnames:
            raise ValueError("El CSV debe tener la columna 'nombre'. Ver ejemplos/negocios.csv.")
        businesses=[]
        for line,row in enumerate(rows,2):
            row={k:(v or "").strip() for k,v in row.items() if k is not None}
            if not row.get("nombre"):
                continue
            barrio = row.get("zona") or zone
            if not barrio:
                raise ValueError(f"Falta zona en fila {line}")
            if zone and normalize(barrio)!=normalize(zone):
                continue
            address=row.get("direccion", "")
            url=website_url(row.get("web", ""))
            key=row.get("id") or hashlib.sha256('|'.join((normalize(row['nombre']),normalize(barrio),normalize(address),url)).encode()).hexdigest()[:24]
            source=row.get("fuente") or "Importación manual CSV: "+path.name
            b=Business("csv:"+key,row['nombre'],barrio,row.get("rubro") or category,address,url,source)
            for kind,column in (("email","correo"),("instagram","instagram"),("whatsapp","whatsapp"),("phone","telefono")):
                if row.get(column):
                    c=from_value(kind,row[column],source,"aportado por usuario; corroborar")
                    if c:
                        b.contacts.append(c)
            businesses.append(b)
        return businesses


def search_candidates(business: Business,settings,http):
    """Optional paid search. Never convert search hits into verified contact information."""
    if not settings.search_enabled:
        return [],[]
    key=os.environ.get("BRAVE_SEARCH_API_KEY")
    if not settings.search_storage_rights_confirmed:
        raise ValueError("Confirmá los derechos de almacenamiento de tu plan de búsqueda en config.local.json.")
    if not key:
        raise ValueError("Falta BRAVE_SEARCH_API_KEY; no se hizo una búsqueda paga.")
    query=f'"{business.name}" "{business.zone}" contacto instagram'
    _,body,_=http.request("GET","https://api.search.brave.com/res/v1/web/search",
                         params={"q":query,"count":5,"country":"AR","search_lang":"es"},
                         headers={"X-Subscription-Token":key,"Accept":"application/json"})
    results=json.loads(body).get("web",{}).get("results",[])
    contacts,notes=[],[]
    for hit in results:
        link=website_url(hit.get("url",""))
        if not link:
            continue
        c=from_link(link,link,"candidato de búsqueda; identidad sin verificar")
        if c:
            contacts.append(c)
        else:
            notes.append("Posible sitio externo; verificar identidad manualmente: "+link)
    return contacts,notes
