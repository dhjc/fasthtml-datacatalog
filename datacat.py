from fasthtml.common import * # https://docs.fastht.ml/
from hmac import compare_digest # This is used in login to make it more secure
import pandas as pd # For working with the questions.csv file - can probably use csv instead
import re # For validating emails
import csv # For extracting the fields required to build the dataclass
from typing import Dict, Type # In the creation of the dataclass - need to learn metaprogramming!

# DATABASES
# ---------
# These are created first because one of them is needed to store the users,
# and login functionality is next.

db = database('data/datasets.db') # SQLite via fastlite using MiniDataAPI Spec (https://docs.fastht.ml/explains/minidataapi.html)


# Easy one first :) Create class, use that to create the db, set the primary key.
# Next one is fundamentally the same but much more complex.
class User: name:str; pwd:str
users = db.create(User, pk='name')

def generate_dataset_class(csv_path: str) -> Type:
    """Build a dataclass, in turn the database, using csv file as input.

    This was generated by claude.ai and works - but I need to learn about
    metaprogramming!

    The goal of this is to avoid having to maintain a hardcoded database
    definition in this file.  Edits made only in questions.csv.
    """

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

    On the front page, when asked to show a dataset entry, this is
    what shows.

    https://docs.fastht.ml/tutorials/by_example.html#ft-objects-and-html

    Returns a list element - 
    """
    show = AX(self.dataset_name_text, f'/datasets/{self.id}', 'current-dataset')
    # Convenience wrapper to A to take advantage of HTMX (htmx.org) - https://docs.fastht.ml/api/xtend.html#ax
    # Fasthtml uses function names matching HTML tags, won't comment each one.
    edit = AX('edit',     f'/edit/{self.id}' , 'current-dataset')
    fave = '⭐ ' if self.favourite else ''
    lastmodified = f'last modified by {self.lastmod}'
    content = (fave, show, ' | ', edit, ' | ', lastmodified, Hidden(id="id", value=self.id))
    # Does the asterisk do anything? Left for now...
    return Li(*content, id=f'dataset-{self.id}')

datasets = db.create(Dataset)

# APP SETUP

# From this point on interactions with questions.csv are via pandas
questions_df = pd.read_csv('questions.csv').set_index('named')

# Direct to login directory if not logged on.
login_redir = RedirectResponse('/login', status_code=303)

def before(req, sess):
    auth = req.scope['auth'] = sess.get('auth', None)
    if not auth: return login_redir

def _not_found(req, exc): return Titled('Oh no!', Div('We could not find that page :('))

bware = Beforeware(before, skip=[r'/favicon\.ico', r'/static/.*', r'.*\.css', '/login'])
app = FastHTML(before=bware,
               exception_handlers={404: _not_found},
               hdrs=(picolink,
                     Style(':root { --pico-font-size: 100%; }'),
                     )
                )

# ROUTES

rt = app.route

# If you use fast_app instead of FastHTML above, this next bit isn't needed
@rt("/{fname:path}.{ext:static}")
def get(fname:str, ext:str): return FileResponse(f'{fname}.{ext}') 


# Routes relating to user login
# -----------------------------
# Skip to the next section if you're interested only in
# the data catalog implementation.  None of this has been changed from FastHTML's idiomatic
# app example

@rt("/login")
def get():
    frm = Form(
        Input(id='name', placeholder='Name              If this is your first use, as long as you pick a unique name an account will be set up'),
        Input(id='pwd', type='password', placeholder='Password        ***Make it unique, do not reuse a password** Admins can see this in plain text!'),
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
    """What the user sees on login - GET /

    Searches result in a request to POST /searchengine

    New dataset requests are handled by POST /
    """
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
    new_inp = Input(id="dataset_name_text", placeholder="New Dataset")
    new_inp2 = Hidden(id='lastmod', value=auth)
    add = Form(Group(new_inp,new_inp2, Button("Add")),
               hx_post="/", target_id='results', hx_swap="afterbegin")
    return Title(title), Container(top, add, search)

@rt("/searchengine")
def post(query: str, limit: int = 5):
    """When a user searches, the query goes down this route, the user sees what is returned
    """
    if query != "":
        return datasets(where=f'dataset_name_text like "%{query}%" OR details_text like "%{query}%"', order_by='dataset_name_text', limit=limit)
    else:
        return datasets(order_by='dataset_name_text', limit=limit)

def clr_details(): return Div(hx_swap_oob='innerHTML', id='current-dataset') # Returns a blank div to #current-dataset, use in DEL /datasets/id to remove details from view after delete

@rt("/datasets/{id}")
def delete(id:int):
    """Handles delete requests
    """
    datasets.delete(id)
    return clr_details()

@rt('/contact/email/{idx}')
async def post(req, idx: str):
    """Handles email validation (front-end info only, not enforced)
    """
    # Extract form data
    strict_email = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,63}$'
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
    """Automates creation of suitbaly formated questions from the info in questions.csv

    Goal here is to avoid hardcoding anything, allowing users to control questions
    just by using the questions.csv file.

    Returns HTML to feed into the edit form at GET /edit/id
    """
    def create_select(idx, row):
        options = row['options'].split('|') if pd.notna(row['options']) else []
        return Div(
            Label(row['full_question']),
            Select(
                *[Option(opt.strip(), value=opt.strip()) for opt in options],
                id=idx, name=idx
            )
        )

    def create_radio(idx, row):
        options = row['options'].split('|') if pd.notna(row['options']) else []
        return Div(
            Label(row['full_question']),
            *[Label(
                Input(type="radio", name=idx, value=opt.strip()),
                opt.strip()
            ) for opt in options],
            cls="radio-group"
        )

    def create_email(idx, row):
        return Div(
            Label('Email Address'),
            Input(id=idx, type='email', placeholder=row.get('placeholder_text', ''), 
                 name=idx,
                 hx_post=f'/contact/email/{idx}',
                 hx_indicator='#ind'),
            hx_target='this',
            hx_swap='outerHTML'
        )

    def create_date(idx, row):
        return Div(Label(
            row['full_question'],
            Input(id=idx, type='date', placeholder=row.get('placeholder_text', ''))
        ))

    def create_text(idx, row):
        return Div(Label(
            row['full_question'],
            Input(id=idx, type='text', placeholder=row.get('placeholder_text', ''))
        ))

    type_handlers = {
        'select': create_select,
        'radio': create_radio,
        'email': create_email,
        'date': create_date,
        'text': create_text
    }
    
    def get_handler_for_field(idx, row):
        htmltype = row['htmltype']
        if htmltype not in type_handlers:
            raise ValueError(f"Unknown input type '{htmltype}' for field: {idx}")
        return type_handlers[htmltype]

    list_to_exclude=['lastmod', 'id', 'favourite']
    included_questions_df = questions_df.query('named not in @list_to_exclude')
    
    result = []
    for idx, row in included_questions_df.iterrows():
        handler = get_handler_for_field(idx, row)
        result.append(handler(idx, row))
    
    return result

@rt("/edit/{id}")
def get(id:int, auth):
    """When a user clicks the edit button, this is what they see

    Saving the dataset via the button invokes PUT /
    """
    questions = create_question_labels(questions_df)

    res = Form(
        Hidden(id="id"), CheckboxX(id="favourite", label='Favourite'),
        *questions,
        Button("Save Dataset"),
        hx_put="/", target_id=f'dataset-{id}', id="edit", hx_swap='outerHTML')
    return fill_form(res, datasets[id])

@rt("/")
def put(dataset: Dataset, auth):
    """Handles updates to a dataset PUT /
    """
    dataset.lastmod = auth
    return datasets.update(dataset), clr_details()

@rt("/")
def post(dataset:Dataset):
    """Handles the addition of a new dataset POST /
    """
    # Doesn't use auth as it is entered as a hidde value in the form that creates this dataset in get /
    new_inp =  Input(id="dataset_name_text", placeholder="New Dataset", hx_swap_oob='true')
    return datasets.insert(dataset), new_inp

def create_answer_paragraphs(dataset, questions_df):
    """When viewing the dataset, this is what is rendered

    At the moment all it really does is ensure that links show as links

    Used in GET /datasets/id
    """
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
    """This is what a user sees when they click to view a specific dataset entry

    This is also where the option to delete is.
    """
    dataset = datasets[id]
    answer_paragraphs = create_answer_paragraphs(dataset, questions_df)
    btn = Button('delete', hx_delete=f'/datasets/{dataset.id}',
                 target_id=f'dataset-{dataset.id}', hx_swap="outerHTML")

    return Div(H2(dataset.dataset_name_text), 
               *answer_paragraphs,
               btn, Hr())

# And go!
serve()
