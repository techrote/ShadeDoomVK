#include <cassert>
#include <cstdio>
#include <cstdint>
#include <functional>
#include <stdexcept>
#include <string>
#include <vector>

struct FString
{
	std::string value;
	FString(const char* text = "") : value(text) {}
	int Compare(const char* text) const { return value.compare(text); }
	int CompareNoCase(const FString& text) const { return value.compare(text.value); }
	bool IsEmpty() const { return value.empty(); }
	const char* GetChars() const { return value.c_str(); }
	void Format(const char* format, const char* text)
	{
		char buffer[64];
		std::snprintf(buffer, sizeof(buffer), format, text);
		value = buffer;
	}
	FString operator+(const FString& other) const { return (value + other.value).c_str(); }
};

struct FArgs
{
	const char* Map;
	int NumArgs() const { return Map ? 1 : 0; }
	const char* GetArg(int) const { return Map; }
};

template<class T> struct TArray : std::vector<T>
{
	void Clear() { this->clear(); }
	unsigned Size() const { return static_cast<unsigned>(this->size()); }
	void Push(T value) { this->push_back(value); }
};

struct LightmapTile
{
	bool NeedsInitialBake = true;
	bool HasLiveAtlasAllocation(int) const { return true; }
};

struct FLevelLocals;

struct DoomLevelMesh
{
	int packer = 0;
	struct { TArray<LightmapTile> Tiles; int* AtlasPacker; } Lightmap{{}, &packer};
	int saves = 0, deletes = 0;
	void BeginFrame(FLevelLocals&) {}
	unsigned AtlasPixelCount() const { return 0; }
	struct Stats { struct { unsigned total, dirty; } tiles, pixels; };
	Stats GatherTilePixelStats()
	{
		Stats result{};
		result.tiles.total = Lightmap.Tiles.Size();
		for (const auto& tile : Lightmap.Tiles) result.tiles.dirty += tile.NeedsInitialBake;
		return result;
	}
	void SaveLightmapLump(FLevelLocals&) { ++saves; }
	void DeleteLightmapLump(FLevelLocals&) { ++deletes; }
	static FString GetMapFilename(FLevelLocals&);
};

struct FLevelLocals
{
	FString MapName;
	DoomLevelMesh* levelMesh = nullptr;
	bool lightmaps = true;
	int lumpnum = -1;
};

struct BakeScreen
{
	bool vulkan = true, completes = true, cancelled = false;
	std::vector<unsigned> batches;
	bool IsVulkan() const { return vulkan; }
	void BeginFrame() {}
	void UpdateLightmaps(const TArray<LightmapTile*>& tiles)
	{
		batches.push_back(tiles.Size());
		if (completes)
			for (auto* tile : tiles) tile->NeedsInitialBake = false;
	}
	void Update() { if (cancelled) throw std::runtime_error("cancelled"); }
};

static struct
{
	int CheckNumForFullName(const char* name) const { return std::string(name) == "maps/map01.wad" ? 17 : -1; }
	int GetFileContainer(int lump) const { return lump == 17 ? 3 : -1; }
	const char* GetFileFullName(int) const { return "maps/map01.wad"; }
	const char* GetResourceFileFullName(int) const { return "editable/"; }
} fileSystem;

static FLevelLocals level;
static BakeScreen renderer;
static BakeScreen* screen = &renderer;
static int gameaction;
static constexpr int ga_nothing = 0;
static bool stuck, redirected;
static FString requestedMap;
static DoomLevelMesh fixtureMesh;

static void Printf(const char*, ...) {}
[[noreturn]] static void I_Error(const char* message, ...) { throw std::runtime_error(message); }
static bool P_CheckMapData(const char* name) { return std::string(name) == "map01"; }
static void G_DeferedInitNew(const char* name) { requestedMap = name; gameaction = 1; }
static void D_SingleTick()
{
	if (stuck) return;
	level.MapName = redirected ? FString("map02") : requestedMap;
	gameaction = ga_nothing;
}

struct Commandlet
{
	void RunInGame(const std::function<void()>& action) { action(); }
};
struct LightmapBuildCmdlet : Commandlet { void OnCommand(FArgs args); };
struct LightmapDeleteCmdlet : Commandlet { void OnCommand(FArgs args); };

#include "commandlet_methods.inc"

static void Reset(unsigned dirty)
{
	fixtureMesh.Lightmap.Tiles.assign(dirty, LightmapTile{});
	fixtureMesh.saves = fixtureMesh.deletes = 0;
	level = {FString("map01"), &fixtureMesh, true};
	renderer = BakeScreen{};
	gameaction = ga_nothing;
	stuck = redirected = false;
}

static void ExpectFailure(const std::function<void()>& action, const char* error)
{
	try
	{
		action();
		assert(false && "invalid lightmap operation succeeded");
	}
	catch (const std::runtime_error& failure)
	{
		assert(std::string(failure.what()).find(error) != std::string::npos);
	}
	assert(fixtureMesh.saves == 0 && fixtureMesh.deletes == 0);
}

int main()
{
	LightmapBuildCmdlet build;
	LightmapDeleteCmdlet remove;

	Reset(1002);
	build.OnCommand({nullptr});
	assert((renderer.batches == std::vector<unsigned>{1001, 1}));
	assert(fixtureMesh.saves == 1 && fixtureMesh.GatherTilePixelStats().tiles.dirty == 0);

	Reset(1);
	renderer.completes = false;
	ExpectFailure([&] { build.OnCommand({"*"}); }, "made no progress");
	assert(renderer.batches == std::vector<unsigned>{1});

	Reset(1);
	renderer.cancelled = true;
	ExpectFailure([&] { build.OnCommand({nullptr}); }, "cancelled");

	Reset(0);
	build.OnCommand({nullptr});
	assert(fixtureMesh.saves == 1 && renderer.batches.empty());

	Reset(1);
	ExpectFailure([&] { build.OnCommand({"missing"}); }, "Could not find");
	Reset(1);
	redirected = true;
	ExpectFailure([&] { remove.OnCommand({nullptr}); }, "Could not finish");
	Reset(1);
	stuck = true;
	ExpectFailure([&] { build.OnCommand({nullptr}); }, "Could not finish");
	Reset(1);
	level.lightmaps = false;
	ExpectFailure([&] { build.OnCommand({nullptr}); }, "not enabled");
	remove.OnCommand({nullptr});
	assert(fixtureMesh.deletes == 1 && renderer.batches.empty());

	Reset(0);
	renderer.vulkan = false;
	ExpectFailure([&] { build.OnCommand({nullptr}); }, "requires the Vulkan");

	// The normal directory path remains unchanged. A higher-priority map
	// supplied by another WAD can have the same map name but a different lump.
	level.lumpnum = 17;
	assert(DoomLevelMesh::GetMapFilename(level).Compare("editable/maps/map01.wad") == 0);
	level.lumpnum = 23;
	ExpectFailure([&] { (void)DoomLevelMesh::GetMapFilename(level); }, "not the maps/");
}
