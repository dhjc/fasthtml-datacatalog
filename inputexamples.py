from fasthtml.common import *

import re
strict_email = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,63}$'


app,rt = fast_app()

@rt('/')
def get():
    return Div(H3('Signup Form'),
        Form(
            Div(
                Label('Email Address'),
                Input(name='email', hx_post='/contact/email', hx_indicator='#ind'),
                hx_target='this',
                hx_swap='outerHTML'
            ),
            Label('Select your favorite data format...'),
            Select(
                Option('Select here', selected='', disabled='', value=''),
                Option('xlsx'),
                Option('csv'),
                Option('parquet'),
                Option('json'),
                Option('xml'),
                name='favorite-dataformat',
                aria_label='Select your favorite data format...',
                required=''
            ),
            Label('Date of Entry'),
            Input(type='date', lang="en-GB"),
            Fieldset(
                Legend('Yes or No?'),
                Label(
                    Input(type='radio', name='yesno', checked=''),
                    'Yes'
                ),
                Label(
                    Input(type='radio', name='yesno'),
                    'No'
                ),
                Label(
                    Input(type='radio', name='yesno'),
                    'Maybe?'
                )
            )

        ))



@rt('/contact/email')
def post(email: str):
    if re.match(strict_email, email):
        return Div(
            Label('Email Address'),
            Input(name='email', hx_post='/contact/email', hx_indicator='#ind', value=email, aria_invalid="false"),
            hx_target='this',
            hx_swap='outerHTML',
            cls='success'
        )
    else:
        return Div(
            Label('Email Address'),
            Input(name='email', hx_post='/contact/email', hx_indicator='#ind', value=email, aria_invalid="true"),
            Small('Error :(', cls='error-message', role="alert"),
            hx_target='this',
            hx_swap='outerHTML',
            cls='error'
        )

serve()