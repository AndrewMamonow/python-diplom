from django.shortcuts import render
from rest_framework.request import Request
from rest_framework.generics import ListAPIView


from backend.models import (
    User, 
    Shop, 
    Category, 
    Product, 
    ProductInfo, 
    Parameter, 
    ProductParameter, 
    Order, 
    OrderItem,
    Contact, 
    )

from backend.serializers import (
    UserSerializer, 
    CategorySerializer, 
    ShopSerializer, 
    ProductInfoSerializer,
    OrderItemSerializer, 
    OrderSerializer, 
    ContactSerializer,
    )


class CategoryView(ListAPIView):
    """
    Класс для просмотра категорий
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    
class ShopView(ListAPIView):
    """
    Класс для просмотра списка магазинов
    """
    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer
