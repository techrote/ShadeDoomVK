"""Production semantic-copy/fence negatives; no renderer or Vulkan device."""
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import run_fixture
from tools.pf_oracle.tests.test_sdvk009_publication_contract import production_function


FIXTURE = r'''
#include "hw_collision_readback.h"
#include <cassert>
#include <cstring>
#include <limits>
#include <string>
using namespace CollisionReadback;

struct Node { int left = -1, right = -1, element_index = -1; };
template<typename F> void rejects(F function, const char* text) {
    bool rejected = false;
    try { function(); }
    catch (const std::runtime_error& error) {
        rejected = std::string(error.what()).find(text) != std::string::npos;
    }
    assert(rejected);
}

int main() {
    // Nonzero root; untouched exported0 and full backing tails are never read.
    // Occupied index hole has an intentionally invalid third index, which
    // remains in INDX bytes but does not authorize reading that vertex.
    const std::vector<Node> nodes = { {-1,-1,-1}, {-1,-1,3}, {-1,-1,6}, {1,2,-1} };
    const std::vector<uint32_t> indexes = {0,0,0xffffffffu, 4,8,9, 8,9,11};
    const Snapshot snapshot = {7,19,4,32,64,9,3};
    const std::array<Allocation,3> sources = {{{101,16+48*100}, {102,32*32}, {103,4*64}}};
    auto nodeAt = [&](uint32_t id) -> const Node& { assert(id > 0 && id < 4); return nodes[id]; };
    auto indexAt = [&](uint32_t id) { assert(id < indexes.size()); return indexes[id]; };
    const auto plan = Build(snapshot, sources, nodeAt, indexAt);
    assert((plan.ReachableNodes == std::vector<uint32_t>{1,2,3}));
    assert((plan.ReferencedVertices == std::vector<uint32_t>{4,8,9,11}));
    assert(plan.Bytes == 4 + 3*36 + 9*4 + 4*12);
    assert(plan.Regions.size() == 1 + 3*3 + 1 + 4);
    Validate(plan, sources);

    // Execute the actual planned copies on poisoned CPU byte storage. Only
    // semantic fields are initialized, exactly as the diagnostic contract
    // permits. No output may contain native padding/tail poison.
    std::array<std::vector<unsigned char>,3> storage;
    for (unsigned i=0; i<3; ++i) storage[i].resize(static_cast<size_t>(sources[i].Bytes), 0xdd);
    std::vector<unsigned char> expected;
    for (const auto& r : plan.Regions) {
        auto& bytes = storage[static_cast<unsigned>(r.Buffer)];
        const auto value = static_cast<unsigned char>(1 + r.Identity + static_cast<unsigned>(r.Semantic));
        std::fill(bytes.begin()+static_cast<size_t>(r.SrcOffset), bytes.begin()+static_cast<size_t>(r.SrcOffset+r.Bytes), value);
        expected.insert(expected.end(), static_cast<size_t>(r.Bytes), value);
    }
    std::vector<unsigned char> destination(static_cast<size_t>(plan.Bytes), 0xee);
    for (const auto& r : plan.Regions)
        std::memcpy(destination.data()+r.DstOffset, storage[static_cast<unsigned>(r.Buffer)].data()+r.SrcOffset, static_cast<size_t>(r.Bytes));
    assert(destination == expected);
    for (auto value : destination) assert(value != 0xdd && value != 0xee);

    auto changed = sources; changed[0].Id++;
    rejects([&]{ Validate(plan, changed); }, "allocation-generation");
    changed=sources; changed[1].Bytes--;
    rejects([&]{ Validate(plan, changed); }, "allocation-generation");
    changed=sources; changed[0].Id=0;
    rejects([&]{ Build(snapshot, changed, nodeAt, indexAt); }, "allocation-generation");
    auto bad = plan; bad.Regions[1].SrcOffset -= 16;
    rejects([&]{ Validate(bad, sources); }, "field-offset-or-size");
    bad=plan; bad.Regions[2].Bytes=16;
    rejects([&]{ Validate(bad, sources); }, "field-offset-or-size");
    bad=plan; bad.Regions[2].Semantic=Field::Vertex;
    rejects([&]{ Validate(bad, sources); }, "field-offset-or-size");
    bad=plan; bad.Regions[3].DstOffset+=4;
    rejects([&]{ Validate(bad, sources); }, "field-offset-or-size");
    bad=plan; bad.Regions.erase(bad.Regions.begin()+5);
    rejects([&]{ Validate(bad, sources); }, "field-offset-or-size");
    bad=plan; bad.Regions.push_back(bad.Regions.back());
    rejects([&]{ Validate(bad, sources); }, "extra-copy");
    bad=plan; bad.State.Event=0;
    rejects([&]{ Validate(bad, sources); }, "complete-snapshot");
    bad=plan; bad.ReferencedVertices.push_back(11);
    rejects([&]{ Validate(bad, sources); }, "vertex-identity-order");
    auto oversized = snapshot; oversized.VertexExtent=MaxElements+1;
    rejects([&]{ Build(oversized, sources, nodeAt, indexAt); }, "extents");
    oversized=snapshot; oversized.ExportedCount=MaxElements+1;
    rejects([&]{ Build(oversized, sources, nodeAt, indexAt); }, "extents");
    oversized=snapshot; oversized.OccupiedCount=65;
    rejects([&]{ Build(oversized, sources, nodeAt, indexAt); }, "extents");
    auto invalidNodes=nodes; invalidNodes[3].right=3;
    rejects([&]{ Build(snapshot,sources,[&](uint32_t id)->const Node&{return invalidNodes[id];},indexAt); }, "repeated-reachable");
    invalidNodes=nodes; invalidNodes[3].right=4;
    rejects([&]{ Build(snapshot,sources,[&](uint32_t id)->const Node&{return invalidNodes[id];},indexAt); }, "reachable-child");
    invalidNodes=nodes; invalidNodes[2].element_index=8;
    rejects([&]{ Build(snapshot,sources,[&](uint32_t id)->const Node&{return invalidNodes[id];},indexAt); }, "reachable-leaf");
    auto invalidIndexes=indexes; invalidIndexes[8]=32;
    rejects([&]{ Build(snapshot,sources,nodeAt,[&](uint32_t id){return invalidIndexes[id];}); }, "vertex-reference");
    changed=sources; changed[2].Bytes=32;
    rejects([&]{ Build(snapshot,changed,nodeAt,indexAt); }, "outside-source");
    bad=plan; bad.Bytes=MaxBytes+1;
    rejects([&]{ Validate(bad,sources); }, "budget");

    // Empty root must not read the initialized-but-unreachable sentinel node,
    // an occupied hole's vertex, or any array capacity tail.
    auto empty=snapshot; empty.Root=-1; empty.ExportedCount=1; empty.OccupiedCount=3;
    auto noNode=[](uint32_t)->const Node& { assert(false); throw std::runtime_error("node"); };
    const auto emptyPlan=Build(empty,sources,noNode,[&](uint32_t id){assert(id<3); return indexes[id];});
    assert(emptyPlan.ReachableNodes.empty() && emptyPlan.ReferencedVertices.empty());
    assert(emptyPlan.Regions.size()==2 && emptyPlan.Bytes==16);
    empty.OccupiedCount=0;
    const auto initial=Build(empty,sources,noNode,[](uint32_t)->uint32_t{assert(false);return 0;});
    assert(initial.Regions.size()==1 && initial.Bytes==4);

    Completion completion;
    rejects([&]{completion.RequireReadable();},"before-successful");
    rejects([&]{completion.Record(0,1);},"command-generation");
    completion.Record(501,3);
    rejects([&]{completion.Submit(501,4,{8,700,2});},"submit-identity");
    rejects([&]{completion.Submit(502,3,{8,700,2});},"submit-identity");
    rejects([&]{completion.Complete({8,700,2},true);},"fence-generation");
    completion.Submit(501,3,{8,700,2});
    rejects([&]{completion.RequireReadable();},"before-successful");
    rejects([&]{completion.Complete({8,700,2},false);},"fence-generation");
    rejects([&]{completion.Complete({16,700,2},true);},"fence-generation");
    rejects([&]{completion.Complete({8,701,2},true);},"fence-generation");
    rejects([&]{completion.Complete({8,700,3},true);},"fence-generation");
    completion.Complete({8,700,2},true);
    completion.RequireReadable();
    rejects([&]{completion.Complete({8,700,2},true);},"fence-generation");
}
'''


