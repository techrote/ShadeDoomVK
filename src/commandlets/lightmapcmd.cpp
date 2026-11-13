
#include "lightmapcmd.h"
#include "d_event.h"
#include "engineerrors.h"
#include "g_level.h"
#include "g_levellocals.h"
#include "p_setup.h"
#include "v_video.h"

void D_SingleTick();

namespace
{
DoomLevelMesh& LoadLightmapCommandMap(const FArgs& args)
{
	const char* first = args.NumArgs() > 0 ? args.GetArg(0) : nullptr;
	FString mapname = first && first[0] != '-' ? first : "map01";
	if (mapname.Compare("*") == 0)
		mapname = level.MapName;

	if (mapname.IsEmpty() || !P_CheckMapData(mapname.GetChars()))
		I_Error("Could not find lightmap command map '%s'", mapname.GetChars());

	G_DeferedInitNew(mapname.GetChars());
	for (int i = 0; i < 100 && gameaction != ga_nothing; i++)
		D_SingleTick();

	// A failed or redirected map command must not write to another map's WAD.
	if (gameaction != ga_nothing || level.MapName.CompareNoCase(mapname) != 0)
		I_Error("Could not finish loading lightmap command map '%s' (current map is '%s')",
			mapname.GetChars(), level.MapName.GetChars());
	if (!level.levelMesh)
		I_Error("Map '%s' has no level mesh", mapname.GetChars());

	return *level.levelMesh;
}
}

LightmapCmdletGroup::LightmapCmdletGroup()
{
	SetLongFormName("lightmap");
	SetShortDescription("Lightmapper commands");

	AddCommand<LightmapBuildCmdlet>();
	AddCommand<LightmapDeleteCmdlet>();
}

/////////////////////////////////////////////////////////////////////////////

LightmapBuildCmdlet::LightmapBuildCmdlet()
{
	SetLongFormName("build");
	SetShortDescription("Build lightmap lump");
}

void LightmapBuildCmdlet::OnCommand(FArgs args)
{
	RunInGame([&]() {

		if (!screen->IsVulkan())
			I_Error("Building lightmaps requires the Vulkan renderer");

		auto& mesh = LoadLightmapCommandMap(args);
		if (!level.lightmaps)
			I_Error("Lightmapping is not enabled in map '%s'", level.MapName.GetChars());
		mesh.BeginFrame(level);
		const auto atlasPixelCount = mesh.AtlasPixelCount();
		const auto stats = mesh.GatherTilePixelStats();

		Printf("Tiles: %u (%u out of date)\n", stats.tiles.total, stats.tiles.dirty);
		Printf("Tile pixel area to update: %u\n", stats.pixels.dirty);
		Printf("Tile pixel area: %u\nAtlas pixel area: %u\n", stats.pixels.total, atlasPixelCount);
		if (atlasPixelCount > 0)
			Printf("Atlas efficiency: %.4f%%\n", float(stats.pixels.total) / float(atlasPixelCount) * 100.0f);
		Printf("Baking lightmaps. Please wait...\n");

		TArray<LightmapTile*> tiles;
		auto dirty = stats.tiles.dirty;
		while (dirty > 0)
		{
			tiles.Clear();
			for (auto& tile : mesh.Lightmap.Tiles)
			{
				if (tile.HasLiveAtlasAllocation(*mesh.Lightmap.AtlasPacker) && tile.NeedsInitialBake)
				{
					tiles.Push(&tile);
					if (tiles.Size() == 1001)
						break;
				}
			}

			if (tiles.Size() == 0)
				I_Error("No live lightmap tiles found for %u unfinished bakes", dirty);

			screen->BeginFrame();
			screen->UpdateLightmaps(tiles);
			screen->Update();

			const auto remaining = mesh.GatherTilePixelStats().tiles.dirty;
			if (remaining >= dirty)
				I_Error("Lightmap bake made no progress in map '%s' (%u unfinished tiles)",
					level.MapName.GetChars(), remaining);
			dirty = remaining;
		}

		mesh.SaveLightmapLump(level);

		Printf("Lightmap build complete.\n");
	});
}

void LightmapBuildCmdlet::OnPrintHelp()
{
	Printf(TEXTCOLOR_ORANGE "lightmap build " TEXTCOLOR_CYAN "[map name]" TEXTCOLOR_NORMAL " - Bakes all the lightmap lights and stores the result in a LIGHTMAP lump\n");
}

/////////////////////////////////////////////////////////////////////////////

LightmapDeleteCmdlet::LightmapDeleteCmdlet()
{
	SetLongFormName("delete");
	SetShortDescription("Delete lightmap lump");
}

void LightmapDeleteCmdlet::OnCommand(FArgs args)
{
	// Pretty lame that we have to load the map here, but cba to figure out how to deal with map loading outside the engine...

	RunInGame([&]() {
		LoadLightmapCommandMap(args).DeleteLightmapLump(level);
	});
}

void LightmapDeleteCmdlet::OnPrintHelp()
{
	Printf(TEXTCOLOR_ORANGE "lightmap delete " TEXTCOLOR_CYAN "[map name]" TEXTCOLOR_NORMAL " - Deletes the LIGHTMAP lump\n");
}
