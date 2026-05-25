"""Generate realistic test data for the optimization lab.

Run:
    python manage.py load_db

By default creates 1000 products and ~100,000 sales rows.
Override with --products N --sales-per-product M.
"""

import os
import random
from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import Brand, Category, Variation, Product, Sale


BRANDS = [
    'Nike', 'Adidas', 'Reebok', 'Timberland', 'Versace', 'Swatch', 'Swarovski',
    'Ray-Ban', 'Pepe Jeans', 'Oakley', 'Lacoste', 'Hugo Boss', 'Ferrari',
    'Diesel', 'Casio', 'Armani',
]

CATEGORIES = [
    'Footwear', 'Accessories', 'Watches', 'Sunglasses', 'Apparel',
    'Bags', 'Jewelry', 'Electronics', 'Sportswear', 'Outerwear',
]

SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL']
COLORS = ['Red', 'White', 'Black', 'Blue', 'Yellow', 'Orange', 'Green']


class Command(BaseCommand):
    help = "Load realistic test data for the optimization lab."

    def add_arguments(self, parser):
        parser.add_argument('--products', type=int, default=1000,
                            help='Number of products (default 1000)')
        parser.add_argument('--sales-per-product', type=int, default=100,
                            help='Sales rows per product (default 100)')

    def handle(self, *args, **options):
        n_products = options['products']
        n_sales = options['sales_per_product']

        self.stdout.write(self.style.WARNING("Wiping existing data..."))
        Sale.objects.all().delete()
        Product.objects.all().delete()
        Variation.objects.all().delete()
        Brand.objects.all().delete()
        Category.objects.all().delete()

        self.stdout.write("Creating brands and categories...")
        brands = [Brand.objects.create(name=name) for name in BRANDS]
        categories = [Category.objects.create(name=name) for name in CATEGORIES]

        self.stdout.write("Creating variations...")
        size_variations = [
            Variation.objects.create(variation_type='Size', variation_value=v)
            for v in SIZES
        ]
        color_variations = [
            Variation.objects.create(variation_type='Color', variation_value=v)
            for v in COLORS
        ]

        word_file = os.path.join(
            settings.BASE_DIR, 'catalog', 'utils', 'words.txt')
        with open(word_file, encoding='utf-8') as fh:
            words = fh.read().splitlines()

        def random_phrase(max_words):
            n = random.randint(1, max_words)
            return ' '.join(random.choice(words) for _ in range(n)).title()

        self.stdout.write(f"Creating {n_products} products...")
        products = []
        for i in range(n_products):
            current_price = Decimal(str(round(random.uniform(5, 200), 2)))
            cost = current_price * Decimal(str(round(random.uniform(0.4, 0.7), 2)))
            cost = cost.quantize(Decimal('0.01'))
            products.append(Product(
                sku=f'SKU-{i + 1000:06d}',
                name=random_phrase(3),
                description=random_phrase(20),
                brand=random.choice(brands),
                category=random.choice(categories),
                current_price=current_price,
                cost=cost,
                stock=random.randint(0, 200),
                active=random.random() > 0.05,
            ))
        Product.objects.bulk_create(products, batch_size=500)

        # bulk_create doesn't return PKs reliably across DBs — re-fetch
        all_products = list(Product.objects.all())

        self.stdout.write("Attaching variations (M2M)...")
        for product in all_products:
            chosen = []
            for v in size_variations:
                if random.random() > 0.6:
                    chosen.append(v)
            for v in color_variations:
                if random.random() > 0.6:
                    chosen.append(v)
            if chosen:
                product.variations.add(*chosen)

        self.stdout.write(
            f"Creating sales (~{n_products * n_sales:,} rows)...")
        yesterday = timezone.now() - timedelta(days=1)
        first_day = yesterday - timedelta(days=n_sales - 1)

        sales = []
        for product in all_products:
            current_date = first_day
            while current_date <= yesterday:
                sales.append(Sale(
                    product=product,
                    date=current_date,
                    quantity_purchased=random.randint(1, 10),
                    price=product.current_price,
                ))
                current_date = current_date + timedelta(days=1)
                # flush every 5000 to keep memory low
                if len(sales) >= 5000:
                    Sale.objects.bulk_create(sales, batch_size=2000)
                    sales = []
        if sales:
            Sale.objects.bulk_create(sales, batch_size=2000)

        self.stdout.write(self.style.SUCCESS(
            f"Loaded {Product.objects.count()} products, "
            f"{Sale.objects.count():,} sales, "
            f"{Variation.objects.count()} variations."
        ))
