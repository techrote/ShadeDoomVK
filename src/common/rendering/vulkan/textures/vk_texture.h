
#pragma once

#include <zvulkan/vulkanobjects.h>
#include "vulkan/textures/vk_imagetransition.h"
#include "hwrenderer/data/hw_resourcegeneration.h"
#include "hwrenderer/data/hw_uploadstaging.h"
#include <list>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <unordered_map>

class VulkanRenderDevice;
class VkHardwareTexture;
class VkMaterial;
class VkPPTexture;
class VkTextureImage;
enum class PPTextureType;
class PPTexture;
struct FSWColormap;

class VkTextureManager
{
public:
	VkTextureManager(VulkanRenderDevice* fb);
	~VkTextureManager();

	void Deinit();

	void BeginFrame(int lightmapTextureSize, int lightmapCount);

	void SetLightmapCount(int size, int count);

	void CreateLightmap(int size, int count, const TArray<uint16_t>& data);
	void DownloadLightmap(int arrayIndex, uint16_t* buffer);

	void ResetLightProbes();
	void UploadIrradiancemap(int cubeCount, const TArray<uint16_t>& data);
	void UploadPrefiltermap(int cubeCount, const TArray<uint16_t>& data);
	void CopyIrradiancemap(const std::vector<std::unique_ptr<VulkanImage>>& probes);
	void CopyPrefiltermap(const std::vector<std::unique_ptr<VulkanImage>>& probes);
	void DownloadIrradiancemap(int probeCount, TArrayView<uint16_t> irradianceMaps);
	void DownloadPrefiltermap(int probeCount, TArrayView<uint16_t> prefilterMaps);

	void CheckIrradiancemapSize(int cubeCount);
	void CheckPrefiltermapSize(int cubeCount);

	void SetGamePalette();

	VkTextureImage* GetTexture(const PPTextureType& type, PPTexture* tex);
	VkFormat GetTextureFormat(PPTexture* texture);

	void AddTexture(VkHardwareTexture* texture);
	void RemoveTexture(VkHardwareTexture* texture);

	void AddPPTexture(VkPPTexture* texture);
	void RemovePPTexture(VkPPTexture* texture);

	VulkanImage* GetNullTexture() { return NullTexture.get(); }
	VulkanImageView* GetNullTextureView() { return NullTextureView.get(); }

	VulkanImage* GetBrdfLutTexture() { return BrdfLutTexture.get(); }
	VulkanImageView* GetBrdfLutTextureView() { return BrdfLutTextureView.get(); }

	VulkanImage* GetGamePalette() { return GamePalette.get(); }
	VulkanImageView* GetGamePaletteView() { return GamePaletteView.get(); }

	VulkanImageView* GetSWColormapView(FSWColormap* colormap);

	int GetHWTextureCount() { return (int)Textures.size(); }

	struct Lightmap
	{
		VkTextureImage Light;
		VkTextureImage Probe;
	};

	VkTextureImage Shadowmap;
	std::vector<Lightmap> Lightmaps;
	std::vector<VkTextureImage> Irradiancemaps;
	std::vector<VkTextureImage> Prefiltermaps;

	static const int MAX_REFLECTION_LOD = 4; // Note: must match what lightmodel_pbr.glsl expects

	void ProcessMainThreadTasks();
	void RunOnWorkerThread(std::function<void()> task);
	void RunOnMainThread(std::function<void()> task);

	struct FAsyncTextureUploadTicket
	{
		int ID = 0;
		FRendererEpochToken ManagerEpoch;
		FRendererEpochToken TargetEpoch;
	};

	struct FAsyncTextureUploadStats
	{
		uint64_t JobsQueued = 0;
		uint64_t JobsCompleted = 0;
		uint64_t PendingCancellations = 0;
		uint64_t MissingTicketRejects = 0;
		uint64_t ManagerEpochRejects = 0;
		uint64_t TargetEpochRejects = 0;
	};

	FAsyncTextureUploadTicket CreateUploadTicket(VkHardwareTexture* tex, FRendererEpochToken targetEpoch)
	{
		FAsyncTextureUploadTicket ticket;
		ticket.ID = CreateUploadID(tex);
		ticket.ManagerEpoch = AsyncUploadEpoch.Snapshot();
		ticket.TargetEpoch = targetEpoch;
		AsyncUploadStats.JobsQueued++;
		return ticket;
	}

	bool CheckUploadTicket(const FAsyncTextureUploadTicket& ticket)
	{
		if (!CheckUploadID(ticket.ID))
		{
			AsyncUploadStats.MissingTicketRejects++;
			return false;
		}
		if (!AsyncUploadEpoch.Validate(ticket.ManagerEpoch))
		{
			AsyncUploadStats.ManagerEpochRejects++;
			return false;
		}
		return true;
	}

	void CancelUploads(VkHardwareTexture* texture)
	{
		for (auto it = PendingUploads.begin(); it != PendingUploads.end();)
		{
			if (it->second == texture)
			{
				it = PendingUploads.erase(it);
				AsyncUploadStats.PendingCancellations++;
			}
			else
			{
				++it;
			}
		}
	}

