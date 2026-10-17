"""Real EPANET DLL smoke test; skipped if WNTR unavailable."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
try:
    import wntr
except ImportError:
    wntr = None

from stage2_epanet import run_quality_epanet, DEFAULT_INP
from core import Scenario


@unittest.skipUnless(wntr is not None,'WNTR unavailable: real EPANET smoke test skipped')
class TestRealEpanet(unittest.TestCase):
    def test_pulse_quality_epanet_22(self):
        quality=run_quality_epanet(Scenario('REAL_SMOKE','J08',5.5,8.0,1.0),inp_file=DEFAULT_INP)
        self.assertGreater(float(quality.loc[8*3600,'J08']),0.02,
            'Injected tracer should be present at source during active pulse')
        self.assertLess(float(quality.loc[3*3600,'J08']),0.02,
            'No tracer should be present at source before pulse')
        self.assertEqual(len(quality.columns),21)
        self.assertAlmostEqual(float(quality.min().min()),0,delta=0.01)


if __name__=='__main__':
    unittest.main()
