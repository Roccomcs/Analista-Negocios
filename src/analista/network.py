"""HTTP público acotado: sin sesiones privadas, formularios ni evasión de bloqueos."""
import ipaddress
import socket
import time
from urllib.parse import urlsplit, urljoin
from urllib.robotparser import RobotFileParser
import requests


class FetchError(RuntimeError):
    pass


def public_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
            raise ValueError("URL no pública")
        if parts.port not in (None,80,443):
            raise ValueError("Puerto no permitido")
        addresses = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError("La URL apunta a una red local o reservada")
    except (ValueError, OSError) as exc:
        raise FetchError(f"URL rechazada: {exc}") from exc
    return url


class PublicHTTP:
    def __init__(self, settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers["User-Agent"] = settings.user_agent
        self.last = {}
        self.robots = {}

    def request(self, method: str, url: str, *, limit=2_000_000, obey_robots=False, **kwargs):
        original_host=(urlsplit(url).hostname or '').removeprefix('www.')
        for _ in range(5):
            public_url(url)
            if obey_robots and (urlsplit(url).hostname or '').removeprefix('www.') != original_host:
                raise FetchError('Redirige a otro dominio; confirmar identidad manualmente antes de analizar')
            if obey_robots and not self.can_fetch(url):
                raise FetchError("robots.txt no permite revisar la página o no se pudo verificar")
            origin = urlsplit(url).netloc
            wait = self.settings.domain_delay - (time.monotonic()-self.last.get(origin,0))
            if wait > 0:
                time.sleep(wait)
            self.last[origin] = time.monotonic()
            try:
                with self.session.request(method,url,allow_redirects=False,timeout=(8,self.settings.request_timeout),stream=True,**kwargs) as response:
                    if response.status_code in (301,302,303,307,308):
                        url = urljoin(url,response.headers.get("Location",""))
                        # Never forward authorization or payload to a different redirect destination.
                        kwargs.pop("headers",None)
                        kwargs.pop("data",None)
                        kwargs.pop("params",None)
                        method = "GET"
                        continue
                    if response.status_code in (401,403,429):
                        raise FetchError(f"HTTP {response.status_code}: acceso restringido; no se reintenta ni evade")
                    response.raise_for_status()
                    chunks, count = [], 0
                    for chunk in response.iter_content(32768):
                        count += len(chunk)
                        if count > limit:
                            raise FetchError("Respuesta demasiado grande")
                        chunks.append(chunk)
                    body = b"".join(chunks)
                    encoding = response.encoding
                    if not encoding or encoding.lower() == "iso-8859-1":
                        encoding = "utf-8"
                    return response.url, body.decode(encoding,errors="replace"), response.headers.get("Content-Type","")
            except requests.RequestException as exc:
                # Do not leak API keys, query strings or response bodies to logs.
                raise FetchError(f"Error HTTP en {origin}: {type(exc).__name__}") from exc
        raise FetchError("Demasiadas redirecciones")

    def can_fetch(self, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self.robots:
            try:
                _, text, _ = self.request("GET", origin+"/robots.txt", limit=250_000)
                parser = RobotFileParser()
                parser.parse(text.splitlines())
                self.robots[origin] = parser
            except FetchError as exc:
                cause = exc.__cause__
                code = getattr(getattr(cause,"response",None),"status_code",None)
                self.robots[origin] = True if code in (404,410) else False
        policy = self.robots[origin]
        if isinstance(policy,bool):
            return policy
        delay = policy.crawl_delay(self.settings.user_agent) or policy.crawl_delay("*")
        if delay:
            wait = delay - (time.monotonic()-self.last.get(parts.netloc,0))
            if wait > 0:
                if wait > 30:
                    return False
                time.sleep(wait)
        return policy.can_fetch(self.settings.user_agent,url)

    def html(self, url: str):
        if not self.can_fetch(url):
            raise FetchError("robots.txt no permite revisar la página o no se pudo verificar")
        # Inspect redirects individually to honor the destination site's robots policy too.
        public_url(url)
        final, text, content_type = self.request("GET", url, obey_robots=True)
        if final != url and not self.can_fetch(final):
            raise FetchError("La página de destino no permite la revisión")
        if "html" not in content_type.lower():
            raise FetchError("No es una página HTML")
        return final,text
