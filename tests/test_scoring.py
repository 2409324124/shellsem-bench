import unittest
from runner.scoring import summarize

class ScoringTests(unittest.TestCase):
    def test_correct_submission_with_truncated_response_is_not_clean(self):
        events=[{'type':'message_end','message':{'role':'assistant','stopReason':'length'}}]
        result=summarize({'status':'pass','cases':[{'passed':True}]*6},events)
        self.assertEqual(result['submission'],{'status':'pass','passed':6,'total':6})
        self.assertEqual(result['generation']['status'],'completed_with_anomalies')
        self.assertIn('output_truncated',result['generation']['anomalies'])

    def test_timeout_recovered_is_visible_and_not_a_submission_failure(self):
        events=[{'type':'message_end','message':{'role':'assistant','stopReason':'error','errorMessage':'Request timed out.'}},
                {'type':'auto_retry_start','attempt':1,'delayMs':2000,'errorMessage':'Request timed out.'},
                {'type':'auto_retry_end','attempt':1,'success':True},
                {'type':'message_end','message':{'role':'assistant','stopReason':'stop'}}]
        score=summarize({'status':'pass','cases':[{'passed':True}]},events)
        self.assertEqual(score['submission']['status'],'pass')
        self.assertEqual(score['generation']['status'],'recovered')
        self.assertEqual(score['generation']['retry_count'],1)
        self.assertIn('api_timeout',score['generation']['anomalies'])

    def test_exhausted_retry_with_partial_answer_keeps_two_dimensions(self):
        events=[{'type':'auto_retry_start','attempt':2,'errorMessage':'503 unavailable'},
                {'type':'auto_retry_end','attempt':2,'success':False,'finalError':'Request timed out.'}]
        score=summarize({'status':'generation_error','cases':[{'passed':True}],'generation_failure':'api_timeout'},events)
        self.assertEqual(score['submission']['status'],'pass')
        self.assertEqual(score['generation']['status'],'failed')
        self.assertEqual(score['generation']['failure'],'api_timeout')
        self.assertIn('retry_exhausted',score['generation']['anomalies'])

    def test_failed_tool_and_unknown_legacy_run_are_not_clean(self):
        score=summarize({'status':'missing_or_oversized_submission'},[{'type':'tool_execution_end','isError':True}])
        self.assertEqual(score['submission']['total'],0)
        self.assertEqual(score['generation']['tool_errors'],1)
        self.assertNotEqual(score['generation']['status'],'completed')
        self.assertEqual(summarize({'status':'pass','cases':[{'passed':True}]},[])['generation']['status'],'unknown')
