"""Помощники для работы с шаблонами"""
from django.template.loader import render_to_string
from django.http import HttpResponse
from logic.base.response_handler import UnifiedResponseHandler
import re

class TemplateHelper:
    """Класс для работы с шаблонами"""
    
    @staticmethod
    def render_template(template_name, context=None, request=None):
        """Рендеринг шаблона в строку"""
        try:
            if context is None:
                context = {}
            
            return render_to_string(template_name, context, request=request)
        except Exception as e:
            return f"Ошибка рендеринга шаблона: {str(e)}"
    
    @staticmethod
    def render_template_response(template_name, context=None, request=None):
        """Рендеринг шаблона в HTTP ответ"""
        try:
            if context is None:
                context = {}
            
            html_content = render_to_string(template_name, context, request=request)
            return HttpResponse(html_content)
        except Exception as e:
            error_html = f"<h1>Ошибка</h1><p>Ошибка рендеринга шаблона: {str(e)}</p>"
            return HttpResponse(error_html, status=500)

class FormHelper:
    """Класс для работы с формами"""
    
    @staticmethod
    def get_form_errors(form):
        """Получение ошибок формы в удобном формате"""
        try:
            errors = {}
            for field, field_errors in form.errors.items():
                errors[field] = [str(error) for error in field_errors]
            return errors
        except Exception:
            return {}
    
    @staticmethod
    def is_form_valid(form):
        """Проверка валидности формы"""
        try:
            return form.is_valid()
        except Exception:
            return False
    
    @staticmethod
    def get_form_field_value(form, field_name, default=None):
        """Получение значения поля формы"""
        try:
            return form.cleaned_data.get(field_name, default)
        except (AttributeError, KeyError):
            return default

class ValidationHelper:
    """Класс для валидации данных"""
    
    @staticmethod
    def validate_email(email):
        """Валидация email адреса"""
        try:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            return bool(re.match(email_pattern, email))
        except Exception:
            return False
    
    @staticmethod
    def validate_phone(phone):
        """Валидация номера телефона"""
        try:
            # Простая валидация российских номеров
            phone_pattern = r'^(\+7|8)?[\s\-]?\(?[489][0-9]{2}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}$'
            return bool(re.match(phone_pattern, phone))
        except Exception:
            return False
    
    @staticmethod
    def validate_url(url):
        """Валидация URL"""
        try:
            url_pattern = r'^https?://[^\s/$.?#].[^\s]*$'
            return bool(re.match(url_pattern, url))
        except Exception:
            return False

class DataFormatHelper:
    """Класс для форматирования данных"""
    
    @staticmethod
    def format_currency(amount, currency='RUB'):
        """Форматирование валюты"""
        try:
            if currency == 'RUB':
                return f"{amount:,.2f} ₽"
            elif currency == 'USD':
                return f"${amount:,.2f}"
            elif currency == 'EUR':
                return f"€{amount:,.2f}"
            else:
                return f"{amount:,.2f} {currency}"
        except Exception:
            return str(amount)
    
    @staticmethod
    def format_date(date_obj, format_str='%d.%m.%Y'):
        """Форматирование даты"""
        try:
            return date_obj.strftime(format_str)
        except Exception:
            return str(date_obj)
    
    @staticmethod
    def format_datetime(datetime_obj, format_str='%d.%m.%Y %H:%M'):
        """Форматирование даты и времени"""
        try:
            return datetime_obj.strftime(format_str)
        except Exception:
            return str(datetime_obj)
    
    @staticmethod
    def truncate_text(text, max_length=100, suffix='...'):
        """Обрезка текста"""
        try:
            if len(text) <= max_length:
                return text
            return text[:max_length - len(suffix)] + suffix
        except Exception:
            return str(text)

class ResponseHelper:
    """Класс для работы с ответами"""
    
    @staticmethod
    def success_response(data=None, message="Успешно"):
        """Создание успешного ответа"""
        return UnifiedResponseHandler.success_response(data, message)
    
    @staticmethod
    def error_response(error_message="Ошибка", status_code=400):
        """Создание ошибочного ответа"""
        return UnifiedResponseHandler.error_response(error_message, status_code)
    
    @staticmethod
    def json_response(data, status_code=200):
        """Создание JSON ответа"""
        return UnifiedResponseHandler.json_response(data, status_code)
