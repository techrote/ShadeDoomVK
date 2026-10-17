#pragma once

#include "templates.h"
#include <memory>
#include <cstdint>
#include <cstddef>

// Enable this if you want to test if atlas building is broken internally in the RectPacker
// #define VALIDATE_RECTPACKER

class RectPacker;
class RectPackerPage;
class RectPackerShelf;
class RectPackerItem;

// Value receipt, independent of recyclable item storage. It is not a pointer,
// page number or content revision. Nonempty does not imply live: resolve only
// against the current owning packer before consuming coordinates or freeing.
struct RectPackerAllocation
{
	uint64_t Owner = 0;
	uint64_t Incarnation = 0;
	size_t Slot = 0;

	explicit operator bool() const { return Owner != 0 || Incarnation != 0 || Slot != 0; }
	bool operator==(const RectPackerAllocation& other) const
	{
		return Owner == other.Owner && Incarnation == other.Incarnation && Slot == other.Slot;
	}
	bool operator!=(const RectPackerAllocation& other) const { return !(*this == other); }
};

struct RectPackerRegion
{
	int X = 0, Y = 0, Width = 0, Height = 0, PageIndex = 0;
};

class RectPackerItem
{
public:
	int X = 0;
	int Y = 0;
	int Width = 0;
	int Height = 0;
	int PageIndex = 0;

private:
	size_t Slot = 0;
	uint64_t Incarnation = 0; // zero for free space / retired storage
	RectPackerShelf* Shelf = nullptr;

	RectPackerItem* PrevItem = nullptr;
	RectPackerItem* NextItem = nullptr;

	bool IsAvailable = false;
	RectPackerItem* PrevAvailable = nullptr;
	RectPackerItem* NextAvailable = nullptr;

	friend class RectPacker;
};

class RectPackerShelf
{
public:
	int Y = 0;
	int Height = 0;
	RectPackerItem* ItemList = nullptr;
	RectPackerItem* AvailableList = nullptr;
};

class RectPackerPage
{
public:
	RectPackerPage(int pageIndex) : PageIndex(pageIndex) { }

	int PageIndex = 0;
	TArray<std::unique_ptr<RectPackerShelf>> Shelves;
};

class RectPacker
{
public:
	RectPacker(int width, int height, int padding);
	RectPacker(const RectPacker&) = delete;
	RectPacker& operator=(const RectPacker&) = delete;
	RectPacker(RectPacker&&) = delete;
	RectPacker& operator=(RectPacker&&) = delete;

	void Clear();

	RectPackerAllocation Alloc(int width, int height);
	// Invalid/foreign/retired frees do not mutate the current owner.
	bool Free(const RectPackerAllocation& allocation);
	bool IsLive(const RectPackerAllocation& allocation) const;
	bool TryGetRegion(const RectPackerAllocation& allocation, RectPackerRegion& region) const;
	RectPackerRegion GetRegion(const RectPackerAllocation& allocation) const;

	int GetNumPages() const { return (int)Pages.size(); }

private:
	RectPackerItem* FindAllocation(const RectPackerAllocation& allocation) const;
	RectPackerAllocation PublishAllocation(RectPackerItem* item);
	uint64_t Owner = 0;
	uint64_t LastIncarnation = 0; // never reset by Clear; never allowed to wrap

	void AddPadding(RectPackerItem* item);
	void RemovePadding(RectPackerItem* item);

	RectPackerItem* AllocateRoom(RectPackerItem* item, int width, int height);
	RectPackerItem* CreateShelf(RectPackerPage* page, int y, int width, int height);

	RectPackerItem* AllocItem(RectPackerShelf* shelf);
	void FreeItem(RectPackerItem* item);

	void AddToItemList(RectPackerItem* item, RectPackerItem* insertAt = nullptr);
	void RemoveFromItemList(RectPackerItem* item);

	void AddToAvailableList(RectPackerItem* item);
	void RemoveFromAvailableList(RectPackerItem* item);

	int PageWidth = 0;
	int PageHeight = 0;
	int Padding = 0;
	TArray<RectPackerPage> Pages;
	TArray<std::unique_ptr<RectPackerItem>> Items;
	TArray<RectPackerItem*> ItemFreeList;

#ifdef VALIDATE_RECTPACKER
	void ValidateAllocation(RectPackerItem* item, bool dealloc);
	TArray<uint8_t> ValidationBuffer;
#endif

	friend class RectPackerPage;
};
