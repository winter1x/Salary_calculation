from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from .data_access import load_employees_df


class TabNumberBackend:
    def authenticate(self, request, username: str | None = None, **kwargs):
        if not username:
            return None

        username = str(username).strip()
        if not username:
            return None

        user_model = get_user_model()
        user = user_model.objects.filter(username=username).first()
        if user and (user.is_superuser or user.groups.filter(name="budgetologist").exists()):
            return user

        df = load_employees_df()
        row = df[df["Таб. №"].astype(str).str.strip() == username]
        if row.empty:
            return None

        if not user:
            user = user_model.objects.create_user(username=username)
            user.set_unusable_password()
            user.save()

        fio = row.iloc[0].get("Ф.И.О.")
        if fio and user.first_name != fio:
            user.first_name = fio
            user.save(update_fields=["first_name"])

        group, _ = Group.objects.get_or_create(name="employee")
        if not user.groups.filter(name="employee").exists():
            user.groups.add(group)

        return user

    def get_user(self, user_id):
        user_model = get_user_model()
        try:
            return user_model.objects.get(pk=user_id)
        except user_model.DoesNotExist:
            return None
