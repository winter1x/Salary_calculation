from __future__ import annotations

import pandas as pd
from django.conf import settings

from payroll_processor import PayrollProcessor


def load_employees_df(force_recalc: bool = False) -> pd.DataFrame:
    output_path = settings.OUTPUT_DIR / "employees_fot.csv"
    if output_path.exists() and not force_recalc:
        return pd.read_csv(output_path)

    processor = PayrollProcessor(settings.DATA_DIR, settings.OUTPUT_DIR)
    employees, _, _ = processor.process(write_outputs=False, plot=False)
    return employees
