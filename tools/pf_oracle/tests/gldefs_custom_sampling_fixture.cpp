// PF-020 production-source-extracted GLDEFS custom-texture property fixture.
// The generated header contains actual current allocation/filter/error blocks
// plus the exact original allocation-default mutation. This fixture supplies
// bounded scanner, texture-lookup and container services only; it does not
// claim complete GLDEFS dispatch, descriptor execution, or GPU/image evidence.
#include <algorithm>
#include <array>
#include <cctype>
#include <cstdio>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

static int checks = 0;
static int expectedErrors = 0;

static void Check(bool value, const std::string& message)
{
    ++checks;
    if (!value) throw std::runtime_error(message);
}

class FString
{
public:
    std::string Value;
    FString() = default;
    FString(const char* value) : Value(value) { }
    explicit FString(std::string value) : Value(std::move(value)) { }
    int Compare(const FString& other) const { return Value.compare(other.Value); }
    const char* GetChars() const { return Value.c_str(); }
};

struct FGameTexture
{
    FString Name;
    const FString& GetName() const { return Name; }
};

template<class T> class TArray : public std::vector<T>
{
public:
    void Push(const T& value) { this->push_back(value); }
};

template<class T, std::size_t N> constexpr std::size_t countof(const T (&)[N]) { return N; }
enum class ETextureType { Any };
struct FTextureManager { static constexpr int TEXMAN_TryAny = 1; };

struct TextureManagerStub
{
    FGameTexture Base{FString("PF020BASE")};
    std::array<FGameTexture, 20> Textures{};
    TextureManagerStub()
    {
        for (std::size_t i = 0; i < Textures.size(); ++i)
            Textures[i].Name = FString("PF020T" + std::to_string(i));
    }
    FGameTexture* FindGameTexture(const char* name, ETextureType, int)
    {
        for (auto& texture : Textures)
            if (texture.Name.Value == name) return &texture;
        return nullptr;
    }
} TexMan;

struct ScriptFailure : std::runtime_error { using std::runtime_error::runtime_error; };

class FScanner
{
    std::vector<std::string> Tokens;
    std::size_t Position = 0;
    std::string Current;
public:
    const char* String = "";
    explicit FScanner(std::vector<std::string> tokens) : Tokens(std::move(tokens)) { }
    void MustGetString()
    {
        if (Position >= Tokens.size()) throw ScriptFailure("missing string token");
        Current = Tokens[Position++];
        String = Current.c_str();
    }
    bool Compare(const char* text) const
    {
        std::string a = Current, b = text;
        for (char& value : a) value = static_cast<char>(std::tolower(static_cast<unsigned char>(value)));
        for (char& value : b) value = static_cast<char>(std::tolower(static_cast<unsigned char>(value)));
        return a == b;
    }
    bool CheckToken(char token)
    {
        if (Position < Tokens.size() && Tokens[Position] == std::string(1, token))
        {
            ++Position;
            return true;
        }
        return false;
    }
    template<class... Args> [[noreturn]] void ScriptError(const char* format, Args... args)
    {
        std::array<char, 1024> message{};
        std::snprintf(message.data(), message.size(), format, args...);
        throw ScriptFailure(message.data());
    }
    bool Complete() const { return Position == Tokens.size(); }
};

#include "gldefs_extracted_sampling.h"

enum class Route { Material, Global, Map, Class, Legacy };

struct State
{
    MaterialLayers Layers;
    TArray<FString> Names;
    TArray<int> Indices;
    explicit State(Route route) : Layers(route == Route::Legacy ? InitialLegacy() : InitialMaterial()) { }
};

static void Parse(State& state, Route route, bool original, const std::vector<std::string>& tokens)
{
    FScanner scanner(tokens);
    const FString target(route == Route::Map ? "default map MAP01" :
                         route == Route::Class ? "default class DoomPlayer" : "default");
    const bool global = route == Route::Global || route == Route::Map || route == Route::Class;
    if (route == Route::Legacy)
    {
        if (original) OriginalLegacy(scanner, state.Layers, state.Names, state.Indices, false, target);
        else CurrentLegacy(scanner, state.Layers, state.Names, state.Indices, false, target);
    }
    else
    {
        if (original) OriginalMaterial(scanner, state.Layers, state.Names, state.Indices, global, target);
        else CurrentMaterial(scanner, state.Layers, state.Names, state.Indices, global, target);
    }
    Check(scanner.Complete(), "property block failed to consume supplied tokens");
}

static std::vector<std::string> Property(int id, const std::string& filter = "", const std::string& alias = "")
{
    std::vector<std::string> tokens{alias.empty() ? "custom" + std::to_string(id) : alias,
                                    "PF020T" + std::to_string(id)};
    if (!filter.empty()) tokens.insert(tokens.end(), {"{", "filter", filter, "}"});
    return tokens;
}

static MaterialLayerSampling Sampling(const std::string& filter)
{
    if (filter == "nearest") return MaterialLayerSampling::NearestMipLinear;
    if (filter == "linear" || filter == "LiNeAr") return MaterialLayerSampling::LinearMipLinear;
    return MaterialLayerSampling::Default;
}

