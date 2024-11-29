from fasthtml.common import *
from hmac import compare_digest
import time
import pandas as pd

import re
strict_email = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,63}$'

# Add validation: https://gallery.fastht.ml/split/dynamic_user_interface/inline_validation

# DATABASES
# ---------
# These are created first because one of them is needed to store the users,
# and login functionality is next.

db = database('data/datasets.db')

class User: name:str; pwd:str

import csv
from typing import Dict, Type

def generate_dataset_class(csv_path: str) -> Type:
    # Read field definitions
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        fields = {row['named']: row['type'] for row in reader}
    
    # Generate class code
    class_code = ["class Dataset:"]
    annotations = []
    
    for name, type_str in fields.items():
        annotations.append(f"    {name}: {type_str}")
    
    # Join all parts
    complete_code = "\n".join(class_code + annotations)
    
    # Create and return class
    namespace = {}
    exec(complete_code, namespace)
    return namespace['Dataset']

Dataset = generate_dataset_class('questions.csv')

@patch
def __ft__(self:Dataset):
    """Tells FastHTML how a dataset should be presented as HTML
    """
    show = AX(self.dataset_name, f'/datasets/{self.id}', 'current-dataset')
    edit = AX('edit',     f'/edit/{self.id}' , 'current-dataset')
    fave = '⭐ ' if self.favourite else ''
    lastmodified = f'last modified by {self.lastmod}'
    cts = (fave, show, ' | ', edit, ' | ', lastmodified, Hidden(id="id", value=self.id))
    return Li(*cts, id=f'dataset-{self.id}')

users = db.create(User, pk='name')
datasets = db.create(Dataset)

questions_df = pd.read_csv('questions.csv').set_index('named')

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

# If you use fast_app instead of FastHTML above, this next bit isn't needed
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
    new_inp = Input(id="dataset_name", placeholder="New Dataset")
    new_inp2 = Hidden(id='lastmod', value=auth)
    add = Form(Group(new_inp,new_inp2, Button("Add")),
               hx_post="/", target_id='results', hx_swap="afterbegin")
    return Title(title), Container(top, add, search)

@rt("/searchengine")
def post(query: str, limit: int = 10):
    if query != "":
        return datasets(where=f'dataset_name like "%{query}%" OR details like "%{query}%"', order_by='dataset_name')
    else:
        return datasets(order_by='dataset_name')

def clr_details(): return Div(hx_swap_oob='innerHTML', id='current-dataset')


@rt("/datasets/{id}")
def delete(id:int):
    datasets.delete(id)
    return clr_details()

@rt('/contact/email/{idx}')
async def post(req, idx: str):
    # Extract form data
    form_data = await req.form()
    email = form_data.get(idx)  # Get email using the field name

    if re.match(strict_email, email):
        return Div(
            Label('Email Address'),
            Input(name=idx, hx_post=f'/contact/email/{idx}', hx_indicator='#ind', 
                  value=email, aria_invalid="false"),
            hx_target='this',
            hx_swap='outerHTML',
            cls='success'
        )
    else:
        return Div(
            Label('Email Address'),
            Input(name=idx, hx_post=f'/contact/email/{idx}', hx_indicator='#ind',
                  value=email, aria_invalid="true"),
            Small('Error :(', cls='error-message', role="alert"),
            hx_target='this',
            hx_swap='outerHTML',
            cls='error'
        )

def create_question_labels(questions_df):
    list_to_exclude=['lastmod', 'name', 'id', 'favourite']
    included_questions_df = questions_df.query('named not in @list_to_exclude')
    print(included_questions_df)
    return [
        Div(Label(
            row.iloc[1],
            Input(id=idx, type=row.iloc[3],placeholder=row.iloc[2])
        )) if 'email' not in idx else
        Div(
            Label('Email Address'),
            Input(id=idx, type=row.iloc[3], placeholder=row.iloc[2], 
                 name=idx,  # For database storage
                 hx_post=f'/contact/email/{idx}',  # Pass field name in URL
                 hx_indicator='#ind'),
            hx_target='this',
            hx_swap='outerHTML'
        )
        for idx, row in included_questions_df.iterrows()
    ]

#[x if condition else y for x in items]

@rt("/edit/{id}")
def get(id:int, auth):
    questions = create_question_labels(questions_df)

    res = Form(Group(Input(id="dataset_name")),
        Hidden(id="id"), CheckboxX(id="favourite", label='Favourite'),
        Textarea(id="details", placeholder=f"Hi {auth}, in future changes to the catalog will include you username as metadata for any changes.", rows=10),
        *questions,
        Button("Save Dataset"),
        hx_put="/", target_id=f'dataset-{id}', id="edit")
    return fill_form(res, datasets[id])

@rt("/")
def put(dataset: Dataset, auth):
    dataset.lastmod = auth
    return datasets.update(dataset), clr_details()

@rt("/")
def post(dataset:Dataset):
    # Doesn't use auth as it is entered as a hidde value in the form that creates this dataset in get /
    new_inp =  Input(id="dataset_name", placeholder="New Dataset", hx_swap_oob='true')
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

def create_answer_paragraphs(dataset, questions_df):
    paragraphs = []
    for idx, row in questions_df.iterrows():
        # Get the answer value from the dataset using the index name
        answer = getattr(dataset, idx, None)
        if answer:
            # Create a paragraph with question text and answer link
            if 'url' in idx:
                p = P(
                    f"{row.iloc[1]}: ",  # Question text
                    A("Link", href=answer)
                )
            else:
                p = P(
                    f"{row.iloc[1]}: {answer}"
                )
            paragraphs.append(p)
    return paragraphs

@rt("/datasets/{id}")
def get(id:int):
    dataset = datasets[id]
    btn = Button('delete', hx_delete=f'/datasets/{dataset.id}',
                 target_id=f'dataset-{dataset.id}', hx_swap="outerHTML")
    answer_paragraphs = create_answer_paragraphs(dataset, questions_df)

    return Div(H2(dataset.dataset_name), 
               *answer_paragraphs,
               Div(dataset.details, cls="markdown"), btn, Hr())

# leave this here
# P(questions_df.loc['answer_with_url'].iloc[1]+": ", A("Link",href=dataset.answer_with_url))

# And go!
serve()
