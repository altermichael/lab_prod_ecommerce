from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import F, Sum, Q
from datetime import date, timedelta

from .models import Product
from .serializers import ProductSerializer
#Hi ee

class ProductViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = ProductSerializer

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['brand', 'category', 'active']
    search_fields = ['sku', 'name', 'description', 'brand__name', 'category__name']
    ordering_fields = ['current_price', 'created_at', 'name']
    ordering = ['-created_at']

    def get_queryset(self):
        cutoff_date = date.today() - timedelta(days=30)
        return Product.objects.select_related('category', 'brand'
            ).prefetch_related('variations').annotate(
                profit=F('current_price') - F('cost'),
                last_30_days_sales=Sum(
                'sales__quantity_purchased', 
                filter=Q(sales__date__gte=cutoff_date)
            )
        )
                                                      
