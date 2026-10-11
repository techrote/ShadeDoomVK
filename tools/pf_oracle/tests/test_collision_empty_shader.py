"""CPU execution of exact GLSL traversal entry bodies with checked node access.

This checks source control flow, not GLSL/SPIR-V compilation or GPU execution.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.test_collision_upload_root import production_function

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).resolve().parent / "fixtures"

PREFIX = r'''
#include <cassert>
#include <iostream>
#include <stdexcept>
#include <vector>
struct vec3 {
    float x=0,y=0,z=0;
    vec3 operator+(const vec3& b) const { return {x+b.x,y+b.y,z+b.z}; }
    vec3 operator*(float a) const { return {x*a,y*a,z*a}; }
};
struct RayBBox {};
RayBBox create_ray(vec3,vec3) { return {}; }
struct TraceHit { float fraction; int triangle; float b,c; };
struct Node { int left=-1,right=-1,element_index=-1; float fraction=1; };
struct Nodes : std::vector<Node> {
    const Node& operator[](int i) const {
        if (i<0 || static_cast<size_t>(i)>=size()) throw std::out_of_range("node bounds");
        return std::vector<Node>::operator[](i);
    }
} nodes;
int nodesRoot=-1,accesses=0;
bool overlap_bv_ray(RayBBox,int i) { ++accesses;(void)nodes[i];return true; }
bool is_leaf(int i) { return nodes[i].element_index!=-1; }
float intersect_triangle_ray(RayBBox,int i,float& b,float& c) {
    b=0.2f;c=0.3f;return nodes[i].fraction;
}
'''

SUFFIX = r'''
int main(int argc,char** argv) {
    assert(argc==3);
    const bool repaired=argv[1][0]=='1';
    const int scenario=argv[2][0]-'0';
    assert(scenario>=0 && scenario<=4);
    // Empty inputs include retained buffer capacity/stale contents. Root is authority.
    if (scenario==1) nodes.push_back({-1,-1,999,0.1f});
    if (scenario>=2) {
        nodes.push_back({-1,-1,3,scenario==4?1.0f:0.25f});
        nodesRoot=0;
        if (scenario==3) {
            nodes.push_back({-1,-1,6,0.75f});
            nodes.push_back({0,1,-1,1});nodesRoot=2;
        }
    }
    bool any=false,anyBlocked=false,firstBlocked=false;
    TraceHit hit{1,-1,0,0};
    try { any=TraceAnyHit({},0,{},1); } catch (const std::out_of_range&) { anyBlocked=true; }
    try { hit=find_first_hit({}); } catch (const std::out_of_range&) { firstBlocked=true; }
    const bool empty=scenario<2;
    assert(anyBlocked==(!repaired && empty));
    assert(firstBlocked==(!repaired && empty));
    if (repaired && empty) assert(accesses==0);
    if (!anyBlocked) assert(any==(scenario==2 || scenario==3));
    if (!firstBlocked) {
        assert(hit.fraction==((scenario==2 || scenario==3)?0.25f:1.0f));
        assert(hit.triangle==((scenario==2 || scenario==3)?1:-1));
        if (empty || scenario==4) assert(hit.b==0 && hit.c==0);
        else assert(hit.b==0.2f && hit.c==0.3f);
    }
    const int before=accesses;
    assert(!TraceAnyHit({},0,{},0));
    assert(accesses==before);
    std::cout << "scenario=" << scenario << " any=" << any << " fraction=" << hit.fraction
        << " triangle=" << hit.triangle << " accesses=" << accesses << '\n';
}
'''


def entry_bodies(source):
    software = source[source.index("#else"):]
    return production_function(software, "bool TraceAnyHit(") + "\n" + production_function(
        software, "TraceHit find_first_hit(")


class CollisionEmptyShaderTests(unittest.TestCase):
    def test_exact_software_bodies_reject_empty_roots_before_access(self):
        old = (FIXTURES / "collision_empty_shader_pre_fix.glsl").read_text()
        evidence = json.loads((FIXTURES / "collision_sparse_slots_evidence.json").read_text())
        self.assertEqual(hashlib.sha256(old.encode()).hexdigest(), evidence["shader_retained_sha256"])
        current = (ROOT / "wadsrc/static/shaders/lightmap/polyfill_rayquery.glsl").read_text()
        nonempty = {}
        with tempfile.TemporaryDirectory() as directory:
            for repaired, source in ((False, old), (True, current)):
                unit = Path(directory) / f"empty_shader_{int(repaired)}.cpp"
                unit.write_text(PREFIX + entry_bodies(source) + SUFFIX)
                exe = compile_fixture(unit, output_dir=directory)
                for scenario in range(5):
                    with self.subTest(repaired=repaired, scenario=scenario):
                        result = subprocess.run([str(exe), str(int(repaired)), str(scenario)],
                                                check=True, capture_output=True, text=True, timeout=10)
                        if scenario >= 2:
                            if repaired:
                                self.assertEqual(result.stdout, nonempty[scenario])
                            else:
                                nonempty[scenario] = result.stdout


if __name__ == "__main__":
    unittest.main()
