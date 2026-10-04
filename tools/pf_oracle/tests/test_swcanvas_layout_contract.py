"""#112 source-extracted software-image/descriptor layout regression.

Real AllocateBuffer, MapBuffer, CreateTexture(nullptr), GetImage and descriptor
writer definitions execute against bounded recording Vulkan services. The real
contiguous material image-selection/layer-publication block is also extracted.
Layer lookup and image allocation/upload are stubs, explicitly outside this
layout proof. Unused generic CreateTexture parameter declarations receive
[[maybe_unused]] after source hashing, without changing its executable body.
No Vulkan driver, software scene, GPU output or fence is executed.
The exact accepted-master definitions remain an expected negative witness.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.test_indexed_material_contract import definition

BASELINE = "4df7dea1338f063c6417e024f967bfa4aa23edd4"
BACKEND = "src/common/rendering/vulkan/textures/vk_hwtexture.cpp"
WRITER = "src/common/rendering/vulkan/descriptorsets/vk_descriptorset.cpp"
WRITER_HEADER = "src/common/rendering/vulkan/descriptorsets/vk_descriptorset.h"
FROZEN_ORIGINAL = {
    'allocate': r'''void VkHardwareTexture::AllocateBuffer(int w, int h, int texelsize)
{
	if (mImage.Image && (mImage.Image->width != w || mImage.Image->height != h || mTexelsize != texelsize))
	{
		Reset();
	}

	if (!mImage.Image)
	{
		VkFormat format = texelsize == 4 ? VK_FORMAT_B8G8R8A8_UNORM : VK_FORMAT_R8_UNORM;

		VkDeviceSize allocatedBytes = 0;
		mImage.Image = ImageBuilder()
			.Format(format)
			.Size(w, h)
			.LinearTiling()
			.Usage(VK_IMAGE_USAGE_SAMPLED_BIT, VMA_MEMORY_USAGE_UNKNOWN, VMA_ALLOCATION_CREATE_DEDICATED_MEMORY_BIT | VMA_ALLOCATION_CREATE_MAPPED_BIT)
			.MemoryType(
				VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT,
				VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT | VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)
			.DebugName("VkHardwareTexture.mImage")
			.Create(fb->GetDevice(), &allocatedBytes);

		mTexelsize = texelsize;

		mImage.View = ImageViewBuilder()
			.Image(mImage.Image.get(), format)
			.DebugName("VkHardwareTexture.mImageView")
			.Create(fb->GetDevice());

		VkImageTransition()
			.AddImage(&mImage, VK_IMAGE_LAYOUT_GENERAL, true)
			.Execute(fb->GetCommands()->GetTransferCommands());

		bufferpitch = int(allocatedBytes / h / texelsize);
	}
}''',
    'map': r'''uint8_t *VkHardwareTexture::MapBuffer()
{
	if (!mappedSWFB)
		mappedSWFB = (uint8_t*)mImage.Image->Map(0, mImage.Image->width * mImage.Image->height * mTexelsize);
	return mappedSWFB;
}''',
    'create': r'''unsigned int VkHardwareTexture::CreateTexture(unsigned char * buffer, int w, int h, int texunit, bool mipmap, const char *name)
{
	// CreateTexture is used by the software renderer to create a screen output but without any screen data.
	if (buffer)
		CreateTexture(&mImage, w, h, mTexelsize, mTexelsize == 4 ? VK_FORMAT_B8G8R8A8_UNORM : VK_FORMAT_R8_UNORM, buffer, mipmap);
	return 0;
}''',
    'image': r'''VkTextureImage *VkHardwareTexture::GetImage(FTexture *tex, int translation, int flags)
{
	// Palette-index and RedIsAlpha data are both R8 uploads, but they have
	// different producer semantics (palette index vs luminance-as-alpha). They
	// therefore must never alias the same cached VkTextureImage.
	if (flags & CTF_IndexedRedIsAlpha)
	{
		if (!mAlphaImage.Image)
			CreateImage(&mAlphaImage, tex, translation, flags);
		return &mAlphaImage;
	}
	else if (flags & CTF_Indexed)
	{
		if (!mPaletteImage.Image)
			CreateImage(&mPaletteImage, tex, translation, flags);
		return &mPaletteImage;
	}
	else
	{
		if (!mImage.Image)
			CreateImage(&mImage, tex, translation, flags);
		return &mImage;
	}
}''',
    'writer': r'''void VkDescriptorSetManager::SetBindlessTexture(int index, VulkanImageView* imageview, VulkanSampler* sampler)
{
	if (index < 0 || index >= Bindless.Plan.Effective)
		I_FatalError("Bindless descriptor write index %d is outside effective capacity %d.", index, Bindless.Plan.Effective);

	if (CfxTrace::ResourcesEnabled())
	{
		// Only allocation starts have PF tokens; interior/fixed slots are explicitly
		// raw slot writes and are correlated with the preceding allocation span.
		const auto id = Bindless.Allocator.CurrentIdentity(index);
		char line[260];
		std::snprintf(line, sizeof(line), "set_id=%llu index=%d generation=%u epoch=%u span=%u view=0x%llx sampler=0x%llx",
			(unsigned long long)Bindless.Set->diagnosticId, index, id.Generation, id.Epoch, id.Span,
			(unsigned long long)(uint64_t)imageview->view, (unsigned long long)(uint64_t)sampler->sampler);
		CfxTrace::ResourceMark("bindless-write-queued", line);
	}
	Bindless.Writer.AddCombinedImageSampler(Bindless.Set.get(), 0, index, imageview, sampler, VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL);
}''',
    'material': r'''auto systeximage = systex->GetImage(layer->layerTexture, state.mTranslation, layer->scaleFlags | paletteFlags);
	descriptors->SetBindlessTexture(texIndex++, systeximage->View.get(), fb->GetSamplerManager()->Get(GetLayerFilter(0), clampmode));

	if (!(layer->scaleFlags & CTF_Indexed))
	{
		for (int i = 1; i < numLayersMat; i++)
		{
			auto syslayer = static_cast<VkHardwareTexture*>(GetLayer(i, 0, &layer));
			auto syslayerimage = syslayer->GetImage(layer->layerTexture, 0, layer->scaleFlags | paletteFlags);
			descriptors->SetBindlessTexture(texIndex++, syslayerimage->View.get(), fb->GetSamplerManager()->Get(GetLayerFilter(i), clampmode));
		}

		if(globalshader)
		{
			size_t i = 0;
			for (auto& texture : globalshader.CustomShaderTextures)
			{
				if (texture != nullptr)
				{
					VkHardwareTexture *tex = static_cast<VkHardwareTexture*>(texture.get()->GetHardwareTexture(0, 0));
					VkTextureImage *img = tex->GetImage(texture.get(), 0, paletteFlags);
					descriptors->SetBindlessTexture(texIndex++, img->View.get(), fb->GetSamplerManager()->Get(globalshader.CustomShaderTextureSampling[i], clampmode));
				}
				i++;
			}
		}
	}
	else
	{
		for (int i = 1; i < 3; i++)
		{
			auto syslayer = static_cast<VkHardwareTexture*>(GetLayer(i, translation, &layer));
			auto syslayerimage = syslayer->GetImage(layer->layerTexture, 0, layer->scaleFlags | paletteFlags);
			descriptors->SetBindlessTexture(texIndex++, syslayerimage->View.get(), fb->GetSamplerManager()->Get(GetLayerFilter(i), clampmode));
		}
	}
''',
}
FROZEN_HASHES = {'allocate': '429bb229660522a10151f575f282ac100f436bdd7884509d514e5ee81df08275', 'map': '2db66696140a64c618beffec9ebf24a7a442d55d660dc16258e2f0ffa93538ae', 'create': '63c8ae219bdc9d88a0f5e787cc7e8a37ad8dda0498a7bd5a3a8a7da13f688bd7', 'image': '97c0870c10e6061eadc9e17057238e127b37ffc420f2ff2ce7dbe25bd60563ec', 'writer': '236030a447e8fc11f2ac3641f5ff5bd6cec42b20891e88ab9d176248f9635185', 'material': '534c34dae58f14052873addfcd948c0848746a38fd749d64a45aaf8b7c28843c'}


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def extract_parts(backend: str, writer: str) -> dict[str, str]:
    material = definition(backend, "VkMaterial::DescriptorEntry& VkMaterial::GetDescriptorEntry(")
    start = material.index("auto systeximage =")
    end = material.index("\n\tif (texIndex !=", start)
    return {
        "allocate": definition(backend, "void VkHardwareTexture::AllocateBuffer("),
        "map": definition(backend, "uint8_t *VkHardwareTexture::MapBuffer("),
        "create": definition(backend, "unsigned int VkHardwareTexture::CreateTexture("),
        "image": definition(backend, "VkTextureImage *VkHardwareTexture::GetImage("),
        "writer": definition(writer, "void VkDescriptorSetManager::SetBindlessTexture("),
        "material": material[start:end],
    }


def generated_header(*, original: bool) -> str:
    parts = FROZEN_ORIGINAL if original else extract_parts(source(BACKEND), source(WRITER))
    if original:
        declaration = "void SetBindlessTexture(int index, VulkanImageView* imageview, VulkanSampler* sampler);"
    else:
        match = re.search(r"void\s+SetBindlessTexture\s*\([^;]+\);", source(WRITER_HEADER))
        if not match:
            raise AssertionError("Production SetBindlessTexture declaration missing")
        declaration = match.group(0)
    explicit_layout = "VkImageLayout" in declaration
    output = [
        "// Production bodies follow unchanged; Vulkan services are CPU recordings.",
        "#ifndef PF_LAYOUT_DECLARATIONS\n#define PF_LAYOUT_DECLARATIONS",
        "#define PF_SET_BINDLESS_DECL " + " ".join(declaration.split()),
        "#define PF_HAS_EXPLICIT_LAYOUT " + str(int(explicit_layout)),
        "#define PF_ORIGINAL " + str(int(original)),
        "#endif",
        "#ifdef PF_LAYOUT_DEFINITIONS",
        *[instrumented_body(name, parts[name]) for name in ("allocate", "map", "create", "image", "writer")],
        "int VkMaterial::PublishOrdinary() {\n"
        "auto descriptors = fb->GetDescriptorSetManager();\n"
        "MaterialLayerInfo* layer = nullptr;\n"
        "auto systex = static_cast<VkHardwareTexture*>(GetLayer(0, 0, &layer));\n"
        "[[maybe_unused]] const bool indexedMaterial = false;\n"
        "const int paletteFlags = 0;\n"
        "[[maybe_unused]] const int translation = 0;\n"
        "FMaterialState state;\n"
        "const GlobalShaderDesc globalshader;\n"
        "const int numLayersMat = NumLayers();\n"
        "const int bindlessIndex = 259, clampmode = 3;\n"
        "int texIndex = bindlessIndex;\n" + parts["material"] +
        "\nreturn texIndex - bindlessIndex;\n}",
        "#endif",
    ]
    return "\n\n".join(output) + "\n"


def instrumented_body(name: str, body: str) -> str:
    if name == "create":
        return body.replace("int texunit,", "[[maybe_unused]] int texunit,", 1).replace(
            "const char *name)", "[[maybe_unused]] const char *name)", 1)
    return body


class SWCanvasLayoutContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="pf-swcanvas-layout-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.executables = {}
        for original in (True, False):
            directory = Path(cls.temp.name) / ("original" if original else "current")
            directory.mkdir()
            (directory / "production_swcanvas_layout.h").write_text(
                generated_header(original=original), encoding="utf-8", newline="\n")
            cls.executables[original] = compile_fixture(
                "tools/pf_oracle/tests/swcanvas_layout_fixture.cpp", output_dir=directory,
                includes=(directory,), root=ROOT)

    def fixture(self, mode: str, *, original: bool = False):
        result = subprocess.run([str(self.executables[original]), mode], cwd=ROOT,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(mode + " passed", result.stdout)
        return result

    def test_original_mapped_r8_declares_read_while_actual_general(self):
        self.assertIn("actual=GENERAL declared=READ", self.fixture("mapped-r8", original=True).stdout)

    def test_original_mapped_bgra_declares_read_while_actual_general(self):
        self.assertIn("actual=GENERAL declared=READ", self.fixture("mapped-bgra", original=True).stdout)

    def test_current_mapped_r8_preserves_general_and_existing_palette(self):
        self.fixture("mapped-r8")

    def test_current_mapped_bgra_preserves_general_and_existing_palette(self):
        self.fixture("mapped-bgra")

    def test_repeated_existing_mapped_images_do_not_upload_or_transition(self):
        self.fixture("repeated")

    def test_extent_and_format_reallocation_preserve_layout_authority(self):
        self.fixture("resize")

    def test_ordinary_uploaded_controls_and_default_writer_remain_read(self):
        self.fixture("ordinary")

    def test_illegal_layouts_and_out_of_capacity_writes_are_rejected(self):
        self.fixture("invalid")


class SWCanvasSourceContract(unittest.TestCase):
    def test_original_bodies_are_exact_pinned_accepted_master_extractions(self):
        self.assertEqual(set(FROZEN_ORIGINAL), {"allocate", "map", "create", "image", "writer", "material"})
        for name, body in FROZEN_ORIGINAL.items():
            self.assertEqual(hashlib.sha256(body.encode("utf-8")).hexdigest(), FROZEN_HASHES[name])
        self.assertIn("VK_IMAGE_LAYOUT_GENERAL", FROZEN_ORIGINAL["allocate"])
        self.assertIn("VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL", FROZEN_ORIGINAL["writer"])
        self.assertNotIn("VK_IMAGE_USAGE_TRANSFER_SRC_BIT", FROZEN_ORIGINAL["allocate"])

    def test_actual_software_producer_keeps_its_separate_palette_route(self):
        scene = definition(source("src/rendering/swrenderer/r_swscene.cpp"), "sector_t *SWSceneDrawer::RenderView(")
        for statement in (
            "FBTextureIndex = (FBTextureIndex + 1) % 2;",
            "GetSystemTexture()->AllocateBuffer(screen->GetWidth(), screen->GetHeight(), V_IsTrueColor() ? 4 : 1);",
            "mat->AddTextureLayer(PaletteTexture, false, MaterialLayerSampling::Default);",
            "SWRenderer->RenderView(player, Canvas.get(), buf, systemTexture->GetBufferPitch());",
            'systemTexture->CreateTexture(nullptr, screen->GetWidth(), screen->GetHeight(), 0, false, "swbuffer");',
        ):
            self.assertIn(statement, scene)

    def test_layout_proof_retains_untouched_current_producer_bodies(self):
        parts = extract_parts(source(BACKEND), source(WRITER))
        header = generated_header(original=False)
        for name in ("allocate", "map", "create", "image", "writer", "material"):
            self.assertIn(instrumented_body(name, parts[name]), header)
        self.assertNotIn("VK_IMAGE_USAGE_TRANSFER_SRC_BIT", parts["allocate"])


if __name__ == "__main__":
    unittest.main()
