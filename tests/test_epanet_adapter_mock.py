"""Mock the WNTR boundary to verify documented unit conversion and source timing.
This test does NOT call the real EPANET solver and makes no physical claims.
"""
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from core import Scenario, read_inp
from stage2_epanet import run_quality_epanet, DEFAULT_INP


class AdapterMockTest(unittest.TestCase):
    def test_source_timing_si_conversion_and_result_mg_l(self):
        calls={}
        net=read_inp(DEFAULT_INP)

        class Options:
            def __init__(self):
                self.time=types.SimpleNamespace(duration=0,hydraulic_timestep=0,
                    quality_timestep=0,pattern_timestep=0,report_timestep=0)
                self.quality=types.SimpleNamespace(parameter='NONE')

        class FakeNetwork:
            def __init__(self, file):
                calls['inp_file']=file
                self.options=Options()
                self.node_name_list=list(net.node_order)
                self.junction_name_list=list(net.candidates)
                calls['network']=self
            def add_pattern(self, name,pattern):
                calls['pattern_name']=name
                calls['pattern']=pattern
            def add_source(self, name,node,source_type,quality,pattern):
                calls['source']=(name,node,source_type,quality,pattern)

        def fake_binary_pattern(name,**kwargs):
            calls['pattern_kwargs']=kwargs
            return object()

        class FakeEpanetSimulator:
            def __init__(self, network):
                self.network=network
            def run_sim(self, **kwargs):
                calls['run_kwargs']=kwargs
                # Synthetic mock concentration values in WNTR SI kg/m^3
                q=pd.DataFrame(0.0005,index=[i*1800 for i in range(49)],columns=net.node_order)
                return types.SimpleNamespace(node={'quality':q})

        module=types.SimpleNamespace(
            network=types.SimpleNamespace(
                WaterNetworkModel=FakeNetwork,
                elements=types.SimpleNamespace(Pattern=types.SimpleNamespace(binary_pattern=fake_binary_pattern))
            ),
            sim=types.SimpleNamespace(EpanetSimulator=FakeEpanetSimulator),
        )
        with patch.dict(sys.modules,{'wntr':module}):
            result=run_quality_epanet(Scenario('MOCK','J08',6.0,7.5,1.0))
        self.assertAlmostEqual(float(result.loc[8*3600,'J08']),0.5)
        self.assertEqual(calls['source'][:3],('AS_SOURCE','J08','SETPOINT'))
        self.assertAlmostEqual(calls['source'][3],0.001) # mg/L -> kg/m3
        self.assertEqual(calls['pattern_kwargs']['start_time'],6*3600)
        self.assertEqual(calls['pattern_kwargs']['end_time'],int(13.5*3600))
        self.assertEqual(calls['run_kwargs']['version'],2.2)
        self.assertEqual(calls['network'].options.quality.parameter,'CHEMICAL')
        self.assertEqual(calls['network'].options.time.report_timestep,1800)

    def test_rejects_misaligned_injection(self):
        net=read_inp(DEFAULT_INP)
        class FakeNetwork:
            node_name_list=net.node_order
            junction_name_list=net.candidates
            options=types.SimpleNamespace(time=types.SimpleNamespace(),
                                          quality=types.SimpleNamespace())
        module=types.SimpleNamespace(network=types.SimpleNamespace(WaterNetworkModel=lambda _:FakeNetwork()))
        with patch.dict(sys.modules,{'wntr':module}):
            with self.assertRaisesRegex(ValueError,'30-minute'):
                run_quality_epanet(Scenario('BAD','J08',6.2,7.5,1.0))


if __name__=='__main__':
    unittest.main()
