from analista.contacts import extract,from_link,from_value,research
from analista.network import FetchError


def test_contacts_are_separated_and_tracked():
    html='''<title>Prueba</title><a href="tel:+541145678900">Llamar</a>
    <a href="https://wa.me/5491155550000?text=hola">WhatsApp</a>
    <a href="https://www.instagram.com/negocio/">IG</a><a href="mailto:info@negocio.com">Email</a>
    <a href="https://instagram.com/p/123">Post</a><p>Ventas: ventas@negocio.com</p>'''
    page,contacts,_=extract(html,'https://negocio.com/')
    assert {c.kind for c in contacts}=={'phone','whatsapp','instagram','email'}
    assert len([c for c in contacts if c.kind=='instagram'])==1
    assert all(c.source=='https://negocio.com/' for c in contacts)
    assert [c.value for c in contacts if c.kind=='whatsapp']==['https://wa.me/5491155550000']


def test_phone_never_becomes_whatsapp_without_label():
    _,contacts,_=extract('<a href="tel:+541145678900">Teléfono</a>','https://negocio.com/')
    assert [c.kind for c in contacts]==['phone']
    assert from_link('https://whatsapp.com/','https://negocio.com/') is None


def test_printed_whatsapp_and_structured_contacts():
    html='''<p>WhatsApp: +54 9 11 5555 0000</p>
    <script type="application/ld+json">{"@type":"LocalBusiness","email":"info@negocio.com","sameAs":["https://instagram.com/negocio"]}</script>'''
    _,contacts,_=extract(html,'https://negocio.com/')
    assert {c.kind for c in contacts}=={'whatsapp','email','instagram'}
    assert from_value('instagram','@negocio','fuente').value=='https://www.instagram.com/negocio/'


def test_same_host_links_and_no_fake_email():
    _,contacts,links=extract('<a href="/contacto">Contacto</a><a href="https://otro.com/">Otro</a>', 'https://negocio.com/')
    assert not contacts
    assert links==['https://negocio.com/contacto']


def test_blocked_site_is_not_claimed_missing_business():
    class Blocked:
        def html(self,url):raise FetchError('robots.txt restringido')
    pages,contacts,notes=research('https://negocio.com/',Blocked(),4)
    assert not pages and not contacts
    assert 'robots.txt' in notes[0]


def test_social_url_not_scraped():
    pages,contacts,notes=research('https://www.instagram.com/negocio/',None,4)
    assert not pages and contacts[0].kind=='instagram'
    assert 'manualmente' in notes[0]


def test_job_application_form_is_not_a_sales_contact():
    html='<form id="contact"><textarea></textarea><input type="email"></form>'
    _,contacts,_=extract(html,'https://negocio.com/trabaja-con-nosotros/')
    assert not any(c.kind=='form' for c in contacts)


def test_printed_landline_and_invalid_instagram_post():
    _,contacts,_=extract('<p>Teléfono: 4545-8899</p><p>Dirección: Calle 4555</p>', 'https://local.example/')
    assert [(c.kind,c.value) for c in contacts]==[('phone','45458899')]
    assert from_value('instagram','https://instagram.com/p/postid/','fuente') is None


def test_fast_research_stops_after_first_message_channel():
    class HTTP:
        calls=[]
        def html(self,url):
            self.calls.append(url)
            return url,'<a href="mailto:info@local.example">Correo</a><a href="/contacto">Contacto</a>'
    http=HTTP()
    pages,contacts,_=research('https://local.example/',http,4,stop_on_contact=True)
    assert len(http.calls)==1 and len(pages)==1 and contacts[0].kind=='email'


def test_phone_only_keeps_looking_for_direct_messages_and_prioritizes_contact_page():
    class HTTP:
        calls=[]
        def html(self,url):
            self.calls.append(url)
            if url.endswith('/contacto'):
                return url,'<a href="https://instagram.com/local/">Instagram</a>'
            return url,'<a href="tel:45458899">Tel</a><a href="/about">Nosotros</a><a href="/contacto">Contacto</a>'
    http=HTTP()
    _,contacts,_=research('https://local.example/',http,2,stop_on_contact=True)
    assert http.calls[-1]=='https://local.example/contacto'
    assert {c.kind for c in contacts}=={'phone','instagram'}
