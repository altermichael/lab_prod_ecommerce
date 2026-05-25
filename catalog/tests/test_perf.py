"""
Performance specification for /api/products/.

Each test below is a requirement the endpoint MUST meet.
You decide HOW to meet it.

DO NOT modify this file — it's the spec.

Run:
    python manage.py test catalog.tests.test_perf
"""

from datetime import timedelta
from decimal import Decimal

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from catalog.models import Brand, Category, Variation, Product, Sale


def _make_dataset(n_products=30, sales_per_product=10):
    brand_a = Brand.objects.create(name='BrandA')
    brand_b = Brand.objects.create(name='BrandB')
    cat_a = Category.objects.create(name='CategoryA')
    cat_b = Category.objects.create(name='CategoryB')

    size_m = Variation.objects.create(variation_type='Size', variation_value='M')
    color_red = Variation.objects.create(variation_type='Color', variation_value='Red')

    products = []
    for i in range(n_products):
        p = Product.objects.create(
            sku=f'SKU-{i:04d}',
            name=f'Product {i}',
            description='lorem ipsum',
            brand=brand_a if i % 2 == 0 else brand_b,
            category=cat_a if i % 3 == 0 else cat_b,
            current_price=Decimal('100.00'),
            cost=Decimal('50.00'),
            stock=10,
        )
        p.variations.add(size_m, color_red)
        products.append(p)

    now = timezone.now()
    sales = []
    for p in products:
        for d in range(sales_per_product):
            sales.append(Sale(
                product=p,
                date=now - timedelta(days=d),
                quantity_purchased=2,
                price=Decimal('100.00'),
            ))
    Sale.objects.bulk_create(sales)
    return products


@override_settings(REST_FRAMEWORK={
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
})
class ProductPerfTests(APITestCase):
    """
    Requirements for /api/products/.

    The query budget is 3 queries per request, regardless of how many
    products exist in the database. Adding 100 or 100,000 products must
    NOT change the query count.
    """

    @classmethod
    def setUpTestData(cls):
        _make_dataset()

    def test_list_runs_in_constant_queries(self):
        """Listing products must run in 3 queries — not N+1."""
        with self.assertNumQueries(3):
            response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, 200)

    def test_response_includes_profit(self):
        """Profit must be exposed in the response, but must not add queries."""
        with self.assertNumQueries(3):
            response = self.client.get('/api/products/')
        first = response.json()[0] if isinstance(response.json(), list) \
            else response.json()['results'][0]
        self.assertIn('profit', first)

    def test_response_includes_last_30_days_sales(self):
        """30-day sales total must be in the response — without per-product queries."""
        with self.assertNumQueries(3):
            response = self.client.get('/api/products/')
        first = response.json()[0] if isinstance(response.json(), list) \
            else response.json()['results'][0]
        self.assertIn('last_30_days_sales', first)

    def test_search_runs_in_constant_queries(self):
        """Searching by SKU must run in 3 queries (database-side LIKE)."""
        with self.assertNumQueries(3):
            response = self.client.get('/api/products/?search=SKU-0001')
        self.assertEqual(response.status_code, 200)

    def test_ordering_runs_in_constant_queries(self):
        """Ordering by price must run in 3 queries (database-side ORDER BY)."""
        with self.assertNumQueries(3):
            response = self.client.get('/api/products/?ordering=-current_price')
        self.assertEqual(response.status_code, 200)
