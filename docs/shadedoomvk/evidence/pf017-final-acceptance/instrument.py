"""Matched, archived diagnostics only. Production binaries are already frozen."""
import pathlib,sys,shutil,subprocess,json,hashlib
root=pathlib.Path(__file__).parent
tree=pathlib.Path(sys.argv[1]); name=sys.argv[2]
original=root/(name+'-originals'); original.mkdir(exist_ok=False)
def edit(rel,transform):
 p=tree/rel; data=p.read_bytes(); backup=original/rel;backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(data)
 text=data.decode().replace('\r\n','\n'); result=transform(text);assert result!=text,rel;p.write_bytes(result.encode())
candidate=name=='candidate'
header='src/common/rendering/hwrenderer/data/hw_pf17acceptance.h'
shutil.copy2(root/'hw_pf17acceptance.h',tree/header)
edit('src/common/rendering/hwrenderer/data/hw_dynlightdata.h',lambda s:s.replace('#include "tarray.h"','#include "tarray.h"\n#include "hw_pf17acceptance.h"').replace('TArray<FDynLightInfo> arrays[3];','TArray<FDynLightInfo> arrays[3];\n\tstd::vector<PF17Acceptance::Identity> identities[3];').replace('arrays[i].Clear();','arrays[i].Clear();\n\t\t\tidentities[i].clear();'))
edit('src/playsim/a_dynlight.cpp',lambda s:s.replace('#include "a_dynlight.h"','#include "a_dynlight.h"\n#include "hw_pf17acceptance.h"').replace('memset(ret, 0, sizeof(*ret));','memset(ret, 0, sizeof(*ret));\n\tPF17Acceptance::Born(ret);'))
def packing(s):
 start=s.index('void AddLightToList('); end=s.index('void AddSunLightToList(',start); body=s[start:end]
 if candidate:
  first='\t\tdld.arrays[lightClass].Push(info);'
  oracle='\t\tFDynLightInfo checked = {};\n\t\tint checkedClass = PackLightInfo(checked, group, light, forceAttenuate, doTrace);\n\t\tPF17Acceptance::Pack(true, false, false, checkedClass != lightClass || memcmp(&checked, &info, 80) != 0);\n'
  body=body.replace(first,oracle+first,1)
  common='\tdld.arrays[lightClass].Push(info);'
  # Insert identities at both the hit and accepted-pack append sites.
  identity='dld.identities[lightClass].push_back(PF17Acceptance::Source(light, light->target ? light->target->tid : 0, light->Sector ? light->Sector->PortalGroup : -1, group, (forceAttenuate ? 1 : 0) | (doTrace ? 2 : 0)));'
  body=body.replace('dld.arrays[lightClass].Push(info);',identity+'\n\tdld.arrays[lightClass].Push(info);')
  at=body.rindex(identity);body=body[:at]+'PF17Acceptance::Pack(false, !qualified, contextEpoch == 0, false);\n\t'+body[at:]
 else:
  assert 'dld.arrays[i].Push(info);' in body
  body=body.replace('dld.arrays[i].Push(info);','PF17Acceptance::Pack(false, false, false, false);\n\tdld.identities[i].push_back(PF17Acceptance::Source(light, light->target ? light->target->tid : 0, light->Sector ? light->Sector->PortalGroup : -1, group, (forceAttenuate ? 1 : 0) | (doTrace ? 2 : 0)));\n\tdld.arrays[i].Push(info);')
 s=s[:start]+body+s[end:]
 sun=s.index('void AddSunLightToList(')
 s=s[:sun]+s[sun:].replace('dld.arrays[LIGHTARRAY_NORMAL].Push(info);','dld.identities[LIGHTARRAY_NORMAL].push_back({});\n\tdld.arrays[LIGHTARRAY_NORMAL].Push(info);').replace('dld.arrays[0].Push(info);','dld.identities[0].push_back({});\n\tdld.arrays[0].Push(info);')
 return s
edit('src/rendering/hwrenderer/hw_dynlightdata.cpp',packing)
def upload(s):
 s=s.replace('void VkRenderState::BeginFrame()\n{','void VkRenderState::BeginFrame()\n{\n\tPF17Acceptance::Frame(mRSBuffers->Lightbuffer, level.maptime);')
 start=s.index('int VkRenderState::UploadLights(');end=s.index('int VkRenderState::UploadBones',start)
 body=s[start:end]
 if candidate:
  body=body.replace('memcpy(indexptr, parmcnt.data(), sizeof(int) * 4);','PF17Acceptance::Write(16);\n\t\t\tmemcpy(indexptr, parmcnt.data(), sizeof(int) * 4);')
  body=body.replace('if (!canReuse)','PF17Acceptance::Class(canReuse, revisions, count);\n\t\t\tif (!canReuse)').replace('memcpy(\n\t\t\t\t\tdataptr + classOffset,','PF17Acceptance::Write((size_t)count * 80);\n\t\t\t\tmemcpy(\n\t\t\t\t\tdataptr + classOffset,')
 else:
  body=body.replace('memcpy(indexptr, parmcnt, sizeof(int) * 4);','PF17Acceptance::Write(16);\n\t\tPF17Acceptance::Write(size0 * 80);\n\t\tPF17Acceptance::Write(size1 * 80);\n\t\tPF17Acceptance::Write(size2 * 80);\n\t\tmemcpy(indexptr, parmcnt, sizeof(int) * 4);')
 body=body.replace('return indexindex;','PF17Acceptance::Consumer(data, mRSBuffers->Lightbuffer, indexindex, dataindex);\n\t\treturn indexindex;')
 return s[:start]+body+s[end:]
edit('src/common/rendering/vulkan/vk_renderstate.cpp',upload)
edit('src/d_main.cpp',lambda s:s.replace('}, true);','}, false);',1))
(root/(name+'-diagnostic.patch')).write_bytes(subprocess.check_output(['git','-C',str(tree),'diff','--','src']))
(root/(name+'-diagnostic-originals.json')).write_text(json.dumps({str(p.relative_to(original)):hashlib.sha256(p.read_bytes()).hexdigest() for p in original.rglob('*') if p.is_file()},indent=2))
print(name+' matched diagnostics applied; originals/patch/header preserved')
