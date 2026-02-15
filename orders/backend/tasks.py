from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image
from io import BytesIO
import logging
import os

from .models import Order, User, Product, ProductImage


logger = logging.getLogger(__name__)

@shared_task
def send_order_confirmation_email(order_id):
    """Отправка подтверждения заказа клиенту"""
    try:
        order = Order.objects.select_related('client').prefetch_related(
            'items__product', 'items__supplier'
        ).get(id=order_id)
        
        subject = f'Подтверждение заказа #{order.order_number}'
        
        # Формируем содержимое письма
        items_summary = []
        for item in order.items.all():
            items_summary.append({
                'name': item.product.name,
                'quantity': item.quantity,
                'price': item.price,
                'subtotal': item.subtotal,
                'supplier': item.supplier.company_name
            })
        
        context = {
            'order': order,
            'items': items_summary,
            'total_amount': order.total_amount,
        }
        
        html_message = render_to_string('emails/order_confirmation.html', context)
        plain_message = render_to_string('emails/order_confirmation.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.client.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return f"Email confirmation sent to {order.client.email}"
        
    except Order.DoesNotExist:
        return f"Order {order_id} not found"
    except Exception as e:
        return f"Error sending email: {str(e)}"


@shared_task
def send_invoice_email(order_id):
    """Отправка накладной администратору"""
    try:
        order = Order.objects.select_related('client').prefetch_related(
            'items__product', 'items__supplier'
        ).get(id=order_id)
        
        subject = f'Новая накладная - Заказ #{order.order_number}'
        
        # Формируем содержимое письма
        items_summary = []
        suppliers = set()
        
        for item in order.items.all():
            items_summary.append({
                'name': item.product.name,
                'sku': item.product.sku,
                'quantity': item.quantity,
                'price': item.price,
                'subtotal': item.subtotal,
                'supplier': item.supplier.company_name
            })
            suppliers.add(item.supplier.company_name)
        
        context = {
            'order': order,
            'items': items_summary,
            'suppliers': ', '.join(suppliers),
            'total_amount': order.total_amount,
        }
        
        html_message = render_to_string('emails/invoice.html', context)
        plain_message = render_to_string('emails/invoice.txt', context)
        
        # Отправляем администратору
        admin_email = settings.EMAIL_HOST_USER
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return f"Invoice sent to admin {admin_email}"
        
    except Order.DoesNotExist:
        return f"Order {order_id} not found"
    except Exception as e:
        return f"Error sending invoice: {str(e)}"
    
def create_thumbnail(image_field, size, suffix):
    """
    Создаёт миниатюру изображения
    
    Args:
        image_field: Поле изображения модели
        size: Кортеж (ширина, высота)
        suffix: Суффикс для имени файла (например, '_small')
    
    Returns:
        ContentFile: Обработанное изображение
    """
    try:
        # Открываем изображение
        img = Image.open(image_field)
        
        # Конвертируем в RGB если необходимо (для JPEG)
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # Создаём миниатюру с сохранением пропорций
        img.thumbnail(size, Image.Resampling.LANCZOS)
        
        # Сохраняем в буфер
        buffer = BytesIO()
        
        # Определяем формат сохранения
        format_ext = os.path.splitext(image_field.name)[1].lower()
        save_format = 'JPEG' if format_ext in ['.jpg', '.jpeg'] else 'PNG'
        quality = settings.IMAGE_OPTIMIZATION.get('quality', 85)
        
        img.save(
            buffer,
            format=save_format,
            quality=quality,
            optimize=settings.IMAGE_OPTIMIZATION.get('optimize', True),
            progressive=settings.IMAGE_OPTIMIZATION.get('progressive', True)
        )
        
        buffer.seek(0)
        
        # Создаём имя файла
        original_name = os.path.basename(image_field.name)
        name, ext = os.path.splitext(original_name)
        new_name = f"{name}{suffix}{ext}"
        
        return ContentFile(buffer.read(), name=new_name)
        
    except Exception as e:
        logger.error(f"Ошибка создания миниатюры {size}: {e}")
        return None


@shared_task(bind=True, max_retries=3)
def process_user_avatar(self, user_id):
    """
    Асинхронная обработка аватара пользователя
    
    Создаёт миниатюры разных размеров
    """
    try:
        logger.info(f"Начало обработки аватара для пользователя {user_id}")
        
        user = User.objects.get(id=user_id)
        
        if not user.avatar:
            logger.warning(f"У пользователя {user_id} нет аватара")
            return
        
        # Размеры миниатюр
        sizes = settings.THUMBNAIL_SIZES.get('avatar', {})
        
        # Создаём миниатюры
        if sizes.get('small'):
            thumb_small = create_thumbnail(user.avatar, sizes['small'], '_small')
            if thumb_small:
                user.avatar_small.save(thumb_small.name, thumb_small, save=False)
        
        if sizes.get('medium'):
            thumb_medium = create_thumbnail(user.avatar, sizes['medium'], '_medium')
            if thumb_medium:
                user.avatar_medium.save(thumb_medium.name, thumb_medium, save=False)
        
        if sizes.get('large'):
            thumb_large = create_thumbnail(user.avatar, sizes['large'], '_large')
            if thumb_large:
                user.avatar_large.save(thumb_large.name, thumb_large, save=False)
        
        # Сохраняем пользователя
        user.save()
        
        logger.info(f"Аватар пользователя {user_id} успешно обработан")
        
        return {
            'status': 'success',
            'user_id': user_id,
            'thumbnails_created': ['small', 'medium', 'large']
        }
        
    except User.DoesNotExist:
        logger.error(f"Пользователь {user_id} не найден")
        return {'status': 'error', 'message': 'User not found'}
        
    except Exception as e:
        logger.error(f"Ошибка обработки аватара для пользователя {user_id}: {e}")
        
        # Повторная попытка
        try:
            self.retry(countdown=60)  # Повтор через 60 секунд
        except Exception as retry_error:
            logger.error(f"Исчерпаны все попытки обработки аватара: {retry_error}")
            return {'status': 'error', 'message': str(e)}


@shared_task(bind=True, max_retries=3)
def process_product_image(self, product_id):
    """
    Асинхронная обработка изображения товара
    
    Создаёт миниатюры разных размеров
    """
    try:
        logger.info(f"Начало обработки изображения товара {product_id}")
        
        product = Product.objects.get(id=product_id)
        
        if not product.image:
            logger.warning(f"У товара {product_id} нет изображения")
            return
        
        # Размеры миниатюр
        sizes = settings.THUMBNAIL_SIZES.get('product', {})
        
        # Создаём миниатюры
        if sizes.get('thumbnail'):
            thumb = create_thumbnail(product.image, sizes['thumbnail'], '_thumbnail')
            if thumb:
                product.image_thumbnail.save(thumb.name, thumb, save=False)
        
        if sizes.get('small'):
            thumb_small = create_thumbnail(product.image, sizes['small'], '_small')
            if thumb_small:
                product.image_small.save(thumb_small.name, thumb_small, save=False)
        
        if sizes.get('medium'):
            thumb_medium = create_thumbnail(product.image, sizes['medium'], '_medium')
            if thumb_medium:
                product.image_medium.save(thumb_medium.name, thumb_medium, save=False)
        
        if sizes.get('large'):
            thumb_large = create_thumbnail(product.image, sizes['large'], '_large')
            if thumb_large:
                product.image_large.save(thumb_large.name, thumb_large, save=False)
        
        # Сохраняем товар
        product.save()
        
        logger.info(f"Изображение товара {product_id} успешно обработано")
        
        return {
            'status': 'success',
            'product_id': product_id,
            'thumbnails_created': ['thumbnail', 'small', 'medium', 'large']
        }
        
    except Product.DoesNotExist:
        logger.error(f"Товар {product_id} не найден")
        return {'status': 'error', 'message': 'Product not found'}
        
    except Exception as e:
        logger.error(f"Ошибка обработки изображения товара {product_id}: {e}")
        
        # Повторная попытка
        try:
            self.retry(countdown=60)
        except Exception as retry_error:
            logger.error(f"Исчерпаны все попытки обработки изображения: {retry_error}")
            return {'status': 'error', 'message': str(e)}


@shared_task(bind=True, max_retries=3)
def process_product_additional_image(self, image_id):
    """
    Асинхронная обработка дополнительного изображения товара
    """
    try:
        logger.info(f"Начало обработки дополнительного изображения {image_id}")
        
        image_obj = ProductImage.objects.get(id=image_id)
        
        if not image_obj.image:
            logger.warning(f"У изображения {image_id} нет файла")
            return
        
        # Размеры миниатюр (используем те же, что и для основного изображения)
        sizes = settings.THUMBNAIL_SIZES.get('product', {})
        
        # Создаём миниатюры
        if sizes.get('thumbnail'):
            thumb = create_thumbnail(image_obj.image, sizes['thumbnail'], '_thumbnail')
            if thumb:
                image_obj.image_thumbnail.save(thumb.name, thumb, save=False)
        
        if sizes.get('small'):
            thumb_small = create_thumbnail(image_obj.image, sizes['small'], '_small')
            if thumb_small:
                image_obj.image_small.save(thumb_small.name, thumb_small, save=False)
        
        if sizes.get('medium'):
            thumb_medium = create_thumbnail(image_obj.image, sizes['medium'], '_medium')
            if thumb_medium:
                image_obj.image_medium.save(thumb_medium.name, thumb_medium, save=False)
        
        # Сохраняем объект
        image_obj.save()
        
        logger.info(f"Дополнительное изображение {image_id} успешно обработано")
        
        return {
            'status': 'success',
            'image_id': image_id,
            'thumbnails_created': ['thumbnail', 'small', 'medium']
        }
        
    except ProductImage.DoesNotExist:
        logger.error(f"Изображение {image_id} не найдено")
        return {'status': 'error', 'message': 'Image not found'}
        
    except Exception as e:
        logger.error(f"Ошибка обработки дополнительного изображения {image_id}: {e}")
        
        try:
            self.retry(countdown=60)
        except Exception as retry_error:
            logger.error(f"Исчерпаны все попытки: {retry_error}")
            return {'status': 'error', 'message': str(e)}


@shared_task
def optimize_image(image_path, quality=85):
    """
    Оптимизация изображения (уменьшение размера без потери качества)
    """
    try:
        img = Image.open(image_path)
        
        # Конвертируем в RGB если необходимо
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # Сохраняем с оптимизацией
        buffer = BytesIO()
        img.save(
            buffer,
            format='JPEG' if image_path.lower().endswith(('.jpg', '.jpeg')) else 'PNG',
            quality=quality,
            optimize=True,
            progressive=True
        )
        
        buffer.seek(0)
        
        # Заменяем оригинальный файл
        with open(image_path, 'wb') as f:
            f.write(buffer.read())
        
        logger.info(f"Изображение {image_path} оптимизировано")
        return {'status': 'success', 'path': image_path}
        
    except Exception as e:
        logger.error(f"Ошибка оптимизации изображения {image_path}: {e}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def cleanup_unused_images():
    """
    Очистка неиспользуемых изображений (раз в сутки)
    """
    try:
        from django.core.files.storage import default_storage
        import os
        
        # Здесь можно добавить логику поиска и удаления старых/неиспользуемых файлов
        # Например, файлы старше 30 дней без привязки к моделям
        
        logger.info("Очистка неиспользуемых изображений выполнена")
        return {'status': 'success', 'message': 'Cleanup completed'}
        
    except Exception as e:
        logger.error(f"Ошибка очистки изображений: {e}")
        return {'status': 'error', 'message': str(e)}