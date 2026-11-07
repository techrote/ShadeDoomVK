"""Replay production HUD rectangle arithmetic on actual authored PNG offsets.

CPU-only source extraction. Texture-border expansion encloses this opaque content
rectangle by one texel; it does not move the content's center or lower baseline.
"""
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import unittest

from tools.pf_oracle.fixture_runner import compile_fixture
from tools.pf_oracle.tests.sdvk014_source import block
from tools.renderer_oracle import prepare

ROOT = Path(__file__).resolve().parents[3]


def png_layout(raw):
    width, height = struct.unpack_from(">II", raw, 16)
    at, offset = 8, None
    while at < len(raw):
        length = struct.unpack_from(">I", raw, at)[0]
        if raw[at + 4:at + 8] == b"grAb":
            offset = struct.unpack_from(">ii", raw, at + 8)
        at += length + 12
    if offset is None:
        raise AssertionError("Weapon PNG has no authored grAb offsets")
    return width, height, *offset


def production_rect_program():
    texture = block((ROOT / "src/common/textures/gametexture.cpp").read_text(), "void FGameTexture::SetSpriteRect()")
    start = texture.index("spi.mSpriteRect.left =")
    end = texture.index(";", texture.index("spi.mSpriteRect.height =", start)) + 1
    texture = texture[start:end]
    weapon = block((ROOT / "src/rendering/hwrenderer/scene/hw_weapon.cpp").read_text(), "bool HUDSprite::GetWeaponRect(")
    start = weapon.index("float vw =")
    end = weapon.index(";", weapon.index("y2 = y1 +", start)) + 1
    weapon = weapon[start:end]
    # UVs are assigned later in GetWeaponRect, outside this scalar-rectangle
    # replay. Omit only their unused declarations; retain every position line.
    weapon = weapon.replace(", u1, v1, u2, v2", "")
    header = (ROOT / "src/playsim/p_pspr.h").read_text()
    top = re.search(r"#define\s+WEAPONTOP\s+([0-9.]+)", header).group(1)
    return r'''
#include <cstdlib>
#include <iomanip>
#include <iostream>
struct FloatRect { float left=0,top=0,width=0,height=0; };
struct Position {
  FloatRect mSpriteRect; float spriteWidth=0,spriteHeight=0;
  FloatRect GetSpriteRect() const { return mSpriteRect; }
};
struct Scale { double X=1.0,Y=1.2; };
struct PSprite { Scale baseScale; int Flags=0; float GetYAdjust(bool) const { return 0; } };
constexpr int PSPF_MIRROR=1;
int main(int argc,char** argv) {
  if(argc!=7) return 2;
  Position spi;
  spi.spriteWidth=std::strtof(argv[1],nullptr);spi.spriteHeight=std::strtof(argv[2],nullptr);
  float leftOffset=std::strtof(argv[3],nullptr),topOffset=std::strtof(argv[4],nullptr);
  float fxScale=1,fyScale=1;
''' + texture + r'''
  int viewwidth=std::atoi(argv[5]),viewheight=std::atoi(argv[6]);
  int SCREENWIDTH=viewwidth,SCREENHEIGHT=viewheight,viewwindowx=0,viewwindowy=0,screenblocks=12;
  struct { double WidescreenRatio; } r_viewwindow{double(viewwidth)/viewheight};
  PSprite sprite;PSprite* psp=&sprite;
  float sx=0,sy=''' + top + r''';
  float tx,scale,scalex,ftextureadj,ftexturemid;
#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable:4244)
#endif
''' + weapon + r'''
#ifdef _MSC_VER
#pragma warning(pop)
#endif
  std::cout<<std::setprecision(9)<<x1<<' '<<y1<<' '<<x2<<' '<<y2<<'\n';
}
'''


class HudLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="sdvk011-hud-layout-")
        cls.addClassCleanup(cls.temporary.cleanup)
        directory = Path(cls.temporary.name)
        code = directory / "hud_layout.cpp"
        code.write_text(production_rect_program())
        cls.executable = compile_fixture(code, output_dir=directory)
        scene = next(s for s in prepare.load_catalog()["scenes"] if s["id"] == "viewmodel-legacy")
        _, cls.members, _ = prepare.scene_assets(scene)

    def rect(self, layout, viewport=(640, 480)):
        result = subprocess.run([str(self.executable), *map(str, (*layout, *viewport))],
                                capture_output=True, text=True, timeout=5, check=True)
        return tuple(map(float, result.stdout.split()))

    def test_actual_ready_and_fire_pngs_are_centered_visible_and_lower_hud_anchored(self):
        for frame in ("A", "B"):
            layout = png_layout(self.members[f"sprites/SDVU{frame}0.png"])
            self.assertEqual(layout, (96, 96, -112, -72))
            for viewport in ((640, 480), (1280, 720)):
                with self.subTest(frame=frame, viewport=viewport):
                    x1, y1, x2, y2 = self.rect(layout, viewport)
                    self.assertGreater(x1, 0)
                    self.assertLess(x2, viewport[0])
                    self.assertAlmostEqual((x1 + x2) / 2, viewport[0] / 2, delta=.001)
                    self.assertGreaterEqual(y1, viewport[1] / 2)
                    self.assertLess(y1, viewport[1])
                    self.assertAlmostEqual(y2, viewport[1] + 1, delta=.001)

    def test_prior_actor_style_offset_reproduces_half_clipped_hud_counterexample(self):
        x1, _, x2, _ = self.rect((96, 96, 48, -72))
        self.assertAlmostEqual(x1, -96, delta=.001)
        self.assertAlmostEqual(x2, 96, delta=.001)
        self.assertAlmostEqual((min(x2, 640) - max(x1, 0)) / (x2 - x1), .5, delta=.001)


if __name__ == "__main__":
    unittest.main()
