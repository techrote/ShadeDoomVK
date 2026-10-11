"""CPU-only logical centroid bounds audit; never launches a renderer.

Production constructor and both subdivision bodies are extracted verbatim.
The sole expression instrumentation replaces centroid subscripts with a
checker that logs logical identities and throws before an unpopulated read.
The production tree algorithm, triangle selection, and storage are unchanged.
"""
from pathlib import Path
import hashlib
import platform
import tempfile
import unittest
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import compile_fixture

FIXTURES = Path(__file__).resolve().parent/"fixtures"


def block(text, signature):
    start = text.index(signature)
    begin = text.index('{', start)
    depth = 0
    for i in range(begin, len(text)):
        depth += (text[i] == '{') - (text[i] == '}')
        if depth == 0:
            return text[start:i+1]
    raise ValueError(signature)


PREFIX = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <iostream>
#include <stdexcept>
#include <vector>
struct FVector3 {
    float X, Y, Z;
    FVector3(float x=0, float y=0, float z=0): X(x),Y(y),Z(z) {}
    FVector3 operator+(const FVector3& b) const { return {X+b.X,Y+b.Y,Z+b.Z}; }
    FVector3 operator-(const FVector3& b) const { return {X-b.X,Y-b.Y,Z-b.Z}; }
    FVector3 operator*(float b) const { return {X*b,Y*b,Z*b}; }
    FVector3& operator+=(const FVector3& b) { X+=b.X;Y+=b.Y;Z+=b.Z;return *this; }
    FVector3& operator/=(float b) { X/=b;Y/=b;Z/=b;return *this; }
    float operator|(const FVector3& b) const { return X*b.X+Y*b.Y+Z*b.Z; }
};
struct FVector4 {
    float X,Y,Z,W;
    FVector4() = default;
    FVector4(float x,float y,float z,float w): X(x),Y(y),Z(z),W(w) {}
    FVector4(const FVector3& p, float w): X(p.X),Y(p.Y),Z(p.Z),W(w) {}
    FVector3 XYZ() const { return {X,Y,Z}; }
    float operator|(const FVector4& b) const { return X*b.X+Y*b.Y+Z*b.Z+W*b.W; }
};
struct cycle_t { void ResetAndClock() {} void Unclock() {} double TimeMS() const { return 0; } };
struct TraceHit;
class RayBBox;
'''

CHECKER = r'''
static AccelStructScratchBuffer* actualScratch;
static const FFlatVertex* actualVertices;
static const unsigned int* actualElements;
static int reads, mismatches, outOfRange;
static std::vector<int> originalIds;
static const FVector4& checked_centroid(const FVector4* table, int triangle) {
    ++reads;
    assert(table == actualScratch->centroids.data());
    const size_t populated = actualScratch->centroids.size();
    const size_t capacity = actualScratch->centroids.capacity();
    std::cout << "READ original=" << triangle << " populated=" << populated << " capacity=" << capacity;
    if (triangle < 0 || static_cast<size_t>(triangle) >= populated) {
        ++outOfRange;
        std::cout << " OUTSIDE_POPULATED_RANGE\n";
        throw std::out_of_range("logical centroid index");
    }
    const FVector4& value = table[triangle];
    int storedOriginal = -1;
    for (int candidate : originalIds) {
        const int base = candidate*3;
        const FVector3 expectedCandidate = (actualVertices[actualElements[base]].fPos()
            + actualVertices[actualElements[base+1]].fPos()
            + actualVertices[actualElements[base+2]].fPos())*(1.0f/3.0f);
        if (std::abs(value.X-expectedCandidate.X)<1e-5f
            && std::abs(value.Y-expectedCandidate.Y)<1e-5f
            && std::abs(value.Z-expectedCandidate.Z)<1e-5f) storedOriginal = candidate;
    }
    const int e = triangle*3;
    const FVector3 expected = (actualVertices[actualElements[e]].fPos()
        + actualVertices[actualElements[e+1]].fPos()
        + actualVertices[actualElements[e+2]].fPos())*(1.0f/3.0f);
    const bool mismatch = storedOriginal != triangle || std::abs(value.X-expected.X)>1e-5f
        || std::abs(value.Y-expected.Y)>1e-5f || std::abs(value.Z-expected.Z)>1e-5f;
    mismatches += mismatch;
    std::cout << " stored_original=" << storedOriginal << " identity_match=" << !mismatch << '\n';
    return value;
}
'''

SUFFIX = r'''
static void validateGraph(const CPUBottomLevelAccelStruct& tree, const std::vector<int>& expected) {
    if (expected.empty()) { assert(tree.GetRoot()==-1); assert(tree.GetNodes().empty()); return; }
    std::vector<int> pending{tree.GetRoot()}, found;
    int visits=0;
    while (!pending.empty()) {
        const int i=pending.back();pending.pop_back();
        assert(i>=0 && static_cast<size_t>(i)<tree.GetNodes().size());
        assert(++visits<=static_cast<int>(tree.GetNodes().size()));
        const auto& node=tree.GetNodes()[i];
        if (node.IsLeaf()) found.push_back(node.element_index/3);
        else { pending.push_back(node.left); pending.push_back(node.right); }
    }
    std::sort(found.begin(),found.end());
    assert(found==expected);
}
int main(int argc, char** argv) {
    assert(argc==3);
    const bool repaired = argv[2][0]=='1';
    const int scenario=argv[1][0]-'0';
    assert(scenario>=0 && scenario<=4);
    const char* names[]={"no-hole","leading-hole","interior-hole","all-degenerate","trailing-hole"};
    std::cout << "CASE " << names[scenario] << '\n';
    std::vector<FFlatVertex> vertices(12);
    std::vector<unsigned int> elements;
    for (unsigned int i=0;i<4;++i) {
        const float x=10.0f*static_cast<float>(i);
        vertices[3*i].Set(x,0,0,0,0);
        vertices[3*i+1].Set(x+2,0,0,0,0);
        vertices[3*i+2].Set(x,0,1,0,0);
        const bool hole=scenario==3 || (scenario==1 && i==0) || (scenario==2 && i==1) || (scenario==4 && i==3);
        elements.push_back(hole?0:3*i);
        elements.push_back(hole?0:3*i+1);
        elements.push_back(hole?0:3*i+2);
        if (!hole) originalIds.push_back(static_cast<int>(i));
    }
    AccelStructScratchBuffer scratch;
    // Poison reusable capacity: a logical bounds check must use populated size.
    scratch.centroids.resize(7,FVector4(777,777,777,777));
    actualScratch=&scratch;actualVertices=vertices.data();actualElements=elements.data();
    bool blocked=false;
    try {
        CPUBottomLevelAccelStruct tree(vertices.data(),static_cast<int>(vertices.size()),elements.data(),static_cast<int>(elements.size()),scratch);
        validateGraph(tree,originalIds);
        if (repaired) {
            for (int i=0;i<4;++i) {
                if (std::find(originalIds.begin(),originalIds.end(),i)==originalIds.end()) {
                    const auto& unused=scratch.centroids[i];
                    assert(unused.X==0 && unused.Y==0 && unused.Z==0 && unused.W==0);
                }
            }
        }
    } catch (const std::out_of_range&) { blocked=true; }
    std::cout << "SUMMARY reads=" << reads << " wrong_identity=" << mismatches
        << " outside_populated=" << outOfRange << " guarded_stop=" << blocked
        << " centroids_size=" << scratch.centroids.size() << " centroids_capacity=" << scratch.centroids.capacity() << '\n';
    if (!repaired && (scenario==1 || scenario==2)) {
        assert(blocked && outOfRange==1 && mismatches>=1);
        assert(scratch.centroids.size()==3 && scratch.centroids.capacity()>=4);
    } else {
        assert(!blocked && mismatches==0 && outOfRange==0);
        if (scenario==3) assert(reads==0 && (repaired ? scratch.centroids.size()==4 : scratch.centroids.empty()));
        else assert(reads>0);
        if (repaired) assert(scratch.centroids.size()==4);
    }
}
'''


class CollisionCentroidIdentityTests(unittest.TestCase):
    def test_original_triangle_centroids_with_sparse_geometry(self):
        source_path = ROOT/'src/common/rendering/hwrenderer/data/hw_collision.cpp'
        source = source_path.read_text()
        header = source_path.with_suffix('.h').read_text()
        old_constructor = block((FIXTURES/'collision_centroid_pre_fix.txt').read_text(),
            'CPUBottomLevelAccelStruct::CPUBottomLevelAccelStruct(')
        # Retain the exact pre-fix constructor, not a mutation of the repair.
        self.assertEqual(hashlib.sha256(old_constructor.encode()).hexdigest(),
            '81c95f63fe26d71b465f46163c9b3c64042726891d2db0941df8d9e524a60898')
        constructors = {'pre-fix':old_constructor,
            'repaired':block(source,'CPUBottomLevelAccelStruct::CPUBottomLevelAccelStruct(')}
        leaf = block(source,'int CPUBottomLevelAccelStruct::SubdivideLeaf(')
        bodies = {
            'scalar':block(source,'int CPUBottomLevelAccelStruct::Subdivide(int *triangles,'),
            'sse-debug':block(source,'int CPUBottomLevelAccelStruct::Subdivide(int* triangles,'),
        }
        if platform.machine().lower() not in ('amd64','x86_64','x86','i386','i686'):
            # Production defines NO_SSE on non-x86 targets; scalar remains required.
            bodies.pop('sse-debug')
        declarations = '\n'.join(block(header,sig)+';' for sig in (
            'class CollisionBBox\n','class AccelStructScratchBuffer\n','class CPUBottomLevelAccelStruct\n'))
        flat = (ROOT/'src/common/rendering/hwrenderer/data/flatvertices.h').read_text().replace('#pragma once','')
        for variant, body in bodies.items():
            self.assertEqual(body.count('centroids[triangles[i]]'),3)
            # Two executable reads and their original explanatory comment.
            instrumented = body.replace('centroids[triangles[i]]','checked_centroid(centroids, triangles[i])')
            axes = 'static const FVector3 axes[3] = { FVector3(-1,0,0), FVector3(0,-1,0), FVector3(0,0,-1) };' if variant=='sse-debug' else ''
            warnings = '\n#ifdef _MSC_VER\n#pragma warning(push)\n#pragma warning(disable: 4189 4458)\n#else\n#pragma GCC diagnostic push\n#pragma GCC diagnostic ignored "-Wunused-variable"\n#endif\n'
            warnings_end = '\n#ifdef _MSC_VER\n#pragma warning(pop)\n#else\n#pragma GCC diagnostic pop\n#endif\n'
            for name, constructor in constructors.items():
                with tempfile.TemporaryDirectory(prefix='collision-centroid-') as directory:
                    fixture = Path(directory)/'centroid.cpp'
                    intrinsics = '#include <immintrin.h>\n' if variant=='sse-debug' else ''
                    fixture.write_text(intrinsics+PREFIX+flat+declarations+CHECKER+warnings+constructor+leaf+axes+instrumented+warnings_end+SUFFIX)
                    executable = compile_fixture(fixture,output_dir=directory,root=ROOT)
                    for scenario in range(5):
                        with self.subTest(variant=variant,constructor=name,scenario=scenario):
                            result = subprocess.run([str(executable),str(scenario),'1' if name=='repaired' else '0'],
                                capture_output=True,text=True,check=True,timeout=10)
                            self.assertIn('SUMMARY',result.stdout)
                            if name=='pre-fix' and scenario in (1,2):
                                self.assertIn('outside_populated=1 guarded_stop=1',result.stdout)
                            else:
                                self.assertIn('wrong_identity=0 outside_populated=0 guarded_stop=0',result.stdout)


if __name__=='__main__':
    unittest.main()


