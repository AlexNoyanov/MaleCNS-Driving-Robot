import unittest

from mac.brain import FlyBrain, find_cache_path
from mac.geometry import build_fly_cns_geometry


class BrainLocalTests(unittest.TestCase):
    def test_cache_present(self):
        self.assertIsNotNone(find_cache_path())

    def test_step_local_no_network(self):
        brain = FlyBrain()
        self.assertGreater(brain.n_neurons, 1000)
        self.assertGreater(len(brain.rows), 1000)
        ext = brain.sensors_to_input(20, 8, 40)
        spikes = brain.step(ext)
        self.assertEqual(len(spikes), brain.n_neurons)
        left, right = brain.readout(spikes)
        self.assertGreaterEqual(left, 0.0)
        self.assertLessEqual(left, 1.0)
        self.assertGreaterEqual(right, 0.0)

    def test_geometry_offline(self):
        brain = FlyBrain()
        geom = build_fly_cns_geometry(brain.body_ids)
        self.assertEqual(geom["source"], "procedural_fly_cns")
        self.assertGreater(len(geom["neurons"]), 20)
        self.assertGreater(len(geom["silhouette"]["x"]), 20)
