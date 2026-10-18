"""No command runs hardware unless `run` passes the exact packet approval gate."""
import argparse
import hashlib
import json
from pathlib import Path

from .common import Stop, canonical, exclusive, read_json, validate_packet


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--packet", required=True, type=Path)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--seed", required=True, type=Path)
    prepare.add_argument("--packet", required=True, type=Path)
    baseline = sub.add_parser("event-baseline")
    baseline.add_argument("--out", required=True, type=Path)
    host=sub.add_parser("host-identity")
    host.add_argument("--out",required=True,type=Path)
    held = sub.add_parser("init-stop")
    held.add_argument("--root", required=True, type=Path)
    run = sub.add_parser("run")
    run.add_argument("--packet", required=True, type=Path)
    run.add_argument("--approval", required=True, type=Path)
    run.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "init-stop":
            args.root.mkdir(parents=True, exist_ok=False)
            exclusive(args.root / "HELD.json", {"status": "HELD", "physical_gpu_qualified": False})
            print(json.dumps({"status": "HELD", "root": str(args.root.resolve())}))
        elif args.command == "host-identity":
            from .readers import bounded_host_identity
            value=bounded_host_identity()
            exclusive(args.out,value)
            print(json.dumps({"status":"READ_ONLY","out":str(args.out),"sha256":hashlib.sha256(canonical(value)).hexdigest()}))
        elif args.command == "event-baseline":
            from .readers import BoundedReaders, NativeEvents
            value = BoundedReaders(None, NativeEvents().snapshot).call("event")
            exclusive(args.out, value)
            print(json.dumps({"status": "READ_ONLY", "out": str(args.out), "sha256": hashlib.sha256(canonical(value)).hexdigest()}))
        elif args.command == "prepare":
            from .prepare import diagnostic_packet
            packet = diagnostic_packet(read_json(args.seed))
            exclusive(args.packet, packet)
            print(json.dumps({"status": "PREPARED_NO_LAUNCH", "packet_sha256": validate_packet(packet)}))
        elif args.command == "validate":
            print(json.dumps({"status": "VALIDATED_NO_LAUNCH", "packet_sha256": validate_packet(read_json(args.packet))}))
        else:
            from .supervisor import execute
            result = execute(read_json(args.packet), read_json(args.approval), args.out)
            print(json.dumps(result))
            return 0 if result["status"] == "COLLECTED_PENDING_ACCEPTANCE" else 1
        return 0
    except (OSError, ValueError, KeyError, Stop) as error:
        print(json.dumps({"status": "FAILED_STOP", "error": str(error)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
