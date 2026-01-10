from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "cabinet"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="cabinet/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.dashboard_redirect, name="dashboard"),
    path("employee/", views.employee_dashboard, name="employee"),
    path("budget/", views.budget_dashboard, name="budget"),
]
