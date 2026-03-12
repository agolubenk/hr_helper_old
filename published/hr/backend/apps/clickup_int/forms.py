from django import forms
from django.contrib.auth import get_user_model
from .models import ClickUpSettings

User = get_user_model()


class ClickUpSettingsForm(forms.ModelForm):
    """
    Форма для настроек ClickUp интеграции
    
    ВХОДЯЩИЕ ДАННЫЕ:
    - team_id: ID команды/рабочей области (обязательно)
    - space_id: ID пространства (обязательно)
    - folder_id: ID папки (опционально)
    - list_id: ID списка задач (обязательно)
    - auto_sync: автоматическая синхронизация
    - sync_interval: интервал синхронизации в минутах
    
    ИСТОЧНИКИ ДАННЫХ:
    - ClickUpSettings модель из apps.clickup_int.models
    - ClickUp API для получения списков команд, пространств, папок и списков
    
    ОБРАБОТКА:
    - Валидация обязательных полей
    - Настройка виджетов для UI
    - Настройка лейблов и подсказок
    - Динамическое заполнение выборов через ClickUp API
    
    ВЫХОДЯЩИЕ ДАННЫЕ:
    - Django форма для настройки ClickUp интеграции
    
    СВЯЗИ:
    - Использует: ClickUpSettings модель, ClickUp API
    - Передает: Django форма
    - Может вызываться из: ClickUp Integration views
    """
    
    # Явно определяем поля как ChoiceField
    team_id = forms.ChoiceField(choices=[], required=False, widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_team_id'}))
    space_id = forms.ChoiceField(choices=[], required=False, widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_space_id', 'disabled': True}))
    folder_id = forms.ChoiceField(choices=[], required=False, widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_folder_id', 'disabled': True}))
    list_id = forms.ChoiceField(choices=[], required=False, widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_list_id', 'disabled': True}))
    
    class Meta:
        model = ClickUpSettings
        fields = [
            'team_id',
            'space_id',
            'folder_id',
            'list_id',
            'auto_sync',
            'sync_interval'
        ]
        widgets = {
            'auto_sync': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'sync_interval': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '1440'
            })
        }
        labels = {
            'team_id': 'Команда / Рабочая область',
            'space_id': 'Пространство',
            'folder_id': 'Папка',
            'list_id': 'Список задач',
            'auto_sync': 'Автоматическая синхронизация',
            'sync_interval': 'Интервал синхронизации (минуты)'
        }
        help_texts = {
            'team_id': 'Выберите команду или рабочую область. Если команд нет, будут показаны все ваши пространства.',
            'space_id': 'Выберите пространство для работы с задачами.',
            'folder_id': 'Выберите папку в выбранном пространстве (опционально).',
            'list_id': 'Выберите список задач для синхронизации.',
            'auto_sync': 'Автоматически синхронизировать задачи с указанным интервалом.',
            'sync_interval': 'Интервал автоматической синхронизации в минутах (от 1 до 1440).'
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Делаем поле folder_id необязательным
        self.fields['folder_id'].required = False
        
        # Устанавливаем значения по умолчанию
        if self.user and not self.instance.pk:
            self.fields['auto_sync'].initial = True
            self.fields['sync_interval'].initial = 30
        
        # Загружаем команды и пространства, если у пользователя есть API ключ
        if self.user and self.user.clickup_api_key:
            self._load_choices()
        else:
            self.fields['team_id'].choices = [('', 'API токен не настроен')]
        
        # Проверяем, очищены ли настройки из-за изменения API ключа
        if self.user and self.instance and self.instance.pk:
            if (not self.instance.team_id and not self.instance.space_id and 
                not self.instance.list_id and self.user.clickup_api_key):
                # Настройки очищены, но API ключ есть - показываем предупреждение
                self.fields['team_id'].help_text = (
                    'Настройки пути были очищены из-за изменения API ключа. '
                    'Пожалуйста, выберите новые значения.'
                )
    
    def _load_choices(self):
        """Загружает choices для всех полей"""
        try:
            from .services import ClickUpService
            service = ClickUpService(self.user.clickup_api_key)
            
            # Сначала пробуем получить команды
            teams = service.get_teams()
            
            if teams:
                # Если есть команды, показываем их
                team_choices = [('', 'Выберите команду...')]
                for team in teams:
                    team_choices.append((team['id'], team['name']))
                self.fields['team_id'].choices = team_choices
                
                # Загружаем пространства для выбранной команды
                team_id = self.data.get('team_id') or (self.instance.team_id if self.instance else None)
                if team_id:
                    spaces = service.get_spaces(team_id)
                    space_choices = [('', 'Выберите пространство...')]
                    for space in spaces:
                        space_choices.append((space['id'], space['name']))
                    self.fields['space_id'].choices = space_choices
                    self.fields['space_id'].disabled = False
                    
                    # Загружаем папки для выбранного пространства
                    space_id = self.data.get('space_id') or (self.instance.space_id if self.instance else None)
                    if space_id:
                        folders = service.get_folders(space_id)
                        folder_choices = [('', 'Без папки')]
                        for folder in folders:
                            folder_choices.append((folder['id'], folder['name']))
                        self.fields['folder_id'].choices = folder_choices
                        self.fields['folder_id'].disabled = False
                        
                        # Загружаем списки для выбранной папки или пространства
                        folder_id = self.data.get('folder_id') or (self.instance.folder_id if self.instance else None)
                        if folder_id:
                            lists = service.get_lists(folder_id=folder_id)
                        else:
                            lists = service.get_lists(space_id=space_id)
                        
                        list_choices = [('', 'Выберите список задач...')]
                        for list_item in lists:
                            list_choices.append((list_item['id'], list_item['name']))
                        self.fields['list_id'].choices = list_choices
                        self.fields['list_id'].disabled = False
            else:
                # Если команд нет, загружаем пространства напрямую
                spaces = service.get_spaces()
                if spaces:
                    # Создаем "виртуальную команду" для всех пространств
                    team_choices = [('all_spaces', 'Все пространства')]
                    self.fields['team_id'].choices = team_choices
                    
                    # Загружаем пространства в поле space_id
                    space_choices = [('', 'Выберите пространство...')]
                    for space in spaces:
                        space_choices.append((space['id'], space['name']))
                    self.fields['space_id'].choices = space_choices
                    self.fields['space_id'].disabled = False
                else:
                    self.fields['team_id'].choices = [('', 'Нет доступных команд или пространств')]
            
        except Exception as e:
            # В случае ошибки, показываем сообщение об ошибке
            error_msg = f'Ошибка загрузки: {str(e)}'
            self.fields['team_id'].choices = [('', error_msg)]
    
    def clean(self):
        """Общая валидация формы"""
        cleaned_data = super().clean()
        
        # Проверяем, что у пользователя настроен API токен
        if self.user and not self.user.clickup_api_key:
            raise forms.ValidationError('API токен ClickUp не настроен в профиле пользователя. Перейдите в профиль для настройки.')
        
        # Проверяем, что указаны все обязательные поля
        required_fields = ['team_id', 'space_id', 'list_id']
        for field in required_fields:
            if not cleaned_data.get(field):
                raise forms.ValidationError(f'Поле "{self.fields[field].label}" обязательно для заполнения')
        
        return cleaned_data
    
    def clean_team_id(self):
        """Валидация team_id"""
        team_id = self.cleaned_data.get('team_id')
        if team_id and team_id != '':
            # Простая валидация - проверяем, что это не пустая строка
            # Детальную валидацию против API оставляем для тестирования подключения
            pass
        return team_id
    
    def clean_space_id(self):
        """Валидация space_id"""
        space_id = self.cleaned_data.get('space_id')
        if space_id and space_id != '':
            # Простая валидация - проверяем, что это не пустая строка
            pass
        return space_id
    
    def clean_folder_id(self):
        """Валидация folder_id"""
        folder_id = self.cleaned_data.get('folder_id')
        # Папка необязательна, поэтому просто возвращаем значение
        return folder_id
    
    def clean_list_id(self):
        """Валидация list_id"""
        list_id = self.cleaned_data.get('list_id')
        if list_id and list_id != '':
            # Простая валидация - проверяем, что это не пустая строка
            pass
        return list_id
    
    def clean_sync_interval(self):
        """Валидация интервала синхронизации"""
        sync_interval = self.cleaned_data.get('sync_interval')
        
        if sync_interval is not None:
            if sync_interval < 1:
                raise forms.ValidationError('Интервал синхронизации должен быть не менее 1 минуты')
            if sync_interval > 1440:
                raise forms.ValidationError('Интервал синхронизации должен быть не более 1440 минут (24 часа)')
        
        return sync_interval
    


class ClickUpTestConnectionForm(forms.Form):
    """Форма для тестирования подключения к ClickUp"""
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        """Валидация формы"""
        cleaned_data = super().clean()
        
        if self.user and not self.user.clickup_api_key:
            raise forms.ValidationError('API токен ClickUp не настроен в профиле пользователя')
        
        return cleaned_data


class ClickUpPathForm(forms.Form):
    """Форма для выбора пути в ClickUp"""
    
    team_id = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Команда',
        help_text='Выберите команду'
    )
    
    space_id = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Пространство',
        help_text='Выберите пространство'
    )
    
    folder_id = forms.ChoiceField(
        choices=[('', 'Без папки')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Папка',
        help_text='Выберите папку (опционально)'
    )
    
    list_id = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Список задач',
        help_text='Выберите список задач'
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user and self.user.clickup_api_key:
            self._populate_choices()
    
    def _populate_choices(self):
        """Заполняет варианты выбора данными из ClickUp API"""
        try:
            from .services import ClickUpService
            
            service = ClickUpService(self.user.clickup_api_key)
            
            # Получаем команды
            teams = service.get_teams()
            self.fields['team_id'].choices = [(team['id'], team['name']) for team in teams]
            
            # Если есть данные в форме, получаем пространства
            if 'team_id' in self.data:
                team_id = self.data['team_id']
                if team_id:
                    spaces = service.get_spaces(team_id)
                    self.fields['space_id'].choices = [(space['id'], space['name']) for space in spaces]
            
            # Если есть данные в форме, получаем папки
            if 'space_id' in self.data:
                space_id = self.data['space_id']
                if space_id:
                    folders = service.get_folders(space_id)
                    folder_choices = [('', 'Без папки')] + [(folder['id'], folder['name']) for folder in folders]
                    self.fields['folder_id'].choices = folder_choices
            
            # Если есть данные в форме, получаем списки
            if 'folder_id' in self.data or 'space_id' in self.data:
                folder_id = self.data.get('folder_id')
                space_id = self.data.get('space_id')
                
                if folder_id:
                    lists = service.get_lists(folder_id=folder_id)
                elif space_id:
                    lists = service.get_lists(space_id=space_id)
                else:
                    lists = []
                
                self.fields['list_id'].choices = [(list_item['id'], list_item['name']) for list_item in lists]
                
        except Exception as e:
            # В случае ошибки API, оставляем пустые варианты
            pass
