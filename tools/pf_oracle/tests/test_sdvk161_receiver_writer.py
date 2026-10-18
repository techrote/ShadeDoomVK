"""Actual immediate wall writer + owned snapshot + precise UV consumer, CPU only."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import ROOT, block

ADAPTER = r'''
#include <algorithm>
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>
#include "src/rendering/hwrenderer/diagnostics/hw_specialsurfacecontract.h"
struct FVector2 { float X,Y; FVector2(float x,float y):X(x),Y(y){} };
struct FVector3 { float X,Y,Z; FVector3(float x,float y,float z):X(x),Y(y),Z(z){} FVector3 operator-(const FVector3& b) const {return {X-b.X,Y-b.Y,Z-b.Z};} };
float operator|(const FVector3& a,const FVector3& b) {return a.X*b.X+a.Y*b.Y+a.Z*b.Z;}
struct Vertex {
 float x=0,y=0,z=0,u=0,v=0,lu=0,lv=0,lindex=-1;
 void Set(float X,float Z,float Y,float U,float V,float LU,float LV,float Page)
 {x=X;y=Y;z=Z;u=U;v=V;lu=LU;lv=LV;lindex=Page;}
 FVector3 fPos() const {return {x,y,z};}
};
using FFlatVertex=Vertex;
struct Receipt { uint64_t Owner=11,Incarnation=1;size_t Slot=3; };
struct Tile {
 struct {int X=64,Y=32,Width=512,Height=256,ArrayIndex=0;Receipt Allocation;} AtlasLocation;
 struct {FVector3 TranslateWorldToLocal{-128,-128,-16},ProjLocalToU{1,0,0},ProjLocalToV{0,0,1};} Transform;
 @TOUV@
};
using LightmapTile=Tile;
struct Mesh { struct {int TextureSize=1024;} Lightmap;Tile tile;Tile& GetLightmapTile(int i){if(i!=2)throw std::runtime_error("tile");return tile;} };
struct {Mesh* levelMesh;} level;
namespace SdvkDiagnostics {
 bool Selected=true;
 SdvkSurfaceObservation::WrittenVertexStore store;
 bool SpecialSurfaceFrameSelected(){return Selected;}
 void CaptureWrittenVertices(const Mesh* mesh,int first,int count,int tile,const FFlatVertex* written)
 {store.Capture(first,count,tile,mesh->tile.AtlasLocation.Allocation,written);}
}
struct vertex_t {int numheights=3;float heightlist[3]{-10,40,200};float X=16,Y=-32;float fX()const{return X;}float fY()const{return Y;}};
struct seg_t;
struct side_t {int numsegs=2;int Flags=0;seg_t** segs;};
struct seg_t {side_t* sidedef;float sidefrac=0.5f;vertex_t* v2;};
constexpr int WALLF_POLYOBJ=1;
bool gl_seamless=true;
struct FRenderState {
 std::vector<FFlatVertex> actual;
 std::pair<FFlatVertex*,unsigned> AllocVertices(int count){actual.resize(size_t(count));return {actual.data(),100};}
};
struct HWWall {
 enum {LOLFT,UPLFT,UPRGT,LORGT};
 enum {HWF_NOSPLITUPPER=16,HWF_NOSPLITLOWER=32,HWF_NOSPLIT=64};
 struct {float x1=-64,y1=-32,x2=96,y2=-32,fracleft=0,fracright=1;} glseg;
 struct Texcoord{float u=0,v=0;}tcs[4],lightuv[4];
 float ztop[2]{160,160},zbottom[2]{0,0},zceil[2]{160,160},zfloor[2]{0,0};
 float lindex=-1;int lightmaptile=2,flags=0;unsigned vertindex=0,vertcount=0;
 vertex_t* vertexes[2];seg_t* seg;
 int CountVertices();int CreateVertices(FFlatVertex*&,bool);
 void CountLeftEdge(unsigned&);void CountRightEdge(unsigned&);
 void SplitLeftEdge(FFlatVertex*&);void SplitRightEdge(FFlatVertex*&);void SplitUpperEdge(FFlatVertex*&);void SplitLowerEdge(FFlatVertex*&);
 void MakeVertices(FRenderState&,bool,bool=false);
};
// Production retains unused facc/facf values in its wall splitter. Keep the
// exact body while suppressing only that inherited warning in this adapter.
#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable:4189)
#else
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-variable"
#endif
@WRITER@
#ifdef _MSC_VER
#pragma warning(pop)
#else
#pragma GCC diagnostic pop
#endif
void check(bool value,const char* message){if(!value)throw std::runtime_error(message);}
int main() try {
 using namespace SdvkSurfaceObservation;
 Mesh mesh;level.levelMesh=&mesh;
 vertex_t left,right,mid;right.heightlist[1]=80;
 side_t side;seg_t segment{&side,0.5f,&mid};seg_t* pieces[2]{&segment,&segment};side.segs=pieces;
 HWWall wall;wall.vertexes[0]=&left;wall.vertexes[1]=&right;wall.seg=&segment;
 FRenderState state;
 wall.MakeVertices(state,false,true);
 check(wall.vertcount==8,"actual-variable-writer-count");
 WrittenVertices snapshot;
 check(SdvkDiagnostics::store.Copy(100,8,2,snapshot),"actual-writer-snapshot-missing");
 check(CurrentWrittenUV<Vertex>(snapshot,mesh.tile,1024,100,8),"current-written-split-uv");
 // Snapshot owns actual bytes, not a raw vertex pointer or reconstructed UV.
 state.actual[0].lu+=0.125f;
 check(CurrentWrittenUV<Vertex>(snapshot,mesh.tile,1024,100,8),"snapshot-aliases-writer-storage");
 SdvkDiagnostics::store.Capture(100,8,2,mesh.tile.AtlasLocation.Allocation,state.actual.data());
 check(SdvkDiagnostics::store.Copy(100,8,2,snapshot),"corrupt-writer-copy");
 check(!CurrentWrittenUV<Vertex>(snapshot,mesh.tile,1024,100,8),"invented-uv-from-expected-transform");
 state.actual[0].lu-=0.125f;
 SdvkDiagnostics::store.Capture(100,8,2,mesh.tile.AtlasLocation.Allocation,state.actual.data());
 check(SdvkDiagnostics::store.Copy(100,8,2,snapshot),"restored-copy");
 auto bad=snapshot;bad.Vertices[6].U+=1.0f/1024;
 check(!CurrentWrittenUV<Vertex>(bad,mesh.tile,1024,100,8),"stale-one-texel-uv");
 check(CurrentWrittenUV<Vertex>(bad,mesh.tile,1024,100,4),"actual-subrange-only");
 bad=snapshot;bad.Vertices[2].Page=1;
 check(!CurrentWrittenUV<Vertex>(bad,mesh.tile,1024,100,8),"wrong-actual-writer-page");
 bad=snapshot;bad.Vertices[2].V=std::numeric_limits<float>::quiet_NaN();
 check(!CurrentWrittenUV<Vertex>(bad,mesh.tile,1024,100,8),"nan-actual-uv");
 bad=snapshot;bad.Vertices[2].X=std::numeric_limits<float>::infinity();
 check(!CurrentWrittenUV<Vertex>(bad,mesh.tile,1024,100,8),"inf-actual-position");
 mesh.tile.AtlasLocation.Allocation.Incarnation++;
 check(!CurrentWrittenUV<Vertex>(snapshot,mesh.tile,1024,100,8),"same-page-recycled-allocation");
 mesh.tile.AtlasLocation.Allocation.Incarnation--;
 mesh.tile.AtlasLocation.X++;
 check(!CurrentWrittenUV<Vertex>(snapshot,mesh.tile,1024,100,8),"same-page-new-current-transform");
 mesh.tile.AtlasLocation.X--;
 check(!CurrentWrittenUV<Vertex>(snapshot,mesh.tile,1024,99,8),"range-before-writer");
 check(!CurrentWrittenUV<Vertex>(snapshot,mesh.tile,1024,100,9),"range-after-writer");
 SdvkDiagnostics::store.Clear();
 check(!SdvkDiagnostics::store.Copy(100,8,2,snapshot),"cross-frame-evidence");
 wall.vertcount=0;SdvkDiagnostics::Selected=false;wall.MakeVertices(state,false,true);
 check(!SdvkDiagnostics::store.Copy(100,8,2,snapshot),"disabled-observation-writes");
 SdvkDiagnostics::Selected=true;wall.vertcount=0;wall.MakeVertices(state,true,true);
 check(wall.vertcount==4&&SdvkDiagnostics::store.Copy(100,4,2,snapshot),"unsplit-actual-writer");
 SdvkDiagnostics::store.Clear();std::vector<Vertex> bounded(WrittenVertexStore::MaxVertices);
 SdvkDiagnostics::store.Capture(0,int(bounded.size()),2,mesh.tile.AtlasLocation.Allocation,bounded.data());
 bool overflow=false;try{SdvkDiagnostics::store.Capture(5000,1,2,mesh.tile.AtlasLocation.Allocation,bounded.data());}catch(const std::runtime_error&){overflow=true;}
 check(overflow,"silent-snapshot-truncation");
 std::cout<<"PASS actual-writer-owned-snapshot-current-receiver\n";
 return 0;
} catch (const std::exception& error) {std::cerr<<error.what()<<"\n";return 11;}
'''


class ReceiverWriterTests(unittest.TestCase):
    def test_actual_wall_vertex_writer_and_precise_snapshot_contract(self):
        vertex_source=(ROOT/'src/rendering/hwrenderer/scene/hw_walls_vertex.cpp').read_text()
        functions=[block(vertex_source,'void HWWall::'+name+'(') for name in
                   ('SplitLeftEdge','SplitRightEdge','SplitUpperEdge','SplitLowerEdge','CountLeftEdge','CountRightEdge','MakeVertices')]
        functions += [block(vertex_source,'int HWWall::'+name+'(') for name in ('CountVertices','CreateVertices')]
        tile_source=(ROOT/'src/common/rendering/hwrenderer/data/hw_lightmaptile.h').read_text()
        transform=block(tile_source,'FVector2 ToUV(const FVector3& vert, float textureSize) const')
        source=ADAPTER.replace('@TOUV@',transform).replace('@WRITER@','\n'.join(functions))
        with tempfile.TemporaryDirectory(prefix='sdvk161-writer-') as d:
            path=Path(d)/'writer.cpp';path.write_text(source)
            executable=compile_fixture(path,output_dir=d,includes=[ROOT])
            result=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('PASS actual-writer-owned-snapshot-current-receiver',result.stdout)
            # Restore the original absent wall witness while keeping all real
            # writing intact: this must fail the snapshot admission itself.
            mutant=source.replace('SdvkDiagnostics::CaptureWrittenVertices(level.levelMesh, int(vertindex), int(vertcount), lightmaptile, written);',
                                  '(void)written;')
            self.assertNotEqual(mutant,source)
            path.write_text(mutant)
            negative=compile_fixture(path,output_dir=d,includes=[ROOT],name='missing-wall-snapshot')
            result=subprocess.run([str(negative)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,11,result.stdout+result.stderr)
            self.assertEqual(result.stderr.strip(),'actual-writer-snapshot-missing')

    def test_actual_worker_writer_hands_owned_snapshot_to_main_and_next_frame_clears_it(self):
        vertex_source=(ROOT/'src/rendering/hwrenderer/scene/hw_walls_vertex.cpp').read_text()
        functions=[block(vertex_source,'void HWWall::'+name+'(') for name in
                   ('SplitLeftEdge','SplitRightEdge','SplitUpperEdge','SplitLowerEdge','CountLeftEdge','CountRightEdge','MakeVertices')]
        functions += [block(vertex_source,'int HWWall::'+name+'(') for name in ('CountVertices','CreateVertices')]
        tile_source=(ROOT/'src/common/rendering/hwrenderer/data/hw_lightmaptile.h').read_text()
        transform=block(tile_source,'FVector2 ToUV(const FVector3& vert, float textureSize) const')
        diagnostics=(ROOT/'src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp').read_text()
        storage=block(diagnostics,'namespace {\nthread_local SpecialSurfaceMetadata ImmediateSurface;')
        wrapper='namespace SdvkDiagnostics {\n'+storage+"""
 bool Selected=true;
 bool SpecialSurfaceFrameSelected(){return Selected;}
 void Fail(const char* message){throw std::runtime_error(message);}
