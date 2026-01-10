from __future__ import annotations

from decimal import Decimal

import pandas as pd
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from payroll_processor import PayrollProcessor

from .forms import BudgetForm


def _user_in_group(user, group_name: str) -> bool:
    return user.groups.filter(name=group_name).exists()


def _load_employees_df() -> pd.DataFrame:
    output_path = settings.OUTPUT_DIR / "employees_fot.csv"
    if output_path.exists():
        return pd.read_csv(output_path)

    processor = PayrollProcessor(settings.DATA_DIR, settings.OUTPUT_DIR)
    employees, _, _ = processor.process()
    return employees


@login_required
def dashboard_redirect(request):
    if _user_in_group(request.user, "budgetologist"):
        return redirect("cabinet:budget")
    return redirect("cabinet:employee")


@login_required
def employee_dashboard(request):
    df = _load_employees_df()
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
    if not _user_in_group(request.user, "budgetologist"):
        return redirect("cabinet:employee")

    form = BudgetForm(request.POST or None)
    limit = Decimal("10000000")
    if form.is_valid():
        limit = form.cleaned_data["limit"]

    processor = PayrollProcessor(settings.DATA_DIR, settings.OUTPUT_DIR)
    df, _, leftover = processor.process(budget_limit=float(limit), write_outputs=False, plot=False)

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
    }
    return render(request, "cabinet/budget_dashboard.html", context)
