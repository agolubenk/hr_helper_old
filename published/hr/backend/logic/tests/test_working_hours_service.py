"""Тесты для logic.working_hours_service.get_effective_working_hours"""
import unittest
from datetime import time
from unittest.mock import Mock

# Import after path setup if needed
try:
    from logic.working_hours_service import get_effective_working_hours
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    from logic.working_hours_service import get_effective_working_hours


class TestGetEffectiveWorkingHours(unittest.TestCase):
    """Проверка приоритета: пользователь -> компания -> по умолчанию (10-18)."""

    def test_defaults_when_no_user_no_company(self):
        hours = get_effective_working_hours(None, None)
        self.assertEqual(hours['work_start_hour'], 10)
        self.assertEqual(hours['work_end_hour'], 18)
        self.assertEqual(hours['meeting_interval_minutes'], 15)

    def test_user_times_used_when_company_empty(self):
        user = Mock()
        user.interview_start_time = time(9, 0)
        user.interview_end_time = time(18, 0)
        user.meeting_interval_minutes = 30
        company = Mock()
        company.work_start_time = None
        company.work_end_time = None
        hours = get_effective_working_hours(user, company)
        self.assertEqual(hours['work_start_hour'], 9)
        self.assertEqual(hours['work_end_hour'], 18)
        self.assertEqual(hours['meeting_interval_minutes'], 30)

    def test_user_times_override_company(self):
        """Слоты пользователя имеют приоритет над слотом компании."""
        user = Mock()
        user.interview_start_time = time(10, 0)
        user.interview_end_time = time(19, 0)
        user.meeting_interval_minutes = 20
        company = Mock()
        company.work_start_time = time(8, 0)
        company.work_end_time = time(17, 0)
        hours = get_effective_working_hours(user, company)
        self.assertEqual(hours['work_start_hour'], 10)
        self.assertEqual(hours['work_end_hour'], 19)
        self.assertEqual(hours['meeting_interval_minutes'], 20)

    def test_interval_always_from_user_or_default(self):
        user = Mock()
        user.interview_start_time = None
        user.interview_end_time = None
        user.meeting_interval_minutes = 5
        company = Mock()
        company.work_start_time = time(9, 0)
        company.work_end_time = time(18, 0)
        hours = get_effective_working_hours(user, company)
        self.assertEqual(hours['work_start_hour'], 9)
        self.assertEqual(hours['work_end_hour'], 18)
        self.assertEqual(hours['meeting_interval_minutes'], 5)

    def test_when_user_not_participant_use_company_or_defaults(self):
        """Если пользователь не участник встречи — часы только из компании или по умолчанию, не из профиля."""
        user = Mock()
        user.interview_start_time = time(10, 0)
        user.interview_end_time = time(19, 0)
        user.meeting_interval_minutes = 25
        company = Mock()
        company.work_start_time = time(8, 0)
        company.work_end_time = time(17, 0)
        hours = get_effective_working_hours(user, company, user_is_participant=False)
        self.assertEqual(hours['work_start_hour'], 8)
        self.assertEqual(hours['work_end_hour'], 17)
        self.assertEqual(hours['meeting_interval_minutes'], 15)

    def test_when_user_not_participant_no_company_use_defaults(self):
        """Если пользователь не участник и у компании нет часов — 10, 18, 15."""
        user = Mock()
        user.interview_start_time = time(10, 0)
        user.interview_end_time = time(19, 0)
        company = Mock()
        company.work_start_time = None
        company.work_end_time = None
        hours = get_effective_working_hours(user, company, user_is_participant=False)
        self.assertEqual(hours['work_start_hour'], 10)
        self.assertEqual(hours['work_end_hour'], 18)
        self.assertEqual(hours['meeting_interval_minutes'], 15)


if __name__ == '__main__':
    unittest.main()
