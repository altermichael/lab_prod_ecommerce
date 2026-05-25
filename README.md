# E-commerce API Optimization

## The ticket

> **From:** Product Manager
> **To:** You
> **Subject:** /api/products/ is unusably slow
>
> Customers are complaining. Loading 20 products takes 8+ seconds. Sales are dropping.
> The endpoint works correctly — it's just slow.
> Please investigate and fix it. Quality team has written 5 tests that define the performance bar.

That's your task.

---

## Setup

```bash
python -m venv venv
source venv/bin/activate                          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py load_db                          # creates 1000 products + 100k sales
python manage.py runserver
```

Then visit:
- `http://localhost:8000/api/products/` — the slow endpoint
- `http://localhost:8000/silk/` — your profiler

---

## Step 1 — Measure (before changing anything!)

1. Open `http://localhost:8000/silk/` and clear any old data
2. In another tab, hit `http://localhost:8000/api/products/`
3. Go back to silk → click on the request → look at:
   - **SQL queries count**
   - **Total time**
   - The actual SQL queries that ran
4. Take a screenshot of these numbers — you'll need it for submission

Then run the test suite:

```bash
python manage.py test catalog.tests.test_perf
```

You'll see **5 failing tests**. Each is one requirement the endpoint must meet.

---

## Step 2 — Investigate

You're free to change ANY code in `catalog/` **except** `catalog/tests/test_perf.py` (that's the spec).

The tests don't tell you HOW to fix anything. They define WHAT must be true:

| Test | Requirement |
|---|---|
| `test_list_runs_in_constant_queries` | Listing products must run in 3 queries |
| `test_response_includes_profit` | Profit field present, no extra queries |
| `test_response_includes_last_30_days_sales` | 30-day sales field present, no extra queries |
| `test_search_runs_in_constant_queries` | Search must use SQL, not Python |
| `test_ordering_runs_in_constant_queries` | Ordering must use SQL, not Python |

Your job: figure out WHY it's slow, then fix it.

---

## When you're stuck

Try in this order:
1. Re-read the SQL silk shows you
2. Look at `catalog/serializers.py` — what does each field do?
3. Look at `catalog/views.py` — what does the queryset NOT do?
4. Web-search the symptom you see (e.g., "django N+1 queries serializer")

If you've spent 30+ minutes on one test, open the spoilers below in order.

<details>
<summary><b>Hint 1 — where to look</b></summary>

The serializer touches several related fields per product. Each access can trigger an extra query if the queryset hasn't been told to load that data ahead of time.

Two of those accesses are forward foreign keys. One is many-to-many. One is a method that calls `.filter()`. One is a method that does Python arithmetic.

Each of these has a different fix.
</details>

<details>
<summary><b>Hint 2 — categories of the issues</b></summary>

You'll need to apply at least three different techniques:

1. **Eager-loading related rows** — for forward FK fields and for M2M fields. There are two different functions for this. Web-search: "django select_related vs prefetch_related".
2. **Computing values in SQL instead of Python** — Django can compute `a - b` for every row in one SQL statement. Web-search: "django F expressions annotate".
3. **Aggregating with a filter** — instead of looping per product to filter+sum, do it in one query. Web-search: "django conditional aggregation Sum filter".
</details>

<details>
<summary><b>Hint 3 — the rough plan</b></summary>

1. Override `get_queryset()` in `ProductViewSet` instead of using `queryset = ...`
2. Add eager loading for the FK and M2M fields the serializer reads
3. Replace `SerializerMethodField` for profit with a queryset annotation using `F()`
4. Replace `SerializerMethodField` for 30-day sales with a queryset annotation using `Sum(filter=Q(...))`
5. Replace those serializer fields with plain `DecimalField` / `IntegerField` (read-only)
6. Run the tests after each change — see them go green one by one

If you still can't get it after this hint, ask the instructor.
</details>

---

## Bonus — Indexes

Once all 5 tests pass, profile a search like `?search=SKU-0001` in silk. Look at the actual SQL — is there an index on `sku`?

Add `Meta.indexes` to the `Product` model for at least 3 fields you've seen the queries touch most:

```python
class Meta:
    indexes = [
        models.Index(fields=[...]),
        ...
    ]
```

Then `makemigrations`, `migrate`, and use `.explain()` to verify:

```bash
python manage.py shell
>>> from catalog.models import Product
>>> print(Product.objects.filter(sku='SKU-001042').explain(analyze=True))
```

Look for `Index Scan` (good) instead of `Seq Scan` (bad).

---

## Submission Checklist

| Item | Done? |
|---|---|
| All 5 tests in `test_perf.py` passing | ☐ |
| `silk_before.png` — query count BEFORE your changes | ☐ |
| `silk_after.png` — query count AFTER your changes | ☐ |

