"""Native Windows owned handles, suspended creation and read-only file locks.

No PID/name based termination and no job kill-on-close are used. Handle identity
is rechecked before every termination. This module imports on other OSes so the
policy tests do not pretend that a synthetic backend qualifies Windows APIs.
"""
from __future__ import annotations

import ctypes as c
from ctypes import wintypes as w
import hashlib
import os
from pathlib import Path
import subprocess
import time

from .common import Stop, normalized, require, stream_digest


if os.name == "nt":
    k = c.WinDLL("kernel32", use_last_error=True)
    n = c.WinDLL("ntdll")

    def signature(name, restype, argtypes):
        function = getattr(k, name)
        function.restype, function.argtypes = restype, argtypes
        return function

    close = signature("CloseHandle", w.BOOL, [w.HANDLE])
    open_process = signature("OpenProcess", w.HANDLE, [w.DWORD, w.BOOL, w.DWORD])
    get_times = signature("GetProcessTimes", w.BOOL, [w.HANDLE, c.POINTER(w.FILETIME), c.POINTER(w.FILETIME), c.POINTER(w.FILETIME), c.POINTER(w.FILETIME)])
    get_path = signature("QueryFullProcessImageNameW", w.BOOL, [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)])
    get_pid = signature("GetProcessId", w.DWORD, [w.HANDLE])
    get_exit = signature("GetExitCodeProcess", w.BOOL, [w.HANDLE, c.POINTER(w.DWORD)])
    terminate = signature("TerminateProcess", w.BOOL, [w.HANDLE, w.UINT])
    wait = signature("WaitForSingleObject", w.DWORD, [w.HANDLE, w.DWORD])
    resume_thread = signature("ResumeThread", w.DWORD, [w.HANDLE])
    create_file = signature("CreateFileW", w.HANDLE, [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p, w.DWORD, w.DWORD, w.HANDLE])
    read_file = signature("ReadFile", w.BOOL, [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p])
    seek = signature("SetFilePointerEx", w.BOOL, [w.HANDLE, c.c_longlong, c.POINTER(c.c_longlong), w.DWORD])
    create_job = signature("CreateJobObjectW", w.HANDLE, [c.c_void_p, w.LPCWSTR])
    assign_job = signature("AssignProcessToJobObject", w.BOOL, [w.HANDLE, w.HANDLE])
    query_job = signature("QueryInformationJobObject", w.BOOL, [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.POINTER(w.DWORD)])
    snapshot_processes = signature("CreateToolhelp32Snapshot", w.HANDLE, [w.DWORD, w.DWORD])

    class PROCESSENTRY(c.Structure):
        _fields_ = [("size", w.DWORD), ("usage", w.DWORD), ("pid", w.DWORD), ("heap", c.c_size_t),
                    ("module", w.DWORD), ("threads", w.DWORD), ("parent_pid", w.DWORD),
                    ("priority", w.LONG), ("flags", w.DWORD), ("name", w.WCHAR * 260)]
    first_process = signature("Process32FirstW", w.BOOL, [w.HANDLE, c.POINTER(PROCESSENTRY)])
    next_process = signature("Process32NextW", w.BOOL, [w.HANDLE, c.POINTER(PROCESSENTRY)])
    enum_modules = signature("K32EnumProcessModulesEx", w.BOOL, [w.HANDLE, c.POINTER(w.HMODULE), w.DWORD, c.POINTER(w.DWORD), w.DWORD])
    module_path = signature("K32GetModuleFileNameExW", w.DWORD, [w.HANDLE, w.HMODULE, w.LPWSTR, w.DWORD])
    change_first = signature("FindFirstChangeNotificationW", w.HANDLE, [w.LPCWSTR, w.BOOL, w.DWORD])
    change_close = signature("FindCloseChangeNotification", w.BOOL, [w.HANDLE])
    volume_path = signature("GetVolumePathNameW", w.BOOL, [w.LPCWSTR, w.LPWSTR, w.DWORD])
    volume_info = signature("GetVolumeInformationW", w.BOOL, [w.LPCWSTR,w.LPWSTR,w.DWORD,c.c_void_p,c.c_void_p,c.c_void_p,w.LPWSTR,w.DWORD])
    drive_type = signature("GetDriveTypeW", w.UINT, [w.LPCWSTR])
    class FILEINFO(c.Structure):
        _fields_ = [("attributes",w.DWORD),("created",w.FILETIME),("accessed",w.FILETIME),("written",w.FILETIME),
                    ("volume",w.DWORD),("size_high",w.DWORD),("size_low",w.DWORD),("links",w.DWORD),
                    ("index_high",w.DWORD),("index_low",w.DWORD)]
    file_info = signature("GetFileInformationByHandle",w.BOOL,[w.HANDLE,c.POINTER(FILEINFO)])

    class BASIC(c.Structure):
        _fields_ = [("Reserved1", c.c_void_p), ("Peb", c.c_void_p),
                    ("Reserved2", c.c_void_p * 2), ("UniquePid", c.c_size_t), ("ParentPid", c.c_size_t)]

    n.NtQueryInformationProcess.restype = c.c_long
    n.NtQueryInformationProcess.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.ULONG, c.POINTER(w.ULONG)]

    class OSVERSION(c.Structure):
        _fields_=[("size",w.DWORD),("major",w.DWORD),("minor",w.DWORD),("build",w.DWORD),
                  ("platform",w.DWORD),("service_pack",w.WCHAR*128)]

    class TIMEOFDAY(c.Structure):
        # Reviewed native-layout compatibility assumption: Microsoft's public
        # SystemTimeOfDayInformation buffer is opaque and may change by OS.
        # Never accept a changed size/status or fall back to a guessed boot time.
        _fields_=[("boot",c.c_longlong),("current",c.c_longlong),("timezone_bias",c.c_longlong),
                  ("timezone_id",w.ULONG),("reserved",w.ULONG),
                  ("boot_bias",c.c_ulonglong),("sleep_bias",c.c_ulonglong)]

    n.RtlGetVersion.restype=c.c_long
    n.RtlGetVersion.argtypes=[c.POINTER(OSVERSION)]
    n.NtQuerySystemInformation.restype=c.c_long
    n.NtQuerySystemInformation.argtypes=[c.c_int,c.c_void_p,w.ULONG,c.POINTER(w.ULONG)]