static void Slot(const State& state, int index, int texture, MaterialLayerSampling expected, const std::string& witness)
{
    Check(state.Layers.CustomShaderTextures[index] == &TexMan.Textures[static_cast<std::size_t>(texture)], witness + " texture identity");
    const int actual = static_cast<int>(state.Layers.CustomShaderTextureSampling[index]);
    const int wanted = static_cast<int>(expected);
    Check(actual == wanted, witness + " sampling expected=" + std::to_string(wanted) + " actual=" + std::to_string(actual));
}

static void ExpectError(State& state, Route route, const std::vector<std::string>& tokens, const std::string& substring)
{
    bool failed = false;
    try { Parse(state, route, false, tokens); }
    catch (const ScriptFailure& error)
    {
        failed = true;
        Check(std::string(error.what()).find(substring) != std::string::npos, "incorrect parser error: " + std::string(error.what()));
    }
    Check(failed, "production property accepted invalid input: " + substring);
    ++expectedErrors;
}

static void OriginalCounterexamples()
{
    State material(Route::Material);
    Parse(material, Route::Material, true, Property(0, "linear"));
    Slot(material, 0, 0, MaterialLayerSampling::LinearMipLinear, "original first linear before second");
    Parse(material, Route::Material, true, Property(1));
    Slot(material, 0, 0, MaterialLayerSampling::Default, "original overwritten first");
    Slot(material, 1, 1, MaterialLayerSampling::NearestMipLinear, "original unintended second");
    State legacy(Route::Legacy);
    Parse(legacy, Route::Legacy, true, Property(0));
    Parse(legacy, Route::Legacy, true, Property(1));
    Slot(legacy, 0, 0, MaterialLayerSampling::Default, "original legacy first");
    Slot(legacy, 1, 1, MaterialLayerSampling::NearestMipLinear, "original legacy unintended second");
    std::cout << "{\"producer\":\"exact-original-allocation-default\",\"materialActual\":[-1,0],\"materialRequired\":[1,-1],\"legacyActual\":[-1,0],\"legacyRequired\":[-1,-1],\"checks\":" << checks << "}\n";
}

