#pragma once

// Diagnostic-only little-endian serialization. No native padding, addresses or
// uninitialized backing-array tail is written. See tools/collision_replay.py.
#include <cstdint>
#include <cstdio>
#include <cstring>

class CollisionSnapshotFile
{
public:
	explicit CollisionSnapshotFile(const char* path)
	{
#ifdef _MSC_VER
		fopen_s(&File, path, "wbx");
#else
		File = std::fopen(path, "wbx");
#endif
	}
	~CollisionSnapshotFile() { if (File) std::fclose(File); }
	bool IsOpen() const { return File != nullptr; }
	void Bytes(const void* data, size_t size)
	{
		if (!File || std::fwrite(data, 1, size, File) != size) Good = false;
	}
	void UInt(uint32_t value)
	{
		const unsigned char bytes[4] = {
			static_cast<unsigned char>(value), static_cast<unsigned char>(value >> 8),
			static_cast<unsigned char>(value >> 16), static_cast<unsigned char>(value >> 24) };
		Bytes(bytes, sizeof(bytes));
	}
	void Int(int value) { UInt(static_cast<uint32_t>(value)); }
	void Float(float value)
	{
		static_assert(sizeof(float) == sizeof(uint32_t), "snapshot requires binary32");
		uint32_t bits;
		std::memcpy(&bits, &value, sizeof(bits));
		UInt(bits);
	}
	void Section(const char* tag, uint32_t count, uint32_t stride)
	{
		Bytes(tag, 4); UInt(count); UInt(stride);
	}
	bool Finish()
	{
		if (!File) return false;
		const int status = std::fclose(File);
		File = nullptr;
		return Good && status == 0;
	}
private:
	FILE* File = nullptr;
	bool Good = true;
};
