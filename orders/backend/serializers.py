from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.validators import EmailValidator
from decimal import Decimal
import re

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



User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """Сериализатор пользователя"""
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 
            'user_type', 'phone', 'company_name', 'address',
            'supplier_code', 'accepts_orders', 'is_active'
        ]
        read_only_fields = ['user_type', 'supplier_code']
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует.")
        return value
    
    
def validate_tax_number(value):
    """
    Валидация ИНН (ИНН РФ):
    - 10 цифр для юридических лиц
    - 12 цифр для индивидуальных предпринимателей
    """
    if not value:
        return value
    
    # Удаляем пробелы и дефисы
    cleaned = re.sub(r'[\s\-]', '', value)
    
    # Проверяем, что остались только цифры
    if not cleaned.isdigit():
        raise serializers.ValidationError("ИНН должен содержать только цифры")
    
    # Проверяем длину
    if len(cleaned) not in [10, 12]:
        raise serializers.ValidationError("ИНН должен содержать 10 цифр (для юр.лиц) или 12 цифр (для ИП)")
    
    # Проверка контрольных цифр для 10-значного ИНН
    if len(cleaned) == 10:
        if not validate_inn_10(cleaned):
            raise serializers.ValidationError("Неверная контрольная сумма ИНН (10 цифр)")
    
    # Проверка контрольных цифр для 12-значного ИНН
    elif len(cleaned) == 12:
        if not validate_inn_12(cleaned):
            raise serializers.ValidationError("Неверная контрольная сумма ИНН (12 цифр)")
    
    return cleaned


def validate_inn_10(inn):
    """Проверка контрольных цифр для 10-значного ИНН (юр.лица)"""
    coefficients = [2, 4, 10, 3, 5, 9, 4, 6, 8]
    control_sum = sum(int(inn[i]) * coefficients[i] for i in range(9))
    control_digit = (control_sum % 11) % 10
    return control_digit == int(inn[9])


def validate_inn_12(inn):
    """Проверка контрольных цифр для 12-значного ИНН (ИП)"""
    # Первый контрольный разряд
    coefficients_1 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    control_sum_1 = sum(int(inn[i]) * coefficients_1[i] for i in range(10))
    control_digit_1 = (control_sum_1 % 11) % 10
    
    # Второй контрольный разряд
    coefficients_2 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
    control_sum_2 = sum(int(inn[i]) * coefficients_2[i] for i in range(11))
    control_digit_2 = (control_sum_2 % 11) % 10
    
    return control_digit_1 == int(inn[10]) and control_digit_2 == int(inn[11])


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Сериализатор для регистрации"""
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)
    tax_number = serializers.CharField(
        max_length=12, 
        required=False,
        allow_blank=True,
        help_text="ИНН поставщика (10 цифр для юр.лиц, 12 цифр для ИП)"
    )
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'user_type', 'phone',
            'company_name', 'address', 'tax_number'
        ]
    
    def validate(self, data):
        # Проверка паролей
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': 'Пароли не совпадают.'
            })
        
        # Проверка уникальности
        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError({
                'username': 'Пользователь с таким именем уже существует.'
            })
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({
                'email': 'Пользователь с таким email уже существует.'
            })
        
        # Валидация ИНН для поставщиков
        if data.get('user_type') == 'supplier':
            if not data.get('tax_number'):
                raise serializers.ValidationError({
                    'tax_number': 'ИНН обязателен для поставщиков.'
                })
            try:
                data['tax_number'] = validate_tax_number(data['tax_number'])
            except serializers.ValidationError as e:
                raise serializers.ValidationError({'tax_number': str(e)})
        
        return data
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        user_type = validated_data.get('user_type', 'client')
        tax_number = validated_data.pop('tax_number', None)
        
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            user_type=user_type,
            phone=validated_data.get('phone', ''),
            company_name=validated_data.get('company_name', ''),
            address=validated_data.get('address', ''),
        )
        
        # Если поставщик, генерируем код и создаём профиль
        if user_type == 'supplier':
            from django.utils.crypto import get_random_string
            user.supplier_code = f'SUP{get_random_string(8).upper()}'
            user.save()
            
            # Создаём профиль поставщика
            Supplier.objects.create(
                user=user,
                company_name=user.company_name,
                contact_person=f"{user.first_name} {user.last_name}",
                phone=user.phone,
                email=user.email,
                address=user.address,
                tax_number=tax_number  # ← Передаём ИНН
            )
        
        return user


class PasswordResetSerializer(serializers.Serializer):
    """Сериализатор для восстановления пароля"""
    email = serializers.EmailField(validators=[EmailValidator()])


class SupplierSerializer(serializers.ModelSerializer):
    """Сериализатор поставщика"""
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Supplier
        fields = '__all__'


class CategorySerializer(serializers.ModelSerializer):
    """Сериализатор категории"""
    children = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = '__all__'
    
    def get_children(self, obj):
        children = obj.children.all()
        return CategorySerializer(children, many=True).data


class AttributeSerializer(serializers.ModelSerializer):
    """Сериализатор характеристики"""
    class Meta:
        model = Attribute
        fields = '__all__'


class ProductAttributeSerializer(serializers.ModelSerializer):
    """Сериализатор значений характеристик товара"""
    attribute_name = serializers.CharField(source='attribute.name', read_only=True)
    
    class Meta:
        model = ProductAttribute
        fields = ['id', 'attribute', 'attribute_name', 'value']
        read_only_fields = ['attribute_name']


class ProductSerializer(serializers.ModelSerializer):
    """Сериализатор товара"""
    supplier_name = serializers.CharField(source='supplier.company_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    attributes = ProductAttributeSerializer(many=True, required=False)
    
    class Meta:
        model = Product
        fields = '__all__'
        read_only_fields = ['supplier_name', 'category_name']
    
    def create(self, validated_data):
        attributes_data = validated_data.pop('attributes', [])
        product = Product.objects.create(**validated_data)
        
        for attr_data in attributes_data:
            ProductAttribute.objects.create(product=product, **attr_data)
        
        return product
    
    def update(self, instance, validated_data):
        attributes_data = validated_data.pop('attributes', None)
        
        # Обновляем основные поля
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Обновляем характеристики
        if attributes_data is not None:
            instance.attributes.all().delete()
            for attr_data in attributes_data:
                ProductAttribute.objects.create(product=instance, **attr_data)
        
        return instance


class ProductImportSerializer(serializers.Serializer):
    """Сериализатор для импорта товаров"""
    file = serializers.FileField()
    update_existing = serializers.BooleanField(default=True)
    format = serializers.ChoiceField(
        choices=['auto', 'csv', 'json', 'yaml', 'yml'],
        default='auto',
        help_text='Формат файла. Если auto - определяется по расширению'
    )


class OrderItemSerializer(serializers.ModelSerializer):
    """Сериализатор позиции заказа"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.company_name', read_only=True)
    
    class Meta:
        model = OrderItem
        fields = '__all__'
        read_only_fields = ['product_name', 'supplier_name', 'subtotal']


