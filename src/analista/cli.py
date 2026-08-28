import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from filelock import FileLock, Timeout
from . import ai, excel
from .database import Database
from .models import Business,Page
from .pipeline import run
from .providers import ZONES,CATEGORIES
from .settings import load_settings


def synchronize(db,settings,other=None):
    book=Path(other) if other else settings.path(settings.output)
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backups=settings.path('data/backups')
    db.backup(backups/(stamp+'.sqlite3'))
    if book.exists():
        records=excel.read_tracking(book)
        shutil.copy2(book,backups/(stamp+'.xlsx'))
        count=db.import_tracking(records)
        print(f'Seguimiento importado: {count} cambio(s). Copia de seguridad guardada.',flush=True)


def main(argv=None):
    if hasattr(sys.stdout,'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    parser=argparse.ArgumentParser(description='Cadmo · Investigación de negocios. Sin envíos automáticos.')
    parser.add_argument('--config',help='Archivo JSON de configuración')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('zonas',help='Barrios y rubros disponibles')
    sub.add_parser('diagnostico',help='Comprobar modelo, rutas y Excel sin investigar')
    collect=sub.add_parser('ejecutar',help='Buscar propuestas nuevas con contacto, sin IA')
    collect.add_argument('--zona',required=True)
    collect.add_argument('--rubro',choices=list(CATEGORIES),default='todos')
    collect.add_argument('--cantidad',type=int,default=50,help='Meta de propuestas NUEVAS con contacto (1–200)')
    collect.add_argument('--csv',type=Path,help='Importar una lista propia en vez de consultar OSM')
    collect.add_argument('--sin-ia',action='store_true',help=argparse.SUPPRESS)
    collect.add_argument('--detener-archivo',type=Path,help=argparse.SUPPRESS)
    collect.add_argument('--actualizar',action='store_true',help='Revisar también negocios ya procesados')
    export=sub.add_parser('exportar',help='Importar seguimiento y regenerar Excel')
    export.add_argument('--verificar-visual',action='store_true')
    sync=sub.add_parser('importar-seguimiento',help='Importar una copia del Excel, validando conflictos')
    sync.add_argument('archivo',type=Path)
    analyze=sub.add_parser('analizar',help='Analizar páginas ya guardadas, sin volver a visitar webs')
    analyze.add_argument('--cantidad',type=int,default=20)
    analyze.add_argument('--actualizar',action='store_true')
    args=parser.parse_args(argv)
    try:
        settings=load_settings(args.config)
        if args.command=='zonas':
            print('Barrios: '+', '.join(ZONES)+'\nRubros: '+', '.join(CATEGORIES))
            return 0
        if args.command=='diagnostico':
            print(json.dumps({'ia':'Desactivada; no se necesita Ollama para buscar propuestas',
                'excel_node':str(excel.runtime(settings)),'base':str(settings.path(settings.database)),
                'salida':str(settings.path(settings.output))},ensure_ascii=False,indent=2))
            return 0
        path=settings.path(settings.database)
        path.parent.mkdir(parents=True,exist_ok=True)
        with FileLock(str(path)+'.lock',timeout=0):
            db=Database(path)
            try:
                synchronize(db,settings,str(args.archivo) if args.command=='importar-seguimiento' else None)
                if args.command=='ejecutar':
                    result=run(db,settings,zone=args.zona,category=args.rubro,limit=args.cantidad,
                        csv_path=args.csv,refresh=args.actualizar,
                        should_stop=lambda:bool(args.detener_archivo and args.detener_archivo.exists()),
                        log=lambda message:print(message,flush=True))
                elif args.command=='analizar':
                    if not 1<=args.cantidad<=200:
                        raise ValueError('Cantidad entre 1 y 200')
                    if not ai.doctor(settings)['ready']:
                        raise ValueError('Modelo local no disponible')
                    rows=db.conn.execute('''SELECT b.* FROM businesses b JOIN tracking t ON t.business_id=b.id
                        WHERE t.do_not_contact=0 AND (? OR b.analysis_json IS NULL)
                        AND EXISTS(SELECT 1 FROM pages p WHERE p.business_id=b.id) ORDER BY b.created_at LIMIT ?''',
                        (int(args.actualizar),args.cantidad)).fetchall()
                    for row in rows:
                        b=Business('',row['name'],row['zone'],row['category'])
                        pages=[Page(r['url'],r['title'],r['text']) for r in db.conn.execute('SELECT * FROM pages WHERE business_id=?',(row['id'],))]
                        value,seconds=ai.analyze(b,pages,settings)
                        db.finish(row['id'],'analizado' if value else 'sin evidencia web',value.model_dump() if value else None,settings.ollama_model,seconds)
                        print(f"{b.name}: {seconds:.1f}s",flush=True)
                destination=excel.export(db,settings,getattr(args,'verificar_visual',False))
                print('Excel guardado: '+str(destination),flush=True)
                if args.command=='ejecutar' and result['errors']:
                    return 2
                if args.command=='ejecutar' and not result['target_met']:
                    return 3
            finally:
                db.close()
        return 0
    except Timeout:
        print('Ya hay otra ejecución usando esta base. Esperá a que termine.',file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('Interrumpido. Lo ya guardado sigue en SQLite. Ejecutá exportar para recuperar el Excel.',file=sys.stderr)
        return 130
    except Exception as exc:
        print(f'No se completó: {type(exc).__name__}: {exc}',file=sys.stderr)
        print('No se borraron datos. Revisá la configuración o docs/TAREAS_MANUALES.md.',file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
