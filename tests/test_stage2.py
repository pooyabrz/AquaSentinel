"""Stage 2 offline integration tests, with explicitly non-EPANET fixture data."""
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core import Scenario, make_training_bank, make_test_cases, quality_surrogate, read_inp, SAMPLE_SLOTS_H
from stage2_epanet import (validate_quality, build_cache, quality_at,
                           simulate_from_physical_frames, summarize_benchmark,
                           run_pipeline, build_payload, THRESHOLD)

NET = read_inp()


def surrogate_fixture(s: Scenario, *, inp_file=None):
    """Explicitly nonphysical surrogate in mg/L, used ONLY in tests."""
    q = quality_surrogate(NET,s)
    return pd.DataFrame(q,index=[i*1800 for i in range(49)])


class TestStage2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank,cls.priors = make_training_bank()
        cls.frames = {s.name: surrogate_fixture(s) for s in cls.bank}
        cls.cache = build_cache(NET,cls.bank,cls.frames)

    def test_unit_contract_and_time_sample(self):
        frame=surrogate_fixture(Scenario('X','J08',5.5,8,1))
        q=validate_quality(frame,NET.node_order,label='test')
        self.assertEqual(len(q),49)
        self.assertAlmostEqual(quality_at(q,'J08',8),1.0)

    def test_missing_time_rejected(self):
        q=surrogate_fixture(Scenario('X','J08',5.5,8,1)).drop(index=8*3600)
        with self.assertRaisesRegex(ValueError,'timestamps'):
            validate_quality(q,NET.node_order,label='bad')

    def test_bad_nan_rejected(self):
        q=surrogate_fixture(Scenario('X','J08',5.5,8,1))
        q.loc[8*3600,'J08']=float('nan')
        with self.assertRaisesRegex(ValueError,'NaN'):
            validate_quality(q,NET.node_order,label='bad')

    def test_no_event_prior_positive_less_than_one(self):
        self.assertAlmostEqual(sum(self.priors),1)
        like=[self.cache[(s.name,8)]['J08'] for s in self.bank]
        self.assertTrue(all(0 < p < 1 for p in like))

    def test_ranked_adaptive_benchmark_budget(self):
        truth=Scenario('TEST','J08',5.5,8,1)
        q=surrogate_fixture(truth)
        trials=[simulate_from_physical_frames(NET,self.bank,self.priors,self.cache,truth,q,p,2026)
                for p in ('adaptive','static','random')]
        self.assertEqual([r['policy'] for r in trials],['adaptive','static','random'])
        self.assertTrue(all(t['tests_run']==5 for t in trials))
        self.assertTrue(all(len(set(t['sites'].split(',')))==5 for t in trials))
        self.assertTrue(all(t['detection_hour'] in SAMPLE_SLOTS_H or t['detection_hour'] is None for t in trials))
        self.assertEqual(trials[0],simulate_from_physical_frames(NET,self.bank,self.priors,self.cache,truth,q,'adaptive',2026))

    def test_detected_vs_false_alarm(self):
        truth=Scenario('TEST_NONE',None,0,0,0)
        q=surrogate_fixture(truth)
        run=simulate_from_physical_frames(NET,self.bank,self.priors,self.cache,truth,q,'adaptive')
        self.assertFalse(run['detected'])
        self.assertFalse(run['has_event'])
        self.assertIsNone(run['penalized_delay_h'])

    def test_summary_shape(self):
        truth=Scenario('T','J08',5.5,8,1)
        q=surrogate_fixture(truth)
        rows=[simulate_from_physical_frames(NET,self.bank,self.priors,self.cache,truth,q,p)
              for p in ('adaptive','static','random')]
        s=summarize_benchmark(rows)
        self.assertEqual(len(s),3)
        self.assertTrue(all(x['max_tests_per_day']==5 for x in s))

    def test_build_demo_with_fixture_label_not_epanet(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            result=run_pipeline('demo',ROOT/'data'/'demo_network.inp',p,
                                simulator=surrogate_fixture,engine_label='TEST FIXTURE - NOT EPANET')
            self.assertEqual(result['training_scenarios'],25)
            html=Path(result['dashboard']).read_text(encoding='utf-8')
            self.assertIn('TEST FIXTURE',html)
            self.assertIn('NOT an EPANET result',html)
            self.assertNotIn('AQUASENTINEL AI · MILESTONE 02',html)
            self.assertTrue((p/'epanet_training_quality_mg_l.csv').exists())
            self.assertTrue((p/'epanet_initial_ranking.csv').exists())

    def test_benchmark_with_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            result=run_pipeline('benchmark',ROOT/'data'/'demo_network.inp',p,replicates=1,
                                simulator=surrogate_fixture,engine_label='TEST FIXTURE - NOT EPANET')
            self.assertEqual(len(result['benchmark']),3)
            self.assertTrue((p/'epanet_benchmark_trials.csv').exists())
            self.assertEqual(len(pd.read_csv(p/'epanet_benchmark_trials.csv')),
                             len(make_test_cases())*3)
            self.assertTrue((p/'epanet_benchmark_summary.csv').exists())


if __name__ == '__main__':
    unittest.main()
