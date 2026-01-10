from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt


@dataclass
class SourceFiles:
    positions: str = "Должности.csv"
    salaries: str = "Оклады и надбавки.csv"
    org_units: str = "Подразделения, коды блоков, дата приема.csv"
    projects: str = "Проекты.csv"
    bonuses: str = "Проценты премирования.csv"
    insurance: str = "Страховые взносы.csv"
    market: str = "ФОТ по рынку.csv"


class BaseCSVLoader:
    def __init__(self, data_dir: Path | str) -> None:
        self.data_dir = Path(data_dir)

    def load_csv(self, filename: str) -> pd.DataFrame:
        path = self.data_dir / filename
        return pd.read_csv(path, sep="\t", encoding="utf-8-sig", dtype=str)


class PayrollProcessor(BaseCSVLoader):
    def __init__(self, data_dir: Path | str, output_dir: Path | str = "output") -> None:
        super().__init__(data_dir)
        self.output_dir = Path(output_dir)
        self.files = SourceFiles()
        self.salary_pay_cols: list[str] = []

    @staticmethod
    def _to_numeric(series: pd.Series) -> pd.Series:
        return pd.to_numeric(series.astype(str).str.replace(",", ".", regex=False), errors="coerce")

    @staticmethod
    def _parse_date(series: pd.Series, fmt: str | None = None, dayfirst: bool = False) -> pd.Series:
        return pd.to_datetime(series, errors="coerce", format=fmt, dayfirst=dayfirst)

    @staticmethod
    def _normalize_percent(series: pd.Series) -> pd.Series:
        max_val = series.max(skipna=True)
        if pd.notna(max_val) and max_val > 1:
            return series / 100
        return series

    def load_sources(self) -> dict[str, pd.DataFrame]:
        sources = {
            "positions": self.load_csv(self.files.positions),
            "salaries": self.load_csv(self.files.salaries),
            "org_units": self.load_csv(self.files.org_units),
            "projects": self.load_csv(self.files.projects),
            "bonuses": self.load_csv(self.files.bonuses),
            "insurance": self.load_csv(self.files.insurance),
            "market": self.load_csv(self.files.market),
        }

        salary_cols = sources["salaries"].columns.tolist()
        exclude = {
            "Имя штатной единицы",
            "Таб. №",
            "Статус назначения",
            "Кол-во единиц",
            "Дата последнего повышения",
            "Тарифная ставка (оклад), руб.",
        }
        self.salary_pay_cols = [col for col in salary_cols if col not in exclude]
        return sources

    def _split_vacancies(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        is_vacancy = df["Статус назначения"].eq("Вакансия")
        return df.loc[~is_vacancy].copy(), df.loc[is_vacancy].copy()

    def merge_employees(self, sources: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
        positions = sources["positions"]
        salaries = sources["salaries"]
        org_units = sources["org_units"]
        projects = sources["projects"]
        bonuses = sources["bonuses"]

        emp_positions, vacancies = self._split_vacancies(positions)
        emp_salaries, _ = self._split_vacancies(salaries)
        emp_org_units, _ = self._split_vacancies(org_units)
        emp_projects, _ = self._split_vacancies(projects)
        emp_bonuses, _ = self._split_vacancies(bonuses)

        df = emp_positions
        df = pd.merge(df, emp_org_units, how="inner")
        df = pd.merge(df, emp_salaries, how="inner")
        df = pd.merge(df, emp_projects, how="inner")
        df = pd.merge(df, emp_bonuses, how="inner")

        market = sources["market"]
        market_key = [
            "Структурное подразделение - полный путь с группирующими",
            "Код функции",
            "Должность /профессия (разряд, категория)",
            "Грейд",
        ]
        df = df.merge(market, on=market_key, how="left")

        insurance = sources["insurance"]
        df = df.merge(insurance, on="РФ", how="left")
        df.drop_duplicates(inplace=True, subset="Имя штатной единицы")

        return df, vacancies

    def calculate_metrics(self, df: pd.DataFrame, budget_limit: float) -> tuple[pd.DataFrame, float]:
        df["Кол-во единиц"] = self._to_numeric(df["Кол-во единиц"]).fillna(0)
        df["Тарифная ставка (оклад), руб."] = self._to_numeric(df["Тарифная ставка (оклад), руб."])

        for col in self.salary_pay_cols:
            df[col] = self._to_numeric(df[col])

        df["Дата последнего повышения"] = self._parse_date(
            df["Дата последнего повышения"], fmt="%Y-%m-%d"
        )
        df["Дата приема"] = self._parse_date(df["Дата приема"], dayfirst=True)

        premium_cols = [
            "Процент месячной премии",
            "Процент квартальной премии",
            "Процент годовой премии",
        ]
        for col in premium_cols:
            df[col] = self._to_numeric(df[col]).fillna(0)

        df["Процент премирования"] = 1 + (
            df["Процент месячной премии"]
            * (11 / 12)
            + df["Процент квартальной премии"]
            * (9 / 12)
            + df["Процент годовой премии"]
        ) / 100

        df["Надбавки всего"] = df[self.salary_pay_cols].sum(axis=1, skipna=True)
        df["База ФОТ"] = df["Тарифная ставка (оклад), руб."] + df["Надбавки всего"]
        df["ФОТ"] = df["База ФОТ"] * df["Процент премирования"]

        for col in ["OPEX", "CAPEX", "O2O"]:
            df[col] = self._to_numeric(df[col])
            pct = self._normalize_percent(df[col])
            df[f"ФОТ_{col}"] = df["ФОТ"] * pct

        df["Процентр страховых взносов"] = (
            self._to_numeric(df["Процентр страховых взносов"]).fillna(0)
        )
        df["ФОТ с СВ"] = df["ФОТ"] * (1 + df["Процентр страховых взносов"])

        now = pd.Timestamp('today')
        df["Стаж (лет)"] = ((now - pd.DateOffset(months=18) - pd.to_datetime(df["Дата приема"], dayfirst=True)).dt.days / 365.25).round(1)

        df["ФОТ по рынку"] = self._to_numeric(df["ФОТ по рынку"]).replace({0: np.nan})
        df["Проплаченность"] = df["ФОТ"] / df["ФОТ по рынку"]

        six_months_ago = now - pd.DateOffset(months=24)
        df["Рекомендуется повышение"] = (
            (df["Проплаченность"] < 0.8)
            & (df["Дата последнего повышения"] <= six_months_ago)
            & (df["Стаж (лет)"] > 1)
            & (df["Кол-во единиц"] > 0.5)
        )

        df.loc[df["Рекомендуется повышение"], "Сумма повышения"] = (
            df["Тарифная ставка (оклад), руб."] / 100 * 30
        )
        df["Новый ФОТ (до лимита)"] = df["ФОТ"] + df["Сумма повышения"]

        total_desired = df["Сумма повышения"].sum()
        scale = 1.0
        if total_desired > 0 and total_desired > budget_limit:
            scale = (budget_limit / total_desired)
        print(scale, "scale")
        print(total_desired, "total_desired")

        df["Повышение по лимиту"] = df["Сумма повышения"] * scale
        print(df["Повышение по лимиту"].sum(), "Повышение по лимиту")
        print(budget_limit, "Бюджет")
        calc_desired = budget_limit - df["Повышение по лимиту"].sum()
        df["Новый ФОТ (после лимита)"] = df["ФОТ"] + df["Повышение по лимиту"]

        return df, calc_desired

    def save_outputs(self, df: pd.DataFrame, vacancies: pd.DataFrame) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(self.output_dir / "employees_fot.csv", index=False)
        vacancies.to_csv(self.output_dir / "vacancies.csv", index=False)

    def plot_raises(self, df: pd.DataFrame) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        by_mrf = df.groupby("МРФ", dropna=True)["Повышение по лимиту"].sum()
        if not by_mrf.empty:
            fig, ax = plt.subplots(figsize=(12, max(4, len(by_mrf) * 0.35)))
            by_mrf.plot(kind="barh", ax=ax)
            ax.set_title("Raise by MRF")
            ax.set_xlabel("Increase")
            ax.invert_yaxis()
            fig.tight_layout()
            fig.savefig(self.output_dir / "raise_by_mrf.png")
            plt.close(fig)

        by_grade = df.groupby("Грейд", dropna=True)["Повышение по лимиту"].sum()
        if not by_grade.empty:
            fig, ax = plt.subplots(figsize=(10, 6))
            by_grade.plot(kind="bar", ax=ax)
            ax.set_title("Raise by Grade")
            ax.set_ylabel("Increase")
            fig.tight_layout()
            fig.savefig(self.output_dir / "raise_by_grade.png")
            plt.close(fig)

    def process(self, budget_limit: float = 10_000_000) -> tuple[pd.DataFrame, pd.DataFrame, float]:
        sources = self.load_sources()
        merged, vacancies = self.merge_employees(sources)
        enriched, leftover = self.calculate_metrics(merged, budget_limit=budget_limit)
        self.save_outputs(enriched, vacancies)
        self.plot_raises(enriched)
        return enriched, vacancies, leftover