FINISH_PREFIX = r'''
#include "hw_collision_readback.h"
#include <cassert>
#include <cstdio>
#include <filesystem>
#include <memory>
#include <string>
using VkResult = int;
constexpr VkResult VK_SUCCESS = 0;
bool mapFail=false, invalidateFail=false, writeFail=false, closeFail=false;
bool witnessEnabled=true, failAtFence=false;
bool failAtSubmit=false;
unsigned maps=0, unmaps=0, invalidates=0;
std::string directory;
std::vector<std::string> events;
namespace CfxTrace {
bool WitnessEnabled() { return witnessEnabled; }
void WitnessFail(const char*) { events.push_back("failed"); }
void WitnessMark(const char* event, const char*) {
    if (!witnessEnabled) return;
    events.push_back(event);
    if (failAtFence && std::string(event)=="postuse-fence") witnessEnabled=false;
    if (failAtSubmit && std::string(event)=="submit-command") witnessEnabled=false;
}
std::string WitnessFilePath(const char* leaf) { return directory+"/"+leaf; }
}
[[noreturn]] void I_FatalError(const char*, const char*) { throw std::runtime_error("fatal"); }
struct VulkanBuffer {
    uint64_t diagnosticId=0; size_t size=0; int allocation=0;
    std::vector<unsigned char> contents;
    const void* Map(size_t offset, size_t bytes) {
        ++maps; assert(offset==0 && bytes==contents.size());
        return mapFail ? nullptr : contents.data();
    }
    void Unmap() { ++unmaps; }
};
int vmaInvalidateAllocation(int,int,size_t offset,size_t bytes) {
    ++invalidates; assert(maps==1 && unmaps==0 && offset==0 && bytes==4);
    return invalidateFail ? -1 : VK_SUCCESS;
}
size_t TestWrite(const void* data,size_t size,size_t count,std::FILE* file) {
    assert(invalidates==1 && !invalidateFail);
    return writeFail ? 0 : std::fwrite(data,size,count,file);
}
int TestClose(std::FILE* file) {
    const int result=std::fclose(file);
    return closeFail ? EOF : result;
}
struct Device { int allocator=0; };
struct FB { Device device; Device* GetDevice(){return &device;} };
struct Fence { uint64_t fence=91; };
class VkCommandBufferManager {
public:
    struct CollisionPublicationReadback {
        uint64_t Id=1;
        CollisionReadback::Plan Plan;
        std::array<VulkanBuffer*,3> Sources;
        std::unique_ptr<VulkanBuffer> Staging;
        CollisionReadback::Completion Completion;
    };
    void FinishCollisionReadback(unsigned int slot);
    FB fbStorage; FB* fb=&fbStorage;
    uint64_t mWitnessSubmissions[1]={11};
    std::unique_ptr<Fence> mSubmitFence[1];
    std::unique_ptr<CollisionPublicationReadback> mCollisionReadbacks[1];
    std::array<VulkanBuffer,3> sources;
    void Prepare() {
        using namespace CollisionReadback;
        mSubmitFence[0]=std::make_unique<Fence>();
        auto p=std::make_unique<CollisionPublicationReadback>();
        sources[0].diagnosticId=101; sources[0].size=64;
        sources[1].diagnosticId=102; sources[1].size=32;
        sources[2].diagnosticId=103; sources[2].size=4;
        struct Node { int left=-1,right=-1,element_index=-1; };
        p->Plan=Build(Snapshot{1,1,1,0,0,0,-1},
            std::array<Allocation,3>{{{101,64},{102,32},{103,4}}},
            [](uint32_t)->Node{assert(false);return {};},[](uint32_t)->uint32_t{assert(false);return 0;});
        for(unsigned i=0;i<3;++i) p->Sources[i]=&sources[i];
        p->Staging=std::make_unique<VulkanBuffer>();
        p->Staging->diagnosticId=104;p->Staging->size=4;p->Staging->contents.assign(4,0xff);
        p->Completion.Record(501,3);p->Completion.Submit(501,3,{11,91,0});
        mCollisionReadbacks[0]=std::move(p);
    }
};
'''

