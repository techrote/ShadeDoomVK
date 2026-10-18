#pragma once
#include <cstddef>

// The renderer translates its viewpoint using glport->lines[0]. These selected
// endpoint identities are separate from the inherited Viewpoint.sector pointer.
// Observation only: never selects a sector, changes a transform, or probes XY.
namespace SdvkPortalObservation
{
struct SelectedLinePortal
{
    int OriginLine = -1, DestinationLine = -1;
    int SourceSector = -1, DestinationSector = -1;
    int SourceGroup = -1, DestinationGroup = -1;
};

template<class Span>
bool ResolveSelectedLinePortal(const Span* span, size_t lineCount, size_t sectorCount,
    SelectedLinePortal& output)
{
    output = {};
    if (!span || span->lines.Size() == 0 || span->lines.Size() > 64) return false;
    const auto* selected = span->lines[0];
    if (!selected || !selected->mOrigin || !selected->mDestination
        || !selected->mOrigin->frontsector || !selected->mDestination->frontsector) return false;
    const auto* origin = selected->mOrigin;
    const auto* destination = selected->mDestination;
    SelectedLinePortal selection;
    selection.OriginLine = int(origin->Index());
    selection.DestinationLine = int(destination->Index());
    selection.SourceSector = int(origin->frontsector->Index());
    selection.DestinationSector = int(destination->frontsector->Index());
    selection.SourceGroup = origin->frontsector->PortalGroup;
    selection.DestinationGroup = destination->frontsector->PortalGroup;
    if (selection.OriginLine < 0 || size_t(selection.OriginLine) >= lineCount
        || selection.DestinationLine < 0 || size_t(selection.DestinationLine) >= lineCount
        || selection.SourceSector < 0 || size_t(selection.SourceSector) >= sectorCount
        || selection.DestinationSector < 0 || size_t(selection.DestinationSector) >= sectorCount
        || selection.SourceGroup < 0 || selection.DestinationGroup < 0) return false;
    output = selection;
    return true;
}
}
