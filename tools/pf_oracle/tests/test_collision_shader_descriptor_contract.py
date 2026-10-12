from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[3]
class CollisionBindingTest(unittest.TestCase):
 def test_viewer_contract(self):
  s=(R/'wadsrc/static/shaders/lightmap/binding_viewer.glsl').read_text()
  for n,name in ((5,'NodeBuffer'),(6,'VertexBuffer'),(7,'ElementBuffer')):
   self.assertIn(f'layout(set = 0, binding = {n}, std430) buffer readonly {name}',s)
