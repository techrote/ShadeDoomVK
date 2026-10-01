"""CFX-007 read-only automated recovery gate; does not launch a renderer."""
import csv, ctypes, datetime as dt, json, os, pathlib, shutil, subprocess


def command(args, timeout=20):
    try:
        env = os.environ.copy()
        if args[0].lower() == "powershell":
            env = {k:v for k,v in env.items() if k.lower() != "psmodulepath"}  # Windows PowerShell must use its own module roots.
        r = subprocess.run(args, capture_output=True, text=True, errors="replace", timeout=timeout, env=env)
        return {"command":args,"code":r.returncode,"stdout":r.stdout,"stderr":r.stderr}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"command":args,"code":None,"error":str(e),"stdout":"","stderr":""}


def windows_reasons(data):
    reasons=[]
    adapters=data.get("adapters",[])
    if len(adapters)!=1 or adapters[0].get("Name")!="NVIDIA GeForce GTX 1650 SUPER" or adapters[0].get("ConfigManagerErrorCode")!=0 or adapters[0].get("DriverVersion")!="32.0.16.1692":reasons.append("GPU/expected driver absent or disabled")
    if data.get("games"): reasons.append("previous renderer process still alive")
    if not data.get("explorer") or not all(x.get("Responding") for x in data["explorer"]): reasons.append("desktop Explorer unresponsive")
    for e in data.get("events",[]):
        if "WHEA" in e["Provider"] or "BugCheck" in e["Provider"] or e["Id"]==6008 or ("Kernel-Power" in e["Provider"] and e["Id"]==41):reasons.append("unexpected hardware/OS event: "+str(e["RecordId"]))
    for e in data.get("wer",[]):
        if "BlueScreen" in e.get("Xml",""):reasons.append("BSOD WER event: "+str(e["RecordId"]))
    return reasons


def collect(root, since, driver="616.92"):
    root=pathlib.Path(root)
    script = """$ErrorActionPreference='Stop'
$since=[DateTime]::Parse('__SINCE__').ToUniversalTime()
$adapters=@(Get-CimInstance Win32_VideoController | Select-Object Name,PNPDeviceID,Status,ConfigManagerErrorCode,DriverVersion)
$games=@(Get-Process vkdoom,zdoom -ErrorAction SilentlyContinue | Select-Object Id,Name,Responding)
$explorer=@(Get-Process explorer -ErrorAction SilentlyContinue | Select-Object Id,SessionId,Responding)
$events=@(Get-WinEvent -FilterHashtable @{LogName='System';StartTime=$since} -ErrorAction SilentlyContinue | Where-Object {$_.ProviderName -match 'WHEA|BugCheck|Display|nvlddmkm|Kernel-Power' -or $_.Id -eq 6008} | ForEach-Object {[PSCustomObject]@{Id=$_.Id;RecordId=$_.RecordId;Provider=$_.ProviderName;Time=$_.TimeCreated.ToUniversalTime().ToString('o');Message=$_.Message;Xml=$_.ToXml()}})
$wer=@(Get-WinEvent -FilterHashtable @{LogName='Application';ProviderName='Windows Error Reporting';StartTime=$since} -ErrorAction SilentlyContinue | ForEach-Object {[PSCustomObject]@{Id=$_.Id;RecordId=$_.RecordId;Time=$_.TimeCreated.ToUniversalTime().ToString('o');Message=$_.Message;Xml=$_.ToXml()}})
[PSCustomObject]@{adapters=$adapters;games=$games;explorer=$explorer;events=$events;wer=$wer;boot=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime.ToUniversalTime().ToString('o')} | ConvertTo-Json -Depth 5
""".replace("__SINCE__",since)
    ps=command(["powershell","-NoProfile","-NonInteractive","-Command",script],40)
    gpu=command(["nvidia-smi","--query-gpu=name,pci.device_id,driver_version,temperature.gpu,pstate,clocks.current.graphics,clocks.current.memory,clocks.max.graphics,power.draw,power.limit,memory.total,memory.used","--format=csv,noheader,nounits"])
    vk=command(["vulkaninfo","--summary"])
    reasons=[]; data={}
    if ps["code"]!=0: reasons.append("Windows health query failed")
    else:
        try:data=json.loads(ps["stdout"].lstrip("\ufeff"))
        except ValueError:reasons.append("Windows health output invalid")
    if data: reasons.extend(windows_reasons(data))
    if gpu["code"]!=0:reasons.append("nvidia-smi failed")
    else:
        try:
            rows=list(csv.reader(gpu["stdout"].splitlines()))
            assert len(rows)==1
            row=[x.strip() for x in rows[0]]
            assert row[0]=="NVIDIA GeForce GTX 1650 SUPER" and row[1].lower()=="0x218710de" and row[2]==driver
            assert 0<=float(row[3])<80 and row[4] in tuple("P"+str(i) for i in range(16))
            assert 0<float(row[5])<=float(row[7]) and 0<float(row[6])<=10000
            assert 0<=float(row[8])<=float(row[9])*1.10 and 0<float(row[9])<=150
            assert float(row[10])==4096 and 0<=float(row[11])<=4096
        except (AssertionError,ValueError,IndexError):reasons.append("GPU identity/temperature/clock/power/VRAM anomaly")
    if vk["code"]!=0 or vk["stdout"].count("deviceName")==0 or "NVIDIA GeForce GTX 1650 SUPER" not in vk["stdout"]: reasons.append("Vulkan device enumeration failed")
    desktop={}
    try:
        from ctypes import wintypes as w
        u=ctypes.WinDLL('user32',use_last_error=True)
        u.GetShellWindow.restype=w.HWND
        u.SendMessageTimeoutW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM,w.UINT,w.UINT,ctypes.POINTER(ctypes.c_size_t)]
        u.SendMessageTimeoutW.restype=w.LPARAM
        hwnd=u.GetShellWindow(); result=ctypes.c_size_t()
        desktop={"shell_hwnd":hex(hwnd or 0),"wm_null_responded":bool(hwnd and u.SendMessageTimeoutW(hwnd,0,0,0,2,2000,ctypes.byref(result)))}
        if not desktop["wm_null_responded"]:reasons.append("desktop shell WM_NULL timeout")
    except (OSError,AttributeError) as e: reasons.append("desktop session probe failed: "+str(e))
    free=shutil.disk_usage(root).free
    if free<20*1024**3:reasons.append("capture storage below 20 GiB")
    probe=root/".storage-probe"
    try:
        probe.write_bytes(b'CFX007 storage verification');assert probe.read_bytes()==b'CFX007 storage verification';probe.unlink()
    except (OSError,AssertionError):reasons.append("storage write/read failed")
    return {"schema":"cfx-007-recovery-v1","at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"since_utc":since,"pass":not reasons,"stop_reasons":reasons,"windows":data,"desktop":desktop,"gpu_probe":gpu,"vulkan_probe":vk,"windows_query":ps,"storage_free_bytes":free,"physical_pixel_integrity":"not observed; routine human checkpoint waived by owner"}
