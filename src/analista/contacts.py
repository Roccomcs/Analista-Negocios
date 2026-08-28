import json
import re
from urllib.parse import parse_qs, unquote, urljoin, urlsplit, urlunsplit
from bs4 import BeautifulSoup
from .models import Contact, Page, website_url
from .network import FetchError

EMAIL = re.compile(r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63}(?![\w.-])",re.I)
SOCIAL_HOSTS = {"instagram.com","facebook.com","fb.com","tiktok.com","linkedin.com"}
CONTACT_KINDS = {"instagram", "whatsapp", "email", "phone"}
MESSAGE_KINDS = CONTACT_KINDS - {"phone"}


def usable(contact: Contact, kinds=CONTACT_KINDS) -> bool:
    """Published contact, not an unverified search hit or stale evidence."""
    return (contact.kind in kinds and bool(contact.value)
            and not contact.verification.startswith(("candidato", "histórico")))


def host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def phone(value: str) -> str:
    value = value.strip().split(";")[0]
    digits = re.sub(r"\D", "", value)
    return ("+" if value.startswith("+") else "") + digits if 7 <= len(digits) <= 15 else ""


def from_value(kind: str, value: str, source: str, verification="publicado") -> Contact | None:
    value = value.strip()
    if kind == "email":
        match = EMAIL.fullmatch(value)
        value = value.lower() if match else ""
    elif kind == "phone":
        value = phone(value)
    elif kind == "whatsapp":
        if value.startswith(("http://","https://")):
            return from_link(value,source,verification)
        value = phone(value)
    elif kind in ("instagram","facebook"):
        if "/" not in value:
            value = f"https://{kind}.com/{value.lstrip('@')}/"
        link = website_url(value)
        if host(link) not in {f"{kind}.com","m.facebook.com"}:
            return None
        if kind == "instagram":
            return from_link(link, source, verification)
        value = link
    return Contact(kind,value,source,verification) if value else None


def from_link(url: str, source: str, verification="publicado") -> Contact | None:
    parts = urlsplit(url)
    domain = host(url)
    if parts.scheme == "mailto":
        return from_value("email",unquote(parts.path).split(",")[0],source,verification)
    if parts.scheme == "tel":
        return from_value("phone",unquote(parts.path),source,verification)
    if domain in ("wa.me","api.whatsapp.com","web.whatsapp.com","whatsapp.com"):
        if domain == "wa.me":
            number = parts.path.strip("/")
        else:
            number = parse_qs(parts.query).get("phone",[""])[0]
        if number and re.fullmatch(r"\+?\d{7,15}",number):
            return Contact("whatsapp","https://wa.me/"+number.lstrip("+"),source,verification)
        # Official short links have no visible phone; preserve them without guessing a number.
        if domain == "wa.me" and parts.path.startswith("/message/"):
            return Contact("whatsapp",urlunsplit((parts.scheme,parts.netloc,parts.path,"","")),source,verification)
    if domain == "instagram.com":
        path = parts.path.strip("/").split("/")
        if path and re.fullmatch(r"[\w.]{1,30}",path[0]) and path[0] not in {"p","reel","reels","stories","explore","accounts","direct","share"}:
            return Contact("instagram",f"https://www.instagram.com/{path[0]}/",source,verification)
    if domain in ("facebook.com","m.facebook.com","fb.com") and parts.path not in ("/sharer.php","/share.php","/dialog/share"):
        if parts.path.strip("/"):
            return Contact("facebook",url,source,verification)
    return None


