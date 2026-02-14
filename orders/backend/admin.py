from django.contrib import admin
from django.utils.html import format_html
from rest_framework.authtoken.models import TokenProxy
from .models import (
    User, 
    Supplier, 
    Category, 
    Attribute, 
    Product, 
    ProductAttribute, 
    Order, 
    OrderItem, 
    PriceUpdateLog
)


admin.site.unregister(TokenProxy) # Убирает "Токен аутентификации" с админ-панели

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'user_type', 'is_active', 'date_joined']
    list_filter = ['user_type', 'is_active']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('User type', {'fields': ('user_type', 'supplier_code', 'accepts_orders')}),
        ('Company info', {'fields': ('company_name', 'phone', 'address')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'contact_person', 'phone', 'email', 'tax_number','is_active']
    list_filter = ['is_active']
    search_fields = ['company_name', 'contact_person', 'email']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'created_at']
    list_filter = ['parent']
    search_fields = ['name']
    # prepopulated_fields = {'slug': ('name',)}


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'supplier', 'category', 'price', 'stock_quantity', 'is_active']
    list_filter = ['supplier', 'category', 'is_active']
    search_fields = ['name', 'sku', 'description']
    inlines = [ProductAttributeInline]
    readonly_fields = ['created_at', 'updated_at']
    
    def supplier_link(self, obj):
        return format_html('<a href="/admin/api/supplier/{}/change/">{}</a>', 
                          obj.supplier.id, obj.supplier.company_name)
    supplier_link.short_description = 'Supplier'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['subtotal']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'client', 'status', 'total_amount', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['order_number', 'client__username']
    inlines = [OrderItemInline]
    readonly_fields = ['created_at', 'updated_at', 'confirmed_at']
    
    def client_link(self, obj):
        return format_html('<a href="/admin/api/user/{}/change/">{}</a>', 
                          obj.client.id, obj.client.username)
    client_link.short_description = 'Client'


@admin.register(PriceUpdateLog)
class PriceUpdateLogAdmin(admin.ModelAdmin):
    list_display = ['supplier', 'file_name', 'records_count', 'success_count', 'failed_count', 'created_at']
    list_filter = ['supplier', 'created_at']
    readonly_fields = ['created_at']