// Exercises the exact production source-alpha filter; no renderer/GPU claim.
#include "hw_actor_shadowmask.h"
#include <array>
#include <cassert>
#include <iostream>

int main()
{
    std::array<uint32_t, 256> words;
    words.fill(0xffffffffu);
    const uint8_t clear[4] = {255, 127, 63, 0}, solid[4] = {0, 0, 0, 255};
    assert(!HWActorShadow::BuildAlphaMask(clear, 1, 1, 64, 128, 128, words.data(), words.size()));
    for (auto word : words) assert(word == 0);
    assert(HWActorShadow::BuildAlphaMask(solid, 1, 1, 64, 128, 128, words.data(), words.size()));
    for (auto word : words) assert(word == 0xffffffffu);

    // Asymmetry and row packing cannot be hidden by a full-rectangle input.
    uint8_t asymmetric[32] = {};
    asymmetric[3] = 255;
    asymmetric[(1 * 4 + 3) * 4 + 3] = 255;
    uint32_t small = 0;
    assert(HWActorShadow::BuildAlphaMask(asymmetric, 4, 2, 4, 2, 128, &small, 1));
    assert(small == 0x81);

    const uint8_t filtered[8] = {0, 0, 0, 255, 0, 0, 0, 0};
    assert(HWActorShadow::BuildAlphaMask(filtered, 2, 1, 4, 1, 128, &small, 1));
    assert(small == 3);
    uint8_t hole[36];
    for (auto& channel : hole) channel = 255;
    hole[4 * 4 + 3] = 0;
    assert(HWActorShadow::BuildAlphaMask(hole, 3, 3, 3, 3, 128, &small, 1));
    assert(small == (0x1ffu ^ (1u << 4)));
    // Downsampling uses area coverage, preserving a transparent majority.
    const uint8_t sparse[16] = {0,0,0,0, 0,0,0,255, 0,0,0,0, 0,0,0,0};
    assert(!HWActorShadow::BuildAlphaMask(sparse, 4, 1, 1, 1, 128, &small, 1));
    assert(small == 0);

    const uint8_t thresholds[8] = {255, 255, 255, 127, 0, 0, 0, 128};
    assert(HWActorShadow::BuildAlphaMask(thresholds, 2, 1, 2, 1, 128, &small, 1));
    assert(small == 2);
    // Bit31, bit32 and row transitions survive 32-bit packing exactly.
    std::array<uint8_t, 64 * 2 * 4> crossing = {};
    crossing[31 * 4 + 3] = crossing[32 * 4 + 3] = crossing[64 * 4 + 3] = 255;
    const auto original = crossing;
    uint32_t packed[4] = {};
    assert(HWActorShadow::BuildAlphaMask(crossing.data(), 64, 2, 64, 2, 128, packed, 4));
    assert(packed[0] == 0x80000000u && packed[1] == 1 && packed[2] == 1 && packed[3] == 0);
    assert(crossing == original); // Filtering never edits displayed source pixels.

    assert(!HWActorShadow::BuildAlphaMask(hole, 3, 3, 64, 128, 128, &small, 1));
    assert(!HWActorShadow::BuildAlphaMask(nullptr, 3, 3, 3, 3, 128, &small, 1));
    assert(!HWActorShadow::BuildAlphaMask(hole, 2049, 3, 3, 3, 128, &small, 1));
    assert(!HWActorShadow::BuildAlphaMask(hole, 3, 3, 3, 3, 0, &small, 1));
    assert(!HWActorShadow::BuildAlphaMask(hole, 3, 3, 3, 3, 256, &small, 1));
    assert(!HWActorShadow::BuildAlphaMask(hole, -1, 3, 3, 3, 128, &small, 1));
    std::cout << "Production source-alpha filtering and negative controls PASS\n";
}
