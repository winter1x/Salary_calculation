# Zadanie

Обработка кадровых CSV с расчетом ФОТ, распределения по проектам, страховых взносов,
проплаченности и рекомендаций по повышению. Итоги сохраняются в CSV и графиках.

## Быстрый старт (uv)

```bash
uv venv
uv sync
uv run python src/main.py
```

## Структура проекта

```
Zadanie/
  data/        # входные CSV
  output/      # результаты (генерируется)
  src/         # код
```

## Структура данных

Входные файлы должны лежать в папке `data/`:

- `Должности.csv`
- `Оклады и надбавки.csv`
- `Подразделения, коды блоков, дата приема.csv`
- `Проекты.csv`
- `Проценты премирования.csv`
- `Страховые взносы.csv`
- `ФОТ по рынку.csv`

## Результаты

В каталоге `output/` появятся:

- `employees_fot.csv` — основной датасет с расчетами.
- `vacancies.csv` — вакансии, отделенные от сотрудников.
- `raise_by_mrf.png` — график повышений по МРФ.
- `raise_by_grade.png` — график повышений по грейдам.

## Параметры запуска

```bash
uv run python src/main.py --data-dir data --output-dir output --limit 10000000
```

`--limit` — бюджет на повышение (по умолчанию 10 млн).

## Веб-кабинет (Django)

```bash
uv sync
uv run python web/manage.py migrate
uv run python web/manage.py createsuperuser
uv run python web/manage.py runserver
```

После входа в админку создайте группы `employee` и `budgetologist`,
а пользователей добавьте в нужную группу. Для сотрудника логин — это табельный номер.
