from datetime import date, timedelta
from rest_framework import serializers

from .models import Product, Variation


class VariationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variation
        fields = ['id', 'variation_type', 'variation_value']


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    brand_name = serializers.CharField(source='brand.name', read_only=True)

    variations = VariationSerializer(many=True, read_only=True)

    profit = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    last_30_days_sales = serializers.IntegerField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'sku', 'name', 'description',
            'brand_name', 'category_name', 'variations',
            'current_price', 'cost', 'profit',
            'stock', 'active',
            'last_30_days_sales',
            'created_at',
        ]

    # def get_profit(self, product):
    #     return product.current_price - product.cost

    def get_last_30_days_sales(self, product):
        cutoff = date.today() - timedelta(days=30)
        sales = product.sales.all()
        total = 0
        for sale in sales:
            if sale.date.date() >= cutoff:
                total += sale.quantity_purchased
        return total
