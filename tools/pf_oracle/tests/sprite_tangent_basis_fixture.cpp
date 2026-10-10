// SDVK-007/v1 adversarial signed-UV final-quad tangent directions.
// This fixture uses the exact production header without engine dependencies.
#include "hw_sprite_tangent.h"
#include <cassert>
#include <cmath>
#include <limits>

namespace {
using V = HWSpriteTangentVector;
constexpr float pi = 3.14159265358979323846f;
float length2(V a) { return a.X*a.X + a.Y*a.Y + a.Z*a.Z; }
float dot(V a,V b){return a.X*b.X+a.Y*b.Y+a.Z*b.Z;}
V cross(V a,V b){return {a.Y*b.Z-a.Z*b.Y,a.Z*b.X-a.X*b.Z,a.X*b.Y-a.Y*b.X};}
V scale(V a,float s){return {s*a.X,s*a.Y,s*a.Z};}
V add(V a,V b){return {a.X+b.X,a.Y+b.Y,a.Z+b.Z};}
bool near(float a,float b,float tolerance=0.0003f){return std::abs(a-b)<tolerance;}
void good(const HWSpriteTangentBasis& b, float hand)
{
    assert(b.valid && near(b.handedness,hand));
    assert(near(length2(b.tangent),1.f) && near(length2(b.normal),1.f));
    assert(near(dot(b.tangent,b.normal),0.f));
    V bitangent=scale(cross(b.normal,b.tangent),b.handedness);
    assert(near(length2(bitangent),1.f));
}
// Asymmetric normal components mean an accidentally inverted local X and Y
// cannot produce identical mapped normals (unlike a symmetric blue map).
V mapped(const HWSpriteTangentBasis& b)
{
    V bitangent=scale(cross(b.normal,b.tangent),b.handedness);
    return add(add(scale(b.tangent,.31f),scale(bitangent,-.47f)),scale(b.normal,.8265f));
}
void quad(float (&p)[4][3])
{
    const float v[4][3]={{-1,1,0},{1,1,0},{-1,-1,0},{1,-1,0}};
    for(int i=0;i<4;++i)for(int j=0;j<3;++j)p[i][j]=v[i][j];
}
void turn(float (&p)[4][3],float yaw,float pitch,float roll)
{
    yaw*=pi/180.f;pitch*=pi/180.f;roll*=pi/180.f;
    const float cy=std::cos(yaw),sy=std::sin(yaw);
    const float cx=std::cos(pitch),sx=std::sin(pitch);
    const float cz=std::cos(roll),sz=std::sin(roll);
    for(auto& v:p)
    {
        const float x=v[0],y=v[1],z=v[2];
        const float ax=cy*x+sy*z,ay=y,az=-sy*x+cy*z;
        const float bx=ax,by=cx*ay-sx*az,bz=sx*ay+cx*az;
        v[0]=cz*bx-sz*by;v[1]=sz*bx+cz*by;v[2]=bz;
    }
}
}
int main()
{
    float p[4][3];quad(p);
    // Inherited sprite U endpoint order is reversed without mirror;
    // V increases from top to bottom.
    const auto base=ResolveHWSpriteTangentBasis(p,1,0,0,1);
    good(base,+1);
    assert(base.tangent.X<-.999f && base.normal.Z>.999f);
    const auto mirror=ResolveHWSpriteTangentBasis(p,0,1,0,1);
    good(mirror,-1);
    assert(mirror.tangent.X>.999f);
    const auto yflip=ResolveHWSpriteTangentBasis(p,1,0,1,0);
    good(yflip,-1);
    const auto xyflip=ResolveHWSpriteTangentBasis(p,0,1,1,0);
    good(xyflip,+1);
    // Frame mirror and actor XFLIP share one effective UV state; applying
    // a second mirror to the final tangent would undo the intended sign.
    assert(near(mirror.tangent.X,-base.tangent.X));
    assert(near(yflip.tangent.X,base.tangent.X));
    assert(near(cross(base.normal,base.tangent).Y,-1.f));
    assert(near(mapped(base).X,-mapped(mirror).X));
    assert(near(mapped(base).Y,-mapped(yflip).Y));
    assert(near(mapped(base).Z,mapped(mirror).Z));
    assert(near(mapped(base).Z,mapped(yflip).Z));
    for(int doomRotation=0;doomRotation<8;++doomRotation)
    {
        quad(p);turn(p,doomRotation*45.f,0,0);
        const auto b=ResolveHWSpriteTangentBasis(p,1,0,0,1);
        good(b,+1);
        assert(near(b.normal.X,std::sin(doomRotation*45.f*pi/180.f)));
        assert(near(b.normal.Z,std::cos(doomRotation*45.f*pi/180.f)));
    }
    // Face XY / face camera / wall: inherited final-vertex rotations are the
    // authoritative source, including camera yaw + nonzero pitch and roll.
    for(int mode=0;mode<4;++mode)
    {
        quad(p);
        turn(p,34.f+mode*12.f,17.f+mode*3.f,28.f-mode*7.f);
        const auto b=ResolveHWSpriteTangentBasis(p,1,0,0,1);
        good(b,+1);
        assert(near(length2(mapped(b)),.31f*.31f+.47f*.47f+.8265f*.8265f,.001f));
        const auto b2=ResolveHWSpriteTangentBasis(p,1,0,0,1);
        assert(b.tangent.X==b2.tangent.X && b.normal.Z==b2.normal.Z);
    }
    // Flat sprite uses PF-009's own (x2,y2),(x1,y2),(x2,y1) ordering:
    // its geometric forward is vertical, without billboard assumptions.
    float flat[4][3]={{1,0,1},{-1,0,1},{1,0,-1},{-1,0,-1}};
    const auto f=ResolveHWSpriteTangentBasis(flat,1,0,0,1);
    good(f,+1);
    assert(f.normal.Y>.999f);
    // A line/plane-mirror parity is VIEW handedness, not a second world-UV
    // flip. Two mirrors restore view parity; world TBN stays unchanged.
    for(int line=0;line<2;++line)for(int plane=0;plane<2;++plane)
    {
        auto same=ResolveHWSpriteTangentBasis(flat,1,0,0,1);
        good(same,+1);
        const bool viewMirror=bool(line^plane);
        float viewParity=same.handedness*(viewMirror ? -1.f : 1.f);
        assert(viewParity==(line==plane ? +1.f : -1.f));
        assert(same.normal.Y==f.normal.Y && same.tangent.X==f.tangent.X);
    }
    quad(p);
    assert(!ResolveHWSpriteTangentBasis(p,0,0,0,1).valid);
    assert(!ResolveHWSpriteTangentBasis(p,0,1,0,0).valid);
    p[1][0]=p[0][0];p[1][1]=p[0][1];
    assert(!ResolveHWSpriteTangentBasis(p,0,1,0,1).valid);
    quad(p);p[3][2]=.1f;
    assert(!ResolveHWSpriteTangentBasis(p,0,1,0,1).valid);
    quad(p);p[2][0]=std::numeric_limits<float>::infinity();
    assert(!ResolveHWSpriteTangentBasis(p,0,1,0,1).valid);
    return 0;
}
