# Документация API

## Аутентификация

* POST /api/users/register/ - Регистрация пользователя
* POST /api/users/login/ - Вход в систему
* POST /api/users/password-reset/ - Восстановление пароля
* GET /api/users/me/ - Информация о текущем пользователе
* POST /api/token/ - Получение JWT токена
* POST /api/token/refresh/ - Обновление JWT токена

## Пользователи

* GET /api/users/ - Список пользователей
* GET /api/users/{id}/ - Детали пользователя
* PUT /api/users/{id}/ - Обновление пользователя

## Поставщики

* GET /api/suppliers/ - Список поставщиков
* POST /api/suppliers/{id}/toggle-accept-orders/ - Вкл/выкл прием заказов

## Поставщики

* GET /api/suppliers/ - Список поставщиков
* POST /api/suppliers/{id}/toggle-accept-orders/ - Вкл/выкл прием заказов

## Товары

* GET /api/products/ - Список товаров
* POST /api/products/import/ - Импорт товаров из CSV, JSON или YAML
* GET /api/products/my-products/ - Товары текущего поставщика

## Заказы

* GET /api/orders/ - Список заказов
* POST /api/orders/ - Создание заказа
* POST /api/orders/{id}/confirm/ - Подтверждение заказа (поставщик)
* POST /api/orders/{id}/cancel/ - Отмена заказа (клиент)
* GET /api/orders/statistics/ - Статистика по заказам

## Категории и характеристики

* GET /api/categories/ - Список категорий
* GET /api/attributes/ - Список характеристик