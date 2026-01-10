from __future__ import annotations

import argparse
from pathlib import Path

from payroll_processor import PayrollProcessor


def main() -> None:
    parser = argparse.ArgumentParser(description="Пайплайн расчета ФОТ и показателей")
    root_dir = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--data-dir",
        default=root_dir / "data",
        type=Path,
        help="Каталог с исходными CSV",
    )
    parser.add_argument(
        "--output-dir",
        default=root_dir / "output",
        type=Path,
        help="Каталог для результатов",
    )
    parser.add_argument(
        "--limit",
        default=10_000_000,
        type=float,
        help="Лимит бюджета на повышение",
    )
    args = parser.parse_args()

    processor = PayrollProcessor(args.data_dir, args.output_dir)
    employees, vacancies, leftover = processor.process(budget_limit=args.limit)

    print(f"Сотрудников обработано: {len(employees)}")
    print(f"Вакансий отделено: {len(vacancies)}")
    print(f"Неиспользованный лимит: {leftover:.2f}")


if __name__ == "__main__":
    main()
