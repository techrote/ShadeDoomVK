#include "g_classicinput.h"
#include <cassert>
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>

static std::vector<uint8_t> Demo()
{
    return {109,3,1,1,0,0,0,0,0,1,0,0,0,25,232,254,1,206,40,4,6,128};
}
static bool Parse(const std::vector<uint8_t>& data, ClassicInput::Header& h, bool mapxx = true)
{
    std::string error;
    const bool ok = ClassicInput::Parse(data.data(), data.size(), mapxx, h, error);
    assert(ok || !error.empty());
    return ok;
}
int main(int argc, char** argv)
{
    struct Item { Item* Inventory; } ownedLast{nullptr}, ownedFirst{&ownedLast}, foreign{nullptr}, owner{&ownedFirst};
    assert(ClassicInput::OwnsInventory(&owner, &ownedFirst));
    assert(ClassicInput::OwnsInventory(&owner, &ownedLast));
    assert(!ClassicInput::OwnsInventory(&owner, &foreign));
    assert(!ClassicInput::OwnsInventory(&owner, &owner));
    assert(!ClassicInput::OwnsInventory(&owner, static_cast<Item*>(nullptr)));
    assert(!ClassicInput::OwnsInventory(static_cast<Item*>(nullptr), &ownedFirst));
    ClassicInput::Header header;
    const auto good = Demo();
    assert(Parse(good, header) && header.skill == 3 && header.map == 1 && header.tics == 2);
    std::string error;
    ClassicInput::Tic tic;
    assert(ClassicInput::DecodeTic(good.data()+13, 4, tic, error));
    assert(tic.forward == 6400 && tic.side == -6144 && tic.yaw == -512 && tic.buttons == 1 && tic.weapon == -1);
    assert(ClassicInput::DecodeTic(good.data()+17, 4, tic, error));
    assert(tic.forward == -12800 && tic.side == 10240 && tic.yaw == 1024 && tic.buttons == 2 && tic.weapon == 0);
    for (unsigned b = 0; b < 256; ++b)
    {
        uint8_t bytes[] = {uint8_t(b),uint8_t(b),uint8_t(b),0};
        assert(ClassicInput::DecodeTic(bytes, 4, tic, error));
        const int expected = (b < 128 ? int(b) : int(b)-256) * 256;
        assert(tic.forward == expected && tic.side == expected && tic.yaw == expected);
    }
    for (unsigned weapon = 0; weapon < 8; ++weapon)
    {
        uint8_t bytes[] = {0,0,0,uint8_t(4 + weapon*8 + 3)};
        assert(ClassicInput::DecodeTic(bytes, 4, tic, error));
        assert(tic.weapon == int(weapon) && tic.buttons == 3);
    }
    unsigned accepted = 0;
    for (unsigned b = 0; b < 256; ++b)
    {
        uint8_t bytes[] = {0,0,0,uint8_t(b)};
        const bool valid = b < 64 && ((b & 4) != 0 || b < 4);
        const bool actual = ClassicInput::DecodeTic(bytes, 4, tic, error);
        assert(actual == valid);
        accepted += actual ? 1u : 0u;
    }
    assert(accepted == 36);
    for (size_t n = 0; n < good.size(); ++n)
    {
        auto truncated = good; truncated.resize(n);
        assert(!Parse(truncated, header));
    }
    for (unsigned version : {0u, 106u, 110u, 111u, 202u, 221u})
    {
        auto wrong = good; wrong[0] = uint8_t(version); assert(!Parse(wrong, header));
    }
    for (unsigned offset : {1u,2u,3u,4u,5u,6u,7u,8u,9u,10u,11u,12u})
    {
        auto wrong = good; wrong[offset] = 255; assert(!Parse(wrong, header));
    }
    auto trailing = good; trailing.push_back(0); assert(!Parse(trailing, header));
    auto special = good; special[16] = 0x81; assert(!Parse(special, header));
    special[16] = 0x82; assert(!Parse(special, header));
    auto empty = good; empty.resize(14); empty[13] = 128; assert(!Parse(empty, header));
    auto episodic = good; episodic[2] = 4; episodic[3] = 9;
    assert(Parse(episodic, header, false)); assert(!Parse(episodic, header));
    auto options = good; options[5] = options[6] = options[7] = 1;
    assert(Parse(options, header) && header.respawn && header.fast && header.noMonsters);
    for (size_t n = 0; n < 4; ++n) assert(!ClassicInput::DecodeTic(good.data(), n, tic, error));
    assert(!ClassicInput::DecodeTic(nullptr, 4, tic, error));
    assert(!ClassicInput::Parse(nullptr, good.size(), true, header, error));
    if (argc == 2)
    {
        std::ifstream file(argv[1], std::ios::binary);
        assert(file.good());
        const std::vector<uint8_t> actual((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
        assert(Parse(actual, header));
        assert(actual.size() == 914 && header.tics == 225 && header.skill == 3 && header.episode == 1 && header.map == 1);
        for (size_t i = 0; i < header.tics; ++i) assert(ClassicInput::DecodeTic(actual.data()+13+4*i, 4, tic, error));
        std::cout << "Actual lv01-529 input: 225 tics decoded; no simulation or sync claim\n";
    }
    std::cout << "Classic input decoder: sign/range/button/weapon/owned-inventory/header/truncation checks PASS\n";
}
