from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Импорт ViewSets
from apps.accounts.views_api import UserViewSet, GroupViewSet
from apps.accounts.views import unified_api_view, login_api_handler, logout_api_handler
from apps.finance.views_api import (
    GradeViewSet, CurrencyRateViewSet, PLNTaxViewSet,
    SalaryRangeViewSet, BenchmarkViewSet, BenchmarkSettingsViewSet,
    SalaryCalculationViewSet
)
from apps.vacancies.views_api import VacancyViewSet
from apps.interviewers.views_api import InterviewerViewSet, InterviewRuleViewSet
from apps.huntflow.views_api import (
    HuntflowCacheViewSet, HuntflowLogViewSet, HuntflowApiRequestViewSet,
    HHResponsesViewSet, LinkedInApplicantsViewSet, LinkedInThreadMappingViewSet,
    ResumeHuntflowLinkViewSet
)
from apps.google_oauth.views_api import (
    GoogleOAuthAccountViewSet, SyncSettingsViewSet, ScorecardPathSettingsViewSet,
    SlotsSettingsViewSet, InviteViewSet, HRScreeningViewSet, QuestionTemplateViewSet,
    GoogleSyncViewSet
)
from apps.gemini.views_api import ChatSessionViewSet, ChatMessageViewSet, GeminiApiViewSet
# from apps.telegram.views_api import (
#     TelegramUserViewSet, AuthAttemptViewSet, TelegramWebhookViewSet
# )
from apps.clickup_int.views_api import (
    ClickUpSettingsViewSet, ClickUpTaskViewSet, ClickUpSyncLogViewSet,
    ClickUpBulkImportViewSet
)

# Создание роутера
router = DefaultRouter()

# Регистрация ViewSets
# Accounts
router.register(r'accounts/users', UserViewSet, basename='user')
router.register(r'accounts/groups', GroupViewSet, basename='group')

# Finance
router.register(r'finance/grades', GradeViewSet, basename='grade')
router.register(r'finance/currency-rates', CurrencyRateViewSet, basename='currency-rate')
router.register(r'finance/pln-taxes', PLNTaxViewSet, basename='pln-tax')
router.register(r'finance/salary-ranges', SalaryRangeViewSet, basename='salary-range')
router.register(r'finance/benchmarks', BenchmarkViewSet, basename='benchmark')
router.register(r'finance/benchmark-settings', BenchmarkSettingsViewSet, basename='benchmark-settings')
router.register(r'finance/salary-calculations', SalaryCalculationViewSet, basename='salary-calculation')

# Vacancies
router.register(r'vacancies/vacancies', VacancyViewSet, basename='vacancy')

# Interviewers
router.register(r'interviewers/interviewers', InterviewerViewSet, basename='interviewer')
router.register(r'interviewers/interview-rules', InterviewRuleViewSet, basename='interview-rule')

# Huntflow
router.register(r'huntflow/cache', HuntflowCacheViewSet, basename='huntflow-cache')
router.register(r'huntflow/logs', HuntflowLogViewSet, basename='huntflow-log')
router.register(r'huntflow/api', HuntflowApiRequestViewSet, basename='huntflow-api')
router.register(r'huntflow/hh-responses', HHResponsesViewSet, basename='hh-responses')
router.register(r'huntflow/linkedin-applicants', LinkedInApplicantsViewSet, basename='huntflow-linkedin-applicants')
router.register(r'huntflow/resume-links', ResumeHuntflowLinkViewSet, basename='huntflow-resume-links')

# LinkedIn Integration
router.register(r'linkedin/thread-mapping', LinkedInThreadMappingViewSet, basename='linkedin-thread-mapping')

# Google OAuth
router.register(r'google-oauth/accounts', GoogleOAuthAccountViewSet, basename='google-oauth-account')
router.register(r'google-oauth/sync-settings', SyncSettingsViewSet, basename='sync-settings')
router.register(r'google-oauth/scorecard-path-settings', ScorecardPathSettingsViewSet, basename='scorecard-path-settings')
router.register(r'google-oauth/slots-settings', SlotsSettingsViewSet, basename='slots-settings')
router.register(r'google-oauth/invites', InviteViewSet, basename='invite')
router.register(r'google-oauth/hr-screening', HRScreeningViewSet, basename='hr-screening')
router.register(r'google-oauth/question-templates', QuestionTemplateViewSet, basename='question-template')
router.register(r'google-oauth/sync', GoogleSyncViewSet, basename='google-sync')

# Gemini
router.register(r'gemini/chat-sessions', ChatSessionViewSet, basename='chat-session')
router.register(r'gemini/chat-messages', ChatMessageViewSet, basename='chat-message')
router.register(r'gemini/api', GeminiApiViewSet, basename='gemini-api')

# Telegram - временно отключено
# router.register(r'telegram/users', TelegramUserViewSet, basename='telegram-user')
# router.register(r'telegram/auth-attempts', AuthAttemptViewSet, basename='telegram-auth-attempt')
# router.register(r'telegram/webhook', TelegramWebhookViewSet, basename='telegram-webhook')

# ClickUp Integration
router.register(r'clickup/settings', ClickUpSettingsViewSet, basename='clickup-settings')
router.register(r'clickup/tasks', ClickUpTaskViewSet, basename='clickup-task')
router.register(r'clickup/sync-logs', ClickUpSyncLogViewSet, basename='clickup-sync-log')
router.register(r'clickup/bulk-imports', ClickUpBulkImportViewSet, basename='clickup-bulk-import')

# URL patterns для API
urlpatterns = [
    # API v1
    path('v1/', include(router.urls)),
    path('v1/hh/', include('apps.hhru.urls_api')),
    
    # API аутентификация
    path('auth/', include('rest_framework.urls')),
    path('auth/login/', lambda r: unified_api_view(r, login_api_handler), name='api_login'),
    path('auth/logout/', lambda r: unified_api_view(r, logout_api_handler), name='api_logout'),
    
    # API health check
    path('health/', include('apps.common.urls_api')),
]

# Добавляем префикс api/ ко всем URL
urlpatterns = [
    path('api/', include(urlpatterns)),
]
