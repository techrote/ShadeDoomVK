// Classic Doom 1.9 input decoding, reimplemented from the documented byte format.
// This is an input importer, not a vanilla simulation or demo-sync implementation.
#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

namespace ClassicInput
{
struct Header
{
    unsigned skill = 0, episode = 0, map = 0;
    bool respawn = false, fast = false, noMonsters = false;
    size_t tics = 0;
};

// Native demo CVar backup deliberately omits latched CVars. These two imported
// startup settings need their own ownership, without altering the latch queue.
struct StartupValues
{
    bool captured = false;
    int skill = 0, deathmatch = 0;
    void Capture(int currentSkill, int currentDeathmatch)
    {
        skill = currentSkill; deathmatch = currentDeathmatch; captured = true;
    }
    template<class RestoreValues> void Restore(RestoreValues restore)
    {
        if (!captured) return;
        captured = false;
        restore(skill, deathmatch);
    }
};

struct Tic
{
    int16_t forward = 0, side = 0, yaw = 0;
    uint32_t buttons = 0;
    int weapon = -1; // Original zero-based Doom weapon group, 7 = chainsaw.
};

template<class Actor> inline bool OwnsInventory(Actor* owner, Actor* requested)
{
    if (!owner || !requested) return false;
    for (Actor* item = owner->Inventory; item; item = item->Inventory)
        if (item == requested) return true;
    return false;
}

inline int SignedByte(uint8_t value)
{
    return value < 128 ? int(value) : int(value) - 256;
}

inline bool DecodeTic(const uint8_t* data, size_t size, Tic& out, std::string& error)
{
    error.clear();
    if (!data || size < 4) { error = "Truncated classic input tic"; return false; }
    const unsigned buttons = data[3];
    if (buttons & 0x80)
    {
        error = "Classic pause/save special commands are not supported by this input importer";
        return false;
    }
    if ((buttons & 0x40) || (!(buttons & 4) && (buttons & 0x38)))
    {
        error = "Reserved classic button fields";
        return false;
    }
    // Multiplication, rather than left-shifting negative signed values, is defined.
    out.forward = int16_t(SignedByte(data[0]) * 256);
    out.side = int16_t(SignedByte(data[1]) * 256);
    out.yaw = int16_t(SignedByte(data[2]) * 256);
    out.buttons = buttons & 3; // Doom and current engine agree on attack/use bits.
    out.weapon = buttons & 4 ? int((buttons >> 3) & 7) : -1;
    return true;
}

inline bool Parse(const uint8_t* data, size_t size, bool mapxx, Header& out, std::string& error)
{
    error.clear();
    out = {};
    if (!data || size < 14) { error = "Classic input needs a complete 13-byte header and end marker"; return false; }
    if (data[0] != 109) { error = "Only classic Doom version 109 short-tic input is supported (not longtics/Boom/MBF/DSDA variants)"; return false; }
    if (data[1] > 4 || !data[2] || !data[3] ||
        (mapxx ? data[2] != 1 || data[3] > 32 : data[2] > 4 || data[3] > 9))
    {
        error = "Classic input has an unsupported skill/episode/map header";
        return false;
    }
    if (data[4] != 0 || data[8] != 0 || data[9] != 1 || data[10] || data[11] || data[12])
    {
        error = "Classic input import supports only single-player, non-deathmatch player zero";
        return false;
    }
    if (data[5] > 1 || data[6] > 1 || data[7] > 1)
    {
        error = "Invalid classic respawn/fast/no-monsters flags";
        return false;
    }
    Header parsed;
    parsed.skill = data[1]; parsed.episode = data[2]; parsed.map = data[3];
    parsed.respawn = data[5] != 0; parsed.fast = data[6] != 0; parsed.noMonsters = data[7] != 0;
    size_t offset = 13;
    while (offset < size)
    {
        if (data[offset] == 0x80)
        {
            if (!parsed.tics || offset + 1 != size)
            {
                error = "Classic input is empty or has unsupported trailing data";
                return false;
            }
            out = parsed;
            return true;
        }
        Tic tic;
        if (!DecodeTic(data + offset, size - offset, tic, error)) return false;
        offset += 4;
        ++parsed.tics;
    }
    error = "Classic input has no complete end marker";
    return false;
}
}
