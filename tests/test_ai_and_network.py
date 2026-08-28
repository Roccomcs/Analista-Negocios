import socket
import pytest
from analista.models import Analysis,Observation,Page
from analista.ai import validate_evidence,local_endpoint
from analista.settings import Settings
from analista.network import public_url,FetchError


def test_hallucinated_source_or_quote_rejected():
    a=Analysis(summary='Resumen',observations=[Observation(text='Servicios',source='https://negocio.com/',quote='Servicios de peluquería')],opportunities=[],questions=[],priority='media',draft='')
    p=[Page('https://negocio.com/','Título','Servicios de peluquería en Buenos Aires')]
    assert validate_evidence(a,p).priority=='media'
    a.observations[0].quote='Un texto inventado'
    with pytest.raises(ValueError):validate_evidence(a,p)


def test_no_evidence_no_draft():
    a=Analysis(summary='Sin datos',observations=[],opportunities=[],questions=[],priority='alta',draft='Oferta')
    result=validate_evidence(a,[])
    assert result.priority=='sin evidencia' and not result.draft


def test_generic_ai_template_rejected():
    a=Analysis(summary='Resumen de la evidencia recibida',observations=[],opportunities=['Oportunidad 1'],questions=[],priority='sin evidencia',draft='')
    with pytest.raises(ValueError,match='genérica'):
        validate_evidence(a,[])


def test_local_model_not_sent_to_cloud():
    with pytest.raises(ValueError):local_endpoint(Settings(ollama_url='https://nube.com'))


@pytest.mark.parametrize('url',['http://127.0.0.1/','http://10.0.0.1/','file:///etc/passwd','https://user:pass@negocio.com/','http://169.254.169.254/','http://[::1]/'])
def test_private_or_invalid_urls_blocked(url):
    with pytest.raises(FetchError):public_url(url)


def test_dns_private_target_blocked(monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**kw:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('192.168.0.1',443))])
    with pytest.raises(FetchError):public_url('https://negocio.com/')


def test_cross_domain_redirect_stops_before_fetching_new_site(monkeypatch):
    from analista import network
    monkeypatch.setattr(network,'public_url',lambda url:url)
    http=network.PublicHTTP(Settings())
    monkeypatch.setattr(http,'can_fetch',lambda url:True)
    class Response:
        status_code=302
        headers={'Location':'https://otro-negocio.com/'}
        def __enter__(self):return self
        def __exit__(self,*args):pass
    calls=[]
    def request(*args,**kwargs):
        calls.append(args[1]);return Response()
    monkeypatch.setattr(http.session,'request',request)
    with pytest.raises(FetchError,match='otro dominio'):
        http.html('https://negocio.com/')
    assert calls==['https://negocio.com/']
