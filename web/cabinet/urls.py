from django.urls import path

from . import views

app_name = "cabinet"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.dashboard_redirect, name="dashboard"),
    path("employee/", views.employee_dashboard, name="employee"),
    path("budget/", views.budget_dashboard, name="budget"),
]
