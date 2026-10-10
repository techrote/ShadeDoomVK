#pragma once

// SDVK-007/v1. Standalone geometry/UV orientation math; no actor/portal state,
// shader settings or gameplay dependencies. Input coordinates are shader-world
// XYZ (Doom X, height, Doom Y), after HWSprite::CalculateVertices.
#include <cmath>
#include <cstdint>

struct HWSpriteTangentVector
{
    float X = 0, Y = 0, Z = 0;
};

struct HWSpriteTangentBasis
{
    HWSpriteTangentVector tangent{};
    HWSpriteTangentVector normal{};
    float handedness = 0;
    float uSign = 0;
    float vSign = 0;
    bool valid = false;
    const char* reason = "not computed";
};

namespace HWSpriteTangentMath
{
struct Vec3 { double x, y, z; };

inline Vec3 Minus(Vec3 a, Vec3 b) { return {a.x-b.x, a.y-b.y, a.z-b.z}; }
inline Vec3 Times(Vec3 a, double s) { return {a.x*s, a.y*s, a.z*s}; }
inline double Dot(Vec3 a, Vec3 b) { return a.x*b.x + a.y*b.y + a.z*b.z; }
inline Vec3 Cross(Vec3 a, Vec3 b)
{
    return {a.y*b.z-a.z*b.y, a.z*b.x-a.x*b.z, a.x*b.y-a.y*b.x};
}
inline bool Finite(Vec3 a)
{
    return std::isfinite(a.x) && std::isfinite(a.y) && std::isfinite(a.z);
}
inline HWSpriteTangentVector Narrow(Vec3 a)
{
    return {float(a.x), float(a.y), float(a.z)};
}
}

// Actual four vertices, with index 0=(ul,vt), 1=(ur,vt), 2=(ul,vb).
// This uses the final PF-009 sprite quad including yaw, pitch, roll, flat
// mapping and flip/sprite frame selection. The caller never rewrites geometry.
// Degenerate/nonfinite modes explicitly fall back to the legacy shader path.
inline HWSpriteTangentBasis ResolveHWSpriteTangentBasis(
    const float (&p)[4][3], float ul, float ur, float vt, float vb)
{
    using namespace HWSpriteTangentMath;
    HWSpriteTangentBasis result{};
    result.reason = "invalid/nonfinite quad or UV coordinates";
    if (!std::isfinite(ul) || !std::isfinite(ur) || !std::isfinite(vt) || !std::isfinite(vb))
        return result;
    const double du = double(ur)-ul, dv = double(vb)-vt;
    result.reason = "degenerate texture coordinate span";
    if (std::abs(du) < 1e-7 || std::abs(dv) < 1e-7)
        return result;
    const Vec3 a{p[0][0],p[0][1],p[0][2]};
    const Vec3 b{p[1][0],p[1][1],p[1][2]};
    const Vec3 c{p[2][0],p[2][1],p[2][2]};
    const Vec3 d{p[3][0],p[3][1],p[3][2]};
    if (!Finite(a) || !Finite(b) || !Finite(c) || !Finite(d))
        return result;
    // Use double intermediates to avoid cancellation on translated quads.
    const Vec3 rightEdge = Minus(b,a), downEdge = Minus(c,a);
    const double rightLength2 = Dot(rightEdge,rightEdge);
    result.reason = "degenerate sprite right edge";
    if (!std::isfinite(rightLength2) || rightLength2 < 1e-10) return result;
    const Vec3 right = Times(rightEdge,1.0/std::sqrt(rightLength2));
    const Vec3 upUnscaled = Times(Minus(downEdge,Times(right,Dot(downEdge,right))),-1.0);
    const double upLength2 = Dot(upUnscaled,upUnscaled);
    result.reason = "degenerate or collinear sprite up edge";
    if (!std::isfinite(upLength2) || upLength2 < 1e-10) return result;
    const Vec3 up = Times(upUnscaled,1.0/std::sqrt(upLength2));
    const Vec3 normal = Cross(right,up);
    result.reason = "nonfinite/nonorthogonal sprite tangent";
    if (!Finite(right) || !Finite(up) || !Finite(normal) || std::abs(Dot(right,up)) > 1e-4)
        return result;
    // Reject non-coplanar or twisted quads instead of assigning one possibly
    // false constant TBN to fragments on different planes.
    const Vec3 diagonal = Minus(d,a);
    const double scale = std::sqrt(rightLength2) + std::sqrt(upLength2);
    result.reason = "nonplanar sprite quad";
    if (!std::isfinite(scale) || scale <= 0 || std::abs(Dot(diagonal,normal)) > scale*1e-4)
        return result;
    result.uSign = du > 0 ? 1.f : -1.f;
    result.vSign = dv > 0 ? 1.f : -1.f;
    result.handedness = -result.uSign * result.vSign;
    const Vec3 t = Times(right,result.uSign);
    result.tangent = Narrow(t);
    result.normal = Narrow(normal);
    result.valid = std::isfinite(result.tangent.X) && std::isfinite(result.tangent.Y) &&
        std::isfinite(result.tangent.Z) && std::isfinite(result.normal.X) &&
        std::isfinite(result.normal.Y) && std::isfinite(result.normal.Z);
    result.reason = result.valid ? "explicit-final-quad" : "basis cannot fit finite shader floats";
    return result;
}
