"""
Views для социальной аутентификации
"""
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from social_django.utils import psa
from social_core.exceptions import AuthException
from urllib.parse import urlencode
import logging

logger = logging.getLogger(__name__)


class SocialAuthRedirectView(APIView):
    """
    Редирект для начала социальной аутентификации
    
    Возвращает URL для перенаправления пользователя на страницу авторизации провайдера
    """
    permission_classes = [AllowAny]
    
    def get(self, request, backend):
        """
        Получить URL для авторизации через соц. сеть
        
        Параметры:
            backend: Название провайдера (google, github, vk, yandex)
        """
        try:
            # URL для обработки callback
            redirect_uri = request.build_absolute_uri(
                reverse('social:complete', kwargs={'backend': backend})
            )
            
            # Добавляем параметры для возврата в фронтенд
            frontend_redirect = request.GET.get('frontend_redirect', '/')
            
            # Формируем параметры
            params = {
                'redirect_uri': redirect_uri,
                'frontend_redirect': frontend_redirect,
                'backend': backend,
            }
            
            # URL для начала авторизации
            auth_url = reverse('social:begin', kwargs={'backend': backend})
            auth_url += '?' + urlencode(params)
            
            return Response({
                'auth_url': request.build_absolute_uri(auth_url),
                'backend': backend,
                'message': f'Redirect to {backend} for authentication'
            })
            
        except Exception as e:
            logger.error(f"Error generating auth URL: {e}")
            return Response(
                {'error': 'Failed to generate auth URL'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SocialAuthCallbackView(APIView):
    """
    Callback view для обработки ответа от социального провайдера
    
    Этот эндпоинт вызывается после успешной авторизации на стороне провайдера
    """
    permission_classes = [AllowAny]
    
    @psa('social:complete')
    def post(self, request, backend):
        """
        Обработка callback от социального провайдера
        
        Провайдер перенаправляет сюда после авторизации с кодом авторизации
        """
        try:
            # Получаем токен от провайдера
            user = request.backend.complete(request)
            
            if user:
                # Генерируем JWT токен
                from rest_framework_simplejwt.tokens import RefreshToken
                refresh = RefreshToken.for_user(user)
                
                # Получаем данные пользователя
                from .serializers import UserSerializer
                user_data = UserSerializer(user, context={'request': request}).data
                
                # Получаем frontend_redirect из сессии
                frontend_redirect = request.session.get('frontend_redirect', '/')
                
                response_data = {
                    'user': user_data,
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                    'frontend_redirect': frontend_redirect,
                    'message': 'Authentication successful'
                }
                
                logger.info(f"Social authentication successful for {user.username}")
                
                return Response(response_data, status=status.HTTP_200_OK)
            
            return Response(
                {'error': 'Authentication failed'},
                status=status.HTTP_401_UNAUTHORIZED
            )
            
        except AuthException as e:
            logger.error(f"Social auth exception: {e}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error in social auth callback: {e}", exc_info=True)
            return Response(
                {'error': 'Authentication error'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class SocialAuthErrorView(APIView):
    """
    View для обработки ошибок социальной аутентификации
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        error = request.GET.get('error', 'Unknown error')
        error_description = request.GET.get('error_description', '')
        
        logger.warning(f"Social auth error: {error} - {error_description}")
        
        return Response({
            'error': error,
            'error_description': error_description,
            'message': 'Social authentication failed'
        }, status=status.HTTP_400_BAD_REQUEST)


class SocialAuthProvidersView(APIView):
    """
    Получение списка доступных провайдеров социальной аутентификации
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        providers = [
            {
                'name': 'Google',
                'backend': 'google-oauth2',
                'icon': 'google',
                'enabled': bool(request.settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY)
            },
            {
                'name': 'GitHub',
                'backend': 'github',
                'icon': 'github',
                'enabled': bool(request.settings.SOCIAL_AUTH_GITHUB_KEY)
            },
            {
                'name': 'VK',
                'backend': 'vk-oauth2',
                'icon': 'vk',
                'enabled': bool(request.settings.SOCIAL_AUTH_VK_OAUTH2_KEY)
            },
            {
                'name': 'Yandex',
                'backend': 'yandex',
                'icon': 'yandex',
                'enabled': bool(request.settings.SOCIAL_AUTH_YANDEX_OAUTH2_KEY)
            },
        ]
        
        # Фильтруем только включённые провайдеры
        enabled_providers = [p for p in providers if p['enabled']]
        
        return Response({
            'providers': enabled_providers,
            'count': len(enabled_providers)
        })