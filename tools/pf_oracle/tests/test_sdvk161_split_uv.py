"""Actual wall split writers must project final XYZ through clamped tile.ToUV.

CPU-only source replay; authored A endpoint geometry is real, while x32 BSP
subdivision is an explicit input consistent with the glass partition, not a
claim of retained runtime vertex readback. Old production is kept as a negative.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import ROOT, block
from tools.pf_oracle.tests.test_sdvk161_receiver_writer import ADAPTER

RETAINED = ROOT / 'tools/pf_oracle/tests/fixtures/sdvk161-split-uv-pre-fix.json'
RETAINED_SHA256 = 'edcd9f6db0565b7504e8e3e474b052366d9f9a3cc5a093f7a7ce7c93dbcfef0c'

MAIN = r'''
int main(int argc,char** argv) try {
 using namespace SdvkSurfaceObservation;
 check(argc==2,"case-required");const std::string scenario=argv[1];
 Mesh mesh;level.levelMesh=&mesh;
 const bool south=scenario=="south";
 const bool vertical=scenario=="vertical";
 const float y=south?-192.0f:192.0f;
 mesh.tile.Bounds.min={-256,y,0};mesh.tile.Bounds.max={256,y,160};
 mesh.tile.Plane={0,south?1.0f:-1.0f,0,192};
 mesh.tile.SampleDimension=32;mesh.tile.SetupTileTransform(1024);
 // Owned receipt/page and atlas placement are independent of the wall split.
 mesh.tile.AtlasLocation.ArrayIndex=1;
 vertex_t left,right,mid;
 left.numheights=right.numheights=vertical?3:0;
 left.heightlist[0]=right.heightlist[0]=0;
 left.heightlist[1]=right.heightlist[1]=80;
 left.heightlist[2]=right.heightlist[2]=160;
 mid.X=32;mid.Y=y;
 side_t side;side.numsegs=vertical?1:2;
 seg_t segment{&side,south?0.4375f:0.5625f,&mid};
 seg_t* pieces[2]{&segment,&segment};side.segs=pieces;
 HWWall wall;wall.vertexes[0]=&left;wall.vertexes[1]=&right;wall.seg=&segment;
 wall.glseg.x1=south?256.0f:-256.0f;wall.glseg.x2=-wall.glseg.x1;
 wall.glseg.y1=wall.glseg.y2=y;
 for(int i=0;i<4;++i)wall.tcs[i]={float(i)*0.25f,float(3-i)*0.5f};
 if(scenario=="affine")mesh.tile.Transform.TranslateWorldToLocal={-320,y,-64};
 if(scenario=="unlightmapped")wall.lightmaptile=-1;
 FRenderState state;
 wall.MakeVertices(state,scenario=="unsplit",true);
 const int expected=scenario=="unsplit"?4:6;
 check(int(wall.vertcount)==expected,"split-vertex-count");
 // Hex floats preserve exact semantic field values for old/new comparison,
 // including the intentional failure cases before UV admission.
 std::cout<<std::hexfloat<<"geometry";
 for(unsigned i=0;i<wall.vertcount;++i) {
  const auto& v=state.actual[i];
  std::cout<<' '<<v.x<<','<<v.y<<','<<v.z<<','<<v.u<<','<<v.v<<','<<v.lindex;
 }
 std::cout<<"\nlightuv";
 for(unsigned i=0;i<wall.vertcount;++i)std::cout<<' '<<state.actual[i].lu<<','<<state.actual[i].lv;
 std::cout<<'\n';
 WrittenVertices snapshot;
 if(scenario=="unlightmapped") {
  check(!SdvkDiagnostics::store.Copy(100,expected,2,snapshot),"unlightmapped-snapshot-invented");
  for(const auto& v:state.actual)check(v.lu==0&&v.lv==0&&v.lindex==-1,"unlightmapped-policy-changed");
 }else{
  check(SdvkDiagnostics::store.Copy(100,expected,2,snapshot),"split-writer-snapshot-missing");
  // Compare actual written values, not expected values substituted into a copy.
  if(!CurrentWrittenUV<Vertex>(snapshot,mesh.tile,1024,100,expected)) {
   for(const auto& v:state.actual) {
    const auto uv=mesh.tile.ToUV(v.fPos(),1024);
    std::cerr<<"delta "<<v.x<<' '<<v.y<<' '<<v.z<<' '<<(v.lu-uv.X)<<' '<<(v.lv-uv.Y)<<'\n';
   }
   throw std::runtime_error("split-clamped-uv-not-current");
  }
  auto corrupted=snapshot;corrupted.Vertices[2].U+=1.0f/1024;
  check(!CurrentWrittenUV<Vertex>(corrupted,mesh.tile,1024,100,expected),"one-texel-corruption-admitted");
 }
 std::cout<<"PASS "<<scenario<<'\n';return 0;
} catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 11;}
'''


def build(directory, *, original=False):
    directory.mkdir(parents=True, exist_ok=True)
    vertices=(ROOT/'src/rendering/hwrenderer/scene/hw_walls_vertex.cpp').read_text()
    names=('SplitLeftEdge','SplitRightEdge','SplitUpperEdge','SplitLowerEdge',
           'CountLeftEdge','CountRightEdge','MakeVertices')
    functions=[block(vertices,'void HWWall::'+name+'(') for name in names]
    functions += [block(vertices,'int HWWall::CountVertices(')]
    if original:
        raw=RETAINED.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=RETAINED_SHA256:
            raise AssertionError('SDVK-161 original split writer receipt changed')
        record=json.loads(raw)
        if hashlib.sha256(record['content'].encode()).hexdigest()!=record['sha256']:
            raise AssertionError('SDVK-161 original CreateVertices changed')
        functions.append(record['content'])
    else:
        functions.append(block(vertices,'int HWWall::CreateVertices('))
    tile=(ROOT/'src/common/rendering/hwrenderer/data/hw_lightmaptile.h').read_text()
    tile_functions=[block(tile,'enum PlaneAxis')+';']
    for signature in ('static PlaneAxis BestAxis(', 'void SetupTileTransform(',
                      'FVector3 PointAtYZ(', 'FVector3 PointAtXZ(', 'FVector3 PointAtXY('):
        tile_functions.append(block(tile,signature))
    transform=block(tile,'FVector2 ToUV(const FVector3& vert, float textureSize) const')
    source=ADAPTER[:ADAPTER.index('int main() try {')]+MAIN
    source=source.replace('FVector3(float x,float y,float z)', 'FVector3(float x=0,float y=0,float z=0)')
    source=source.replace(' };\nfloat operator|',
        ' FVector3& operator*=(float factor){X*=factor;Y*=factor;Z*=factor;return *this;} };\nfloat operator|')
    source=source.replace('struct Tile {', '''struct FVector4 {float X,Y,Z,W;};
struct Tile {
 struct {FVector3 min,max;} Bounds;
 int SampleDimension=32;bool UseXYAxis=false;FVector4 Plane{0,1,0,192};
 struct {FVector3 WorldOrigin,WorldU,WorldV;} InverseTransform;
'''+ '\n'.join(tile_functions))
    source=source.replace('@TOUV@',transform).replace('@WRITER@','\n'.join(functions))
    path=directory/'split.cpp';path.write_text(source)
    return compile_fixture(path, output_dir=directory, includes=[ROOT])


class SplitUvTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='sdvk161-clamped-split-')
        cls.directory=Path(cls.temp.name)
        cls.current=build(cls.directory/'current')
        cls.original=build(cls.directory/'original',original=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def execute(self, executable, case):
        return subprocess.run([str(executable),case],capture_output=True,text=True,timeout=10)

    def test_current_actual_split_writers_and_unchanged_controls(self):
        for case in ('north','south','vertical','unsplit','affine','unlightmapped'):
            with self.subTest(case=case):
                r=self.execute(self.current,case)
                self.assertEqual(r.returncode,0,r.stdout+r.stderr)
                self.assertIn('PASS '+case,r.stdout)

    def test_original_production_clamp_interpolation_is_a_named_negative(self):
        for case in ('north','south','vertical'):
            with self.subTest(case=case):
                r=self.execute(self.original,case)
                self.assertEqual(r.returncode,11,r.stdout+r.stderr)
                self.assertIn('split-clamped-uv-not-current',r.stderr)
                current=self.execute(self.current,case)
                self.assertEqual(current.returncode,0,current.stdout+current.stderr)
                self.assertEqual(r.stdout.splitlines()[0],current.stdout.splitlines()[0])

    def test_unsplit_affine_and_unlightmapped_geometry_and_material_uvs_preserved(self):
        for case in ('unsplit','affine','unlightmapped'):
            with self.subTest(case=case):
                old=self.execute(self.original,case);new=self.execute(self.current,case)
                self.assertEqual(old.returncode,0,old.stdout+old.stderr)
                self.assertEqual(new.returncode,0,new.stdout+new.stderr)
                self.assertEqual(old.stdout,new.stdout)


if __name__=='__main__':unittest.main()
