"""Fields that deliberately have the name of an attribute of their parent class.

Pydantic warns at class creation when a field is called ``schema`` or ``count``,
because ``BaseModel`` and Beanie's ``Document`` have attributes of those names. Five
models here are called that on purpose: the name is the key stored in MongoDB or the
key in a public response, and both are contracts. Renaming the Python attribute behind
an alias would touch every reader for no change in behaviour, so the notice is declared
expected instead, per field and per model, where the model is defined (#762). The five
lines used to open every container log and were once the whole body of an alert.
"""
import re
import warnings


def expect_field_shadow(field: str, model: str) -> None:
    """Call just above ``class <model>``: its ``<field>`` shadows a parent attribute on purpose."""
    warnings.filterwarnings(
        "ignore",
        message=re.escape(f'Field name "{field}" in "{model}" shadows an attribute in parent'),
        category=UserWarning,
    )
