from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import User, Supplier, Product, Order, Category
from .cache_utils import invalidate_cache_on_save, invalidate_cache_on_delete

# Подключаем сигналы для инвалидации кэша
@receiver(post_save, sender=User)
def user_saved(sender, instance, **kwargs):
    invalidate_cache_on_save(sender, instance, **kwargs)

@receiver(post_delete, sender=User)
def user_deleted(sender, instance, **kwargs):
    invalidate_cache_on_delete(sender, instance, **kwargs)

@receiver(post_save, sender=Product)
def product_saved(sender, instance, **kwargs):
    invalidate_cache_on_save(sender, instance, **kwargs)

@receiver(post_delete, sender=Product)
def product_deleted(sender, instance, **kwargs):
    invalidate_cache_on_delete(sender, instance, **kwargs)

@receiver(post_save, sender=Order)
def order_saved(sender, instance, **kwargs):
    invalidate_cache_on_save(sender, instance, **kwargs)

@receiver(post_delete, sender=Order)
def order_deleted(sender, instance, **kwargs):
    invalidate_cache_on_delete(sender, instance, **kwargs)

@receiver(post_save, sender=Category)
def category_saved(sender, instance, **kwargs):
    invalidate_cache_on_save(sender, instance, **kwargs)

@receiver(post_delete, sender=Category)
def category_deleted(sender, instance, **kwargs):
    invalidate_cache_on_delete(sender, instance, **kwargs)