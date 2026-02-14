from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from django_filters.rest_framework import DjangoFilterBackend
from decimal import Decimal
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.parsers import MultiPartParser, FormParser
import csv
import io
import json
import yaml

from .models import (
    User, 
    Supplier, 
    Category, 
    Attribute, 
    Product, 
    ProductAttribute, 
    Order, 
    PriceUpdateLog
)
from .serializers import (
    UserSerializer, 
    UserRegistrationSerializer, 
    PasswordResetSerializer,
    SupplierSerializer, 
    CategorySerializer, 
    AttributeSerializer,
    ProductSerializer, 
    ProductImportSerializer, 
    OrderSerializer,
    PriceUpdateLogSerializer
)
from .tasks import send_order_confirmation_email, send_invoice_email
from .cache_utils import (
    CacheManager, 
    CacheKeyBuilder, 
    QuerySetCache,
)
import logging


logger = logging.getLogger(__name__)

User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    """ViewSet для пользователей"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user_type', 'is_active']
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def register(self, request):
        """Регистрация нового пользователя"""
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Создаем профиль поставщика если нужно
            if user.user_type == 'supplier':
                Supplier.objects.create(
                    user=user,
                    company_name=user.company_name,
                    contact_person=f"{user.first_name} {user.last_name}",
                    phone=user.phone,
                    email=user.email,
                    address=user.address
                )
            
            # Генерируем JWT токен
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def login(self, request):
        """Вход в систему"""
        from django.contrib.auth import authenticate
        
        username = request.data.get('username')
        password = request.data.get('password')
        
        if not username or not password:
            return Response(
                {'error': 'Username and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = authenticate(username=username, password=password)
        
        if user is None:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {'error': 'User account is disabled'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def password_reset(self, request):
        """Запрос на восстановление пароля"""
        serializer = PasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            
            try:
                user = User.objects.get(email=email)
                # Здесь должна быть логика отправки письма с ссылкой для сброса пароля
                # Для простоты просто возвращаем успех
                return Response({
                    'message': 'Инструкции по восстановлению пароля отправлены на ваш email'
                })
            except User.DoesNotExist:
                # Не раскрываем информацию о существовании пользователя
                return Response({
                    'message': 'Инструкции по восстановлению пароля отправлены на ваш email'
                })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Получить информацию о текущем пользователе"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class SupplierViewSet(viewsets.ModelViewSet):
    """ViewSet для поставщиков"""
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['is_active']
    
    @action(detail=True, methods=['post'])
    def toggle_accept_orders(self, request, pk=None):
        """Включить/выключить прием заказов"""
        supplier = self.get_object()
        supplier.is_active = not supplier.is_active
        supplier.save()
        
        return Response({
            'message': f'Прием заказов {"включен" if supplier.is_active else "выключен"}',
            'is_active': supplier.is_active
        })


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для категорий (только чтение)"""
    queryset = Category.objects.filter(parent__isnull=True).prefetch_related('children')
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        """Кэширование списка категорий"""
        cache_key = CacheKeyBuilder.model_list('category', {'parent__isnull': True})
        cached = CacheManager.get(cache_key)
        
        if cached is not None:
            logger.debug("Using cached categories")
            return Category.objects.filter(pk__in=[c['id'] for c in cached])
        
        # Получаем данные из БД
        queryset = super().get_queryset()
        serialized = CategorySerializer(queryset, many=True).data
        
        # Кэшируем результат
        CacheManager.set(cache_key, serialized, timeout=60 * 60)  # 1 час
        
        return queryset

class AttributeViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для характеристик (только чтение)"""
    queryset = Attribute.objects.all()
    serializer_class = AttributeSerializer
    permission_classes = [permissions.AllowAny]


class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet для товаров"""
    queryset = Product.objects.select_related('supplier', 'category').prefetch_related('attributes__attribute')
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['supplier', 'category', 'is_active']
    search_fields = ['name', 'sku', 'description']
    ordering_fields = ['name', 'price', 'created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Клиенты видят только активные товары
        if self.request.user.user_type == 'client':
            queryset = queryset.filter(is_active=True, stock_quantity__gt=0)
        
        # Поставщики видят только свои товары
        if self.request.user.user_type == 'supplier':
            queryset = queryset.filter(supplier__user=self.request.user)
        
        # Кэширование для списка товаров
        if self.action == 'list':
            cache_key = CacheKeyBuilder.product_catalog(
                supplier_id=self.request.user.id if self.request.user.user_type == 'supplier' else None,
                is_active=True if self.request.user.user_type == 'client' else None
            )
            return QuerySetCache.get_or_set(queryset, cache_key, timeout=60 * 10)  # 10 минут
        
        return queryset
    
    def _detect_format(self, filename, specified_format):
        """Определяет формат файла"""
        if specified_format != 'auto':
            return specified_format
        
        ext = filename.lower().split('.')[-1]
        format_mapping = {
            'csv': 'csv',
            'json': 'json',
            'yaml': 'yaml',
            'yml': 'yaml'
        }
        
        return format_mapping.get(ext, 'csv')
    
    def _parse_csv(self, file_content):
        """Парсит CSV файл"""
        csv_file = io.StringIO(file_content)
        reader = csv.DictReader(csv_file)
        return list(reader)
    
    def _parse_json(self, file_content):
        """Парсит JSON файл"""
        return json.loads(file_content)
    
    def _parse_yaml(self, file_content):
        """Парсит YAML файл"""
        return yaml.safe_load(file_content)
    
    def _validate_product_data(self, product_data, row_num=None):
        """Валидация данных товара"""
        errors = []
        
        # Обязательные поля
        required_fields = ['sku', 'name', 'price', 'stock_quantity']
        for field in required_fields:
            if field not in product_data or not product_data[field]:
                errors.append(f"Отсутствует обязательное поле: {field}")
        
        # Валидация цены
        try:
            if 'price' in product_data:
                price = Decimal(str(product_data['price']))
                if price <= 0:
                    errors.append("Цена должна быть положительной")
        except (ValueError, TypeError):
            errors.append("Некорректный формат цены")
        
        # Валидация количества
        try:
            if 'stock_quantity' in product_data:
                qty = int(product_data['stock_quantity'])
                if qty < 0:
                    errors.append("Количество не может быть отрицательным")
        except (ValueError, TypeError):
            errors.append("Некорректный формат количества")
        
        # Валидация себестоимости
        if 'cost_price' in product_data and product_data['cost_price']:
            try:
                cost_price = Decimal(str(product_data['cost_price']))
                if cost_price < 0:
                    errors.append("Себестоимость не может быть отрицательной")
            except (ValueError, TypeError):
                errors.append("Некорректный формат себестоимости")
        
        if row_num:
            errors = [f"Строка {row_num}: {error}" for error in errors]
        
        return errors
    
    def _process_product_record(self, product_data, supplier, update_existing, row_num=None):
        """Обрабатывает одну запись товара"""
        errors = self._validate_product_data(product_data, row_num)
        
        if errors:
            return False, errors
        
        try:
            # Поиск или создание категории
            category_name = product_data.get('category', 'Без категории')
            category, _ = Category.objects.get_or_create(name=category_name)
            
            # Данные товара
            product_defaults = {
                'supplier': supplier,
                'category': category,
                'name': product_data['name'],
                'description': product_data.get('description', ''),
                'price': Decimal(str(product_data['price'])),
                'stock_quantity': int(product_data['stock_quantity']),
                'min_order_quantity': int(product_data.get('min_order_quantity', 1)),
                'unit': product_data.get('unit', 'шт'),
                'is_active': str(product_data.get('is_active', 'true')).lower() == 'true'
            }
            
            if 'cost_price' in product_data and product_data['cost_price']:
                product_defaults['cost_price'] = Decimal(str(product_data['cost_price']))
            
            # Поиск или создание товара
            if update_existing:
                product, created = Product.objects.update_or_create(
                    sku=product_data['sku'],
                    defaults=product_defaults
                )
            else:
                product, created = Product.objects.get_or_create(
                    sku=product_data['sku'],
                    defaults=product_defaults
                )
            
            # Обработка характеристик
            attributes_data = product_data.get('attributes', {})
            
            # Поддержка разных форматов характеристик
            if isinstance(attributes_data, str):
                # Формат: "цвет:красный;размер:42"
                attr_pairs = attributes_data.split(';')
                for pair in attr_pairs:
                    if ':' in pair:
                        attr_name, attr_value = pair.split(':', 1)
                        attr_name = attr_name.strip()
                        attr_value = attr_value.strip()
                        
                        if attr_name and attr_value:
                            attribute, _ = Attribute.objects.get_or_create(name=attr_name)
                            ProductAttribute.objects.update_or_create(
                                product=product,
                                attribute=attribute,
                                defaults={'value': attr_value}
                            )
            elif isinstance(attributes_data, dict):
                # Формат: {"цвет": "красный", "размер": "42"}
                for attr_name, attr_value in attributes_data.items():
                    if attr_name and attr_value:
                        attribute, _ = Attribute.objects.get_or_create(name=attr_name)
                        ProductAttribute.objects.update_or_create(
                            product=product,
                            attribute=attribute,
                            defaults={'value': str(attr_value)}
                        )
            elif isinstance(attributes_data, list):
                # Формат: [{"name": "цвет", "value": "красный"}, ...]
                for attr_item in attributes_data:
                    if isinstance(attr_item, dict) and 'name' in attr_item and 'value' in attr_item:
                        attribute, _ = Attribute.objects.get_or_create(name=attr_item['name'])
                        ProductAttribute.objects.update_or_create(
                            product=product,
                            attribute=attribute,
                            defaults={'value': str(attr_item['value'])}
                        )
            
            return True, []
            
        except Exception as e:
            error_msg = f"Ошибка обработки товара {product_data.get('sku', 'N/A')}: {str(e)}"
            if row_num:
                error_msg = f"Строка {row_num}: {error_msg}"
            return False, [error_msg]
    
    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser], url_path='import')
    def import_products(self, request):
        """
        Импорт товаров из файла.
        
        Поддерживаемые форматы:
        - CSV: колонки как в примере
        - JSON: массив объектов с полями товара
        - YAML: аналогично JSON
        
        Пример структуры данных:
        {
            "sku": "PRD001",
            "name": "Товар 1",
            "category": "Электроника",
            "price": 1000.50,
            "cost_price": 800.00,
            "stock_quantity": 50,
            "min_order_quantity": 1,
            "unit": "шт",
            "is_active": true,
            "description": "Описание товара",
            "attributes": {
                "цвет": "черный",
                "размер": "42"
            }
        }
        """
        serializer = ProductImportSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        file = request.FILES['file']
        update_existing = serializer.validated_data.get('update_existing', True)
        specified_format = serializer.validated_data.get('format', 'auto')
        
        # Определяем формат файла
        file_format = self._detect_format(file.name, specified_format)
        
        # Проверяем поддерживаемый формат
        if file_format not in ['csv', 'json', 'yaml']:
            return Response(
                {'error': f'Неподдерживаемый формат файла: {file_format}. Поддерживаются: csv, json, yaml'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Читаем содержимое файла
        try:
            file_content = file.read().decode('utf-8')
        except UnicodeDecodeError:
            return Response(
                {'error': 'Ошибка декодирования файла. Убедитесь, что файл в кодировке UTF-8'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Парсим файл в зависимости от формата
        try:
            if file_format == 'csv':
                products_data = self._parse_csv(file_content)
            elif file_format == 'json':
                products_data = self._parse_json(file_content)
            elif file_format == 'yaml':
                products_data = self._parse_yaml(file_content)
        except Exception as e:
            return Response(
                {'error': f'Ошибка парсинга {file_format.upper()} файла: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Проверяем, что получили список
        if not isinstance(products_data, list):
            return Response(
                {'error': f'{file_format.upper()} файл должен содержать массив объектов'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Проверяем права доступа
        if request.user.user_type != 'supplier':
            return Response(
                {'error': 'Импорт товаров доступен только для поставщиков'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        supplier = request.user.supplier_profile
        
        # Обрабатываем товары
        success_count = 0
        failed_count = 0
        errors = []
        
        with transaction.atomic():
            for idx, product_data in enumerate(products_data, start=1):
                row_num = idx if file_format == 'csv' else None
                success, record_errors = self._process_product_record(
                    product_data, supplier, update_existing, row_num
                )
                
                if success:
                    success_count += 1
                else:
                    failed_count += 1
                    errors.extend(record_errors)
        
        # Создаем лог
        log = PriceUpdateLog.objects.create(
            supplier=supplier,
            file_name=file.name,
            records_count=success_count + failed_count,
            success_count=success_count,
            failed_count=failed_count,
            notes='\n'.join(errors) if errors else ''
        )
        
        # Формируем ответ
        response_data = {
            'message': f'Импорт из {file_format.upper()} завершен',
            'format': file_format,
            'success_count': success_count,
            'failed_count': failed_count,
            'total_count': success_count + failed_count,
            'log_id': log.id
        }
        
        if errors:
            response_data['errors'] = errors[:10]  # Ограничиваем вывод первыми 10 ошибками
            if len(errors) > 10:
                response_data['errors_truncated'] = True
                response_data['total_errors'] = len(errors)
        
        return Response(response_data)
    
    @action(detail=False, methods=['get'])
    def my_products(self, request):
        """Получить товары текущего поставщика"""
        if request.user.user_type != 'supplier':
            return Response(
                {'error': 'Только для поставщиков'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        products = self.get_queryset().filter(supplier__user=request.user)
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def export_template(self, request):
        """
        Получить шаблон для импорта в разных форматах
        """
        format_param = request.query_params.get('format', 'json')
        
        template_data = {
            "sku": "PRD001",
            "name": "Наименование товара",
            "category": "Категория товара",
            "price": 1000.50,
            "cost_price": 800.00,
            "stock_quantity": 50,
            "min_order_quantity": 1,
            "unit": "шт",
            "is_active": True,
            "description": "Описание товара",
            "attributes": {
                "цвет": "черный",
                "размер": "42",
                "материал": "хлопок"
            }
        }
        
        # Можно запросить несколько товаров в шаблоне
        template = [template_data]
        
        if format_param == 'json':
            return Response(template, content_type='application/json')
        elif format_param in ['yaml', 'yml']:
            yaml_content = yaml.dump(template, allow_unicode=True, default_flow_style=False)
            return Response(yaml_content, content_type='application/yaml')
        elif format_param == 'csv':
            # Создаем CSV шаблон
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=template_data.keys())
            writer.writeheader()
            writer.writerow(template_data)
            
            return Response(output.getvalue(), content_type='text/csv')
        else:
            return Response(
                {'error': 'Неподдерживаемый формат. Доступны: json, yaml, csv'},
                status=status.HTTP_400_BAD_REQUEST
            )

class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet для заказов"""
    queryset = Order.objects.select_related('client').prefetch_related(
        'items__product', 'items__supplier'
    )
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'created_at']
    ordering_fields = ['created_at', 'total_amount']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Клиенты видят только свои заказы
        if self.request.user.user_type == 'client':
            queryset = queryset.filter(client=self.request.user)
        
        # Поставщики видят заказы со своими товарами
        if self.request.user.user_type == 'supplier':
            supplier = self.request.user.supplier_profile
            queryset = queryset.filter(
                items__supplier=supplier
            ).distinct()
        
        return queryset
    
    def perform_create(self, serializer):
        # Устанавливаем клиента автоматически
        serializer.save(client=self.request.user)
        
        # Отправляем подтверждение на email клиента
        order = serializer.instance
        send_order_confirmation_email.delay(order.id)
        
        # Отправляем накладную администратору
        send_invoice_email.delay(order.id)
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Подтвердить заказ (для поставщика)"""
        order = self.get_object()
        
        if request.user.user_type != 'supplier':
            return Response(
                {'error': 'Только поставщики могут подтверждать заказы'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Проверяем, что заказ содержит товары этого поставщика
        supplier = request.user.supplier_profile
        if not order.items.filter(supplier=supplier).exists():
            return Response(
                {'error': 'Этот заказ не содержит ваших товаров'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'confirmed'
        order.confirmed_at = timezone.now()
        order.save()
        
        return Response({'message': 'Заказ подтвержден'})
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Отменить заказ"""
        order = self.get_object()
        
        # Только клиент может отменить свой заказ
        if order.client != request.user:
            return Response(
                {'error': 'Вы можете отменить только свои заказы'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if order.status in ['shipped', 'delivered']:
            return Response(
                {'error': 'Нельзя отменить заказ, который уже отправлен или доставлен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        order.status = 'cancelled'
        order.save()
        
        return Response({'message': 'Заказ отменен'})
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Статистика по заказам с кэшированием"""
         # Определяем ключ кэша в зависимости от пользователя
        if request.user.user_type == 'supplier':
            cache_key = CacheKeyBuilder.order_statistics()
        else:
            cache_key = CacheKeyBuilder.order_statistics(request.user.id)
        
        cached = CacheManager.get(cache_key)
        if cached is not None:
            logger.debug("Using cached order statistics")
            return Response(cached)
        
        # Получаем данные из БД
        queryset = self.get_queryset()
        
        stats = {
            'total_orders': queryset.count(),
            'total_amount': queryset.aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
            'by_status': {},
            'recent_orders': OrderSerializer(
                queryset.order_by('-created_at')[:10],
                many=True
            ).data
        }
        
        for status_choice in Order.STATUS_CHOICES:
            status_value = status_choice[0]
            stats['by_status'][status_value] = queryset.filter(status=status_value).count()
            
        # Кэшируем результат
        CacheManager.set(cache_key, stats, timeout=60 * 2)  # 2 минуты
        
        return Response(stats)


class PriceUpdateLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для логов обновления прайса"""
    queryset = PriceUpdateLog.objects.select_related('supplier')
    serializer_class = PriceUpdateLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Поставщики видят только свои логи
        if self.request.user.user_type == 'supplier':
            queryset = queryset.filter(supplier__user=self.request.user)
        
        return queryset