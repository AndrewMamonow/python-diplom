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
    ProductImage, 
    Order, 
    OrderItem, 
    PriceUpdateLog
)


admin.site.unregister(TokenProxy) # Убирает "Токен аутентификации" с админ-панели

# Настройка заголовка админки
admin.site.site_header = 'Administration'
admin.site.site_title = 'Admin'
admin.site.index_title = 'Dashboard'

# Кастомизация главной страницы
class DashboardAdminSite(admin.AdminSite):
    site_header = 'Administration'
    site_title = 'Admin Portal'
    index_title = 'Welcome System Admin'
    

admin_site = DashboardAdminSite(name='admin')

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = [
        'avatar_thumbnail', 'username', 'email', 'user_type', 
        'company_name', 'is_active', 'date_joined', 'last_login'
    ]
    list_filter = ['user_type', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'company_name']
    readonly_fields = ['avatar_preview', 'date_joined', 'last_login']
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'avatar', 'avatar_preview')}),
        ('Company info', {'fields': ('user_type', 'company_name', 'phone', 'address')}),
        ('Supplier info', {'fields': ('supplier_code', 'accepts_orders'), 'classes': ('collapse',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    def avatar_thumbnail(self, obj):
        if obj.avatar_small:
            return format_html('<img src="{}" width="40" height="40" style="border-radius: 50%;" />', obj.avatar_small.url)
        elif obj.avatar:
            return format_html('<img src="{}" width="40" height="40" style="border-radius: 50%;" />', obj.avatar.url)
        return format_html('<div style="width: 40px; height: 40px; background: #ddd; border-radius: 50%;"></div>')
    avatar_thumbnail.short_description = 'Avatar'
    
    def avatar_preview(self, obj):
        if obj.avatar_medium:
            return format_html('<img src="{}" width="200" height="200" style="border-radius: 10px;" />', obj.avatar_medium.url)
        elif obj.avatar:
            return format_html('<img src="{}" width="200" height="200" style="border-radius: 10px;" />', obj.avatar.url)
        return "No avatar"
    avatar_preview.short_description = 'Avatar Preview'

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = [
        'logo_thumbnail', 'company_name', 'contact_person', 'phone', 
        'email', 'tax_number', 'is_active', 'products_count'
    ]
    list_filter = ['is_active', 'created_at']
    search_fields = ['company_name', 'contact_person', 'email', 'tax_number']
    readonly_fields = ['logo_preview', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'company_name', 'contact_person', 'tax_number')
        }),
        ('Контакты', {
            'fields': ('phone', 'email', 'address')
        }),
        ('Банковские реквизиты', {
            'fields': ('bank_details',),
            'classes': ('collapse',)
        }),
        ('Статистика', {
            'fields': ('products_count_display', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('Статус', {
            'fields': ('is_active',)
        }),
    )
    
    def logo_thumbnail(self, obj):
        if hasattr(obj.user, 'avatar_small') and obj.user.avatar_small:
            return format_html('<img src="{}" width="40" height="40" style="border-radius: 5px;" />', obj.user.avatar_small.url)
        return format_html('<div style="width: 40px; height: 40px; background: #4CAF50; border-radius: 5px; color: white; display: flex; align-items: center; justify-content: center; font-weight: bold;">S</div>')
    logo_thumbnail.short_description = 'Logo'
    
    def logo_preview(self, obj):
        if hasattr(obj.user, 'avatar_medium') and obj.user.avatar_medium:
            return format_html('<img src="{}" width="200" height="200" style="border-radius: 10px;" />', obj.user.avatar_medium.url)
        return "No logo"
    logo_preview.short_description = 'Logo Preview'
    
    def products_count(self, obj):
        return obj.products.count()
    products_count.short_description = 'Products'
    products_count.admin_order_field = 'products_count'
    
    def products_count_display(self, obj):
        count = obj.products.count()
        return format_html('<span style="font-size: 24px; font-weight: bold; color: #4CAF50;">{}</span> товаров', count)
    products_count_display.short_description = 'Количество товаров'
    
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(products_count=Count('products'))


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'products_count', 'created_at']
    list_filter = ['parent', 'created_at']
    search_fields = ['name']
    readonly_fields = ['created_at']
    
    def products_count(self, obj):
        return obj.products.count()
    products_count.short_description = 'Products'


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ['name', 'products_count']
    search_fields = ['name']
    
    def products_count(self, obj):
        return obj.productattribute_set.count()
    products_count.short_description = 'Products'


class ProductAttributeInline(admin.TabularInline):
    model = ProductAttribute
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'image_thumbnail', 'name', 'sku', 'supplier', 'category', 
        'price', 'stock_quantity', 'is_active', 'created_at'
    ]
    list_filter = ['supplier', 'category', 'is_active', 'created_at']
    search_fields = ['name', 'sku', 'description']
    readonly_fields = ['image_preview', 'created_at', 'updated_at']
    list_editable = ['is_active', 'stock_quantity']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('supplier', 'category', 'name', 'sku', 'description')
        }),
        ('Изображения', {
            'fields': ('image', 'image_preview', 'image_thumbnail', 'image_small', 'image_medium', 'image_large')
        }),
        ('Цены и склад', {
            'fields': ('price', 'cost_price', 'stock_quantity', 'min_order_quantity', 'unit')
        }),
        ('Дополнительно', {
            'fields': ('is_active', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def image_thumbnail(self, obj):
        if obj.image_thumbnail:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image_thumbnail.url)
        elif obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return format_html('<div style="width: 50px; height: 50px; background: #ddd;"></div>')
    image_thumbnail.short_description = 'Image'
    
    def image_preview(self, obj):
        if obj.image_medium:
            return format_html('<img src="{}" width="300" height="300" style="object-fit: cover; border-radius: 5px;" />', obj.image_medium.url)
        elif obj.image:
            return format_html('<img src="{}" width="300" height="300" style="object-fit: cover; border-radius: 5px;" />', obj.image.url)
        return "No image"
    image_preview.short_description = 'Image Preview'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['subtotal']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'client', 'status_badge', 'total_amount', 
        'items_count', 'created_at', 'delivery_address_short'
    ]
    list_filter = ['status', 'created_at',]
    search_fields = ['order_number', 'client__username', 'client__email']
    readonly_fields = ['created_at', 'updated_at', 'confirmed_at']
    
    fieldsets = (
        ('Заказ', {
            'fields': ('order_number', 'client', 'status', 'total_amount')
        }),
        ('Доставка', {
            'fields': ('delivery_address', 'contact_phone', 'notes')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at', 'confirmed_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'pending': '#ff9800',
            'confirmed': '#4CAF50',
            'processing': '#2196F3',
            'shipped': '#9C27B0',
            'delivered': '#009688',
            'cancelled': '#f44336'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; border-radius: 12px; font-weight: bold;">{}</span>',
            colors.get(obj.status, '#999'),
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def items_count(self, obj):
        return obj.items.count()
    items_count.short_description = 'Items'
    
    def delivery_address_short(self, obj):
        return obj.delivery_address[:50] + '...' if len(obj.delivery_address) > 50 else obj.delivery_address
    delivery_address_short.short_description = 'Delivery Address'


@admin.register(PriceUpdateLog)
class PriceUpdateLogAdmin(admin.ModelAdmin):
    list_display = [
        'supplier', 'file_name', 'records_count', 'success_count', 
        'failed_count', 'status_badge', 'created_at'
    ]
    list_filter = ['supplier', 'created_at']
    readonly_fields = ['created_at']
    
    def status_badge(self, obj):
        if obj.failed_count == 0:
            color = '#4CAF50'
            text = 'Success'
        elif obj.failed_count < obj.records_count / 2:
            color = '#ff9800'
            text = 'Partial'
        else:
            color = '#f44336'
            text = 'Failed'
        
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 12px; border-radius: 12px; font-weight: bold;">{}</span>',
            color,
            text
        )
    status_badge.short_description = 'Status'
 
    
@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ['product', 'image_thumbnail', 'sort_order', 'created_at']
    list_filter = ['product__supplier', 'created_at']
    
    def image_thumbnail(self, obj):
        if obj.image_thumbnail:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image_thumbnail.url)
        elif obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return format_html('<div style="width: 50px; height: 50px; background: #ddd;"></div>')
    image_thumbnail.short_description = 'Image'
    
    
@admin.register(ProductAttribute)
class ProductAttributeAdmin(admin.ModelAdmin):
    list_display = ['product', 'attribute', 'value']
    list_filter = ['attribute']
    search_fields = ['product__name', 'attribute__name', 'value']
