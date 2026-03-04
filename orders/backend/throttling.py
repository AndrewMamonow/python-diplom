"""
Кастомные троттлеры для различных сценариев
"""
from rest_framework.throttling import UserRateThrottle, AnonRateThrottle
import logging

logger = logging.getLogger(__name__)


class LoginRateThrottle(UserRateThrottle):
    """Троттлер для эндпоинта входа"""
    scope = 'login'
    
    def throttle_failure(self):
        logger.warning(f"Троттлинг: превышен лимит входа для {self.key}")
        return super().throttle_failure()


class RegisterRateThrottle(AnonRateThrottle):
    """Троттлер для эндпоинта регистрации"""
    scope = 'register'
    
    def throttle_failure(self):
        logger.warning(f"Троттлинг: превышен лимит регистрации для {self.key}")
        return super().throttle_failure()


class ProductListRateThrottle(UserRateThrottle):
    """Троттлер для списка товаров"""
    scope = 'product_list'
    
    def allow_request(self, request, view):
        # Разрешаем больше запросов для поставщиков
        if request.user.is_authenticated and request.user.user_type == 'supplier':
            self.duration = 60  # 1 минута
            self.num_requests = 120  # 120 запросов в минуту для поставщиков
        return super().allow_request(request, view)


class OrderCreateRateThrottle(UserRateThrottle):
    """Троттлер для создания заказов"""
    scope = 'order_create'
    
    def allow_request(self, request, view):
        # Разрешаем больше заказов для клиентов с хорошей историей
        if request.user.is_authenticated:
            # Здесь можно добавить логику проверки истории заказов
            pass
        return super().allow_request(request, view)


class BurstRateThrottle(UserRateThrottle):
    """
    Троттлер для защиты от коротких всплесков запросов
    """
    rate = '10/second'  # 10 запросов в секунду
    
    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class SustainedRateThrottle(UserRateThrottle):
    """
    Троттлер для защиты от длительных атак
    """
    rate = '1000/hour'  # 1000 запросов в час
    
    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)
        
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }