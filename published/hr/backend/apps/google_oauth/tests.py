from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.answer_library.models import PromptTableRow
from apps.google_oauth.models import HRScreening


class HRScreeningPromptTableTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='hr_tester',
            email='hr_tester@example.com',
            password='test-pass-123',
        )
        self.hr = HRScreening(user=self.user, input_data='')

    def test_normalize_text_for_prompt_table(self):
        normalized = self.hr._normalize_text_for_prompt_table('  Relocation?!\nДа, РЕЛОКАЦИЯ  ')
        self.assertEqual(normalized, 'relocation да релокация')

    def test_trigger_exact_match(self):
        normalized = self.hr._normalize_text_for_prompt_table('Кандидат готов к релокации')
        words = normalized.split()
        self.assertTrue(self.hr._prompt_trigger_matches_text('релокация', normalized, words))

    def test_trigger_soft_match_by_word_form(self):
        normalized = self.hr._normalize_text_for_prompt_table('Готов к релокации через месяц')
        words = normalized.split()
        self.assertTrue(self.hr._prompt_trigger_matches_text('релокация', normalized, words))

    def test_get_matching_prompt_table_rows_returns_all_matches(self):
        PromptTableRow.objects.create(
            topic='Релокация',
            trigger_words='релокация, переезд',
            clarification_points='Уточнить сроки релокации',
            order=2,
        )
        PromptTableRow.objects.create(
            topic='Формат сотрудничества',
            trigger_words='b2b, uop',
            clarification_points='Уточнить предпочитаемый формат договора',
            order=1,
        )
        PromptTableRow.objects.create(
            topic='Нерелевантная тема',
            trigger_words='офис минск',
            clarification_points='Не должна попасть',
            order=0,
        )

        rows = self.hr._get_matching_prompt_table_rows(
            'Рассматриваю B2B, готов к релокации в Польшу'
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual([r.topic for r in rows], ['Формат сотрудничества', 'Релокация'])

    def test_get_matching_prompt_table_rows_when_no_matches(self):
        PromptTableRow.objects.create(
            topic='Офисный формат',
            trigger_words='офис, гибрид',
            clarification_points='Уточнить готовность к офису',
            order=1,
        )
        rows = self.hr._get_matching_prompt_table_rows('Интересует только зарплатная вилка')
        self.assertEqual(rows, [])

    def test_build_prompt_table_context(self):
        row = PromptTableRow.objects.create(
            topic='Сроки выхода',
            trigger_words='сроки, выход',
            clarification_points='Когда сможете приступить к работе?',
            order=1,
        )
        context = self.hr._build_prompt_table_context([row])
        self.assertIn('СПРАВОЧНИК PROMPT-TABLE', context)
        self.assertIn('Тема: Сроки выхода', context)
        self.assertIn('Когда сможете приступить к работе?', context)

    def test_inject_prompt_table_context_with_and_without_placeholder(self):
        context = 'СПРАВОЧНИК PROMPT-TABLE (ТОЛЬКО РЕЛЕВАНТНЫЕ СТРОКИ ПО ТРИГГЕРАМ):\n- Тема: test'

        prompt_with_placeholder = 'HEAD\n{prompt_table_context}\nTAIL'
        replaced = self.hr._inject_prompt_table_context(prompt_with_placeholder, context)
        self.assertNotIn('{prompt_table_context}', replaced)
        self.assertIn(context, replaced)

        prompt_without_placeholder = 'HEAD\nTAIL'
        appended = self.hr._inject_prompt_table_context(prompt_without_placeholder, context)
        self.assertTrue(appended.endswith(context))
