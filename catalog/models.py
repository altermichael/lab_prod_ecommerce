from django.db import models


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=200)

    class Meta:
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Variation(models.Model):
    variation_type = models.CharField(max_length=50)   # e.g., "Size", "Color"
    variation_value = models.CharField(max_length=50)  # e.g., "M", "Red"

    def __str__(self):
        return f"{self.variation_type}: {self.variation_value}"


class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    brand = models.ForeignKey(
        Brand, on_delete=models.PROTECT, related_name='products')
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name='products')
    variations = models.ManyToManyField(
        Variation, related_name='products', blank=True)
    current_price = models.DecimalField(
        max_digits=10, decimal_places=2)
    cost = models.DecimalField(
        max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # NOTE: students will add Meta.indexes in Task 6 (bonus)

    class Meta:
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['name']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.sku} — {self.name}"


class Sale(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='sales')
    date = models.DateTimeField()
    quantity_purchased = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Sale of {self.product.sku} on {self.date.date()}"
