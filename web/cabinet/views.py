from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from payroll_processor import PayrollProcessor

from .data_access import load_employees_df
from .forms import BudgetForm, TabLoginForm


def _user_in_group(user, group_name: str) -> bool:
    return user.groups.filter(name=group_name).exists()


def login_view(request):
    if request.user.is_authenticated:
        return redirect("cabinet:dashboard")

    form = TabLoginForm(request.POST or None)
    error = None
    if request.method == "POST" and form.is_valid():
        tab_number = form.cleaned_data["tab_number"].strip()
        user = authenticate(request, username=tab_number)
        if user:
            login(request, user, backend="cabinet.auth_backends.TabNumberBackend")
            return redirect("cabinet:dashboard")
        error = "Сотрудник с таким табельным номером не найден."

    return render(request, "cabinet/login.html", {"form": form, "error": error})


@login_required
def logout_view(request):
    logout(request)
    return redirect("cabinet:login")


@login_required
def dashboard_redirect(request):
    if request.user.is_superuser or _user_in_group(request.user, "budgetologist"):
        return redirect("cabinet:budget")
    return redirect("cabinet:employee")


@login_required
def employee_dashboard(request):
    df = load_employees_df()
    tab_number = str(request.user.username).strip()
    row = df[df["Таб. №"].astype(str) == tab_number]

    employee = None
    if not row.empty:
        data = row.iloc[0].to_dict()
        employee = {
            "fio": data.get("Ф.И.О."),
            "position": data.get("Должность /профессия (разряд, категория)"),
            "grade": data.get("Грейд"),
            "fot": data.get("ФОТ"),
            "fot_market": data.get("ФОТ по рынку"),
            "paid_ratio": data.get("Проплаченность"),
        }

    return render(
        request,
        "cabinet/employee_dashboard.html",
        {"employee": employee, "tab_number": tab_number},
    )


@login_required
def budget_dashboard(request):
    if not (request.user.is_superuser or _user_in_group(request.user, "budgetologist")):
        return redirect("cabinet:employee")

    form = BudgetForm(request.POST or None)
    limit = Decimal("10000000")
    if form.is_valid():
        limit = form.cleaned_data["limit"]

    processor = PayrollProcessor(settings.DATA_DIR, settings.OUTPUT_DIR)
    df, _, leftover = processor.process(budget_limit=float(limit), write_outputs=False, plot=True)

    recommended = df[df["Рекомендуется повышение"]].copy()
    recommended = recommended.sort_values("Повышение по лимиту", ascending=False).head(20)

    by_mrf = (
        df.groupby("МРФ")["Повышение по лимиту"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )
    by_grade = (
        df.groupby("Грейд")["Повышение по лимиту"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )

    recommended_rows = []
    for _, row in recommended.iterrows():
        recommended_rows.append(
            {
                "tab": row.get("Таб. №"),
                "fio": row.get("Ф.И.О."),
                "position": row.get("Должность /профессия (разряд, категория)"),
                "fot": row.get("ФОТ"),
                "fot_market": row.get("ФОТ по рынку"),
                "paid_ratio": row.get("Проплаченность"),
                "raise_amount": row.get("Повышение по лимиту"),
                "mrf": row.get("МРФ"),
                "grade": row.get("Грейд"),
            }
        )

    chart_mrf = settings.OUTPUT_DIR / "raise_by_mrf.png"
    chart_grade = settings.OUTPUT_DIR / "raise_by_grade.png"

    context = {
        "form": form,
        "summary": {
            "total_employees": len(df),
            "recommended_count": int(df["Рекомендуется повышение"].sum()),
            "total_raise": float(df["Повышение по лимиту"].sum()),
            "leftover": float(leftover),
        },
        "recommended": recommended_rows,
        "by_mrf": list(by_mrf.items()),
        "by_grade": list(by_grade.items()),
        "charts": {
            "mrf": settings.MEDIA_URL + chart_mrf.name if chart_mrf.exists() else None,
            "grade": settings.MEDIA_URL + chart_grade.name if chart_grade.exists() else None,
        },
    }
    return render(request, "cabinet/budget_dashboard.html", context)
