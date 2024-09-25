from fasthtml.common import *
from hmac import compare_digest
import time

# DATABASES
# ---------
# These are created first because one of them is needed to store the users,
# and login functionality is next.

db = database('data/datasets.db')

class User: name:str; pwd:str
class Dataset:
    id:int;title:str;favourite:bool;name:str;details:str;lastmod:str
    api_url:str;api_doc_url:str
    def __ft__(self):
        """Tells FastHTML how a dataset should be presented as HTML
        """
        show = AX(self.title, f'/datasets/{self.id}', 'current-dataset')
        edit = AX('edit',     f'/edit/{self.id}' , 'current-dataset')
        fave = '⭐ ' if self.favourite else ''
        lastmodified = f'last modified by {self.lastmod}'
        cts = (fave, show, ' | ', edit, ' | ', lastmodified, Hidden(id="id", value=self.id))
        return Li(*cts, id=f'dataset-{self.id}')

users = db.create(User, pk='name')
datasets = db.create(Dataset)

# APP SETUP

login_redir = RedirectResponse('/login', status_code=303)

def before(req, sess):
    auth = req.scope['auth'] = sess.get('auth', None)
    if not auth: return login_redir

markdown_js = """
import { marked } from "https://cdn.jsdelivr.net/npm/marked/lib/marked.esm.js";
import { proc_htmx} from "https://cdn.jsdelivr.net/gh/answerdotai/fasthtml-js@1.0.3/fasthtml.js";
proc_htmx('.markdown', e => e.innerHTML = marked.parse(e.textContent));
"""

def _not_found(req, exc): return Titled('Oh no!', Div('We could not find that page :('))

bware = Beforeware(before, skip=[r'/favicon\.ico', r'/static/.*', r'.*\.css', '/login'])
app = FastHTML(before=bware,
               exception_handlers={404: _not_found},
               hdrs=(picolink,
                     Style(':root { --pico-font-size: 100%; }'),
                     Script(markdown_js, type='module'))
                )

# ROUTES

rt = app.route

@rt("/{fname:path}.{ext:static}")
def get(fname:str, ext:str): return FileResponse(f'{fname}.{ext}') 


# Routes relating to user login
# -----------------------------
# Skip to the next section if you're interested only in
# the data catalog implementation.  None of this has been changes from FastHTML's idiomatic
# app example

@rt("/login")
def get():
    frm = Form(
        Input(id='name', placeholder='Name'),
        Input(id='pwd', type='password', placeholder='Password'),
        Button('login'),
        action='/login', method='post')
    return Titled("Login", frm)

@dataclass
class Login: name:str; pwd:str

@rt("/login")
def post(login:Login, sess):
    if not login.name or not login.pwd: return login_redir
    try: u = users[login.name]
    except NotFoundError: u = users.insert(login)
    if not compare_digest(u.pwd.encode("utf-8"), login.pwd.encode("utf-8")): return login_redir
    sess['auth'] = u.name
    return RedirectResponse('/', status_code=303)

@app.get("/logout")
def logout(sess):
    del sess['auth']
    return login_redir

# Routes relating to the Data Catalog
# -----------------------------------
# This is probably where you want to look first!

@rt("/")
def get(auth):
    title = f"Data Catalogue"
    welcome = f"Current user: {auth}"
    top = Grid(H1(title), H2(welcome), Div(A('logout', href='/logout'), style='text-align: right'))
    search = Div(Input(hx_post='/searchengine', hx_target="#results",hx_trigger="load, input changed delay:500ms, search", hx_indicator=".htmx-indicator",
            type="search", name="query", placeholder="Begin Typing To Search Datasets...",
        ),
    Span("Searching...", cls="htmx-indicator"),
    Table(
            Thead(Tr(Th("Search Results")),
            Tbody(id="results"),
            )
    ),
    Div(id="current-dataset"))
    new_inp = Input(id="title", placeholder="New Dataset")
    new_inp2 = Hidden(id='lastmod', value=auth)
    add = Form(Group(new_inp,new_inp2, Button("Add")),
               hx_post="/", target_id='results', hx_swap="afterbegin")
    return Title(title), Container(top, add, search)

@rt("/searchengine")
def post(query: str, limit: int = 10):
    if query != "":
        return datasets(where=f'title like "%{query}%" OR details like "%{query}%"', order_by='title')
    else:
        return datasets(order_by='title')

def clr_details(): return Div(hx_swap_oob='innerHTML', id='current-dataset')


@rt("/datasets/{id}")
def delete(id:int):
    datasets.delete(id)
    return clr_details()

@rt("/edit/{id}")
def get(id:int, auth):
    res = Form(Group(Input(id="title")),
        Hidden(id="id"), CheckboxX(id="favourite", label='Favourite'),
        Textarea(id="details", placeholder=f"Hi {auth}, in future changes to the catalog will include you username as metadata for any changes.", rows=10),
        Label('API Endpoint URL', Input(id='api_url',placeholder="Where should a user go to access your API?")),
        Label('API Documentation URL', Input(id='api_doc_url', placeholder="Where should a user go to access your API Documentation?")),
        Button("Save Dataset"),
        hx_put="/", target_id=f'dataset-{id}', id="edit")
    return fill_form(res, datasets[id])

@rt("/")
def put(dataset: Dataset, auth):
    dataset.lastmod = auth
    return datasets.update(dataset), clr_details()

@rt("/")
def post(dataset:Dataset, auth):
    new_inp =  Input(id="title", placeholder="New Dataset", hx_swap_oob='true')
    return datasets.insert(dataset), new_inp

@app.get
def models(make: str, sleep: int = 0):
    time.sleep(sleep)
    cars = {
        "audi": ["A1", "A4", "A6"],
        "toyota": ["Landcruiser", "Tacoma", "Yaris"],
        "bmw": ["325i", "325ix", "X5"],
    }
    return tuple(Option(v, value=v) for v in cars[make])

@rt("/datasets/{id}")
def get(id:int):
    dataset = datasets[id]
    btn = Button('delete', hx_delete=f'/datasets/{dataset.id}',
                 target_id=f'dataset-{dataset.id}', hx_swap="outerHTML")
    return Div(H2(dataset.title), A('API Endpoint URL',href=dataset.api_url), Br(), (A('API Documentation', href=dataset.api_url)), Div(dataset.details, cls="markdown"), btn, Hr())

# And go!
serve()
