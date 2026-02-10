from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.db.models import Q
from decimal import Decimal


class User(AbstractUser):
    """Расширенная модель пользователя"""
    USER_TYPE_CHOICES = (
        ('client', 'Клиент'),
        ('supplier', 'Поставщик'),
        ('admin', 'Администратор'),
    )
    
    user_type = models.CharField(
        max_length=20,
        choices=USER_TYPE_CHOICES,
        default='client'
    )
    phone = models.CharField(max_length=20, blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Для поставщиков
    supplier_code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    accepts_orders = models.BooleanField(default=True)
    
    groups = models.ManyToManyField(
        Group,
        related_name='purchasing_user_set',
        blank=True,
        help_text=_('The groups this user belongs to.'),
        related_query_name='user',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='purchasing_user_permissions_set',
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_query_name='user',
    )
    
    class Meta:
        db_table = 'users'
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
    
    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"


class Supplier(models.Model):
    """Поставщик"""
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        related_name='supplier_profile'
    )
    company_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    address = models.TextField()
    tax_number = models.CharField(max_length=50, unique=True)
    bank_details = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'suppliers'
        verbose_name = 'Поставщик'
        verbose_name_plural = 'Поставщики'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.company_name


class Category(models.Model):
    """Категория товаров"""
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self', 
        null=True, 
        blank=True, 
        on_delete=models.CASCADE,
        related_name='children'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'categories'
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Attribute(models.Model):
    """Характеристика товара"""
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    
    class Meta:
        db_table = 'attributes'
        verbose_name = 'Характеристика'
        verbose_name_plural = 'Характеристики'
    
    def __str__(self):
        return self.name


class Product(models.Model):
    """Товар"""
    supplier = models.ForeignKey(
        Supplier, 
        on_delete=models.CASCADE,
        related_name='products'
    )
    category = models.ForeignKey(
        Category, 
        on_delete=models.PROTECT,
        related_name='products'
    )
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    cost_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        blank=True,
        null=True
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    min_order_quantity = models.PositiveIntegerField(default=1)
    unit = models.CharField(max_length=20, default='шт')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'products'
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'
        ordering = ['name']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['supplier', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.sku})"


class ProductAttribute(models.Model):
    """Значения характеристик для товара"""
    product = models.ForeignKey(
        Product, 
        on_delete=models.CASCADE,
        related_name='attributes'
    )
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    value = models.CharField(max_length=255)
    
    class Meta:
        db_table = 'product_attributes'
        unique_together = ['product', 'attribute']
        verbose_name = 'Характеристика товара'
        verbose_name_plural = 'Характеристики товаров'
    
    def __str__(self):
        return f"{self.product.name} - {self.attribute.name}: {self.value}"


class Order(models.Model):
    """Заказ"""
    STATUS_CHOICES = (
        ('pending', 'Ожидает обработки'),
        ('confirmed', 'Подтвержден'),
        ('processing', 'В обработке'),
        ('shipped', 'Отправлен'),
        ('delivered', 'Доставлен'),
        ('cancelled', 'Отменен'),
    )
    
    client = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='orders'
    )
    order_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    total_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2,
        default=0
    )
    delivery_address = models.TextField()
    contact_phone = models.CharField(max_length=20)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'orders'
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['client', '-created_at']),
        ]
    
    def __str__(self):
        return f"Заказ № {self.order_number}"
    
    def calculate_total(self):
        """Пересчитать общую сумму заказа"""
        total = sum(item.quantity * item.price for item in self.items.all())
        self.total_amount = total
        self.save()


class OrderItem(models.Model):
    """Позиция в заказе"""
    order = models.ForeignKey(
        Order, 
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product, 
        on_delete=models.PROTECT,
        related_name='order_items'
    )
    supplier = models.ForeignKey(
        Supplier, 
        on_delete=models.PROTECT,
        related_name='order_items'
    )
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    
    class Meta:
        db_table = 'order_items'
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
    
    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.price
        self.supplier = self.product.supplier
        super().save(*args, **kwargs)


class PriceUpdateLog(models.Model):
    """Лог обновления прайса"""
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    file_name = models.CharField(max_length=255)
    records_count = models.IntegerField()
    success_count = models.IntegerField()
    failed_count = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'price_update_logs'
        verbose_name = 'Лог обновления прайса'
        verbose_name_plural = 'Логи обновления прайса'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.supplier.company_name} - {self.created_at}"