class OrderSerializer(serializers.ModelSerializer):
    """Сериализатор заказа"""
    items = OrderItemSerializer(many=True)
    client_name = serializers.CharField(source='client.username', read_only=True)
    total_items = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = '__all__'
        read_only_fields = [
            'order_number', 'total_amount', 'client_name', 
            'created_at', 'updated_at', 'confirmed_at'
        ]
    
    def get_total_items(self, obj):
        return obj.items.count()
    
    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Заказ должен содержать хотя бы одну позицию.")
        
        # Проверяем доступность товаров
        for item_data in value:
            product = item_data.get('product')
            quantity = item_data.get('quantity', 0)
            
            if not product:
                raise serializers.ValidationError("Товар обязателен для каждой позиции.")
            
            if quantity <= 0:
                raise serializers.ValidationError("Количество должно быть положительным.")
            
            if quantity > product.stock_quantity:
                raise serializers.ValidationError(
                    f"Недостаточно товара {product.name} на складе. "
                    f"Доступно: {product.stock_quantity}"
                )
        
        return value
    
    def create(self, validated_data):
        items_data = validated_data.pop('items')
        
        # Генерируем номер заказа
        from django.utils.crypto import get_random_string
        order_number = f'ORD{get_random_string(10).upper()}'
        
        # Создаем заказ
        order = Order.objects.create(
            order_number=order_number,
            **validated_data
        )
        
        # Создаем позиции заказа
        total_amount = Decimal('0.00')
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            price = item_data.get('price', product.price)
            
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=price
            )
            
            total_amount += quantity * price
        
        order.total_amount = total_amount
        order.save()
        
        return order
    
    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        
        # Обновляем основные поля
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance


class PriceUpdateLogSerializer(serializers.ModelSerializer):
    """Сериализатор лога обновления прайса"""
    supplier_name = serializers.CharField(source='supplier.company_name', read_only=True)
    
    class Meta:
        model = PriceUpdateLog
        fields = '__all__'
        read_only_fields = ['supplier_name']