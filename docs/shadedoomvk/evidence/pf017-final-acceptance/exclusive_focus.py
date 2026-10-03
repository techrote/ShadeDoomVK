"""One exclusive-use focus request with a finally-detached input association.

No key/mouse synthesis, policy change, or repeated activation is performed.
The existing owned-window readback and monitoring still determine success.
"""
import ctypes
from ctypes import wintypes
from cfx010_foreground import WindowsForeground

class ExclusiveForeground(WindowsForeground):
    def __init__(self):
        super().__init__()
        self.kernel.GetCurrentThreadId.restype=wintypes.DWORD
        self.api.AttachThreadInput.argtypes=[wintypes.DWORD,wintypes.DWORD,wintypes.BOOL]
        self.api.AttachThreadInput.restype=wintypes.BOOL
        self.activation={}

    def activate(self,window):
        current=int(self.kernel.GetCurrentThreadId())
        foreground=self.foreground()
        owner,thread=self.owner(foreground)
        associated=False
        self.activation={'caller_thread':current,'previous_foreground_hwnd':hex(foreground),'previous_foreground_pid':owner,'previous_foreground_thread':thread,'association_attempted':False,'focus_requests':0,'association_detached':None}
        try:
            if thread and thread!=current:
                self.activation['association_attempted']=True
                associated=bool(self.api.AttachThreadInput(current,thread,True))
                self.activation['association_attached']=associated
                if not associated: return False
            self.activation['focus_requests']=1
            result=bool(self.api.SetForegroundWindow(window))
            self.activation['set_foreground_returned']=result
        finally:
            if associated:
                self.activation['association_detached']=bool(self.api.AttachThreadInput(current,thread,False))
        return result and (not associated or self.activation['association_detached'])
