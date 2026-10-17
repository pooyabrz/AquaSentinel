"""Run: python -m unittest discover -s tests -v"""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from core import (read_inp, make_training_bank, make_test_cases, Scenario,
                  quality_surrogate, concentration_at, bayes_update,
                  build_likelihood_cache, rank_sites, benchmark,
                  SAMPLE_SLOTS_H, HORIZON_H, THRESHOLD)

class TestAquaSentinel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.net=read_inp()
        cls.bank,cls.prior=make_training_bank()
        cls.cache=build_likelihood_cache(cls.net,cls.bank)

    def test_network_readable(self):
        self.assertEqual(len(self.net.candidates),20)
        self.assertEqual(len(self.net.directed_edges),30)
        self.assertEqual(len(self.net.node_order),21)

    def test_source_pulse_and_propagation(self):
        s=Scenario('X','J08',5.5,8,1)
        q=quality_surrogate(self.net,s)
        self.assertAlmostEqual(concentration_at(q,'J08',6),1)
        self.assertEqual(concentration_at(q,'J08',3),0)
        self.assertGreater(concentration_at(q,'J19',9),0)
        self.assertEqual(concentration_at(q,'R0',9),0)

    def test_no_contamination(self):
        s=Scenario('NONE',None,0,0,0)
        q=quality_surrogate(self.net,s)
        self.assertTrue(all(x == 0 for seq in q.values() for x in seq))

    def test_probabilities_and_bayes(self):
        self.assertAlmostEqual(sum(self.prior),1)
        before=self.prior[:]
        like=[self.cache[(s.name,8)]['J20'] for s in self.bank]
        after=bayes_update(before,like,False)
        self.assertAlmostEqual(sum(after),1)
        self.assertGreater(after[0],before[0])

    def test_ranking_and_no_repeats(self):
        visited=[]
        for slot in SAMPLE_SLOTS_H:
            ranked=rank_sites(self.net,self.bank,self.prior,self.cache,slot,visited)
            self.assertEqual(len(ranked),20-len(visited))
            self.assertTrue(all(0<=r['p_positive']<=1 for r in ranked))
            visited.append(ranked[0]['node'])
        self.assertEqual(len(set(visited)),5)

    def test_train_test_cases_separate(self):
        ids={s.name for s in self.bank}
        test_ids={s.name for s in make_test_cases()}
        self.assertFalse(ids & test_ids)

    def test_benchmark_budget(self):
        rows,summary=benchmark(self.net,n_reps=1)
        self.assertEqual(len(rows),len(make_test_cases())*3)
        self.assertTrue(all(r['tests_run']==5 for r in rows))
        self.assertTrue(all(0<=s['detection_rate']<=1 for s in summary))
        self.assertTrue(all((r['first_detection_test'] is None or 1<=r['first_detection_test']<=5) for r in rows))

if __name__=='__main__':
    unittest.main()
