#!/usr/bin/env python3
"""Scan for the MKUltra Skelly BLE device and generate a device profile.

This script uses the `bleak` library to discover nearby BLE devices, connect
to a matching device, enumerate its services and characteristics, and write
the collected information to ``config/device_profile.json``. It is intended to
help bootstrap the configuration required by other tooling in this repository.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

try:
    from bleak import BleakClient, BleakError
    from bleak import __version__ as bleak_version
    from bleak import BleakScanner
except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional dep
    raise SystemExit(
        "The 'bleak' package is required to run this script. Install it via\n"
        "    pip install bleak\n"
        "and try again."
    ) from exc


DEFAULT_DEVICE_NAME = "MKUltra Skeleton"
DEFAULT_OUTPUT_PATH = Path("config/device_profile.json")


@dataclass
class DescriptorProfile:
    uuid: str
    handle: Optional[int] = None
    description: Optional[str] = None


@dataclass
class CharacteristicProfile:
    uuid: str
    handle: Optional[int] = None
    description: Optional[str] = None
    properties: List[str] = field(default_factory=list)
    descriptors: List[DescriptorProfile] = field(default_factory=list)


@dataclass
class ServiceProfile:
    uuid: str
    handle: Optional[int] = None
    description: Optional[str] = None
    characteristics: List[CharacteristicProfile] = field(default_factory=list)


@dataclass
class DeviceInfo:
    name: Optional[str]
    address: Optional[str]
    rssi: Optional[int]
    manufacturer_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    bleak_version: str = bleak_version


@dataclass
class DeviceProfile:
    device: DeviceInfo
    services: List[ServiceProfile] = field(default_factory=list)


def _format_key(key: Any) -> str:
    if isinstance(key, int):
        return hex(key)
    return str(key)


def _to_jsonable(value: Any) -> Any:
    """Recursively convert a value into a JSON-serialisable structure."""
    if isinstance(value, (bytes, bytearray, memoryview)):
        return value.hex()
    if isinstance(value, Mapping):
        return {_format_key(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes, bytearray)):
        return [_to_jsonable(v) for v in value]
    return value


async def discover_device(target_name: Optional[str], target_address: Optional[str]):
    """Discover and return a BLE device matching the target criteria."""
    logging.info("Starting BLE scan...")
    devices = await BleakScanner.discover()
    logging.info("Discovered %d devices", len(devices))

    for device in devices:
        logging.debug("Found device: name=%s address=%s rssi=%s", device.name, device.address, device.rssi)
        if target_address and device.address and device.address.lower() == target_address.lower():
            return device
        if target_name and device.name and device.name.lower() == target_name.lower():
            return device
    return None


async def build_profile(args: argparse.Namespace) -> DeviceProfile:
    """Build the device profile for the matching BLE device."""
    target_name = args.device_name or (None if args.mac_address else DEFAULT_DEVICE_NAME)
    device = await discover_device(target_name, args.mac_address)
    if not device:
        identifier = args.mac_address or target_name or "(unknown)"
        raise SystemExit(f"Could not find device matching identifier: {identifier}")

    logging.info("Connecting to device %s (%s)", device.name, device.address)
    try:
        async with BleakClient(device) as client:
            logging.info("Connected. Enumerating services...")
            services = await client.get_services()
            metadata = getattr(device, "metadata", {}) or {}
            profile = DeviceProfile(
                device=DeviceInfo(
                    name=device.name,
                    address=device.address,
                    rssi=device.rssi,
                    manufacturer_data=_to_jsonable(metadata.get("manufacturer_data", {})),
                    metadata=_to_jsonable(metadata),
                )
            )

            for service in services:
                service_profile = ServiceProfile(
                    uuid=service.uuid,
                    handle=getattr(service, "handle", None),
                    description=service.description,
                )
                for characteristic in service.characteristics:
                    char_profile = CharacteristicProfile(
                        uuid=characteristic.uuid,
                        handle=getattr(characteristic, "handle", None),
                        description=characteristic.description,
                        properties=sorted(list(characteristic.properties)),
                    )
                    for descriptor in characteristic.descriptors:
                        descriptor_profile = DescriptorProfile(
                            uuid=descriptor.uuid,
                            handle=getattr(descriptor, "handle", None),
                            description=descriptor.description,
                        )
                        char_profile.descriptors.append(descriptor_profile)
                    service_profile.characteristics.append(char_profile)
                profile.services.append(service_profile)
    except BleakError as exc:
        raise SystemExit(f"Failed to communicate with the device: {exc}") from exc

    return profile


def write_profile(profile: DeviceProfile, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(asdict(profile), fh, indent=2)
    logging.info("Device profile written to %s", output_path)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan for the skeleton BLE device and generate a profile.")
    parser.add_argument(
        "--device-name",
        help="Target device name. Defaults to '%s' if no MAC address is provided." % DEFAULT_DEVICE_NAME,
    )
    parser.add_argument(
        "--mac-address",
        help="Target device MAC address (or BLE address). Overrides the device name if provided.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to write the generated device profile JSON (default: %(default)s).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (can be specified multiple times).",
    )
    return parser.parse_args(argv)


def configure_logging(verbosity: int) -> None:
    if verbosity >= 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


async def async_main(args: argparse.Namespace) -> None:
    profile = await build_profile(args)
    write_profile(profile, args.output)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    configure_logging(args.verbose)

    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        raise SystemExit("Scan cancelled by user.")


if __name__ == "__main__":
    main()
