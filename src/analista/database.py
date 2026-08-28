"""SQLite es la fuente de verdad; el seguimiento editable tiene revisión optimista."""
import json
import sqlite3
from pathlib import Path
from uuid import uuid4
from .models import Business, Contact, Page, normalize, now

STATES = ("Nuevo", "Revisar", "Contactado", "Respondió", "Reunión", "Propuesta", "Cliente", "Descartado")


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=10000")
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version > 2:
            raise RuntimeError("La base pertenece a una versión más nueva de la aplicación.")
        if version == 1:
            backup = path.with_suffix('.v1-backup.sqlite3')
            if not backup.exists():
                self.backup(backup)
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS businesses (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, normalized_name TEXT NOT NULL,
          zone TEXT NOT NULL, category TEXT NOT NULL, address TEXT NOT NULL,
          normalized_address TEXT NOT NULL, website TEXT NOT NULL,
          latitude REAL, longitude REAL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          processed_at TEXT, processing_status TEXT NOT NULL DEFAULT 'pendiente',
          notes_processing TEXT NOT NULL DEFAULT '', details_json TEXT NOT NULL DEFAULT '{}', analysis_json TEXT,
          analysis_model TEXT, analysis_seconds REAL);
        CREATE TABLE IF NOT EXISTS sources (
          source_id TEXT PRIMARY KEY, business_id TEXT NOT NULL REFERENCES businesses(id),
          url TEXT NOT NULL, checked_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS contacts (
          business_id TEXT NOT NULL REFERENCES businesses(id), kind TEXT NOT NULL,
          value TEXT NOT NULL, source TEXT NOT NULL, verification TEXT NOT NULL,
          checked_at TEXT NOT NULL, UNIQUE(business_id,kind,value,source));
        CREATE TABLE IF NOT EXISTS pages (
          business_id TEXT NOT NULL REFERENCES businesses(id), url TEXT NOT NULL,
          title TEXT NOT NULL, text TEXT NOT NULL, checked_at TEXT NOT NULL,
          PRIMARY KEY(business_id,url));
        CREATE TABLE IF NOT EXISTS tracking (
          business_id TEXT PRIMARY KEY REFERENCES businesses(id),
          state TEXT NOT NULL DEFAULT 'Nuevo', owner TEXT NOT NULL DEFAULT '',
          notes TEXT NOT NULL DEFAULT '', next_action TEXT NOT NULL DEFAULT '',
          next_date TEXT NOT NULL DEFAULT '', do_not_contact INTEGER NOT NULL DEFAULT 0,
          revision INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS runs (
          id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
          zone TEXT NOT NULL, category TEXT NOT NULL, requested INTEGER NOT NULL,
          processed INTEGER NOT NULL DEFAULT 0, skipped INTEGER NOT NULL DEFAULT 0,
          errors INTEGER NOT NULL DEFAULT 0, seconds REAL, status TEXT NOT NULL);
        """)
        with self.conn:
            if 'qualified' not in {r[1] for r in self.conn.execute('PRAGMA table_info(runs)')}:
                self.conn.execute('ALTER TABLE runs ADD COLUMN qualified INTEGER NOT NULL DEFAULT 0')
            self.conn.execute('''CREATE TABLE IF NOT EXISTS proposals (
                business_id TEXT PRIMARY KEY REFERENCES businesses(id),
                qualified_at TEXT NOT NULL, run_id TEXT REFERENCES runs(id))''')
            if version == 1:
                # Already delivered contacts must not be sold to the user as new proposals.
                self.conn.execute('''INSERT OR IGNORE INTO proposals(business_id,qualified_at)
                    SELECT DISTINCT business_id,? FROM contacts
                    WHERE kind IN ('instagram','whatsapp','email','phone') AND value<>''
                    AND verification NOT LIKE 'candidato%' AND verification NOT LIKE 'histórico%' ''', (now(),))
            self.conn.execute('PRAGMA user_version=2')

    def close(self):
        self.conn.close()

    def backup(self, target: Path):
        target.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(target) as dest:
            self.conn.backup(dest)

    def upsert(self, b: Business) -> tuple[str, bool]:
        row = self.conn.execute("SELECT business_id FROM sources WHERE source_id=?", (b.source_id,)).fetchone()
        if row is None and b.address.strip():
            matches = self.conn.execute("SELECT id FROM businesses WHERE normalized_name=? AND normalized_address=? AND zone=?",
                (normalize(b.name), normalize(b.address), b.zone)).fetchall()
            if len(matches) == 1:
                row = (matches[0][0],)
        is_new = row is None
        bid = str(uuid4()) if is_new else row[0]
        timestamp = now()
        with self.conn:
            if is_new:
                self.conn.execute("""INSERT INTO businesses
                    (id,name,normalized_name,zone,category,address,normalized_address,website,latitude,longitude,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (bid,b.name,normalize(b.name),b.zone,b.category,b.address,
                    normalize(b.address),b.website,b.latitude,b.longitude,timestamp,timestamp))
                self.conn.execute("INSERT INTO tracking(business_id) VALUES(?)", (bid,))
            else:
                self.conn.execute("""UPDATE businesses SET name=?,normalized_name=?,updated_at=?,
                  website=CASE WHEN ?<>'' THEN ? ELSE website END,
                  address=CASE WHEN ?<>'' THEN ? ELSE address END,
                  normalized_address=CASE WHEN ?<>'' THEN ? ELSE normalized_address END WHERE id=?""",
                  (b.name,normalize(b.name),timestamp,b.website,b.website,b.address,b.address,b.address,normalize(b.address),bid))
            self.conn.execute("INSERT INTO sources VALUES(?,?,?,?) ON CONFLICT(source_id) DO UPDATE SET url=excluded.url,checked_at=excluded.checked_at",
                              (b.source_id,bid,b.source_url,timestamp))
            if b.details:
                self.conn.execute("UPDATE businesses SET details_json=? WHERE id=?", (json.dumps(b.details,ensure_ascii=False),bid))
            self.conn.execute("UPDATE contacts SET verification='histórico; no vuelto a encontrar' WHERE business_id=? AND source=?", (bid,b.source_url))
            for c in b.contacts:
                self._contact(bid,c)
        return bid, is_new

    def _contact(self, bid: str, c: Contact):
        self.conn.execute("INSERT INTO contacts VALUES(?,?,?,?,?,?) ON CONFLICT(business_id,kind,value,source) DO UPDATE SET checked_at=excluded.checked_at,verification=excluded.verification",
                          (bid,c.kind,c.value,c.source,c.verification,now()))

    def save_research(self, bid: str, pages: list[Page], contacts: list[Contact], notes: list[str]):
        with self.conn:
            # These are the pages from the current inspection, not a mixture with stale observations.
            self.conn.execute("""UPDATE contacts SET verification='histórico; no vuelto a encontrar'
                WHERE business_id=? AND source IN (SELECT url FROM pages WHERE business_id=?)""",(bid,bid))
            self.conn.execute("DELETE FROM pages WHERE business_id=?", (bid,))
            for p in pages:
                self.conn.execute("INSERT INTO pages VALUES(?,?,?,?,?)", (bid,p.url,p.title,p.text,now()))
            for c in contacts:
                self._contact(bid,c)
            self.conn.execute("UPDATE businesses SET notes_processing=?, updated_at=? WHERE id=?", ("\n".join(notes),now(),bid))

    def row(self, bid: str):
        return self.conn.execute("SELECT b.*,t.do_not_contact,t.state FROM businesses b JOIN tracking t ON t.business_id=b.id WHERE b.id=?", (bid,)).fetchone()

    def current_contacts(self, bid: str):
        return [Contact(r['kind'],r['value'],r['source'],r['verification']) for r in
                self.conn.execute('SELECT * FROM contacts WHERE business_id=?', (bid,))
                if not r['verification'].startswith(('candidato','histórico'))]

    def was_proposed(self, bid: str):
        return self.conn.execute('SELECT 1 FROM proposals WHERE business_id=?', (bid,)).fetchone() is not None

    def qualify(self, bid: str, run_id: str) -> bool:
        from .contacts import usable
        row = self.row(bid)
        if row['do_not_contact'] or row['state'] not in ('Nuevo','Revisar'):
            return False
        if not any(usable(c) for c in self.current_contacts(bid)):
            return False
        with self.conn:
            return self.conn.execute('INSERT OR IGNORE INTO proposals VALUES(?,?,?)', (bid,now(),run_id)).rowcount == 1

    def finish_contacts(self, bid: str, status: str):
        # Keep older IA analyses in SQLite; the new contact flow never overwrites them.
        with self.conn:
            self.conn.execute('UPDATE businesses SET processed_at=?,processing_status=? WHERE id=?', (now(),status,bid))

    def finish(self, bid: str, status: str, analysis=None, model=None, seconds=None):
        with self.conn:
            self.conn.execute("UPDATE businesses SET processed_at=?,processing_status=?,analysis_json=?,analysis_model=?,analysis_seconds=? WHERE id=?",
                              (now(),status,json.dumps(analysis,ensure_ascii=False) if analysis else None,model,seconds,bid))

    def export_data(self):
        data = {}
        for key, sql in {
            "businesses":"SELECT * FROM businesses ORDER BY zone,name,id",
            "contacts":"SELECT * FROM contacts ORDER BY business_id,kind,value",
            "sources":"SELECT * FROM sources ORDER BY business_id",
            "pages":"SELECT business_id,url,title,checked_at FROM pages",
            "tracking":"SELECT t.*,b.name FROM tracking t JOIN businesses b ON b.id=t.business_id ORDER BY b.zone,b.name,b.id",
            "runs":"SELECT * FROM runs ORDER BY started_at DESC LIMIT 100",
            "proposals":"SELECT * FROM proposals"
        }.items():
            data[key] = [dict(r) for r in self.conn.execute(sql)]
        return data

    def import_tracking(self, records: list[dict]) -> int:
        from datetime import date
        updates, seen = [], set()
        for record in records:
            bid = str(record.get("ID", "")).strip()
            if not bid:
                continue
            if bid in seen:
                raise ValueError(f"ID duplicado en Seguimiento: {bid}")
            seen.add(bid)
            old = self.conn.execute("SELECT * FROM tracking WHERE business_id=?", (bid,)).fetchone()
            if old is None:
                raise ValueError(f"ID desconocido en Seguimiento: {bid}")
            state = str(record.get("Estado", old['state']) or "Nuevo")
            if state not in STATES:
                raise ValueError(f"Estado inválido: {state}")
            next_date = str(record.get("Próxima fecha", old['next_date']) or "").strip()
            if next_date:
                date.fromisoformat(next_date)
            flag = str(record.get("No contactar", 'Sí' if old['do_not_contact'] else 'No') or "No")
            if flag not in ("Sí", "No"):
                raise ValueError("No contactar debe ser Sí o No")
            values = (state, str(record.get("Responsable", old['owner']) or ""), str(record.get("Notas", old['notes']) or ""),
                      str(record.get("Próxima acción", old['next_action']) or ""), next_date, int(flag == "Sí"))
            original = tuple(old[k] for k in ("state","owner","notes","next_action","next_date","do_not_contact"))
            if values == original:
                continue
            try:
                revision = int(record.get("Revisión"))
            except (ValueError,TypeError):
                raise ValueError(f"Revisión inválida para {bid}") from None
            if revision != old["revision"]:
                raise ValueError(f"Excel desactualizado para {bid}: no se sobrescribió el seguimiento.")
            updates.append((*values,bid,revision))
        with self.conn:
            for values in updates:
                self.conn.execute("""UPDATE tracking SET state=?,owner=?,notes=?,next_action=?,next_date=?,do_not_contact=?,revision=revision+1
                                    WHERE business_id=? AND revision=?""",values)
        return len(updates)