FINISH_SUFFIX = r'''
int main(int argc,char** argv) {
    assert(argc==2);
    for(int mode=0;mode<9;++mode) {
        directory=std::string(argv[1])+"/case"+std::to_string(mode);
        std::filesystem::create_directory(directory);
        events.clear();maps=unmaps=invalidates=0;
        mapFail=mode==1;invalidateFail=mode==2;writeFail=mode==3;closeFail=mode==4;
        witnessEnabled=mode!=7;failAtFence=mode==8;
        VkCommandBufferManager manager; manager.Prepare();
        if(mode==5) manager.mWitnessSubmissions[0]=12;
        if(mode==6 || mode==7) manager.sources[1].diagnosticId=900;
        bool failed=false;
        try { manager.FinishCollisionReadback(0); }
        catch(const std::runtime_error& error){failed=std::string(error.what())=="fatal";}
        assert(failed==(mode>=1 && mode<=6));
        if(mode==0) {
            assert((events==std::vector<std::string>{"postuse-fence","postuse-readback"}));
            assert(maps==1 && unmaps==1 && invalidates==1);
            assert(!manager.mCollisionReadbacks[0]);
            assert(std::filesystem::file_size(directory+"/readback-1.bin")==4);
        } else if(mode>=7) {
            // Failed logging never abandons an already submitted command or
            // staging allocation. The original fence still permits retirement,
            // without inspecting source identities or mapping/exporting bytes.
            assert(!manager.mCollisionReadbacks[0]);
            assert(maps==0 && unmaps==0 && invalidates==0);
            assert(events.size()==unsigned(mode==8));
        } else {
            assert(!events.empty() && events.back()=="failed");
            assert(std::find(events.begin(),events.end(),"postuse-readback")==events.end());
            assert(manager.mCollisionReadbacks[0]);
            assert(unmaps==unsigned(mode>=2 && mode<=4));
            if(mode>=5) assert(maps==0 && invalidates==0);
        }
    }
}
'''

