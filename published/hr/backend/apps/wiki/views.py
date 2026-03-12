from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
import json

from .forms import WikiPageEditForm
from .models import WikiPage, WikiPageHistory, WikiTag


@login_required
def wiki_list(request):
    """Список всех страниц вики"""
    category = request.GET.get('category', '')
    tag = request.GET.get('tag', '')
    app = request.GET.get('app', '')
    search_query = request.GET.get('q', '')
    
    pages = WikiPage.get_published_pages().prefetch_related('tags').order_by('category', 'order', 'title')
    
    if category:
        pages = pages.filter(category=category)
    
    if tag:
        pages = pages.filter(tags__name=tag)
    
    if app:
        pages = pages.filter(related_app=app)
    
    if search_query:
        pages = pages.filter(
            Q(title__icontains=search_query) |
            Q(content__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Получаем список категорий для фильтрации (только используемые из предустановленных)
    all_categories = [cat[0] for cat in WikiPage.CATEGORY_CHOICES if cat[0]]
    used_categories = WikiPage.objects.filter(is_published=True, category__in=all_categories).values_list('category', flat=True).distinct()
    categories = [cat for cat in used_categories if cat]
    
    # Получаем список тегов для фильтрации
    tags = WikiTag.objects.filter(pages__is_published=True).distinct().order_by('name')
    
    # Получаем список приложений
    apps = WikiPage.RELATED_APP_CHOICES
    
    # Группируем страницы по категориям
    pages_by_category = {}
    pages_without_category = []
    
    for page in pages:
        if page.category:
            if page.category not in pages_by_category:
                pages_by_category[page.category] = []
            pages_by_category[page.category].append(page)
        else:
            pages_without_category.append(page)
    
    # Сортируем категории согласно порядку в CATEGORY_CHOICES
    category_order = {cat[0]: idx for idx, cat in enumerate(WikiPage.CATEGORY_CHOICES)}
    sorted_categories = sorted(
        pages_by_category.keys(),
        key=lambda x: category_order.get(x, 999)
    )
    
    context = {
        'pages': pages,
        'pages_by_category': pages_by_category,
        'pages_without_category': pages_without_category,
        'sorted_categories': sorted_categories,
        'categories': categories,
        'tags': tags,
        'apps': apps,
        'current_category': category,
        'current_tag': tag,
        'current_app': app,
        'search_query': search_query,
    }
    
    return render(request, 'wiki/list.html', context)


@login_required
def wiki_page_detail(request, slug):
    """Детальная страница вики"""
    page = get_object_or_404(WikiPage.objects.prefetch_related('tags'), slug=slug, is_published=True)
    
    # Получаем историю изменений
    history = page.history.all()[:10]  # Последние 10 изменений
    
    # Получаем связанные страницы (по тегам или приложению)
    related_pages = WikiPage.objects.filter(is_published=True).exclude(id=page.id)
    if page.tags.exists():
        related_pages = related_pages.filter(tags__in=page.tags.all()).distinct()[:5]
    elif page.related_app:
        related_pages = related_pages.filter(related_app=page.related_app)[:5]
    
    context = {
        'page': page,
        'history': history,
        'related_pages': related_pages,
        'can_edit': request.user.is_staff,
    }
    
    return render(request, 'wiki/detail.html', context)


@login_required
def wiki_page_edit(request, slug=None):
    """Редактирование или создание страницы вики. Поле «Содержание» — WYSIWYG (Summernote)."""
    if not request.user.is_staff:
        raise PermissionDenied("Только сотрудники могут редактировать страницы вики")
    
    page = None
    if slug:
        page = get_object_or_404(WikiPage, slug=slug)
    
    all_tags = WikiTag.objects.all().order_by('name')
    
    if request.method == 'POST':
        form = WikiPageEditForm(request.POST)
        tag_ids = request.POST.getlist('tags')
        selected_tags = WikiTag.objects.filter(id__in=tag_ids) if tag_ids else []
        
        if form.is_valid():
            data = form.cleaned_data
            title = data['title']
            slug_value = data['slug']
            content = data['content'].strip()
            description = data['description'] or ''
            category = data['category'] or ''
            related_app = data['related_app'] or ''
            order = data.get('order') or 0
            is_published = data.get('is_published', True)
            change_note = (data.get('change_note') or '').strip()
            
            if not content or len(content) < 10:
                form.add_error('content', 'Содержание должно содержать минимум 10 символов')
            else:
                if not page or page.slug != slug_value:
                    if WikiPage.objects.filter(slug=slug_value).exists():
                        form.add_error('slug', f'Страница с URL-адресом "{slug_value}" уже существует')
                
                if not form.errors:
                    if page:
                        old_content = page.content
                        old_title = page.title
                        if old_content != content or old_title != title:
                            WikiPageHistory.objects.create(
                                page=page,
                                title=old_title,
                                content=old_content,
                                edited_by=request.user,
                                change_note=change_note or 'Обновлено'
                            )
                    
                    if not page:
                        page = WikiPage.objects.create(
                            title=title,
                            slug=slug_value,
                            content=content,
                            description=description,
                            category=category,
                            related_app=related_app,
                            order=order,
                            is_published=is_published,
                            author=request.user,
                            last_edited_by=request.user
                        )
                        messages.success(request, f'Страница "{title}" успешно создана')
                    else:
                        page.title = title
                        page.slug = slug_value
                        page.content = content
                        page.description = description
                        page.category = category
                        page.related_app = related_app
                        page.order = order
                        page.is_published = is_published
                        page.last_edited_by = request.user
                        page.save()
                        messages.success(request, f'Страница "{title}" успешно обновлена')
                    
                    if tag_ids:
                        page.tags.set(WikiTag.objects.filter(id__in=tag_ids))
                    else:
                        page.tags.clear()
                    
                    return redirect('wiki:page_detail', slug=page.slug)
        # Ошибки валидации — отдаём форму с тегами
        context = {
            'page': page,
            'form': form,
            'tags': selected_tags,
            'all_tags': all_tags,
            'apps': WikiPage.RELATED_APP_CHOICES,
            'categories': WikiPage.CATEGORY_CHOICES,
        }
        return render(request, 'wiki/edit.html', context)
    
    # GET — форма с начальными данными
    initial = {}
    if page:
        initial = {
            'title': page.title,
            'slug': page.slug,
            'content': page.content,
            'description': page.description,
            'category': page.category,
            'related_app': page.related_app,
            'order': page.order,
            'is_published': page.is_published,
        }
    form = WikiPageEditForm(initial=initial)
    
    context = {
        'page': page,
        'form': form,
        'tags': page.tags.all() if page else [],
        'all_tags': all_tags,
        'apps': WikiPage.RELATED_APP_CHOICES,
        'categories': WikiPage.CATEGORY_CHOICES,
    }
    return render(request, 'wiki/edit.html', context)


@login_required
@require_http_methods(["POST"])
def wiki_page_delete(request, slug):
    """Удаление страницы вики"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Недостаточно прав'})
    
    page = get_object_or_404(WikiPage, slug=slug)
    page_title = page.title
    page.delete()
    
    messages.success(request, f'Страница "{page_title}" успешно удалена')
    return redirect('wiki:list')


@login_required
@require_http_methods(["POST"])
def wiki_tag_create_api(request):
    """API для создания тега через AJAX"""
    if not request.user.is_staff:
        return JsonResponse({'success': False, 'error': 'Недостаточно прав'})
    
    try:
        data = json.loads(request.body)
        name = data.get('name', '').strip().lower()
        color = data.get('color', '#6c757d').strip()
        
        if not name:
            return JsonResponse({
                'success': False,
                'error': 'Название тега обязательно'
            })
        
        if len(name) < 2:
            return JsonResponse({
                'success': False,
                'error': 'Название тега должно содержать минимум 2 символа'
            })
        
        # Проверяем, существует ли тег
        tag, created = WikiTag.objects.get_or_create(
            name=name,
            defaults={'color': color}
        )
        
        if not created:
            return JsonResponse({
                'success': False,
                'error': f'Тег "{name}" уже существует'
            })
        
        return JsonResponse({
            'success': True,
            'message': f'Тег "{name}" успешно создан',
            'tag': {
                'id': tag.id,
                'name': tag.name,
                'color': tag.color,
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Неверный формат JSON'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
