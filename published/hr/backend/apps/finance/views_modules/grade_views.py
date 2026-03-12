"""Views для работы с грейдами"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from logic.base.response_handler import UnifiedResponseHandler

@login_required
def add_grade(request):
    """
    Добавление нового грейда
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - request.POST: name (обязательно), description (опционально)
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - POST данные формы создания грейда
    
    ОБРАБОТКА:
    - Валидация обязательного поля name
    - Проверка на существование грейда с таким же названием
    - Создание нового объекта Grade
    - Обработка ошибок и успешного создания
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages.success/error: сообщения о результате
    - redirect: перенаправление на finance:dashboard
    
    СВЯЗИ:
    - Использует: Grade.objects.create()
    - Передает: результат создания в messages
    - Может вызываться из: finance/ URL patterns
    """
    try:
        from ..models import Grade
        
        if request.method == 'POST':
            name = request.POST.get('name')
            description = request.POST.get('description', '')
            
            if not name:
                messages.error(request, 'Название грейда обязательно')
                return redirect('finance:add_grade')
            
            # Проверяем, не существует ли уже такой грейд
            if Grade.objects.filter(name=name).exists():
                messages.error(request, 'Грейд с таким названием уже существует')
                return redirect('finance:add_grade')
            
            grade = Grade.objects.create(
                name=name,
                description=description
            )
            
            messages.success(request, f'Грейд "{name}" успешно добавлен')
            return redirect('finance:grades_list')
        
        context = {
            'title': 'Добавить грейд',
        }
        
        return render(request, 'finance/add_grade.html', context)
        
    except Exception as e:
        messages.error(request, f'Ошибка добавления грейда: {str(e)}')
        
        if request.headers.get('Accept') == 'application/json':
            return UnifiedResponseHandler.json_response(
                UnifiedResponseHandler.error_response(str(e)),
                status_code=500
            )
        
        return redirect('finance:grades_list')

@login_required
def delete_grade(request, grade_id):
    """
    Удаление грейда
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - grade_id: ID грейда для удаления
    - request.user: аутентифицированный пользователь
    
    ИСТОЧНИКИ ДАННЫХ:
    - URL параметр grade_id
    - Grade.objects, Benchmark.objects для проверки связей
    
    ОБРАБОТКА:
    - Получение грейда по ID (404 если не найден)
    - Проверка связанных бенчмарков
    - Удаление грейда если нет связей
    - Обработка ошибок
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - messages.success/error: сообщения о результате
    - redirect: перенаправление на finance:dashboard
    
    СВЯЗИ:
    - Использует: Grade.objects, Benchmark.objects
    - Передает: результат удаления в messages
    - Может вызываться из: finance/ URL patterns
    """
    try:
        from ..models import Grade, Benchmark
        
        grade = get_object_or_404(Grade, id=grade_id)
        
        # Проверяем, используется ли грейд в бенчмарках
        benchmarks_count = Benchmark.objects.filter(grade=grade).count()
        
        if benchmarks_count > 0:
            messages.error(request, f'Нельзя удалить грейд, который используется в {benchmarks_count} бенчмарках')
            return redirect('finance:grades_list')
        
        grade_name = grade.name
        grade.delete()
        
        messages.success(request, f'Грейд "{grade_name}" успешно удален')
        return redirect('finance:grades_list')
        
    except Exception as e:
        messages.error(request, f'Ошибка удаления грейда: {str(e)}')
        
        if request.headers.get('Accept') == 'application/json':
            return UnifiedResponseHandler.json_response(
                UnifiedResponseHandler.error_response(str(e)),
                status_code=500
            )
        
        return redirect('finance:grades_list')
