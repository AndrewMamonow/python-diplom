from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

from .models import Order


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