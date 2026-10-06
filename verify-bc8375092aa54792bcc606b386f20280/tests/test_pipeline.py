import unittest
from unittest.mock import Mock, patch
from Dianping_Spider import run


class PipelineTests(unittest.TestCase):
    def test_complete_pipeline_order(self):
        calls = Mock()
        with patch.object(run.collect_national, 'main') as collect, \
             patch.object(run.retry_missing, 'main') as retry, \
             patch.object(run.enrich_districts, 'main') as enrich, \
             patch.object(run.finalize, 'main') as finalize:
            for name, method in [('collect', collect), ('retry', retry), ('enrich', enrich), ('finalize', finalize)]:
                calls.attach_mock(method, name)
            self.assertEqual(run.main(['--workers', '2']), 0)
        self.assertEqual([call[0] for call in calls.mock_calls], ['collect', 'retry', 'enrich', 'finalize'])
        collect.assert_called_once_with(['--phase', 'all', '--workers', '2'])
