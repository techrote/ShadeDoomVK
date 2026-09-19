#pragma once

#include <cstdint>

enum class HWRenderContextType : uint8_t
{
	MainView,
	CameraTexture,
	LightProbe,
	SavePicture,
	Portal,
};

inline const char* HWRenderContextTypeName(HWRenderContextType type)
{
	switch (type)
	{
	case HWRenderContextType::MainView: return "main";
	case HWRenderContextType::CameraTexture: return "camera-texture";
	case HWRenderContextType::LightProbe: return "light-probe";
	case HWRenderContextType::SavePicture: return "save-picture";
	case HWRenderContextType::Portal: return "portal";
	}
	return "unknown";
}

struct HWRenderContext
{
	HWRenderContextType type = HWRenderContextType::MainView;
	HWRenderContextType rootType = HWRenderContextType::MainView;
	uint64_t epoch = 0;
	uint64_t identity = 0;
	uint64_t parentIdentity = 0;
	uint32_t recursionDepth = 0;
	int probeFace = -1;
	int eyeIndex = 0;
	bool lineMirror = false;
	bool planeMirror = false;
	bool mirrored = false;
	bool mainView = false;
	bool postprocessEligible = false;
	bool historyEligible = false;

	bool IsPortal() const { return type == HWRenderContextType::Portal; }
	bool HasParent() const { return parentIdentity != 0; }
};

// Renderer scene submission is sequential at this boundary. The sequence gives
// each top-level RenderViewpoint invocation an epoch and each scene pass within
// that invocation (stereo eye or recursive portal) an identity. Persistent
// consumers must use the pair (epoch, identity), not identity alone.
class HWRenderContextSequence
{
public:
	uint64_t BeginEpoch()
	{
		++epoch;
		if (epoch == 0) ++epoch;
		nextIdentity = 0;
		return epoch;
	}

	uint64_t CurrentEpoch() const { return epoch; }

	uint64_t AllocateIdentity()
	{
		if (epoch == 0) BeginEpoch();
		++nextIdentity;
		if (nextIdentity == 0) ++nextIdentity;
		return nextIdentity;
	}

private:
	uint64_t epoch = 0;
	uint64_t nextIdentity = 0;
};

inline HWRenderContextSequence& HWRenderContextRuntimeSequence()
{
	static HWRenderContextSequence sequence;
	return sequence;
}

inline HWRenderContextType ClassifyHWRenderContext(bool mainview, bool toscreen, int probeFace)
{
	if (probeFace >= 0) return HWRenderContextType::LightProbe;
	if (mainview && toscreen) return HWRenderContextType::MainView;
	if (mainview) return HWRenderContextType::SavePicture;
	return HWRenderContextType::CameraTexture;
}

inline HWRenderContext MakeHWRootRenderContext(HWRenderContextType type, uint64_t epoch, uint64_t identity, int probeFace, int eyeIndex)
{
	HWRenderContext context;
	context.type = type;
	context.rootType = type;
	context.epoch = epoch;
	context.identity = identity;
	context.probeFace = type == HWRenderContextType::LightProbe ? probeFace : -1;
	context.eyeIndex = eyeIndex;
	context.mainView = type == HWRenderContextType::MainView;
	// Preserve the inherited mainview distinction: save pictures run the same
	// postprocess route, but they are not eligible for persistent main history.
	context.postprocessEligible = type == HWRenderContextType::MainView || type == HWRenderContextType::SavePicture;
	context.historyEligible = type == HWRenderContextType::MainView;
	return context;
}

inline HWRenderContext MakeHWPortalRenderContext(const HWRenderContext& parent, uint64_t identity, bool lineMirror, bool planeMirror)
{
	HWRenderContext context;
	context.type = HWRenderContextType::Portal;
	context.rootType = parent.rootType;
	context.epoch = parent.epoch;
	context.identity = identity;
	context.parentIdentity = parent.identity;
	context.recursionDepth = parent.recursionDepth + 1;
	context.probeFace = parent.probeFace;
	context.eyeIndex = parent.eyeIndex;
	context.lineMirror = lineMirror;
	context.planeMirror = planeMirror;
	context.mirrored = lineMirror != planeMirror;
	// Portal passes deliberately never claim main/postprocess/history ownership.
	context.mainView = false;
	context.postprocessEligible = false;
	context.historyEligible = false;
	return context;
}
