#include "version.h"
#if defined(WIN32)

#define WIN32_MEAN_AND_LEAN
#include <Windows.h>

int I_ToolMain(HINSTANCE hInstance, HINSTANCE nothing, LPWSTR cmdline, int nCmdShow);

int wmain(int argc, wchar_t** argv)
{
	if (argc == 2 && PrintVersionIfRequested(argv[1]))
		return 0;
	return I_ToolMain(GetModuleHandle(0), 0, GetCommandLineW(), SW_SHOW);
}

#else

int I_ToolMain(int argc, char** argv);

int main(int argc, char** argv)
{
	if (argc == 2 && PrintVersionIfRequested(argv[1]))
		return 0;
	return I_ToolMain(argc, argv);
}

#endif
