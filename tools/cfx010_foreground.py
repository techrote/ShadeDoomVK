"""Opt-in host focus proof, one focus request, bounded observations; no input synthesis."""
import ctypes
from ctypes import wintypes
import platform
import threading
import time


class WindowsForeground:
    def __init__(self):
        if platform.system() != 'Windows': raise OSError('Windows foreground proof unavailable')
        self.api = ctypes.WinDLL('user32', use_last_error=True)
        self.callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self.api.EnumWindows.argtypes = [self.callback, wintypes.LPARAM]
        self.api.GetForegroundWindow.restype = wintypes.HWND
        self.api.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        for name in ('SetForegroundWindow', 'IsWindow', 'IsWindowVisible', 'IsIconic'):
            getattr(self.api, name).argtypes = [wintypes.HWND]
        self.api.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        class GUI(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('flags', wintypes.DWORD),
                ('hwndActive', wintypes.HWND), ('hwndFocus', wintypes.HWND), ('hwndCapture', wintypes.HWND),
                ('hwndMenuOwner', wintypes.HWND), ('hwndMoveSize', wintypes.HWND), ('hwndCaret', wintypes.HWND), ('rcCaret', wintypes.RECT)]
        self.GUI = GUI
        self.api.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUI)]
        self.event_callback = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD,
            wintypes.HWND, wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
        self.api.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE,
            self.event_callback, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
        self.api.SetWinEventHook.restype = wintypes.HANDLE
        self.api.UnhookWinEvent.argtypes = [wintypes.HANDLE]
        self.api.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                       wintypes.UINT, wintypes.UINT, wintypes.UINT]
        self.api.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        self.api.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.GetTickCount64.restype = ctypes.c_ulonglong

    def owner(self, window):
        owner = wintypes.DWORD()
        thread = self.api.GetWindowThreadProcessId(window, ctypes.byref(owner))
        return int(owner.value), int(thread)

    def windows(self, pid):
        found = []
        def visit(window, unused):
            name = ctypes.create_unicode_buffer(128)
            self.api.GetClassNameW(window, name, len(name))
            if self.owner(window)[0] == pid and name.value == 'MainWindow' and self.api.IsWindowVisible(window):
                found.append(int(window))
            return True
        callback = self.callback(visit)
        if not self.api.EnumWindows(callback, 0): raise OSError('EnumWindows failed')
        return found

    def activate(self, window): return bool(self.api.SetForegroundWindow(window))
    def foreground(self): return int(self.api.GetForegroundWindow() or 0)

    def install_events(self, pid, receive):
        def dispatch(hook, event, window, obj, child, thread, stamp):
            delivered = int(time.time()*1000)
            elapsed = (self.kernel.GetTickCount64() - stamp) & 0xffffffff
            receive(int(event), int(window or 0), delivered - elapsed, delivered)
        callback = self.event_callback(dispatch)
        # Out-of-context callbacks run on this monitoring thread; no process injection.
        hooks = [self.api.SetWinEventHook(3, 3, None, callback, 0, 0, 0),
                 self.api.SetWinEventHook(10, 11, None, callback, pid, 0, 0)]
        if not all(hooks):
            for hook in hooks:
                if hook: self.api.UnhookWinEvent(hook)
            raise OSError('foreground/move-size WinEvent hook unavailable')
        return hooks, callback  # retain the native callback until unhooked

    def pump_events(self):
        message = wintypes.MSG()
        # Bounded dispatch; any pathological backlog prevents a complete proof.
        for unused in range(64):
            if not self.api.PeekMessageW(ctypes.byref(message), None, 0, 0, 1): return
            self.api.TranslateMessage(ctypes.byref(message)); self.api.DispatchMessageW(ctypes.byref(message))
        raise OSError('foreground event backlog exceeds bounded dispatch')

    def remove_events(self, hooks):
        removed = [self.api.UnhookWinEvent(hook) for hook in hooks[0]]
        if not all(removed):
            raise OSError('foreground WinEvent hook cleanup failed')

    def inspect(self, window):
        _, thread = self.owner(window)
        gui = self.GUI(); gui.cbSize = ctypes.sizeof(gui)
        ok = bool(self.api.GetGUIThreadInfo(thread, ctypes.byref(gui)))
        return {'alive': bool(self.api.IsWindow(window)), 'visible': bool(self.api.IsWindowVisible(window)),
                'minimized': bool(self.api.IsIconic(window)), 'thread_info_ok': ok,
                'in_move_size': bool(gui.flags & 2) or gui.hwndMoveSize == window}


