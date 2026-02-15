"""
Тесты для троттлинга
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from unittest.mock import patch
import time

User = get_user_model()


class ThrottlingTests(TestCase):
    """Тесты для проверки работы троттлинга"""
    
    def setUp(self):
        """Настройка перед каждым тестом"""
        self.client = APIClient()
        
        # Создаём тестового пользователя
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123',
            user_type='client'
        )
        
        # Получаем токен для аутентификации
        response = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'testuser', 'password': 'TestPass123'}
        )
        self.access_token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
    
    def test_login_throttling(self):
        """Тест: ограничение количества запросов на вход"""
        url = reverse('user-login')
        
        # Делаем 5 запросов (лимит: 5/минуту)
        for i in range(5):
            response = self.client.post(url, {
                'username': 'testuser',
                'password': 'TestPass123'
            })
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 6-й запрос должен быть отклонён
        response = self.client.post(url, {
            'username': 'testuser',
            'password': 'TestPass123'
        })
        
        # Ожидаем 429 Too Many Requests
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('detail', response.data)
        print(f"✓ Троттлинг входа работает: {response.data['detail']}")
    
    def test_register_throttling(self):
        """Тест: ограничение количества запросов на регистрацию"""
        url = reverse('user-register')
        
        # Регистрируем 10 пользователей (лимит: 10/час)
        for i in range(10):
            response = self.client.post(url, {
                'username': f'newuser{i}',
                'email': f'newuser{i}@example.com',
                'password': 'TestPass123',
                'password_confirm': 'TestPass123',
                'user_type': 'client'
            })
            # Первые запросы должны пройти
            if i < 10:
                self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])
        
        # 11-й запрос должен быть отклонён
        response = self.client.post(url, {
            'username': 'newuser11',
            'email': 'newuser11@example.com',
            'password': 'TestPass123',
            'password_confirm': 'TestPass123',
            'user_type': 'client'
        })
        
        # Ожидаем 429 Too Many Requests
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        print(f"✓ Троттлинг регистрации работает: {response.data['detail']}")
    
    def test_product_list_throttling(self):
        """Тест: ограничение запросов к списку товаров"""
        url = reverse('product-list')
        
        # Делаем 60 запросов (лимит: 60/минуту)
        for i in range(60):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 61-й запрос должен быть отклонён
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        print(f"✓ Троттлинг списка товаров работает: {response.data['detail']}")
    
    def test_order_create_throttling(self):
        """Тест: ограничение создания заказов"""
        url = reverse('order-list')
        
        # Создаём 20 заказов (лимит: 20/час)
        for i in range(20):
            response = self.client.post(url, {
                'delivery_address': 'Test Address',
                'contact_phone': '+79001234567',
                'items': []  # В реальном тесте добавьте валидные товары
            }, format='json')
            
            # Некоторые запросы могут быть 400 из-за валидации, но не 429
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        
        # 21-й запрос должен быть отклонён
        response = self.client.post(url, {
            'delivery_address': 'Test Address',
            'contact_phone': '+79001234567',
            'items': []
        }, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        print(f"✓ Троттлинг создания заказов работает: {response.data['detail']}")
    
    def test_anon_throttling(self):
        """Тест: ограничение для анонимных пользователей"""
        self.client.logout()  # Отключаем аутентификацию
        
        url = reverse('product-list')
        
        # Делаем 100 запросов (лимит анонимов: 100/час)
        for i in range(100):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 101-й запрос должен быть отклонён
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        print(f"✓ Троттлинг для анонимов работает: {response.data['detail']}")
    
    def test_throttle_headers(self):
        """Тест: проверка заголовков троттлинга"""
        url = reverse('product-list')
        
        # Первый запрос
        response = self.client.get(url)
        
        # Проверяем наличие заголовков троттлинга
        self.assertIn('X-RateLimit-Limit', response.headers)
        self.assertIn('X-RateLimit-Remaining', response.headers)
        self.assertIn('X-RateLimit-Reset', response.headers)
        
        remaining = int(response.headers['X-RateLimit-Remaining'])
        print(f"✓ Заголовки троттлинга присутствуют. Осталось: {remaining} запросов")
    
    def test_burst_protection(self):
        """Тест: защита от коротких всплесков запросов"""
        url = reverse('product-list')
        
        # Быстро делаем 15 запросов подряд (лимит: 10/секунду)
        start_time = time.time()
        for i in range(15):
            response = self.client.get(url)
            # Первые 10 должны пройти
            if i >= 10:
                # Запросы 11-15 должны быть отклонены
                self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        
        elapsed = time.time() - start_time
        print(f"✓ Защита от всплесков работает. Время: {elapsed:.2f} сек")
    
    @patch('api.throttling.ProductListRateThrottle.allow_request')
    def test_custom_throttle_logic(self, mock_allow_request):
        """Тест: кастомная логика троттлинга для поставщиков"""
        # Создаём поставщика
        supplier = User.objects.create_user(
            username='supplier1',
            email='supplier@example.com',
            password='TestPass123',
            user_type='supplier'
        )
        
        # Мокаем метод allow_request
        mock_allow_request.return_value = True
        
        # Аутентифицируем как поставщика
        response = self.client.post(
            reverse('token_obtain_pair'),
            {'username': 'supplier1', 'password': 'TestPass123'}
        )
        supplier_token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {supplier_token}')
        
        # Запрос к списку товаров
        url = reverse('product-list')
        response = self.client.get(url)
        
        # Проверяем, что кастомный троттлер вызвался
        self.assertTrue(mock_allow_request.called)
        print("✓ Кастомный троттлер для поставщиков вызывается")


class ThrottlingResponseTests(TestCase):
    """Тесты для проверки формата ответов при троттлинге"""
    
    def setUp(self):
        self.client = APIClient()
    
    def test_throttle_response_format(self):
        """Тест: формат ответа при превышении лимита"""
        url = reverse('product-list')
        
        # Мокаем троттлер для имитации превышения лимита
        with patch('rest_framework.throttling.UserRateThrottle.allow_request', return_value=False):
            with patch('rest_framework.throttling.UserRateThrottle.wait', return_value=60):
                response = self.client.get(url)
                
                # Проверяем статус
                self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
                
                # Проверяем формат ответа
                self.assertIn('detail', response.data)
                self.assertIn('available_in', response.data)
                
                # Проверяем типы данных
                self.assertIsInstance(response.data['detail'], str)
                self.assertIsInstance(response.data['available_in'], int)
                
                print(f"✓ Формат ответа троттлинга корректен: {response.data}")
    
    def test_throttle_retry_after_header(self):
        """Тест: заголовок Retry-After"""
        url = reverse('product-list')
        
        with patch('rest_framework.throttling.UserRateThrottle.allow_request', return_value=False):
            with patch('rest_framework.throttling.UserRateThrottle.wait', return_value=60):
                response = self.client.get(url)
                
                # Проверяем наличие заголовка Retry-After
                self.assertIn('Retry-After', response.headers)
                self.assertEqual(response.headers['Retry-After'], '60')
                
                print(f"✓ Заголовок Retry-After присутствует: {response.headers['Retry-After']} сек")