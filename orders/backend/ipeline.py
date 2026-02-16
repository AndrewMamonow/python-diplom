"""
Custom pipeline для социальной аутентификации
"""
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils.crypto import get_random_string
from .models import Supplier
import logging

logger = logging.getLogger(__name__)


def create_user_profile(strategy, details, user=None, *args, **kwargs):
    """
    Создание профиля пользователя после социальной аутентификации
    
    Этот шаг выполняется после создания пользователя в базе данных
    """
    if user:
        # Устанавливаем тип пользователя (по умолчанию - клиент)
        if not hasattr(user, 'user_type') or not user.user_type:
            user.user_type = 'client'
            user.is_active = True
            user.save()
        
        # Генерируем код поставщика если нужно
        if user.user_type == 'supplier' and not user.supplier_code:
            user.supplier_code = f'SUP{get_random_string(8).upper()}'
            user.save()
        
        # Создаём профиль поставщика если это поставщик
        if user.user_type == 'supplier' and not hasattr(user, 'supplier_profile'):
            try:
                Supplier.objects.create(
                    user=user,
                    company_name=details.get('company_name', user.username),
                    contact_person=f"{user.first_name} {user.last_name}".strip() or user.username,
                    phone=details.get('phone', ''),
                    email=user.email or details.get('email', ''),
                    address=details.get('address', ''),
                    tax_number=details.get('tax_number', None)
                )
                logger.info(f"Created supplier profile for {user.username}")
            except Exception as e:
                logger.error(f"Error creating supplier profile: {e}")
        
        logger.info(f"User profile created/updated for {user.username}")
    
    return {'user': user}


def generate_jwt_token(strategy, user=None, *args, **kwargs):
    """
    Генерация JWT токена после успешной аутентификации
    
    Возвращает токены для использования в ответе
    """
    if user:
        refresh = RefreshToken.for_user(user)
        
        return {
            'user': user,
            'jwt_tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }
    
    return {}


def validate_email(strategy, details, backend, user=None, *args, **kwargs):
    """
    Валидация email перед созданием пользователя
    """
    email = details.get('email')
    
    if not email:
        raise ValueError('Email is required for social authentication')
    
    # Проверка домена (опционально)
    allowed_domains = getattr(strategy.settings, 'SOCIAL_AUTH_ALLOWED_EMAIL_DOMAINS', [])
    if allowed_domains:
        domain = email.split('@')[-1]
        if domain not in allowed_domains:
            raise ValueError(f'Email domain {domain} is not allowed')
    
    return {'details': details}


def check_user_active(strategy, user, *args, **kwargs):
    """
    Проверка активности пользователя
    """
    if user and not user.is_active:
        raise ValueError('User account is inactive')
    
    return {'user': user}


def update_user_details(strategy, details, user=None, *args, **kwargs):
    """
    Обновление данных пользователя из социального профиля
    
    Выполняется при каждом входе через соц. сеть
    """
    if user:
        # Обновляем имя и фамилию
        if details.get('first_name'):
            user.first_name = details['first_name']
        if details.get('last_name'):
            user.last_name = details['last_name']
        
        # Обновляем аватар
        if details.get('picture'):
            # Здесь можно добавить логику загрузки аватара
            pass
        
        # Обновляем телефон если есть
        if details.get('phone'):
            user.phone = details['phone']
        
        user.save()
        
        logger.info(f"Updated user details for {user.username}")
    
    return {'user': user}