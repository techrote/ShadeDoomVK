#include "hw_collision_snapshot.h"
#include <cassert>

int main(int argc, char** argv)
{
	assert(argc == 2);
	CollisionSnapshotFile writer(argv[1]);
	assert(writer.IsOpen());
	writer.Bytes("SDVKCL01", 8);
	writer.UInt(0x12345678u);
	writer.Int(-1);
	writer.Float(-0.0f);
	writer.Float(1.5f);
	writer.Section("TEST", 2, 4);
	writer.Int(-2147483647);
	writer.Int(2147483647);
	assert(writer.Finish());
	// Existing evidence must not be overwritten.
	CollisionSnapshotFile duplicate(argv[1]);
	assert(!duplicate.IsOpen());
	assert(!duplicate.Finish());
	assert(!writer.Finish());
	return 0;
}