def checked(value, message):
    if not value:
        raise Stop(message + ": " + str(c.WinError(c.get_last_error())))
    return value


def platform_check():
    require(os.name == "nt", "Native physical supervisor requires Windows")


def host_identity():
    """Read-only OS/boot identity; no subprocess, Vulkan or fallback reader."""
    platform_check()
    version=OSVERSION();version.size=c.sizeof(version)
    status=n.RtlGetVersion(c.byref(version))
    if status!=0:
        error=Stop("Native OS version read failed; NTSTATUS="+str(status))
        error.evidence={"reader":"native-host-identity","operation":"RtlGetVersion","ntstatus":status}
        raise error
    time_of_day=TIMEOFDAY();returned=w.ULONG()
    require(c.sizeof(time_of_day)==48,"Unsupported native boot-time layout")
    status=n.NtQuerySystemInformation(3,c.byref(time_of_day),c.sizeof(time_of_day),c.byref(returned))
    if status!=0 or returned.value!=48:
        error=Stop("Native boot-time read/layout failed; NTSTATUS="+str(status)+" returned_size="+str(returned.value))
        error.evidence={"reader":"native-host-identity","operation":"NtQuerySystemInformation(3)",
                        "ntstatus":status,"returned_size":returned.value,"expected_size":48}
        raise error
    if not 116444736000000000 <= time_of_day.boot <= time_of_day.current:
        error=Stop("Native boot time is invalid/future")
        error.evidence={"reader":"native-host-identity","boot_time_100ns":time_of_day.boot,
                        "current_time_100ns":time_of_day.current}
        raise error
    return {"schema":"physical-supervisor/host-v1","native_pointer_bits":c.sizeof(c.c_void_p)*8,
            "os_major":version.major,"os_minor":version.minor,"os_build":version.build,"os_platform_id":version.platform,
            "service_pack":version.service_pack,"boot_time_100ns":time_of_day.boot}


