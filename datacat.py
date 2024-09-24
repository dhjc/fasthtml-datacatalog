from fasthtml.common import *
from hmac import compare_digest

db = database('data/udatasets.db')

class User: name:str; pwd:str
class Dataset:
    id:int;title:str;done:bool;name:str;details:str;priority:int
    def __ft__(self):
        show = AX(self.title, f'/datasets/{self.id}', 'current-dataset')
        edit = AX('edit',     f'/edit/{self.id}' , 'current-dataset')
        dt = '✅ ' if self.done else ''
        cts = (dt, show, ' | ', edit, Hidden(id="id", value=self.id), Hidden(id="priority", value="0"))
        return Ul(*cts, id=f'dataset-{self.id}')

users = db.create(User, pk='name')
datasets = db.create(Dataset)

login_redir = RedirectResponse('/login', status_code=303)

def before(req, sess):
    auth = req.scope['auth'] = sess.get('auth', None)
    if not auth: return login_redir
    datasets.xtra(name=auth)

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
                     SortableJS('.sortable'),
                     Script(markdown_js, type='module'))
                )
rt = app.route

@rt("/favicon.ico")
def favicon():
    return FileResponse("favicon.ico")

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

@rt("/{fname:path}.{ext:static}")
def get(fname:str, ext:str): return FileResponse(f'{fname}.{ext}')

@rt("/")
def get(auth):
    title = f"{auth}'s Data Catalogue: "
    top = Grid(H1(title), Div(A('logout', href='/logout'), style='text-align: right'))
    search = Div(Input(hx_post='/searchengine', hx_target="#results",hx_trigger="load, input changed delay:500ms, search", hx_indicator=".htmx-indicator",
            type="search", name="query", placeholder="Begin Typing To Search Datasets...",
        ),
    Span(Img(src="/img/bars.svg"), "Searching...", cls="htmx-indicator"),
    Table(
            Thead(Tr(Th("Search Results")),
            Tbody(id="results"),
            )
    ),
    Div(id="current-dataset"))
    new_inp = Input(id="new-title", name="title", placeholder="New Dataset")
    add = Form(Group(new_inp, Button("Add")),
               hx_post="/", target_id='results', hx_swap="afterbegin")
    return Title(title), Container(top, search, add)

@rt("/searchengine")
def post(query: str, limit: int = 10):
    datasets(order_by='priority')
    if query != "":
        return datasets(where=f'title like "%{query}%"')
    else:
        return datasets()

@rt("/reorder")
def post(id:list[int]):
    for i,id_ in enumerate(id): datasets.update({'priority':i}, id_)
    return tuple(datasets(order_by='priority'))

def clr_details(): return Div(hx_swap_oob='innerHTML', id='current-dataset')

@rt("/datasets/{id}")
def delete(id:int):
    datasets.delete(id)
    return clr_details()

@rt("/edit/{id}")
def get(id:int):
    res = Form(Group(Input(id="title"), Button("Save")),
        Hidden(id="id"), CheckboxX(id="done", label='Done'),
        Textarea(id="details", name="details", rows=10),
        hx_put="/", target_id=f'dataset-{id}', id="edit")
    return fill_form(res, datasets[id])

@rt("/")
def put(dataset: Dataset):
    return datasets.update(dataset), clr_details()

@rt("/")
def post(dataset:Dataset):
    new_inp =  Input(id="new-title", name="title", placeholder="New Dataset", hx_swap_oob='true')
    return datasets.insert(dataset), new_inp

@rt("/datasets/{id}")
def get(id:int):
    dataset = datasets[id]
    btn = Button('delete', hx_delete=f'/datasets/{dataset.id}',
                 target_id=f'dataset-{dataset.id}', hx_swap="outerHTML")
    return Div(H2(dataset.title), Div(dataset.details, cls="markdown"), btn)

serve()
