"""Actual selected line-portal endpoint groups, separate from legacy view sector."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import ROOT, block

ADAPTER = r'''
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
#include "selected_contract.h"
#include "src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnosticcore.h"
template<class T> struct Array:std::vector<T>{using std::vector<T>::vector;size_t Size()const{return this->size();}};
struct Sector{int id,PortalGroup;int Index()const{return id;}};
struct Line{int id;Sector* frontsector;int Index()const{return id;}};
struct Portal{Line* mOrigin;Line* mDestination;};
struct Span{Array<Portal*> lines;};
struct HWPortal{virtual ~HWPortal()=default;};
struct HWLineToLinePortal:HWPortal{Span* glport;};
struct LevelType{Array<int> lines=Array<int>(30);Array<int> sectors=Array<int>(7);};
struct HWDrawInfo{HWPortal* mCurrentPortal;LevelType* Level;};
using namespace SdvkObservation;
@SERIALIZER@
void check(bool b,const char* message){if(!b)throw std::runtime_error(message);}
int main() try {
 using namespace SdvkPortalObservation;
 Sector roomA{0,1},roomB{1,2};Line origin{10,&roomB},destination{3,&roomA};
 Portal reverse{&origin,&destination};Span span;span.lines.push_back(&reverse);
 SelectedLinePortal result;
 check(ResolveSelectedLinePortal(&span,30,7,result),"valid-selected-portal-unavailable");
 check(result.SourceGroup==2&&result.DestinationGroup==1,"selected-portal-source-destination");
 check(result.OriginLine==10&&result.DestinationLine==3&&result.SourceSector==1&&result.DestinationSector==0,"selected-endpoint-identity");
 HWLineToLinePortal current;current.glport=&span;LevelType level;HWDrawInfo di{&current,&level};
 const auto json=SelectedLinePortalContext(&di);
 check(json.find("\"source_group\":2")!=std::string::npos&&json.find("\"destination_group\":1")!=std::string::npos,"serialized-selected-groups");
 check(json.find("\"origin_line\":10")!=std::string::npos&&json.find("\"destination_line\":3")!=std::string::npos,"serialized-selected-lines");
 // Forward direction must not be inferred from the reverse camera/group.
 std::swap(reverse.mOrigin,reverse.mDestination);
 check(ResolveSelectedLinePortal(&span,30,7,result)&&result.SourceGroup==1&&result.DestinationGroup==2,"forward-selected-groups");
 std::swap(reverse.mOrigin,reverse.mDestination);
 // Setup translates using span[0], not another valid span entry.
 Portal forward{&destination,&origin};span.lines.push_back(&forward);
 check(ResolveSelectedLinePortal(&span,30,7,result)&&result.OriginLine==10&&result.DestinationGroup==1,"wrong-selected-span-entry");
 span.lines.pop_back();
 auto invalid=[&]{check(!ResolveSelectedLinePortal(&span,30,7,result),"invalid-selected-portal-admitted");check(result.OriginLine==-1&&result.DestinationGroup==-1,"stale-selection-output");};
 origin.id=-1;invalid();origin.id=30;invalid();origin.id=10;
 destination.id=30;invalid();destination.id=3;
 roomA.id=7;invalid();roomA.id=0;
 roomB.PortalGroup=-1;invalid();roomB.PortalGroup=2;
 reverse.mDestination=nullptr;invalid();reverse.mDestination=&destination;
 origin.frontsector=nullptr;invalid();origin.frontsector=&roomB;
 span.lines[0]=nullptr;invalid();span.lines[0]=&reverse;
 span.lines.clear();invalid();
 span.lines.resize(65,&reverse);invalid();span.lines.resize(1);
 check(!ResolveSelectedLinePortal<Span>(nullptr,30,7,result),"null-span-admitted");
 current.glport=nullptr;
 check(SelectedLinePortalContext(&di).find("\"available\":false")!=std::string::npos,"invalid-context-selection-available");
 HWPortal ordinary;di.mCurrentPortal=&ordinary;
 check(SelectedLinePortalContext(&di).find("\"available\":false")!=std::string::npos,"nonline-context-invents-selection");
 std::cout<<"PASS selected-endpoint-identities\n";return 0;
} catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 11;}
'''


class PortalSelectionTests(unittest.TestCase):
    def test_production_selection_and_serializer_with_wrong_group_counterfactuals(self):
        diagnostics=(ROOT/'src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp').read_text()
        helper=(ROOT/'src/rendering/hwrenderer/diagnostics/hw_lineportalobservation.h').read_text()
        source=ADAPTER.replace('@SERIALIZER@',block(diagnostics,'std::string SelectedLinePortalContext('))
        with tempfile.TemporaryDirectory(prefix='sdvk161-selected-portal-') as d:
            path=Path(d)/'selection.cpp';path.write_text(source)
            header=Path(d)/'selected_contract.h'
            for name,contract,error in (
                ('current',helper,None),
                ('wrong-destination',helper.replace('selection.DestinationGroup = destination->frontsector->PortalGroup;',
                                                    'selection.DestinationGroup = origin->frontsector->PortalGroup;'),
                 'selected-portal-source-destination'),
                ('wrong-source',helper.replace('selection.SourceGroup = origin->frontsector->PortalGroup;',
                                               'selection.SourceGroup = destination->frontsector->PortalGroup;'),
                 'selected-portal-source-destination')):
                with self.subTest(name=name):
                    header.write_text(contract)
                    executable=compile_fixture(path,output_dir=d,includes=[ROOT,Path(d)],name=name)
                    result=subprocess.run([str(executable)],capture_output=True,text=True,timeout=10)
                    self.assertEqual(result.returncode,0 if error is None else 11,result.stdout+result.stderr)
                    self.assertEqual(result.stdout.strip() if error is None else result.stderr.strip(),
                                     'PASS selected-endpoint-identities' if error is None else error)

    def test_additive_context_preserves_legacy_group_and_uses_actual_setup_selection(self):
        source=(ROOT/'src/rendering/hwrenderer/diagnostics/hw_sdvkdiagnostics.cpp').read_text()
        context=block(source,'std::string Context(const HWDrawInfo* di)')
        self.assertIn('const int group = vp.sector ? vp.sector->PortalGroup : -1;',context)
        self.assertIn('Int("portal_group", group)',context)
        self.assertIn('std::to_string(group)',context)
        # Context is in the anonymous namespace, outside SdvkDiagnostics.
        self.assertIn('if (SdvkDiagnostics::SpecialSurfaceEnabled())\n        result.Raw("line_portal_selection", SelectedLinePortalContext(di));',context)
        selected=block(source,'std::string SelectedLinePortalContext(')
        self.assertIn('dynamic_cast<const HWLineToLinePortal*>(di->mCurrentPortal)',selected)
        self.assertIn('ResolveSelectedLinePortal(portal->glport,',selected)
        self.assertIn('di->Level->lines.Size(), di->Level->sectors.Size(), selection)',selected)
        for forbidden in ('Viewpoint','PointInSector','PointInSubsector','SetViewArea','SetupView'):
            self.assertNotIn(forbidden,selected)
        setup=block((ROOT/'src/rendering/hwrenderer/scene/hw_portal.cpp').read_text(),'bool HWLineToLinePortal::Setup(')
        self.assertIn('line_t *origin = glport->lines[0]->mOrigin;',setup)
        self.assertIn('P_TranslatePortalXY(origin, vp.Pos.X, vp.Pos.Y);',setup)
        self.assertIn('di->SetClipLine(glport->lines[0]->mDestination);',setup)
        # Its inherited sector pointer remains deliberately untouched. The new
        # observer must not repair renderer behavior to make metadata agree.
        self.assertNotIn('SetViewArea',setup)
        self.assertNotIn('vp.sector =',setup)


if __name__=='__main__':unittest.main()