def creation(handle):
    values = [w.FILETIME() for _ in range(4)]
    checked(get_times(handle, *(c.byref(item) for item in values)), "GetProcessTimes")
    return (values[0].dwHighDateTime << 32) | values[0].dwLowDateTime


class FileLock:
    """Deny writers and deletion while permitting renderer/DLL read opens."""
    def __init__(self, row):
        platform_check()
        self.row = row
        self.handle = create_file(row["path"], 0x80000000, 1, None, 3, 0x80, None)
        require(self.handle not in (None, c.c_void_p(-1).value), "Cannot lock pinned asset")
        try:
            self.verify()
        except BaseException:
            self.close()
            raise

    def verify(self):
        checked(seek(self.handle, 0, None, 0), "Pinned file seek")
        hasher, size = hashlib.sha256(), 0
        buffer = c.create_string_buffer(1024 * 1024)
        while True:
            count = w.DWORD()
            checked(read_file(self.handle, buffer, len(buffer), c.byref(count), None), "Pinned file read")
            if not count.value:
                break
            hasher.update(buffer.raw[:count.value])
            size += count.value
        require(size == self.row["size"] and hasher.hexdigest() == self.row["sha256"], "Locked file identity changed")

    def close(self):
        if self.handle:
            close(self.handle)
            self.handle = None


class RootGuard:
    """Terminal native invalidation, established before any audited generation.

    Notifications exclude the watched root itself, so retained no-delete
    handles and path/file-ID/reparse checks also cover every root ancestor.
    This policy supports local fixed NTFS only; it never resets a signal.
    """
    def __init__(self, packet):
        from .common import linklike
        platform_check()
        self.directories, self.changes = [], []
        self.failure = None;self.closed=False
        try:
            paths = set()
            for row in packet["runtime_roots"]:
                root = Path(row["path"])
                for path in (root, *root.parents):
                    require(not linklike(path), "Root guard encountered reparse point")
                    paths.add(path)
                volume=c.create_unicode_buffer(32768)
                checked(volume_path(str(root),volume,len(volume)),"Read guarded volume")
                filesystem=c.create_unicode_buffer(256)
                checked(volume_info(volume.value,None,0,None,None,None,filesystem,len(filesystem)),"Read guarded filesystem")
                require(drive_type(volume.value)==3 and filesystem.value=="NTFS", "Root guard requires local fixed NTFS")
            for path in sorted(paths):
                handle=create_file(str(path),0x80,3,None,3,0x02000000,None)
                require(handle not in (None,c.c_void_p(-1).value),"Cannot retain guarded directory")
                try:identity=self._identity(handle)
                except BaseException:
                    close(handle)
                    raise
                self.directories.append((path,handle,identity))
            for row in packet["runtime_roots"]:
                handle=change_first(row["path"],True,0x1|0x2|0x4|0x8|0x10|0x100)
                require(handle not in (None,c.c_void_p(-1).value),"Cannot establish runtime change notification")
                self.changes.append(handle)
            self.check()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _identity(handle):
        info=FILEINFO()
        checked(file_info(handle,c.byref(info)),"Read guarded directory identity")
        require(info.attributes & 0x10 and not info.attributes & 0x400,"Guarded directory became reparse point")
        return (info.volume,info.index_high,info.index_low)

    def check(self):
        from .common import linklike
        require(not self.closed,"Root guard is closed")
        require(self.failure is None,self.failure or "Root guard invalid")
        try:
            for handle in self.changes:
                require(wait(handle,0)==258,"Runtime change notification signaled/failed; proof invalidated")
            for path,handle,expected in self.directories:
                require(not linklike(path),"Guarded root/ancestor became reparse point")
                current=create_file(str(path),0x80,3,None,3,0x02000000,None)
                require(current not in (None,c.c_void_p(-1).value),"Cannot re-open guarded directory binding")
                try:require(self._identity(current)==expected,"Guarded directory path identity changed")
                finally:close(current)
                require(self._identity(handle)==expected,"Guarded directory handle identity changed")
        except BaseException as error:
            self.failure=str(error)
            raise

    def close(self):
        for handle in self.changes:change_close(handle)
        for _,handle,_ in self.directories:close(handle)
        self.changes,self.directories=[],[]
        self.closed=True