static void CurrentContract()
{
    const std::array<Route, 4> sharedRoutes{Route::Material, Route::Global, Route::Map, Route::Class};
    const std::array<std::string, 4> filters{"", "default", "nearest", "linear"};
    for (Route route : sharedRoutes)
    {
        // The exact first-linear/second-omitted reproducer runs first so an
        // unfixed production branch reports the actual decisive failure.
        State witness(route);
        Parse(witness, route, false, Property(0, "linear"));
        Parse(witness, route, false, Property(1));
        Slot(witness, 0, 0, MaterialLayerSampling::LinearMipLinear, "first linear after second omitted");
        Slot(witness, 1, 1, MaterialLayerSampling::Default, "second omitted default");
        for (const auto& first : filters)
        {
            State one(route);
            Parse(one, route, false, Property(0, first));
            Slot(one, 0, 0, Sampling(first), "single custom texture");
            Check(one.Names.size() == 1 && one.Indices.size() == 1 && one.Indices[0] == 0, "single authoring identity");
            for (const auto& second : filters)
            {
                State two(route);
                Parse(two, route, false, Property(0, first));
                Parse(two, route, false, Property(1, second));
                Slot(two, 0, 0, Sampling(first), "previous explicit/omitted filter retained");
                Slot(two, 1, 1, Sampling(second), "later explicit/omitted filter assigned");
                Check(two.Names.size() == 2 && two.Indices[0] == 0 && two.Indices[1] == 1, "two authoring identities");
            }
        }
        State caseInsensitive(route);
        Parse(caseInsensitive, route, false, Property(0, "LiNeAr"));
        Slot(caseInsensitive, 0, 0, MaterialLayerSampling::LinearMipLinear, "case-insensitive filter dispatch");
        State full(route);
        for (int i = 0; i < MAX_CUSTOM_HW_SHADER_TEXTURES; ++i)
            Parse(full, route, false, Property(i, filters[static_cast<std::size_t>(i) % filters.size()]));
        for (int i = 0; i < MAX_CUSTOM_HW_SHADER_TEXTURES; ++i)
        {
            Slot(full, i, i, Sampling(filters[static_cast<std::size_t>(i) % filters.size()]), "full supported capacity");
            Check(full.Indices[static_cast<std::size_t>(i)] == i, "full capacity authoring index");
        }
        ExpectError(full, route, Property(15), "out of texture units");
        Check(full.Names.size() == 15, "overflow must not publish a sixteenth authoring name");
        for (int i = 0; i < MAX_CUSTOM_HW_SHADER_TEXTURES; ++i)
            Slot(full, i, i, Sampling(filters[static_cast<std::size_t>(i) % filters.size()]), "overflow retained prior state");

        State missing(route);
        ExpectError(missing, route, {"first", "MISSING"}, "not found");
        Check(missing.Names.empty() && missing.Indices.empty(), "missing texture must not publish authoring identity");
        Parse(missing, route, false, Property(0, "linear"));
        ExpectError(missing, route, {"later", "MISSING"}, "not found");
        Slot(missing, 0, 0, MaterialLayerSampling::LinearMipLinear, "failed later lookup retained earlier sampling");
        Check(missing.Names.size() == 1, "failed later lookup must not publish name");
        ExpectError(missing, route, Property(1, "", "custom0"), "redefine");
        Slot(missing, 0, 0, MaterialLayerSampling::LinearMipLinear, "duplicate retained earlier sampling");

        State badFilter(route);
        Parse(badFilter, route, false, Property(0, "nearest"));
        ExpectError(badFilter, route, Property(1, "trilinear"), "unexpected");
        Slot(badFilter, 0, 0, MaterialLayerSampling::NearestMipLinear, "invalid later filter retained earlier sampling");
        State badTokens(route);
        ExpectError(badTokens, route, {"custom0"}, "missing string");
        ExpectError(badTokens, route, {"custom0", "PF020T0", "{", "filter"}, "missing string");
    }

    // Legacy HardwareShader has no per-texture filter block; omitted defaults
    // are its authoring contract. A pre-populated sparse state below exercises
    // allocation invariants, not an invented legacy filtering syntax.
    State legacy(Route::Legacy);
    Parse(legacy, Route::Legacy, false, Property(0));
    Slot(legacy, 0, 0, MaterialLayerSampling::Default, "legacy single omitted default");
    Check(legacy.Names.size() == 1 && legacy.Indices[0] == 0, "legacy single authoring identity");
    Parse(legacy, Route::Legacy, false, Property(1));
    Slot(legacy, 0, 0, MaterialLayerSampling::Default, "legacy earlier omitted default retained");
    Slot(legacy, 1, 1, MaterialLayerSampling::Default, "legacy second omitted default");
    for (int i = 2; i < MAX_CUSTOM_HW_SHADER_TEXTURES; ++i)
        Parse(legacy, Route::Legacy, false, Property(i));
    for (int i = 0; i < MAX_CUSTOM_HW_SHADER_TEXTURES; ++i)
        Slot(legacy, i, i, MaterialLayerSampling::Default, "legacy all omitted defaults");
    ExpectError(legacy, Route::Legacy, Property(15), "out of texture units");
    State legacyMissing(Route::Legacy);
    ExpectError(legacyMissing, Route::Legacy, {"bad", "MISSING"}, "not found");
    Parse(legacyMissing, Route::Legacy, false, Property(0));
    ExpectError(legacyMissing, Route::Legacy, Property(1, "", "custom0"), "redefine");
    Check(legacyMissing.Names.size() == 1, "legacy duplicate did not publish an extra name");

    const std::array<Route, 5> allocationRoutes{Route::Material, Route::Global, Route::Map, Route::Class, Route::Legacy};
    for (Route route : allocationRoutes)
    {
        State sparse(route);
        sparse.Layers.CustomShaderTextures[0] = &TexMan.Textures[0];
        sparse.Layers.CustomShaderTextureSampling[0] = MaterialLayerSampling::LinearMipLinear;
        sparse.Layers.CustomShaderTextures[2] = &TexMan.Textures[2];
        sparse.Layers.CustomShaderTextureSampling[2] = MaterialLayerSampling::NearestMipLinear;
        sparse.Layers.CustomShaderTextures[7] = &TexMan.Textures[7];
        sparse.Layers.CustomShaderTextureSampling[7] = MaterialLayerSampling::Default;
        Parse(sparse, route, false, Property(1));
        Slot(sparse, 0, 0, MaterialLayerSampling::LinearMipLinear, "sparse preceding slot preserved");
        Slot(sparse, 1, 1, MaterialLayerSampling::Default, "sparse first free slot initialized");
        Slot(sparse, 2, 2, MaterialLayerSampling::NearestMipLinear, "sparse later slot preserved");
        Slot(sparse, 7, 7, MaterialLayerSampling::Default, "sparse distant slot preserved");
        Check(sparse.Indices.size() == 1 && sparse.Indices[0] == 1, "sparse published original authoring slot");
    }
    std::cout << "{\"producer\":\"current-source-extracted\",\"customTextureCap\":15,\"checks\":" << checks
              << ",\"expectedErrors\":" << expectedErrors << ",\"completeGLDefsLoader\":false,\"gpuExecution\":false}\n";
}

int main(int argc, char** argv)
{
    try
    {
        Check(argc == 2, "select --original or --current");
        const std::string mode = argv[1];
        if (mode == "--original") OriginalCounterexamples();
        else if (mode == "--current") CurrentContract();
        else throw std::runtime_error("unknown fixture producer");
        return 0;
    }
    catch (const std::exception& error)
    {
        std::cerr << "GLDEFS custom-sampling contract failure: " << error.what() << '\n';
        return 1;
    }
}