SUBMIT_TYPES = r'''
#include <atomic>
#include <cassert>
#include <cstdint>
#include <limits>
#include <memory>
#include <vector>
using VkFence=uint64_t;
constexpr int VK_TRUE=1;
constexpr int VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT=1;
constexpr int VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT=2;
unsigned queueCalls=0, waitCalls=0, resetCalls=0;
struct VulkanCommandBuffer { void* buffer=(void*)uintptr_t(22); uint64_t diagnosticId=501,diagnosticRecording=3; };
struct VulkanSemaphore {};
struct FramebufferManager {
    int PresentImageIndex=-1;
    std::unique_ptr<VulkanSemaphore> SwapChainImageAvailableSemaphore;
    VulkanSemaphore* GetRenderFinishedSemaphore(){return nullptr;}
};
struct QueueSubmit {
    std::vector<VulkanCommandBuffer*> commands;
    void AddCommandBuffer(VulkanCommandBuffer* c){commands.push_back(c);}
    void AddWait(int,VulkanSemaphore*){}
    void AddSignal(VulkanSemaphore*){}
    template<typename D,typename F> void Execute(D*,void*,F*) {
        assert(commands.size()==2 && commands.back()->diagnosticId==501);
        ++queueCalls;
    }
};
namespace CfxTrace {
struct TestState {std::atomic<uint64_t> submission{10};};
TestState& State(){static TestState state;return state;}
bool Enabled(){return true;}
uint64_t NextSubmission(){return ++State().submission;}
void Mark(const char*,const char*,int=0){}
}
int vkWaitForFences(uint64_t,unsigned,const uint64_t*,int,uint64_t){++waitCalls;return 0;}
int vkResetFences(uint64_t,unsigned,const uint64_t*){++resetCalls;return 0;}
'''