class ForegroundSession:
    def __init__(self, proc, *, api=None, seconds=10):
        self.proc = proc; self.api = api if api is not None else WindowsForeground()
        self.stop = threading.Event(); self.thread = None
        self.ready = threading.Event()
        self.report = {'schema': 'cfx-010-foreground-v1', 'pid': proc.pid, 'requested': True,
                       'verified': False, 'focus_requests': 0, 'checks': 0, 'events': [], 'omitted_events': 0}
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and proc.poll() is None:
            windows = self.api.windows(proc.pid)
            if len(windows) > 1: self.report['reason'] = 'ambiguous child MainWindow'; return
            if windows:
                self.window = windows[0]
                self.thread = threading.Thread(target=self.monitor, daemon=True); self.thread.start()
                if not self.ready.wait(timeout=1) or not self.report.get('event_hooks_installed'):
                    self.report['reason'] = 'bounded foreground event-hook startup failed'; return
                self.report.update(hwnd=hex(self.window), focus_requests=1,
                                   set_foreground_returned=self.api.activate(self.window))
                self.settle_readback(deadline)
                if not self.report['verified']: self.report['reason'] = 'one foreground request/readback did not settle within 250ms'; return
                return
            self.stop.wait(.05)
        self.report['reason'] = 'child MainWindow not ready within bounded startup interval'

    def settle_readback(self, startup_deadline):
        """Observe a single request; never repeat activation or synthesize input."""
        deadline = min(startup_deadline, time.monotonic() + .25)
        self.report.update(readback_limit_ms=250, readback_observations=[])
        for unused in range(26):
            if self.proc.poll() is not None: return
            foreground = self.api.foreground(); owner = self.api.owner(foreground)[0]
            state = self.api.inspect(self.window); window_owner = self.api.owner(self.window)[0]
            observation = {'ms': int(time.time()*1000), 'foreground_hwnd': hex(foreground), 'foreground_pid': owner,
                           'window_pid': window_owner, **state}
            self.report['readback_observations'].append(observation)
            self.report.update(foreground_hwnd=hex(foreground), foreground_pid=owner)
            if (foreground == self.window and owner == self.proc.pid and window_owner == self.proc.pid and
                    state['alive'] and state['visible'] and state['thread_info_ok'] and
                    not state['minimized'] and not state['in_move_size']):
                self.report.update(verified_at_ms=observation['ms'], verified=True); return
            remaining = deadline - time.monotonic()
            if remaining <= 0: return
            self.stop.wait(min(.01, remaining))

    def record(self, event):
        if len(self.report['events']) < 16: self.report['events'].append(event)
        else: self.report['omitted_events'] += 1

    def receive_event(self, event, window, occurred_ms=None, delivered_ms=None):
        if not self.report['verified']: return
        # Foreground switches and entering a titlebar move/size loop remain evidence
        # even when focus is restored before the next sampled GUI-thread check.
        if event == 3 and window == self.window: return
        if event not in (3, 10): return
        state = self.api.inspect(self.window)
        now = int(time.time()*1000)
        self.record({'ms': now if occurred_ms is None else occurred_ms, 'delivered_ms': now if delivered_ms is None else delivered_ms,
                     'kind': 'native-foreground-change' if event == 3 else 'focus-or-modal-interference',
                     'native_event': event, 'event_hwnd': hex(window), **state})

    def monitor(self):
        hooks = None
        try:
            hooks = self.api.install_events(self.proc.pid, self.receive_event)
            self.report['event_hooks_installed'] = True; self.ready.set()
            while not self.stop.wait(.05) and self.proc.poll() is None:
                self.api.pump_events()
                if not self.report['verified']: continue
                state = self.api.inspect(self.window); self.report['checks'] += 1
                owner = self.api.owner(self.window)[0]
                event = {'ms': int(time.time()*1000), **state, 'foreground_hwnd': hex(self.api.foreground()), 'window_pid': owner}
                if not state['thread_info_ok'] and state['alive']:
                    event['kind'] = 'probe-failed'; self.record(event); return
                if not state['alive'] or not state['visible']:
                    event['kind'] = 'window-ended'; self.record(event); return
                if owner != self.proc.pid or state['minimized'] or state['in_move_size'] or event['foreground_hwnd'] != hex(self.window):
                    event['kind'] = 'focus-or-modal-interference'; self.record(event); return
        except OSError as e:
            self.record({'ms': int(time.time()*1000), 'kind': 'probe-failed', 'reason': str(e)})
        finally:
            self.ready.set()
            if hooks:
                try: self.api.pump_events()  # include callbacks queued immediately before process exit
                except OSError as e: self.record({'ms': int(time.time()*1000), 'kind': 'probe-failed', 'reason': str(e)})
                try: self.api.remove_events(hooks); self.report['event_hooks_removed'] = True
                except OSError as e: self.record({'ms': int(time.time()*1000), 'kind': 'probe-failed', 'reason': str(e)})

    def finish(self):
        self.stop.set()
        if self.thread: self.thread.join(timeout=1)
        self.report['monitor_stopped'] = not self.thread or not self.thread.is_alive()
        return self.report