def extract(html: str, url: str) -> tuple[Page,list[Contact],list[str]]:
    soup = BeautifulSoup(html,"html.parser")
    title = soup.title.get_text(" ",strip=True) if soup.title else ""
    contacts, links = [], []
    for anchor in soup.select("a[href]"):
        target = urljoin(url,anchor.get("href", "").strip())
        contact = from_link(target,url)
        if contact:
            contacts.append(contact)
        if target.startswith(("https://","http://")):
            # Preserve external public contact forms as candidates, without submitting anything.
            label = anchor.get_text(" ",strip=True).lower()
            if any(word in label for word in ("contacto","contactanos","contáctanos")) and host(target) != host(url) and not contact:
                contacts.append(Contact("form",target,url,"pendiente de revisar"))
            if host(target) == host(url):
                parts = urlsplit(target)
                if not parts.query:
                    links.append(urlunsplit((parts.scheme,parts.netloc,parts.path,"","")))
    # sameAs/contactPoint are explicitly published structured data, not guessed contacts.
    def walk(data):
        if isinstance(data,list):
            for item in data:
                walk(item)
        elif isinstance(data,dict):
            for key,value in data.items():
                if key in ("email","telephone") and isinstance(value,str):
                    c = from_value("email" if key == "email" else "phone",value,url)
                    if c:
                        contacts.append(c)
                elif key == "sameAs":
                    for link in value if isinstance(value,list) else [value]:
                        if isinstance(link,str):
                            c = from_link(link,url)
                            if c:
                                contacts.append(c)
                elif isinstance(value,(dict,list)):
                    walk(value)
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            walk(json.loads(script.get_text()))
        except (ValueError,RecursionError):
            pass
    for item in soup(["script","style","noscript","svg","template"]):
        item.decompose()
    text = re.sub(r"\s+"," ",soup.get_text(" ",strip=True))[:24000]
    for email in EMAIL.findall(text):
        c = from_value("email",email,url)
        if c:
            contacts.append(c)
    # Only label a printed phone as WhatsApp when the nearby text explicitly says WhatsApp.
    for match in re.finditer(r"(?i)whats\s*app\s*[:+\-–]?\s*(\+?\d[\d\s().-]{6,22}\d)",text):
        c = from_value("whatsapp",match.group(1),url)
        if c:
            contacts.append(c)
    # Printed landlines/mobile numbers remain phones, never inferred WhatsApp accounts.
    for match in re.finditer(r"(?i)\b(?:tel[eé]fono|tel\.?|fijo|llamanos|ll[aá]manos)\s*[:\-–]?\s*(\+?\d[\d ().-]{5,22}\d)", text):
        c = from_value("phone", match.group(1), url)
        if c:
            contacts.append(c)
    is_job_page=any(word in url.lower() for word in ('trabaja','empleo','career','jobs'))
    for form in soup.find_all("form"):
        if not is_job_page and form.find(["textarea"]) and ('contact' in url.lower() or 'contact' in str(form.get('id','')).lower()):
            contacts.append(Contact("form",url,url,"pendiente de revisar"))
    unique = {(c.kind,c.value,c.source):c for c in contacts}
    return Page(url,title,text),list(unique.values()),list(dict.fromkeys(links))


def research(website: str, http, max_pages: int, *, stop_on_contact=False):
    pages, contacts, notes = [],[],[]
    if not website:
        return pages,contacts,["Sin web publicada. Buscar por nombre y barrio; no asumir que no existe."]
    initial = from_link(website,website)
    if initial:
        contacts.append(initial)
        return pages,contacts,["La web informada es una red social; revisar manualmente. No se automatizan sesiones de Instagram."]
    queue, visited = [website],set()
    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        try:
            final,html = http.html(url)
            page,found,links = extract(html,final)
            if any(p.url == final for p in pages):
                continue
            pages.append(page)
            contacts.extend(found)
            if stop_on_contact and any(usable(c, MESSAGE_KINDS) for c in contacts):
                break
            keywords = ("contact","nosotros","about","reserva","turno","servicio","catalog")
            ranked = sorted((link for link in links if link not in visited),key=lambda link: ("contact" not in link.lower(),not any(k in link.lower() for k in keywords),len(link)))
            queue.extend(link for link in ranked if any(k in link.lower() for k in keywords)
                         and not any(k in link.lower() for k in ('trabaja','empleo','career','jobs')) and link not in queue)
        except FetchError as exc:
            notes.append(f"{url}: {exc}")
    if pages and all(len(p.text)<150 for p in pages):
        notes.append("Contenido escaso: puede requerir JavaScript. No se realizó auditoría visual.")
    if not contacts:
        notes.append("No se encontró contacto en las páginas accesibles; revisión manual pendiente.")
    return pages,list({(c.kind,c.value,c.source):c for c in contacts}.values()),notes