SUBMIT_SUFFIX = r'''
int main(int argc,char** argv) {
    assert(argc==2);
    for(int mode=0;mode<4;++mode) {
        directory=std::string(argv[1])+"/submit"+std::to_string(mode);
        std::filesystem::create_directory(directory);
        events.clear();maps=unmaps=invalidates=queueCalls=waitCalls=resetCalls=0;
        mapFail=invalidateFail=writeFail=closeFail=failAtFence=false;
        witnessEnabled=mode!=1 && mode!=3;failAtSubmit=mode==2;
        CfxTrace::State().submission.store(10);
        VkCommandBufferManager manager;manager.Prepare();
        manager.mRecordedCollisionReadback=std::move(manager.mCollisionReadbacks[0]);
        manager.mRecordedCollisionReadback->Completion=CollisionReadback::Completion();
        manager.mRecordedCollisionReadback->Completion.Record(501,3);
        manager.mRecordedCollisionReadback->Commands=std::make_unique<VulkanCommandBuffer>();
        if(mode==3) {
            // An earlier failed recorder has an old submitted readback in the
            // slot being recycled. Reuse must drain it even with logging off.
            manager.mNextSubmit=8;
            manager.mWitnessSubmissions[0]=5;
            auto old=std::make_unique<VkCommandBufferManager::CollisionPublicationReadback>();
            old->Completion.Record(600,1);old->Completion.Submit(600,1,{5,91,0});
            old->Staging=std::make_unique<VulkanBuffer>();
            manager.mCollisionReadbacks[0]=std::move(old);
        }
        VulkanCommandBuffer ordinary;ordinary.diagnosticId=500;
        VulkanCommandBuffer* commands[]={&ordinary,manager.mRecordedCollisionReadback->Commands.get()};
        manager.FlushCommands(commands,2,false,false);
        assert(queueCalls==1 && !manager.mRecordedCollisionReadback);
        assert(manager.mCollisionReadbacks[0]);
        assert(manager.mCollisionReadbacks[0]->Completion.Fence.Submission==11);
        assert(waitCalls==unsigned(mode==3) && resetCalls==unsigned(mode==3));
        vkWaitForFences(0,1,&manager.mSubmitFence[0]->fence,VK_TRUE,0);
        manager.FinishCollisionReadback(0);
        assert(!manager.mCollisionReadbacks[0]);
        if(mode==0) assert(maps==1 && unmaps==1 && invalidates==1);
        else assert(maps==0 && unmaps==0 && invalidates==0);
    }
}
'''


