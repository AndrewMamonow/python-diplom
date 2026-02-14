"""
Утилиты для кэширования
"""
import json
import functools
import logging
from django.core.cache import cache
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.db.models import QuerySet
from typing import Optional, Any, Callable, TypeVar
import hashlib

logger = logging.getLogger(__name__)

T = TypeVar('T')

class CacheKeyBuilder:
    """Построитель ключей кэша"""
    
    @staticmethod
    def _normalize_key(key: str) -> str:
        """Нормализация ключа (удаление недопустимых символов)"""
        return hashlib.md5(key.encode()).hexdigest()
    
    @staticmethod
    def model_list(model_name: str, filters: dict = None) -> str:
        """Ключ для списка объектов модели"""
        base = f"model_list:{model_name}"
        if filters:
            filter_str = json.dumps(filters, sort_keys=True)
            base += f":{filter_str}"
        return CacheKeyBuilder._normalize_key(base)
    
    @staticmethod
    def model_instance(model_name: str, pk: Any) -> str:
        """Ключ для конкретного объекта модели"""
        return CacheKeyBuilder._normalize_key(f"model:{model_name}:pk:{pk}")
    
    @staticmethod
    def model_count(model_name: str, filters: dict = None) -> str:
        """Ключ для подсчёта объектов"""
        base = f"model_count:{model_name}"
        if filters:
            filter_str = json.dumps(filters, sort_keys=True)
            base += f":{filter_str}"
        return CacheKeyBuilder._normalize_key(base)
    
    @staticmethod
    def user_data(user_id: int) -> str:
        """Ключ для данных пользователя"""
        return CacheKeyBuilder._normalize_key(f"user:{user_id}")
    
    @staticmethod
    def order_statistics(user_id: Optional[int] = None) -> str:
        """Ключ для статистики заказов"""
        base = "order_statistics"
        if user_id:
            base += f":user:{user_id}"
        return CacheKeyBuilder._normalize_key(base)
    
    @staticmethod
    def product_catalog(
        supplier_id: Optional[int] = None,
        category_id: Optional[int] = None,
        is_active: Optional[bool] = None
    ) -> str:
        """Ключ для каталога товаров"""
        base = "product_catalog"
        if supplier_id:
            base += f":supplier:{supplier_id}"
        if category_id:
            base += f":category:{category_id}"
        if is_active is not None:
            base += f":active:{is_active}"
        return CacheKeyBuilder._normalize_key(base)


class CacheManager:
    """Менеджер кэширования"""
    
    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """Получить значение из кэша"""
        try:
            value = cache.get(key)
            if value is not None:
                logger.debug(f"Cache HIT: {key}")
                return value
            logger.debug(f"Cache MISS: {key}")
            return default
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return default
    
    @staticmethod
    def set(key: str, value: Any, timeout: int = DEFAULT_TIMEOUT) -> bool:
        """Установить значение в кэш"""
        try:
            cache.set(key, value, timeout)
            logger.debug(f"Cache SET: {key} (timeout: {timeout}s)")
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    @staticmethod
    def delete(key: str) -> bool:
        """Удалить значение из кэша"""
        try:
            cache.delete(key)
            logger.debug(f"Cache DELETE: {key}")
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    @staticmethod
    def delete_pattern(pattern: str) -> int:
        """Удалить все ключи по паттерну (требует redis)"""
        try:
            count = 0
            for key in cache.keys(pattern):
                cache.delete(key)
                count += 1
            logger.debug(f"Cache DELETE PATTERN: {pattern} ({count} keys)")
            return count
        except Exception as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")
            return 0
    
    @staticmethod
    def clear() -> bool:
        """Очистить весь кэш"""
        try:
            cache.clear()
            logger.info("Cache CLEARED")
            return True
        except Exception as e:
            logger.error(f"Cache clear error: {e}")
            return False


def cache_model_method(timeout: int = 60 * 15):
    """
    Декоратор для кэширования методов модели
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Создаём ключ на основе имени функции и аргументов
            instance = args[0] if args else None
            func_name = f"{instance.__class__.__name__}.{func.__name__}" if instance else func.__name__
            key_args = f"{args[1:] if args else args}:{kwargs}"
            cache_key = CacheKeyBuilder._normalize_key(f"{func_name}:{key_args}")
            
            # Пытаемся получить из кэша
            cached = CacheManager.get(cache_key)
            if cached is not None:
                return cached
            
            # Выполняем функцию и кэшируем результат
            result = func(*args, **kwargs)
            CacheManager.set(cache_key, result, timeout)
            return result
        return wrapper
    return decorator


def invalidate_cache_on_save(sender, instance, **kwargs):
    """
    Signal для инвалидации кэша при сохранении модели
    """
    model_name = sender.__name__.lower()
    
    # Удаляем кэш для этого объекта
    CacheManager.delete(CacheKeyBuilder.model_instance(model_name, instance.pk))
    
    # Удаляем кэш для списка этой модели
    CacheManager.delete_pattern(f"*model_list:{model_name}*")
    
    # Специальная обработка для связанных моделей
    if model_name == 'product':
        # Инвалидируем кэш каталога товаров
        CacheManager.delete_pattern(f"*product_catalog*")
    
    elif model_name == 'order':
        # Инвалидируем кэш статистики заказов
        CacheManager.delete_pattern(f"*order_statistics*")
        if instance.client_id:
            CacheManager.delete(CacheKeyBuilder.order_statistics(instance.client_id))
    
    elif model_name == 'user':
        # Инвалидируем кэш данных пользователя
        CacheManager.delete(CacheKeyBuilder.user_data(instance.pk))


def invalidate_cache_on_delete(sender, instance, **kwargs):
    """
    Signal для инвалидации кэша при удалении модели
    """
    model_name = sender.__name__.lower()
    
    # Удаляем кэш для этого объекта
    CacheManager.delete(CacheKeyBuilder.model_instance(model_name, instance.pk))
    
    # Удаляем кэш для списка этой модели
    CacheManager.delete_pattern(f"*model_list:{model_name}*")


class QuerySetCache:
    """Кэширование QuerySet"""
    
    @staticmethod
    def get_or_set(
        queryset: QuerySet,
        cache_key: str,
        timeout: int = DEFAULT_TIMEOUT,
        use_pickle: bool = True
    ) -> QuerySet:
        """
        Получить QuerySet из кэша или выполнить запрос и закэшировать
        """
        cached = CacheManager.get(cache_key)
        if cached is not None:
            return cached
        
        # Выполняем запрос
        result = list(queryset)  # Выполняем запрос
        
        # Кэшируем результат
        CacheManager.set(cache_key, result, timeout)
        
        # Возвращаем новый QuerySet
        return queryset