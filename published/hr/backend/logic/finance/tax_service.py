"""
Унифицированный сервис для налоговых расчетов
Переиспользуемый компонент для всех приложений
"""
from decimal import Decimal
from typing import Dict, Any, List


class TaxService:
    """Унифицированный сервис для всех налоговых расчетов
    
    Этот сервис предназначен для переиспользования в различных приложениях
    для расчета налогов PLN и других валют.
    """
    
    @staticmethod
    def calculate_gross_from_net(net_amount: Decimal, currency: str = "PLN") -> Decimal:
        """
        Рассчитывает gross сумму из net суммы с учетом всех активных налогов.
        
        Args:
            net_amount: Net сумма
            currency: Валюта (PLN, EUR, BYN, USD)
            
        Returns:
            Gross сумма
        """
        if currency not in ["PLN", "EUR"]:
            # Для других валют пока возвращаем net сумму
            return net_amount
        
        try:
            # Импортируем модель только при необходимости
            from apps.finance.models import PLNTax
            
            active_taxes = PLNTax.objects.filter(is_active=True)
            
            if not active_taxes.exists():
                return net_amount
            
            # Суммируем все налоговые ставки
            total_tax_rate = sum(tax.rate_decimal for tax in active_taxes)
            
            # Gross = Net / (1 - общая_налоговая_ставка)
            if total_tax_rate >= 1:
                # Если общая ставка >= 100%, возвращаем net сумму
                return net_amount
            
            gross_amount = net_amount / (1 - total_tax_rate)
            return gross_amount.quantize(Decimal('0.01'))
            
        except Exception:
            # Если не удалось получить налоги, возвращаем net сумму
            return net_amount
    
    @staticmethod
    def calculate_net_from_gross(gross_amount: Decimal, currency: str = "PLN") -> Decimal:
        """
        Рассчитывает net сумму из gross суммы с учетом всех активных налогов.
        
        Args:
            gross_amount: Gross сумма
            currency: Валюта (PLN, EUR, BYN, USD)
            
        Returns:
            Net сумма
        """
        if currency not in ["PLN", "EUR", "BYN"]:
            # Для других валют пока возвращаем gross сумму
            return gross_amount
        
        try:
            if currency == "BYN":
                # Для BYN используем настройки из BenchmarkSettings
                from apps.finance.models import BenchmarkSettings
                
                settings = BenchmarkSettings.objects.first()
                if settings:
                    tax_rate = settings.belarus_tax_rate / 100  # Конвертируем в десятичное число
                    net_amount = gross_amount * (1 - tax_rate)
                    return net_amount.quantize(Decimal('0.01'))
                else:
                    # Если настройки не найдены, используем 13% по умолчанию
                    net_amount = gross_amount * (1 - Decimal('0.13'))
                    return net_amount.quantize(Decimal('0.01'))
            else:
                # Для PLN и EUR используем PLNTax
                from apps.finance.models import PLNTax
                
                active_taxes = PLNTax.objects.filter(is_active=True)
                
                if not active_taxes.exists():
                    return gross_amount
                
                # Суммируем все налоговые ставки
                total_tax_rate = sum(tax.rate_decimal for tax in active_taxes)
                
                # Net = Gross * (1 - общая_налоговая_ставка)
                if total_tax_rate >= 1:
                    # Если общая ставка >= 100%, возвращаем 0
                    return Decimal('0')
                
                net_amount = gross_amount * (1 - total_tax_rate)
                return net_amount.quantize(Decimal('0.01'))
            
        except Exception:
            # Если не удалось получить налоги, возвращаем gross сумму
            return gross_amount
    
    @staticmethod
    def get_tax_breakdown(gross_amount: Decimal, currency: str = "PLN") -> Dict[str, Any]:
        """
        Получает детализацию налогов для gross суммы.
        
        Args:
            gross_amount: Gross сумма
            currency: Валюта (PLN, BYN, USD)
            
        Returns:
            Словарь с детализацией налогов
        """
        if currency != "PLN":
            return {
                'gross_amount': gross_amount,
                'net_amount': gross_amount,
                'total_tax_amount': Decimal('0'),
                'taxes': [],
                'total_tax_rate_percent': 0
            }
        
        try:
            # Импортируем модель только при необходимости
            from apps.finance.models import PLNTax
            
            active_taxes = PLNTax.objects.filter(is_active=True)
            
            if not active_taxes.exists():
                return {
                    'gross_amount': gross_amount,
                    'net_amount': gross_amount,
                    'total_tax_amount': Decimal('0'),
                    'taxes': [],
                    'total_tax_rate_percent': 0
                }
            
            total_tax_amount = Decimal('0')
            taxes_detail = []
            
            for tax in active_taxes:
                tax_amount = gross_amount * tax.rate_decimal
                total_tax_amount += tax_amount
                
                taxes_detail.append({
                    'name': tax.name,
                    'rate': float(tax.rate),
                    'amount': tax_amount.quantize(Decimal('0.01'))
                })
            
            net_amount = gross_amount - total_tax_amount
            total_tax_rate_percent = float(sum(tax.rate for tax in active_taxes))
            
            return {
                'gross_amount': gross_amount,
                'net_amount': net_amount.quantize(Decimal('0.01')),
                'total_tax_amount': total_tax_amount.quantize(Decimal('0.01')),
                'taxes': taxes_detail,
                'total_tax_rate_percent': total_tax_rate_percent
            }
            
        except Exception:
            # Если не удалось получить налоги, возвращаем базовую структуру
            return {
                'gross_amount': gross_amount,
                'net_amount': gross_amount,
                'total_tax_amount': Decimal('0'),
                'taxes': [],
                'total_tax_rate_percent': 0
            }
    
    @staticmethod
    def calculate_salary_with_taxes(
        net_amount: Decimal,
        currency_from: str = "PLN",
        currency_to: str = "BYN"
    ) -> Dict[str, Any]:
        """
        Рассчитывает зарплату с налогами и конвертацией валют.
        
        Args:
            net_amount: Net сумма в исходной валюте
            currency_from: Исходная валюта
            currency_to: Целевая валюта
            
        Returns:
            Словарь с детальным расчетом
        """
        result = {
            'net_amount_original': net_amount,
            'gross_amount_original': Decimal('0'),
            'total_tax_amount_original': Decimal('0'),
            'tax_breakdown': [],
            'currency_conversion': {},
            'final_amounts': {}
        }
        
        # Рассчитываем gross сумму в исходной валюте
        gross_amount = TaxService.calculate_gross_from_net(net_amount, currency_from)
        result['gross_amount_original'] = gross_amount
        
        # Получаем детализацию налогов
        breakdown = TaxService.get_tax_breakdown(gross_amount, currency_from)
        result['total_tax_amount_original'] = breakdown['total_tax_amount']
        result['tax_breakdown'] = breakdown['taxes']
        
        # Для простоты пока не делаем конвертацию валют
        result['final_amounts'] = {
            'gross': gross_amount,
            'net': net_amount,
            'currency': currency_from
        }
        
        return result
    
    @staticmethod
    def get_tax_summary() -> Dict[str, Any]:
        """
        Получает сводку по налогам.
        
        Returns:
            Словарь со сводкой по налогам
        """
        try:
            # Импортируем модель только при необходимости
            from apps.finance.models import PLNTax
            
            active_taxes = PLNTax.objects.filter(is_active=True)
            inactive_taxes = PLNTax.objects.filter(is_active=False)
            
            total_tax_rate = sum(tax.rate for tax in active_taxes)
            
            return {
                'active_taxes_count': active_taxes.count(),
                'inactive_taxes_count': inactive_taxes.count(),
                'total_tax_rate_percent': float(total_tax_rate),
                'active_taxes': [
                    {
                        'name': tax.name,
                        'rate': float(tax.rate)
                    }
                    for tax in active_taxes
                ],
                'inactive_taxes': [
                    {
                        'name': tax.name,
                        'rate': float(tax.rate)
                    }
                    for tax in inactive_taxes
                ]
            }
            
        except Exception:
            return {
                'active_taxes_count': 0,
                'inactive_taxes_count': 0,
                'total_tax_rate_percent': 0,
                'active_taxes': [],
                'inactive_taxes': []
            }
    
    @staticmethod
    def calculate_multiple_salaries(salaries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Рассчитывает налоги для нескольких зарплат.
        
        Args:
            salaries: Список словарей с данными зарплат
            
        Returns:
            Словарь с результатами расчетов
        """
        results = []
        total_gross = Decimal('0')
        total_net = Decimal('0')
        total_taxes = Decimal('0')
        
        for salary_data in salaries:
            amount = Decimal(str(salary_data.get('amount', 0)))
            currency = salary_data.get('currency', 'PLN')
            calculation_type = salary_data.get('type', 'net')  # 'net' или 'gross'
            
            if calculation_type == 'net':
                gross = TaxService.calculate_gross_from_net(amount, currency)
                net = amount
            else:
                gross = amount
                net = TaxService.calculate_net_from_gross(amount, currency)
            
            breakdown = TaxService.get_tax_breakdown(gross, currency)
            
            result_item = {
                'original_amount': amount,
                'gross_amount': gross,
                'net_amount': net,
                'total_tax_amount': breakdown['total_tax_amount'],
                'currency': currency,
                'calculation_type': calculation_type,
                'tax_breakdown': breakdown['taxes']
            }
            
            results.append(result_item)
            
            total_gross += gross
            total_net += net
            total_taxes += breakdown['total_tax_amount']
        
        return {
            'individual_results': results,
            'totals': {
                'total_gross': total_gross,
                'total_net': total_net,
                'total_taxes': total_taxes
            },
            'count': len(results)
        }