class Process:
    def __init__(self, handle, thread=None, pid=None):
        self.handle, self.thread = handle, thread
        self.pid = pid or get_pid(handle)
        self.parent_handle = None

    @classmethod
    def open(cls, pid):
        platform_check()
        return cls(checked(open_process(0x1000 | 0x0400 | 0x00100000 | 1 | 0x10, False, pid), "Open owned process"), pid=pid)

    @classmethod
    def spawn(cls, argv, cwd, stdout, stderr, *, env=None, job=None, before_create=None):
        platform_check()
        import _winapi
        import msvcrt
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESTDHANDLES
        with open(os.devnull, "rb") as stdin:
            handles = [msvcrt.get_osfhandle(stream.fileno()) for stream in (stdin, stdout, stderr)]
            for handle in handles:
                os.set_handle_inheritable(handle, True)
            startup.hStdInput, startup.hStdOutput, startup.hStdError = handles
            startup.lpAttributeList = {"handle_list": handles}
            try:
                executable=str(Path(argv[0]).resolve(strict=True))
                command_line=subprocess.list2cmdline(argv)
                working_directory=str(cwd)
                not_after=before_create() if before_create else None
                create_attempt=time.monotonic()
                require(not_after is None or create_attempt<not_after,"Native creation proof expired before call attempt")
                handle, thread, pid, _ = _winapi.CreateProcess(executable,
                    command_line, None, None, True, 0x4 | 0x200, env, working_directory, startup)
            finally:
                for item in handles:
                    os.set_handle_inheritable(item, False)
        result = cls(handle, thread, pid)
        result.create_native_call_attempt_monotonic=create_attempt
        # Retain the suspended owned handle on assign failure so caller can
        # record/verify/terminate it. No renderer code runs before assignment.
        if job:
            try:
                job.assign(result)
            except BaseException as error:
                result.assignment_error = str(error)
        return result

    def identity(self):
        require(get_pid(self.handle) == self.pid, "Owned process handle/PID mismatch")
        length = w.DWORD(32768)
        buffer = c.create_unicode_buffer(length.value)
        checked(get_path(self.handle, 0, buffer, c.byref(length)), "Owned executable path")
        basic = BASIC()
        require(n.NtQueryInformationProcess(self.handle, 0, c.byref(basic), c.sizeof(basic), None) == 0,
                "Cannot authenticate parent PID")
        if self.parent_handle is None:
            self.parent_handle = checked(open_process(0x1000, False, basic.ParentPid), "Cannot authenticate parent creation time")
        require(get_pid(self.parent_handle) == basic.ParentPid, "Retained parent handle/PID mismatch")
        parent_creation = creation(self.parent_handle)
        path = normalized(buffer.value)
        with open(path, "rb") as stream:
            sha = stream_digest(stream)
        return {"pid": self.pid, "creation_ticks": creation(self.handle), "path": path,
                "sha256": sha, "parent_pid": basic.ParentPid, "parent_creation_ticks": parent_creation}

    def verify(self, expected):
        require(self.identity() == expected, "Owned process identity/creation/parent/path/hash mismatch; no termination")

    def poll(self):
        status = wait(self.handle, 0)
        require(status in (0, 258), "Process wait failed")
        if status == 258:
            return None
        value = w.DWORD()
        checked(get_exit(self.handle, c.byref(value)), "Process exit read")
        return value.value

    def resume(self, expected, *, before_resume=None):
        self.verify(expected)
        require(self.thread is not None, "No owned primary thread")
        not_after=before_resume() if before_resume else None
        resume_attempt=time.monotonic()
        require(not_after is None or resume_attempt<not_after,"Native resume proof expired before call attempt")
        self.resume_native_call_attempt_monotonic=resume_attempt
        require(resume_thread(self.thread) == 1, "Primary thread was not suspended exactly once")
        close(self.thread)
        self.thread = None

    def kill(self, expected):
        if self.poll() is not None:
            return False
        try:self.verify(expected)
        except BaseException:
            if self.exited_owned(expected):return False
            raise
        checked(terminate(self.handle, 0xE0000001), "Terminate owned authenticated handle")
        require(wait(self.handle, 5000) == 0, "Owned termination did not complete")
        return True

    def exited_owned(self, expected):
        """Classify only a positively exited SAME held object; never terminate.

        Windows can tear down image-path information between an active poll
        and identity query. No live/inaccessible object receives this exception.
        """
        return (self.poll() is not None and get_pid(self.handle)==self.pid==expected["pid"] and
                creation(self.handle)==expected["creation_ticks"])

    def modules(self, expected):
        self.verify(expected)
        handles=(w.HMODULE*4096)()
        needed=w.DWORD()
        checked(enum_modules(self.handle,handles,c.sizeof(handles),c.byref(needed),3),"Enumerate actual owned target modules")
        require(needed.value <= c.sizeof(handles) and needed.value % c.sizeof(w.HMODULE)==0,"Module inventory truncated/invalid")
        paths=[]
        for handle in handles[:needed.value//c.sizeof(w.HMODULE)]:
            buffer=c.create_unicode_buffer(32768)
            count=module_path(self.handle,handle,buffer,len(buffer))
            require(0 < count < len(buffer)-1,"Cannot identify actual owned module path")
            paths.append(normalized(buffer.value))
        require(paths and len(paths)==len(set(paths)),"Missing/duplicate actual module inventory")
        return sorted(paths)

    def close(self):
        if self.parent_handle:
            close(self.parent_handle)
            self.parent_handle = None
        if self.thread:
            close(self.thread)
            self.thread = None
        if self.handle:
            close(self.handle)
            self.handle = None


class Job:
    """Containment inventory only. No kill-on-close identity bypass."""
    def __init__(self):
        platform_check()
        self.handle = checked(create_job(None, None), "Create containment job")

    def assign(self, process):
        checked(assign_job(self.handle, process.handle), "Assign containment job")

    def pids(self):
        # A bounded array overflow is a fault, never a truncated inventory.
        class PIDS(c.Structure):
            _fields_ = [("assigned", w.DWORD), ("count", w.DWORD), ("pids", c.c_size_t * 256)]
        value = PIDS()
        checked(query_job(self.handle, 3, c.byref(value), c.sizeof(value), None), "Read containment inventory")
        require(value.assigned == value.count and value.count <= 256, "Job inventory truncated")
        return set(value.pids[:value.count])

    def close(self):
        close(self.handle)


def reject_unowned_renderer(renderer, allowed=()):
    """Name selects inspection candidates only; never terminates any process.

    Inaccessible or unowned same-name images are a STOP. Full path, bytes,
    creation ticks and parent identity must match an already held owner record.
    """
    platform_check()
    snapshot = snapshot_processes(2, 0)
    require(snapshot not in (None, c.c_void_p(-1).value), "Cannot enumerate possible concurrent renderers")
    expected = {row["pid"]: row for row in allowed}
    try:
        row = PROCESSENTRY()
        row.size = c.sizeof(row)
        ok = first_process(snapshot, c.byref(row))
        require(ok, "Cannot begin process inventory")
        while ok:
            if row.name.casefold() == Path(renderer).name.casefold():
                require(row.pid in expected, "Existing/unowned renderer candidate; no termination")
                process = Process.open(row.pid)
                try:
                    if process.poll() is None:
                        try:process.verify(expected[row.pid])
                        except BaseException:
                            if not process.exited_owned(expected[row.pid]):raise
                    else:
                        # An already owned, held object can be observed during
                        # image teardown when QueryFullProcessImageName fails.
                        # No executable remains active; still reject PID reuse.
                        require(creation(process.handle) == expected[row.pid]["creation_ticks"], "Exited candidate PID reused")
                finally:
                    process.close()
            ok = next_process(snapshot, c.byref(row))
        require(c.get_last_error() == 18, "Process inventory ended ambiguously")
    finally:
        close(snapshot)