	void RecordTargetUploadStale() { AsyncUploadStats.TargetEpochRejects++; }
	void RecordUploadCompleted() { AsyncUploadStats.JobsCompleted++; }
	const FAsyncTextureUploadStats& GetAsyncUploadStats() const { return AsyncUploadStats; }

	static constexpr std::size_t UploadStagingCapacity = 64u * 1024u * 1024u;

	struct FUploadStagingAllocation
	{
		VulkanBuffer* Buffer = nullptr;
		VkDeviceSize Offset = 0;
		bool Dedicated = false;

		bool IsSet() const { return Buffer != nullptr; }
	};

	struct FUploadStagingRuntimeStats
	{
		uint64_t PersistentBufferAllocations = 0;
		uint64_t DedicatedBufferAllocations = 0;
		uint64_t DedicatedWaits = 0;
	};

	FUploadStagingAllocation StageTextureUpload(const void* pixels, std::size_t size);
	void FinishTextureUpload(const FUploadStagingAllocation& allocation);
	const FRendererUploadStagingStats& GetUploadStagingPlannerStats() const { return UploadStagingPlanner.GetStats(); }
	const FUploadStagingRuntimeStats& GetUploadStagingRuntimeStats() const { return UploadStagingRuntimeStats; }

	FRendererEpochToken GetTextureEpoch() const { return TextureEpoch.Snapshot(); }
	FRendererEpochToken GetLightmapEpoch() const { return LightmapEpoch.Snapshot(); }
	FRendererEpochToken GetLightProbeEpoch() const { return LightProbeEpoch.Snapshot(); }
	FRendererEpochToken GetAsyncUploadEpoch() const { return AsyncUploadEpoch.Snapshot(); }
	bool ValidateTextureEpoch(FRendererEpochToken token) { return TextureEpoch.Validate(token); }
	bool ValidateLightmapEpoch(FRendererEpochToken token) { return LightmapEpoch.Validate(token); }
	bool ValidateLightProbeEpoch(FRendererEpochToken token) { return LightProbeEpoch.Validate(token); }
	bool ValidateAsyncUploadEpoch(FRendererEpochToken token) { return AsyncUploadEpoch.Validate(token); }

	const FRendererEpochStats& GetTextureEpochStats() const { return TextureEpoch.GetStats(); }
	const FRendererEpochStats& GetLightmapEpochStats() const { return LightmapEpoch.GetStats(); }
	const FRendererEpochStats& GetLightProbeEpochStats() const { return LightProbeEpoch.GetStats(); }
	const FRendererEpochStats& GetAsyncUploadEpochStats() const { return AsyncUploadEpoch.GetStats(); }

	static const int PrefiltermapSize = 128;
	static const int IrradiancemapSize = 32;

private:
	void CreateNullTexture();
	void CreateBrdfLutTexture();
	void CreateGamePalette();
	void CreateShadowmap();
	void CreateLightmap();
	void CreateIrradiancemap();
	void CreatePrefiltermap();
	void DownloadTexture(VkTextureImage* texture, uint16_t* buffer);

	void StartWorkerThread();
	void StopWorkerThread();
	void WorkerThreadMain();

	VkPPTexture* GetVkTexture(PPTexture* texture);

	int CreateUploadID(VkHardwareTexture* tex);
	bool CheckUploadID(int id);

	VulkanRenderDevice* fb = nullptr;

	std::list<VkHardwareTexture*> Textures;
	std::list<VkPPTexture*> PPTextures;

	std::unique_ptr<VulkanImage> NullTexture;
	std::unique_ptr<VulkanImageView> NullTextureView;

	std::unique_ptr<VulkanImage> BrdfLutTexture;
	std::unique_ptr<VulkanImageView> BrdfLutTextureView;

	std::unique_ptr<VulkanImage> GamePalette;
	std::unique_ptr<VulkanImageView> GamePaletteView;

	struct SWColormapTexture
	{
		std::unique_ptr<VulkanImage> Texture;
		std::unique_ptr<VulkanImageView> View;
	};
	std::vector<SWColormapTexture> Colormaps;

	FRendererEpoch TextureEpoch;
	FRendererEpoch LightmapEpoch;
	FRendererEpoch LightProbeEpoch;
	FRendererEpoch AsyncUploadEpoch;

	int NextUploadID = 1;
	std::unordered_map<int, VkHardwareTexture*> PendingUploads;
	FAsyncTextureUploadStats AsyncUploadStats;

	std::unique_ptr<VulkanBuffer> UploadStagingBuffer;
	FRendererUploadStagingPlanner UploadStagingPlanner{ UploadStagingCapacity };
	FUploadStagingRuntimeStats UploadStagingRuntimeStats;

	struct
	{
		std::thread Thread;
		std::mutex Mutex;
		std::condition_variable CondVar;
		bool StopFlag = false;
		std::list<std::function<void()>> WorkerTasks;
		std::vector<std::function<void()>> MainTasks;
	} Worker;
};