"""+'\n'.join(block(diagnostics,signature) for signature in
                   ('void CaptureWrittenVertices(', 'void ApplyWrittenVertices(',
                    'SpecialSurfaceScope::SpecialSurfaceScope(', 'SpecialSurfaceScope::~SpecialSurfaceScope()'))+'\n}'
        source=ADAPTER.replace('@TOUV@',transform).replace('@WRITER@','\n'.join(functions))
        source=source.replace('#include <vector>','#include <vector>\n#include <thread>\n#include <exception>')
        source=source.replace('#include "src/rendering/hwrenderer/diagnostics/hw_specialsurfacecontract.h"',
                              '#include "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.h"')
        source=source.replace('struct Vertex {','struct FFlatVertex {').replace('using FFlatVertex=Vertex;','using Vertex=FFlatVertex;')
        source=source.replace('struct Mesh {','class LevelMesh { public:')
        source=source.replace('Tile& GetLightmapTile(int i){if(i!=2)throw std::runtime_error("tile");return tile;}',
                              'const Tile& GetLightmapTile(int i)const{if(i!=2)throw std::runtime_error("tile");return tile;} Tile& GetLightmapTile(int i){return const_cast<Tile&>(static_cast<const LevelMesh*>(this)->GetLightmapTile(i));}')
        source=source.replace('struct {Mesh* levelMesh;} level;','using Mesh=LevelMesh;\nstruct {Mesh* levelMesh;} level;')
        start=source.index('namespace SdvkDiagnostics {');end=source.index('\nstruct vertex_t',start)
        source=source[:start]+wrapper+source[end:]
        source=source.replace('SdvkDiagnostics::store','SdvkDiagnostics::WrittenVertices')
        # Execute the actual MakeVertices/CreateVertices/splitters on a worker,
        # then consume the actual production ApplyWrittenVertices on main.
        source=source.replace(' wall.MakeVertices(state,false,true);',"""
 std::exception_ptr error;
 std::thread worker([&]{try{wall.MakeVertices(state,false,true);}catch(...){error=std::current_exception();}});
 worker.join();if(error)std::rethrow_exception(error);
 SdvkDiagnostics::SpecialSurfaceMetadata emitted;
 emitted.VertexFirst=100;emitted.VertexCount=8;emitted.Tile=2;
 SdvkDiagnostics::ApplyWrittenVertices(emitted);
 check(emitted.WrittenUV.Vertices.size()==8,"worker-writer-main-snapshot-missing");
 check(CurrentWrittenUV<Vertex>(emitted.WrittenUV,mesh.tile,1024,100,8),"worker-writer-main-current-uv");
