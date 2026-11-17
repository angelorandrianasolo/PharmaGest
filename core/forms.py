"""Comportements communs aux formulaires."""

from django import forms


class BootstrapFormMixin:
    """Ajoute les classes Bootstrap à tous les champs d'un formulaire."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            classes = field.widget.attrs.get("class", "")
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = f"{classes} form-check-input".strip()
            elif isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs["class"] = f"{classes} form-select".strip()
            else:
                field.widget.attrs["class"] = f"{classes} form-control".strip()
