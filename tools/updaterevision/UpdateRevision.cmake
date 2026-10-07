#!/usr/bin/cmake -P
# Public domain. Query this source checkout, including linked worktrees, rather
# than the caller's working directory. Archives explicitly report unknown state.

if(NOT CMAKE_ARGC EQUAL 4)
	message(FATAL_ERROR "Usage: cmake -P UpdateRevision.cmake <path to gitinfo.h>")
endif()
get_filename_component(ScriptDir "${CMAKE_SCRIPT_MODE_FILE}" DIRECTORY)
get_filename_component(SourceRoot "${ScriptDir}/../.." ABSOLUTE)
get_filename_component(OutputFile "${CMAKE_ARGV3}" ABSOLUTE)
set(Hash "0")
set(Tag "<unknown version>")
set(Timestamp "")
set(State "unknown")

# Do not attribute an archive inside another repository to that parent repo.
if(EXISTS "${SourceRoot}/.git")
	execute_process(COMMAND git -C "${SourceRoot}" rev-parse --verify HEAD
		RESULT_VARIABLE HashError OUTPUT_VARIABLE RepoHash
		OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
	execute_process(COMMAND git -C "${SourceRoot}" describe --tags --always --dirty=-m
		RESULT_VARIABLE TagError OUTPUT_VARIABLE RepoTag
		OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
	execute_process(COMMAND git -C "${SourceRoot}" show -s --format=%ai HEAD
		RESULT_VARIABLE TimeError OUTPUT_VARIABLE RepoTime
		OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
	execute_process(COMMAND git -C "${SourceRoot}" status --porcelain --untracked-files=normal
		RESULT_VARIABLE StateError OUTPUT_VARIABLE RepoStatus
		OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
	if(HashError EQUAL 0 AND TagError EQUAL 0 AND TimeError EQUAL 0 AND StateError EQUAL 0)
		set(Hash "${RepoHash}")
		set(Tag "${RepoTag}")
		set(Timestamp "${RepoTime}")
		if(RepoStatus STREQUAL "")
			set(State "clean")
		else()
			set(State "modified")
		endif()
	endif()
endif()

# Git tags can contain quotes and backslashes; keep them data in the C++ header.
foreach(Field Hash Tag Timestamp State)
	string(REPLACE "\\" "\\\\" ${Field} "${${Field}}")
	string(REPLACE "\"" "\\\"" ${Field} "${${Field}}")
endforeach()
get_filename_component(OutputDir "${OutputFile}" DIRECTORY)
file(MAKE_DIRECTORY "${OutputDir}")
# configure_file leaves unchanged bytes untouched, but still updates dirty/tag
# state at the same commit. A hash-only short circuit would retain stale state.
configure_file("${ScriptDir}/gitinfo.h.in" "${OutputFile}" @ONLY)
message(STATUS "ShadeDoomVK build identity: ${Hash} (${State}); ${OutputFile}")
