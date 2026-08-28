"""Collect contacts until the NEW proposal target is met, without any IA calls."""
import time
from pathlib import Path
from uuid import uuid4
from .contacts import research, from_link, usable, MESSAGE_KINDS
from .models import now
from .network import PublicHTTP
from .providers import OSMProvider, read_csv, candidate_order


def run(db, settings, *, zone, category, limit, csv_path=None, use_ai=False,
        refresh=False, log=print, should_stop=lambda: False):
    if not 1 <= limit <= 200:
        raise ValueError('La meta debe estar entre 1 y 200 propuestas nuevas por corrida.')
    if use_ai:
        raise ValueError('La búsqueda de propuestas ya no utiliza IA.')
    http = PublicHTTP(settings)
    started = time.monotonic()
    rid = str(uuid4())
    with db.conn:
        db.conn.execute('INSERT INTO runs(id,started_at,zone,category,requested,status) VALUES(?,?,?,?,?,?)',
                        (rid, now(), zone, category, limit, 'en curso'))
    processed = skipped = errors = qualified = 0
    status = 'fuente agotada'
    seen = set()
    try:
        log(f'Buscando {limit} propuestas NUEVAS en {zone} · {category}. Sin IA.')
        if csv_path:
            businesses = read_csv(Path(csv_path), zone, category)
            warnings = ['CSV propio: verificar procedencia de los contactos.']
        else:
            businesses, warnings = OSMProvider(settings, http).discover(zone, category, refresh)
        for message in warnings:
            log(message)
        truncated = any('máximo de candidatos' in message for message in warnings)
        log(f'Candidatos disponibles: {len(businesses)}. La meta cuenta negocios con contacto, no páginas visitadas.')
        for business in sorted(businesses, key=candidate_order):
            if qualified >= limit:
                break
            if should_stop():
                status = 'detenido'
                break
            if business.website:
                direct = from_link(business.website, business.source_url or business.website,
                                   'directorio público; corroborar identidad')
                if direct:
                    business.contacts.append(direct)
            bid, _ = db.upsert(business)
            previous = db.row(bid)
            was_proposed = db.was_proposed(bid)
            if (bid in seen or previous['do_not_contact'] or previous['state'] not in ('Nuevo', 'Revisar')
                    or (was_proposed and not refresh)):
                skipped += 1
                continue
            seen.add(bid)
            existing = db.current_contacts(bid)
            # Updated directory/CSV contacts can qualify a previously empty record.
            if previous['processed_at'] and not refresh and not any(usable(c) for c in existing):
                skipped += 1
                continue
            processed += 1
            log(f'[{qualified}/{limit} propuestas · {processed} revisados] {business.name}')
            business.website = previous['website']
            try:
                # A published DM/email channel already meets the goal. No web request needed.
                if business.website and (refresh or not any(usable(c, MESSAGE_KINDS) for c in existing)):
                    pages, contacts, notes = research(business.website, http, settings.max_pages,
                                                      stop_on_contact=True)
                    db.save_research(bid, pages, contacts, notes)
                elif not existing and not business.website:
                    db.save_research(bid, [], [], ['Sin contacto publicado; buscar manualmente por nombre y barrio.'])
                contactable = any(usable(c) for c in db.current_contacts(bid))
                db.finish_contacts(bid, 'con contacto' if contactable else 'sin contacto publicado')
                if db.qualify(bid, rid):
                    qualified += 1
                    log(f'  Propuesta nueva: {qualified}/{limit}.')
                elif contactable:
                    log('  Contacto actualizado; no se cuenta nuevamente.')
                else:
                    log('  Sin contacto útil. Se guarda en Pendientes y continúa la búsqueda.')
            except Exception as exc:
                errors += 1
                log(f'  Error guardado; continúa con otro negocio: {type(exc).__name__}: {str(exc)[:220]}')
                with db.conn:
                    db.conn.execute("UPDATE businesses SET notes_processing=notes_processing||?,processing_status='error' WHERE id=?",
                                    ('\n'+str(exc)[:500], bid))
                # An inaccessible website does not invalidate a published phone.
                if db.qualify(bid, rid):
                    qualified += 1
                    log(f'  Conserva contacto publicado: {qualified}/{limit} propuestas.')
        if qualified >= limit:
            status = 'meta alcanzada'
        elif status != 'detenido':
            status = 'límite de candidatos' if truncated else 'fuente agotada'
        log(f'RESULTADO: {qualified}/{limit} propuestas nuevas · {processed} revisados · {skipped} omitidos · {errors} errores.')
        if status == 'fuente agotada':
            log('No quedan candidatos nuevos en esta consulta. Elegí otro rubro/barrio o aportá un CSV. No se inventan contactos.')
        elif status == 'límite de candidatos':
            log('Consulta parcial: se llegó al límite de candidatos. Usá un rubro más específico; no se agotó todo el barrio.')
        elif status == 'detenido':
            log('Detenido por el usuario. Se exportarán los resultados reunidos hasta ahora.')
    except BaseException:
        status = 'interrumpido'
        raise
    finally:
        elapsed = time.monotonic() - started
        with db.conn:
            db.conn.execute('UPDATE runs SET finished_at=?,processed=?,qualified=?,skipped=?,errors=?,seconds=?,status=? WHERE id=?',
                            (now(), processed, qualified, skipped, errors, elapsed, status, rid))
        http.session.close()
        log(f'Tiempo de búsqueda: {elapsed:.1f} segundos (sin Excel; no se utilizó IA).')
    return {'processed': processed, 'qualified': qualified, 'skipped': skipped, 'errors': errors,
            'seconds': elapsed, 'status': status, 'target_met': qualified >= limit, 'run_id': rid}