""",1)
        source=source.replace(' SdvkDiagnostics::WrittenVertices.Clear();\n check(!SdvkDiagnostics::WrittenVertices.Copy(100,8,2,snapshot),"cross-frame-evidence");',"""
 // Same lifetime boundary as production BeginFrame, after RenderBSP future.wait.
 SdvkDiagnostics::WrittenVertices.Clear();
 SdvkDiagnostics::SpecialSurfaceMetadata nextFrame;
 nextFrame.VertexFirst=100;nextFrame.VertexCount=8;nextFrame.Tile=2;
 SdvkDiagnostics::ApplyWrittenVertices(nextFrame);
 check(nextFrame.WrittenUV.Vertices.empty(),"worker-snapshot-crossed-frame");
 check(!SdvkDiagnostics::WrittenVertices.Copy(100,8,2,snapshot),"cross-frame-evidence");
""")
        with tempfile.TemporaryDirectory(prefix='sdvk161-worker-main-') as d:
            path=Path(d)/'worker.cpp';path.write_text(source)
            executable=compile_fixture(path,output_dir=d,includes=[ROOT])
            result=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            # Reintroduce the real TLS defect while preserving actual writing,
            # submission metadata, and receipt checks: main must see no copy.
            tls=source.replace('SdvkSurfaceObservation::WrittenVertexStore WrittenVertices;',
                               'thread_local SdvkSurfaceObservation::WrittenVertexStore WrittenVertices;')
            self.assertNotEqual(tls,source)
            path.write_text(tls)
            executable=compile_fixture(path,output_dir=d,includes=[ROOT],name='original-worker-tls')
            result=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,11,result.stdout+result.stderr)
            self.assertEqual(result.stderr.strip(),'worker-writer-main-snapshot-missing')

    def test_actual_writer_capture_and_precise_consumer_are_joined(self):
        vertices=(ROOT/'src/rendering/hwrenderer/scene/hw_walls_vertex.cpp').read_text()
        writer=block(vertices,'void HWWall::MakeVertices(')
        self.assertLess(writer.index('const auto written = ret.first'),writer.index('CreateVertices(ret.first, split)'))
        self.assertLess(writer.index('CreateVertices(ret.first, split)'),writer.index('CaptureWrittenVertices('))
        self.assertIn('int(vertcount), lightmaptile, written',writer)
        self.assertIn('observeWritten && SdvkDiagnostics::SpecialSurfaceFrameSelected()',writer)
        diagnostics=(ROOT/'src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp').read_text()
        capture=block(diagnostics,'void CaptureWrittenVertices(')
        self.assertIn('if (!SpecialSurfaceFrameSelected()',capture)
        self.assertLess(capture.index('GetLightmapTile(tile)'),capture.index('WrittenVertices.Capture('))
        self.assertIn('WrittenVertices.Clear();',block(diagnostics,'void BeginFrame('))
        self.assertNotIn('thread_local SdvkSurfaceObservation::WrittenVertexStore',diagnostics)
        contract=(ROOT/'src/rendering/hwrenderer/diagnostics/hw_specialsurfacecontract.h').read_text()
        store=block(contract,'class WrittenVertexStore')
        self.assertEqual(store.count('std::lock_guard<std::mutex> lock(Mutex);'),3)
        self.assertIn('mutable std::mutex Mutex;',store)
        bsp=(ROOT/'src/rendering/hwrenderer/scene/hw_bsp.cpp').read_text()
        worker=block(bsp,'void HWDrawInfo::RenderBSP(')
        self.assertLess(worker.index('jobQueue.AddJob(RenderJob::TerminateJob'),worker.index('future.wait();'))
        draw=block((ROOT/'src/rendering/hwrenderer/scene/hw_drawinfo.cpp').read_text(),'void HWDrawInfo::DrawScene(')
        self.assertLess(draw.index('CreateScene('),draw.index('RenderScene(state)'))
        precise=block((ROOT/'src/common/rendering/vulkan/textures/vk_sdvkdiagnostics.cpp').read_text(),'static void ImmediateSpecialSurface(')
        self.assertIn('CurrentWrittenUV<FFlatVertex>(source.WrittenUV, tile,',precise)
        self.assertIn('mesh->Lightmap.TextureSize, firstIndex, count)',precise)
        self.assertIn('tile.HasValidAtlasRegion(',precise)
        self.assertNotIn('UvVertexCount == 4',precise)
        walls=(ROOT/'src/rendering/hwrenderer/scene/hw_walls.cpp').read_text()
        draw=block(walls,'void HWWall::DrawWall(')
        self.assertIn('value.Type = LevelMeshInfo.Type;',draw)
        self.assertIn('value.ControlSector = LevelMeshInfo.ControlSector ? LevelMeshInfo.ControlSector->Index() : -1;',draw)
        # Semantic producer state must survive the immediate dispatcher too.
        # Previously these assignments existed only inside the builder else.
        texture=block(walls,'void HWWall::DoTexture(')
        self.assertNotIn('LevelMeshInfo.',block(texture,'if (di->di)'))
        self.assertGreater(texture.index('LevelMeshInfo.Type ='),texture.index('lightmaptile = -1;'))
        ff=block(walls,'void HWWall::BuildFFBlock(')
        self.assertIn('}\n\tLevelMeshInfo.Type = ST_MIDDLESIDE;\n\tLevelMeshInfo.ControlSector = rover->model;',ff)
        for forbidden in ('GetDescriptorEntry(', 'GetBindlessTextureIndex(', 'AllocTile('):self.assertNotIn(forbidden,precise)


if __name__=='__main__':unittest.main()
