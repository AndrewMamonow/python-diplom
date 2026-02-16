from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    UserViewSet, 
    SupplierViewSet, 
    CategoryViewSet,
    AttributeViewSet, 
    ProductViewSet, 
    OrderViewSet,
    PriceUpdateLogViewSet
)
from .social_views import (
    SocialAuthRedirectView,
    SocialAuthCallbackView,
    SocialAuthErrorView,
    SocialAuthProvidersView
)


router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'attributes', AttributeViewSet, basename='attribute')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'price-update-logs', PriceUpdateLogViewSet, basename='price-update-log')

urlpatterns = [
    path('', include(router.urls)),
    
     # Социальная аутентификация
    path('auth/social/providers/', SocialAuthProvidersView.as_view(), name='social-providers'),
    path('auth/social/<str:backend>/redirect/', SocialAuthRedirectView.as_view(), name='social-redirect'),
    path('auth/social/<str:backend>/callback/', SocialAuthCallbackView.as_view(), name='social-callback'),
    path('auth/social/error/', SocialAuthErrorView.as_view(), name='social-error'),
    
    # URL для python-social-auth
    path('auth/social/', include('social_django.urls', namespace='social')),
    
    # JWT endpoints
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
     # User endpoints
    path('users/<int:pk>/upload-avatar/', UserViewSet.as_view({'patch': 'upload_avatar'}), name='user-upload-avatar'),
    path('users/<int:pk>/delete-avatar/', UserViewSet.as_view({'delete': 'delete_avatar'}), name='user-delete-avatar'),
    
    # Product endpoints
    path('products/<int:pk>/upload-image/', ProductViewSet.as_view({'patch': 'upload_image'}), name='product-upload-image'),
    path('products/<int:pk>/add-additional-image/', ProductViewSet.as_view({'post': 'add_additional_image'}), name='product-add-additional-image'),
    path('products/<int:pk>/remove-additional-image/', ProductViewSet.as_view({'delete': 'remove_additional_image'}), name='product-remove-additional-image'),
    
    # Order endpoints
    path('orders/<int:pk>/confirm/', 
         OrderViewSet.as_view({'post': 'confirm'}), 
         name='order-confirm'),
    path('orders/<int:pk>/cancel/', 
         OrderViewSet.as_view({'post': 'cancel'}), 
         name='order-cancel'),
    path('orders/statistics/', 
         OrderViewSet.as_view({'get': 'statistics'}), 
         name='order-statistics'),
]

urlpatterns += router.urls