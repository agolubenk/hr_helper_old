from django.urls import path

from .views_api import (
    HHIntegrationStatusView,
    HHInviteView,
    HHRejectView,
    HHActionsAvailabilityView,
)

urlpatterns = [
    path("integration-status", HHIntegrationStatusView.as_view(), name="hh-integration-status"),
    path("invite", HHInviteView.as_view(), name="hh-invite"),
    path("reject", HHRejectView.as_view(), name="hh-reject"),
    path("actions-availability", HHActionsAvailabilityView.as_view(), name="hh-actions-availability"),
]

