#pragma once
// Standalone CPU replay adapter. Production math/layout/range code is retained.
#include <vector>
#include <stdexcept>
#include <cstdint>
#include "hw_levelmesh_contract.h"

template<class T> class ReplayArray : public std::vector<T>
{
public:
    using std::vector<T>::vector;
    unsigned int Size() const { return static_cast<unsigned int>(this->size()); }
    void Resize(unsigned int size) { this->resize(size); }
    void Clear() { this->clear(); }
    T* Data() { return this->data(); }
    const T* Data() const { return this->data(); }
    T& operator[](size_t i) { return this->at(i); }
    const T& operator[](size_t i) const { return this->at(i); }
    void Insert(size_t i, const T& value) { this->insert(this->begin() + i, value); }
    void Delete(size_t i, size_t count) { this->erase(this->begin() + i, this->begin() + i + count); }
};

class MeshBufferUploads
{
public:
    void Clear();
    void Add(int position, int count);
    const ReplayArray<MeshBufferRange>& GetRanges() const { return Ranges; }
    ReplayArray<MeshBufferRange> Ranges;
};

class LevelMesh
{
public:
    struct {
        ReplayArray<FFlatVertex> Vertices;
        ReplayArray<uint32_t> Indexes;
        int IndexCount = 0;
        ReplayArray<CollisionNode> Nodes;
        int RootNode = -1;
    } Mesh;
    struct { MeshBufferUploads Vertex, Index, Node; } UploadRanges;
};