def startup_failure(report, timeline):
    if not report or not report.get('verified') or not report.get('event_hooks_installed'):
        return 'owned foreground/event-hook startup proof failed'
    if timeline.is_file():
        frames = [int(c[0]) for line in timeline.read_text(encoding='utf-8', errors='replace').splitlines()[2:]
                  if len(c := line.split('\t')) == 9 and c[6] == 'frame']
        if frames and report['verified_at_ms'] > min(frames):
            return 'foreground verification followed the first captured CPU frame'
    return None


def abort_failed_start(proc, report, timeline):
    reason = startup_failure(report, timeline)
    if reason:
        if proc.poll() is None: proc.kill()
        return reason, proc.wait(timeout=15)
    return None


def verify(report, timeline):
    if (not report or report.get('verified') is not True or report.get('focus_requests') != 1 or
            report.get('foreground_pid') != report.get('pid') or not report.get('monitor_stopped') or
            not report.get('event_hooks_installed') or not report.get('event_hooks_removed') or
            report.get('checks', 0) < 1 or report.get('omitted_events')):
        raise ValueError('CFX010 foreground startup/monitor proof failed')
    rows = [c for line in timeline.read_text(encoding='utf-8').splitlines()[2:] if len(c := line.split('\t')) == 9]
    frames = [int(c[0]) for c in rows if c[6] == 'frame']
    teardown = [int(c[0]) for c in rows if c[6] == 'address-binding-summary' and c[7].startswith('reason=device-teardown ')]
    if not frames or report['verified_at_ms'] > min(frames):
        raise ValueError('CFX010 foreground not verified before first captured frame')
    for event in report.get('events', []):
        if (event['kind'] == 'native-foreground-change' and teardown and event['ms'] >= max(teardown)
                and (not event['alive'] or not event['visible'])):
            continue  # natural final window teardown; an earlier queued switch cannot inherit this exception
        if event['kind'] != 'window-ended' or event['ms'] < max(frames):
            raise ValueError('CFX010 foreground/modal interference invalidates qualification')
