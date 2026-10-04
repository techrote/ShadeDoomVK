#pragma once

#include "zstring.h"
#include <cstddef>
#include <string>

class VulkanRenderDevice;
class VulkanImage;
class VulkanImageView;
class VkTextureImage;
class VkShaderKey;
class VkPipelineKey;
class VkRenderPassKey;
class FCanvasTexture;

// Explicit PF020 fixture evidence only. No normal-path allocation or cache
// redirection; recorded keys are the actual arguments to production map routes.
namespace Pf020VulkanDiagnostics
{
FString CacheFilename(const char* leaf);
void CacheFile(const char* kind, const char* stage, const FString& filename, bool operationCompleted, size_t entries = 0);
void ShaderLookup(const VkShaderKey& key, bool generalized, bool hit, const char* route);
void ShaderBinaryLookup(const char* actualSourceChecksum, bool hit);
void PipelineLookup(const VkPipelineKey& key, const VkRenderPassKey& pass, const char* route, bool hit, bool ready);
void WorkerScheduled(bool precache);
void WorkerStarted();
void WorkerFinished(bool failed);
void MainTaskScheduled();
void MainTaskCompleted();
void ProbeFaceCompleted(int side, VulkanImageView* actualAttachment);
void ProbeCompleted(VulkanRenderDevice* fb, VulkanImage* image, VulkanImageView* cubeView);
void CameraCompleted(VulkanRenderDevice* fb, VkTextureImage* image, FCanvasTexture* texture);
}
