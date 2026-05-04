import os
import platform
from collections import namedtuple

# Windowsでのplatform.uname() (WMIクエリ) によるフリーズを回避するためのパッチ
if os.name == "nt":
    try:
        # 実際に呼んでみてフリーズするかチェックするのは危険なので、
        # 常に安全な代替実装を定義する。
        # オリジナルのunameを保存
        _original_uname = platform.uname

        _UnameResult = namedtuple(
            "uname_result", ["system", "node", "release", "version", "machine", "processor"]
        )

        def _patched_uname():
            # WMIを使わずに環境変数やosモジュールから情報を取得
            system = "Windows"
            node = os.environ.get("COMPUTERNAME", "unknown")
            release = os.sys.getwindowsversion().major if hasattr(os, "sys") else "10"
            version = os.sys.getwindowsversion().build if hasattr(os, "sys") else "unknown"
            machine = os.environ.get("PROCESSOR_ARCHITECTURE", "AMD64")
            processor = os.environ.get("PROCESSOR_IDENTIFIER", "unknown")
            return _UnameResult(system, node, str(release), str(version), machine, processor)

        platform.uname = _patched_uname
        # machine()などはuname()を内部で呼ぶので、これもパッチの影響を受ける
    except Exception:
        pass