class CollisionPostUseProductionTests(unittest.TestCase):
    def test_production_planner_semantics_and_completion_negatives(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "collision_readback.cpp"
            source.write_text(FIXTURE, encoding="utf-8")
            run_fixture(source, includes=[ROOT / "src/common/rendering/hwrenderer/data"])

    def test_actual_finish_rejects_map_invalidation_write_close_and_identity_failures(self):
        source = (ROOT / "src/common/rendering/vulkan/commands/vk_commandbuffer.cpp").read_text(encoding="utf-8")
        finish = production_function(source, "void VkCommandBufferManager::FinishCollisionReadback(unsigned int slot)")
        # Substitute only the external stdio boundary so the real production
        # control flow sees deterministic short writes and close errors.
        finish = finish.replace("std::fwrite(", "TestWrite(").replace("std::fclose(", "TestClose(")
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "collision_readback_finish.cpp"
            fixture.write_text(FINISH_PREFIX + finish + FINISH_SUFFIX, encoding="utf-8")
            run_fixture(fixture, includes=[ROOT / "src/common/rendering/hwrenderer/data"], args=[directory])

    def test_actual_submit_and_recycle_preserve_ownership_after_logger_failure(self):
        source = (ROOT / "src/common/rendering/vulkan/commands/vk_commandbuffer.cpp").read_text(encoding="utf-8")
        submit = production_function(source, "void VkCommandBufferManager::FlushCommands(VulkanCommandBuffer** commands, size_t count, bool finish, bool lastsubmit)")
        finish = production_function(source, "void VkCommandBufferManager::FinishCollisionReadback(unsigned int slot)")
        prefix = FINISH_PREFIX.replace("struct Device { int allocator=0; };", """
struct Device { int allocator=0; uint64_t device=0; void* GraphicsQueue=nullptr;
void CheckVulkanError(int result,const char*){assert(result==0);} };
""").replace("struct FB { Device device; Device* GetDevice(){return &device;} };", """
struct FB { Device device; FramebufferManager framebuffer;
Device* GetDevice(){return &device;}
FramebufferManager* GetFramebufferManager(){return &framebuffer;} };
""").replace("class VkCommandBufferManager {", "class VkCommandBufferManager {")
        prefix = prefix.replace("void FinishCollisionReadback(unsigned int slot);", """
void FinishCollisionReadback(unsigned int slot);
void FlushCommands(VulkanCommandBuffer** commands,size_t count,bool finish,bool lastsubmit);
enum { maxConcurrentSubmitCount=8 };
int mNextSubmit=0;
std::unique_ptr<VulkanSemaphore> mSubmitSemaphore[8];
std::unique_ptr<CollisionPublicationReadback> mRecordedCollisionReadback;
""").replace("std::unique_ptr<VulkanBuffer> Staging;", "std::unique_ptr<VulkanBuffer> Staging; std::unique_ptr<VulkanCommandBuffer> Commands;")
        prefix = prefix.replace("mWitnessSubmissions[1]", "mWitnessSubmissions[8]").replace("mSubmitFence[1]", "mSubmitFence[8]").replace("mCollisionReadbacks[1]", "mCollisionReadbacks[8]")
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "collision_readback_submit.cpp"
            fixture.write_text(SUBMIT_TYPES + prefix + submit + finish + SUBMIT_SUFFIX, encoding="utf-8")
            run_fixture(fixture, includes=[ROOT / "src/common/rendering/hwrenderer/data"], args=[directory])

    def test_real_submit_and_host_readback_order(self):
        source = (ROOT / "src/common/rendering/vulkan/commands/vk_commandbuffer.cpp").read_text(encoding="utf-8")
        record = production_function(source, "std::unique_ptr<VkCommandBufferManager::CollisionPublicationReadback> VkCommandBufferManager::RecordCollisionReadback()")
        finish = production_function(source, "void VkCommandBufferManager::FinishCollisionReadback(unsigned int slot)")
        flush = production_function(source, "void VkCommandBufferManager::FlushCommands(bool finish, bool lastsubmit, bool uploadOnly)")
        submit = production_function(source, "void VkCommandBufferManager::FlushCommands(VulkanCommandBuffer** commands, size_t count, bool finish, bool lastsubmit)")
        wait = production_function(source, "void VkCommandBufferManager::WaitForCommands(bool finish, bool uploadOnly)")
        closure = production_function(source, "void VkCommandBufferManager::FinishPublicationWitness()")
        self.assertLess(flush.index("mThreadCommands.clear()"), flush.index("RecordCollisionReadback()"))
        self.assertLess(flush.index("RecordCollisionReadback()"), flush.index("FlushCommands(mFlushCommands.data()"))
        self.assertIn("!uploadOnly && (mDrawCommands || !mThreadCommands.empty())", flush)
        self.assertLess(submit.index("submit.Execute("), submit.index('WitnessMark("submit-command"'))
        self.assertIn("commands[count - 1] == mRecordedCollisionReadback->Commands.get()", submit)
        self.assertLess(submit.index("} while (result != VK_SUCCESS)"), submit.index("FinishCollisionReadback("))
        self.assertLess(submit.index("FinishCollisionReadback("), submit.index("vkResetFences(fb->"))
        self.assertLess(wait.index('Require(result == VK_SUCCESS'), wait.index("FinishCollisionReadback("))
        self.assertLess(wait.index("FinishCollisionReadback("), wait.index("vkResetFences(fb->"))
        self.assertLess(wait.index("FinishCollisionReadback("), wait.index("DeleteFrameObjects("))
        self.assertIn("VK_ACCESS_TRANSFER_WRITE_BIT | VK_ACCESS_SHADER_READ_BIT", record)
        self.assertIn("VK_ACCESS_VERTEX_ATTRIBUTE_READ_BIT", record)
        self.assertIn("VK_ACCESS_INDEX_READ_BIT", record)
        self.assertLess(record.index("copyBuffer("), record.index("VK_ACCESS_HOST_READ_BIT"))
        self.assertIn("VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT", record)
        self.assertLess(finish.index("RequireReadable()"), finish.index("->Map("))
        self.assertLess(finish.index("->Map("), finish.index("vmaInvalidateAllocation("))
        self.assertLess(finish.index("Require(invalidated == VK_SUCCESS"), finish.index("hash ^= data[i]"))
        self.assertLess(finish.index('Require(written && closed'), finish.index('WitnessMark("postuse-readback"'))
        for function in (record, finish, closure):
            self.assertNotIn("vkWaitForFences(", function)
            self.assertNotIn("WaitForCommands(", function)
            self.assertNotIn("vkQueueWaitIdle(", function)
            self.assertNotIn("vkDeviceWaitIdle(", function)

    def test_snapshot_identity_is_committed_after_file_close(self):
        source = (ROOT / "src/common/rendering/hwrenderer/data/hw_collision.cpp").read_text(encoding="utf-8")
        writer = production_function(source, "void CPUAccelStruct::DumpSnapshot(unsigned int phase)")
        self.assertLess(writer.index("file.Finish()"), writer.index("SnapshotExportedCount = exportedCount"))
        self.assertLess(writer.index("file.Finish()"), writer.index("SnapshotEventId = event"))


if __name__ == "__main__":
    unittest.main()
