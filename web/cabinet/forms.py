from django import forms


class BudgetForm(forms.Form):
    limit = forms.DecimalField(
        label="Лимит повышения",
        max_digits=14,
        decimal_places=2,
        min_value=0,
        initial=10_000_000,
    )
