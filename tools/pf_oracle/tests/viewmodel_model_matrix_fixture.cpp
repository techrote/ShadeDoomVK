#include <cassert>
#include <cmath>
#ifdef _MSC_VER
#pragma warning(push)
#pragma warning(disable:4100)
#endif
// Execute the inherited production matrix implementation, not a second math
// implementation. Restore its legacy warnings before fixture assertions.
#include "src/common/utility/matrix.cpp"
#ifdef _MSC_VER
#pragma warning(pop)
#endif

static float dot3(const FVector4& a, const FVector4& b)
{
    return a.X*b.X + a.Y*b.Y + a.Z*b.Z;
}

int main()
{
    for (float mirror : {1.f, -1.f})
    {
        VSMatrix view = VSMatrix::identity();
        view.rotate(23.f, 0.f, 0.f, 1.f);
        view.rotate(-31.f, 1.f, 0.f, 0.f);
        view.rotate(57.f, 0.f, 1.f, 0.f);
        view.translate(-64.f, -41.f, 96.f);
        VSMatrix cameraToWorld;
        assert(view.inverseMatrix(cameraToWorld));

        VSMatrix authored = VSMatrix::identity();
        authored.scale(2.f*mirror, 3.f, 0.5f);
        authored.translate(1.f, -2.f, -24.f);
        authored.rotate(17.f, 0.f, 1.f, 0.f);
        VSMatrix objectToWorld = cameraToWorld;
        objectToWorld.multMatrix(authored);
        VSMatrix normalToWorld;
        normalToWorld.computeNormalMatrix(objectToWorld);

        const FVector4 p(2.f, 3.f, 4.f, 1.f);
        const auto expected = authored * p;
        const auto actual = view * (objectToWorld * p);
        assert(std::abs(actual.X-expected.X) < 0.0001f);
        assert(std::abs(actual.Y-expected.Y) < 0.0001f);
        assert(std::abs(actual.Z-expected.Z) < 0.0001f);

        const FVector4 tangent(1.f, 1.f, 0.f, 0.f);
        const FVector4 normal(1.f, -1.f, 0.f, 0.f);
        const auto worldTangent = objectToWorld * tangent;
        const auto worldNormal = normalToWorld * normal;
        assert(std::abs(dot3(worldTangent, worldNormal)) < 0.0001f);
        // Deliberate wrong model-matrix normal transform loses orthogonality
        // under the same non-uniform scale, including mirrored presentation.
        assert(std::abs(dot3(worldTangent, objectToWorld * normal)) > 1.f);
    }
}
