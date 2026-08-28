"""Exports use artifact-tool in the bundled Node runtime. Imports use read-only XML."""
import json
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime,timedelta
from pathlib import Path
from .settings import ROOT

NS={"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
TRACKING_HEADERS=("ID","Negocio","Estado","Responsable","Notas","Próxima acción","Próxima fecha","No contactar","Revisión")
SIMPLE_HEADERS={
    'Propuestas': ('Negocio','Barrio','Instagram','WhatsApp','Correo','Teléfono','Web','Dirección',
                   'Estado','Notas','No contactar','Encontrado','Fuente','ID','Revisión'),
    'Pendientes': ('Negocio','Barrio','Dirección','Web','Buscar Instagram','Estado','Notas','No contactar','Fuente','ID','Revisión'),
}


def read_tracking(path:Path):
    """No macros, external links, formulas or code are executed while importing a workbook."""
    with zipfile.ZipFile(path) as archive:
        if sum(i.file_size for i in archive.infolist())>80_000_000:
            raise ValueError("Excel demasiado grande para importar con seguridad")
        strings=[]
        if "xl/sharedStrings.xml" in archive.namelist():
            doc=ET.fromstring(archive.read("xl/sharedStrings.xml"))
            strings=["".join(t.text or "" for t in node.findall(".//m:t",NS)) for node in doc]
        book=ET.fromstring(archive.read("xl/workbook.xml"))
        sheets=book.find("m:sheets",NS)
        rels=ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        records=[]
        by_name={s.get('name'):s for s in sheets}
        selected=['Seguimiento'] if 'Seguimiento' in by_name else list(SIMPLE_HEADERS)
        for name in selected:
            if name not in by_name:
                raise ValueError(f'Falta la hoja {name}; se conservan tus notas y no se sobrescribe el archivo.')
            relation=by_name[name].get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
            target=next(r.get('Target') for r in rels if r.get('Id')==relation)
            target=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            doc=ET.fromstring(archive.read(target))
            headers=None
            expected=TRACKING_HEADERS if name=='Seguimiento' else SIMPLE_HEADERS[name]
            for row in doc.findall('.//m:sheetData/m:row',NS):
                row_number=int(row.get('r','0'))
                if row_number<4:
                    continue  # Title/summary formulas are never imported or evaluated.
                values={}
                for cell in row:
                    col=''.join(c for c in cell.get('r','') if c.isalpha())
                    if cell.find('m:f',NS) is not None:
                        raise ValueError('No uses fórmulas en las filas de seguimiento; no se sobrescribieron datos.')
                    if cell.get('t')=='inlineStr':
                        value=''.join(t.text or '' for t in cell.findall('.//m:t',NS))
                    else:
                        value=cell.findtext('m:v',default='',namespaces=NS)
                        if cell.get('t')=='s':
                            value=strings[int(value)]
                    values[col]=value
                if row_number==4:
                    headers=values
                    if len(headers)!=len(expected) or set(headers.values())!=set(expected):
                        raise ValueError(f'Cambió la estructura de {name}; no se sobrescribirá el Excel.')
                    continue
                if not headers:
                    raise ValueError(f'Faltan encabezados de {name}.')
                record={title:values.get(col,'') for col,title in headers.items() if title in TRACKING_HEADERS}
                if not record.get('ID'):
                    if any(values.values()):
                        raise ValueError(f'Fila sin ID en {name}; no se sobrescribirá el Excel.')
                    continue
                for key in ('Notas','Responsable','Próxima acción'):
                    value=record.get(key,'')
                    if value.startswith("'") and value[1:].lstrip().startswith(('=','+','@','-')):
                        record[key]=value[1:]
                date=record.get('Próxima fecha','')
                if date:
                    try:
                        record['Próxima fecha']=(datetime(1899,12,30)+timedelta(days=float(date))).date().isoformat()
                    except ValueError:
                        pass
                records.append(record)
            if headers is None:
                raise ValueError(f'Faltan encabezados de {name}.')
        return records


def runtime(settings):
    path=settings.path(settings.excel_runtime)
    if not path.exists():
        raise RuntimeError("Falta el motor de Excel. Ver docs/TAREAS_MANUALES.md; los datos siguen guardados en SQLite.")
    config=json.loads(path.read_text("utf-8-sig"))
    executable=Path(config["node"])
    if not executable.is_file():
        raise RuntimeError("No se encontró Node del motor de Excel; revisar .runtime/excel.json")
    return executable


def export(db,settings,preview=False):
    node=runtime(settings)
    dest=settings.path(settings.output)
    dest.parent.mkdir(parents=True,exist_ok=True)
    payload=db.export_data()
    payload["generated_at"]=datetime.now().astimezone().isoformat(timespec="seconds")
    payload["states"]=["Nuevo","Revisar","Contactado","Respondió","Reunión","Propuesta","Cliente","Descartado"]
    temporary=settings.path("data/tmp")
    temporary.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w",encoding="utf-8",suffix=".json",dir=temporary,delete=False) as handle:
        json.dump(payload,handle,ensure_ascii=False)
        input_path=Path(handle.name)
    try:
        args=[str(node),str(ROOT/"excel"/"workbook.mjs"),str(input_path),str(dest)]
        if preview:
            args.append("--preview")
        result=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=180)
        if result.returncode:
            raise RuntimeError("Falló la exportación de Excel; SQLite se conservó. "+result.stderr[-2000:])
        return dest
    finally:
        input_path.unlink(missing_ok=True)
