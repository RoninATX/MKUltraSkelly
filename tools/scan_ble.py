#!/usr/bin/env python3
"""Scan for nearby BLE devices and optionally generate a device profile.

This script uses the `bleak` library to harvest nearby Bluetooth Low Energy
devices for a configurable period of time. The discovered devices are written
to ``config/discovered_devices.json`` (by default) so that you can review the
advertised names, addresses, and signal strength before attempting a direct
connection. Once you identify the skeleton in the discovery output, you can
re-run the script with the matching name or address to generate a detailed
profile in ``config/device_profile.json``.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import logging
import platform
import subprocess
from datetime import datetime, timezone
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

try:
    from bleak import BleakClient, BleakError
    from bleak import BleakScanner
    from bleak.backends.device import BLEDevice
    # Try to get version from __version__ (pip installations)
    try:
        from bleak import __version__ as bleak_version
    except ImportError:
        # Fall back to importlib.metadata (apt installations)
        try:
            bleak_version = importlib.metadata.version("bleak")
        except Exception:
            bleak_version = "unknown"
except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional dep
    raise SystemExit(
        "The 'bleak' package is required to run this script. Install it via\n"
        "    pip install bleak\n"
        "and try again."
    ) from exc

DEFAULT_SCAN_DURATION = 30.0
DEFAULT_SCAN_OUTPUT_PATH = Path("config/discovered_devices.json")
DEFAULT_PROFILE_OUTPUT_PATH = Path("config/device_profile.json")


def check_bluetooth_adapter(adapter: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """Check if Bluetooth adapter exists and is powered on.
    
    Returns:
        Tuple of (is_available, error_message)
    """
    # On Linux/Raspberry Pi, check using hciconfig or bluetoothctl
    if platform.system() != "Linux":
        return True, None  # Skip checks on non-Linux systems
    
    adapter_name = adapter or "hci0"
    
    # Try hciconfig first (if available)
    try:
        result = subprocess.run(
            ["hciconfig", adapter_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            output = result.stdout
            if "UP" in output or "RUNNING" in output:
                return True, None
            elif "DOWN" in output:
                logging.warning(f"Bluetooth adapter {adapter_name} is DOWN.")
                return False, (
                    f"Bluetooth adapter {adapter_name} is DOWN.\n"
                    f"Power it on with: sudo hciconfig {adapter_name} up\n"
                    f"Or use bluetoothctl: sudo bluetoothctl power on"
                )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # hciconfig not available, try bluetoothctl
    
    # Fall back to bluetoothctl
    try:
        result = subprocess.run(
            ["bluetoothctl", "show", adapter_name],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            output = result.stdout
            if "Powered: yes" in output:
                return True, None
            else:
                logging.warning(f"Bluetooth adapter {adapter_name} is not powered.")
                return False, (
                    f"Bluetooth adapter {adapter_name} is not powered.\n"
                    f"Power it on with: bluetoothctl power on\n"
                    f"Or: sudo hciconfig {adapter_name} up"
                )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # If we can't check, assume it might work but warn
    logging.warning(
        "Could not verify Bluetooth adapter status (hciconfig/bluetoothctl not available). "
        "Proceeding anyway, but if you get errors, check that Bluetooth is enabled."
    )
    return True, None


def get_available_adapters() -> List[str]:
    """List available Bluetooth adapters."""
    adapters = []
    
    if platform.system() != "Linux":
        return adapters
    
    # Try to get adapters from hciconfig
    try:
        result = subprocess.run(
            ["hciconfig"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Parse hciX from output
            for line in result.stdout.splitlines():
                if line.strip().startswith("hci"):
                    adapter = line.split()[0].rstrip(":")
                    adapters.append(adapter)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Fall back to bluetoothctl
    if not adapters:
        try:
            result = subprocess.run(
                ["bluetoothctl", "list"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                # Parse controller addresses/names
                for line in result.stdout.splitlines():
                    if "Controller" in line or line.strip().startswith("hci"):
                        # Try to extract adapter name
                        parts = line.split()
                        for part in parts:
                            if part.startswith("hci"):
                                adapters.append(part.rstrip(":"))
                                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    
    # Default to hci0 if nothing found but on Linux
    if not adapters and platform.system() == "Linux":
        adapters = ["hci0"]
    
    return adapters


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


def _extract_device_info(device: BLEDevice) -> DeviceInfo:
    metadata = getattr(device, "metadata", {}) or {}
    return DeviceInfo(
        name=device.name,
        address=device.address,
        rssi=device.rssi,
        manufacturer_data=_to_jsonable(metadata.get("manufacturer_data", {})),
        metadata=_to_jsonable(metadata),
    )


async def build_profile(device: BLEDevice) -> DeviceProfile:
    """Build the device profile for the provided BLE device."""
    logging.info("Connecting to device %s (%s)", device.name, device.address)
    try:
        async with BleakClient(device) as client:
            logging.info("Connected. Enumerating services...")
            services = await client.get_services()
            profile = DeviceProfile(
                device=_extract_device_info(device)
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


async def scan_devices(duration: float, adapter: Optional[str] = None) -> Sequence[BLEDevice]:
    """Scan for BLE devices with optional adapter specification."""
    logging.info("Scanning for BLE devices for %.1f seconds...", duration)
    
    # Check adapter availability before scanning (Linux only)
    if platform.system() == "Linux":
        available, error_msg = check_bluetooth_adapter(adapter)
        if not available and error_msg:
            raise SystemExit(
                f"Bluetooth adapter not available: {error_msg}\n\n"
                "For Raspberry Pi Zero W 2, ensure:\n"
                "  1. Bluetooth service is running: sudo systemctl start bluetooth\n"
                "  2. Adapter is powered on: sudo hciconfig hci0 up\n"
                "  3. User is in bluetooth group: sudo usermod -aG bluetooth $USER\n"
                "  4. pi-bluetooth package is installed: sudo apt install pi-bluetooth"
            )
    
    # Create scanner with optional adapter
    # On Linux/BlueZ, adapter can be specified when creating BleakScanner
    try:
        if adapter:
            # Create scanner with specific adapter
            scanner = BleakScanner(adapter=adapter)
            devices = await scanner.discover(timeout=duration)
        else:
            # Use default adapter discovery
            devices = await BleakScanner.discover(timeout=duration)
    except BleakError as exc:
        if "No powered Bluetooth adapters found" in str(exc):
            available_adapters = get_available_adapters()
            error_msg = (
                f"Bluetooth adapter not detected: {exc}\n\n"
                "Troubleshooting steps:\n"
            )
            if available_adapters:
                error_msg += f"  Found adapters: {', '.join(available_adapters)}\n"
                if adapter and adapter not in available_adapters:
                    error_msg += f"  Specified adapter '{adapter}' not found.\n"
                elif not adapter:
                    error_msg += f"  Try specifying adapter explicitly: --adapter {available_adapters[0]}\n"
            else:
                error_msg += "  No adapters detected by system tools.\n"
            
            error_msg += (
                "  For Raspberry Pi Zero W 2:\n"
                "    1. Check Bluetooth service: sudo systemctl status bluetooth\n"
                "    2. Power on adapter: sudo hciconfig hci0 up\n"
                "    3. Verify in /boot/config.txt: ensure 'dtoverlay=disable-bt' is commented out\n"
                "    4. Install pi-bluetooth: sudo apt install pi-bluetooth\n"
                "    5. Reboot if needed: sudo reboot"
            )
            raise SystemExit(error_msg) from exc
        raise
    
    logging.info("Discovered %d devices", len(devices))
    for device in devices:
        logging.debug(
            "Found device: name=%s address=%s rssi=%s",
            device.name,
            device.address,
            device.rssi,
        )
    return devices


def write_scan_results(devices: Sequence[BLEDevice], output_path: Path, duration: float) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scan_duration_seconds": duration,
        "device_count": len(devices),
        "devices": [asdict(_extract_device_info(device)) for device in devices],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    logging.info("Discovery results written to %s", output_path)


def select_device(devices: Sequence[BLEDevice], target_name: Optional[str], target_address: Optional[str]) -> Optional[BLEDevice]:
    for device in devices:
        if target_address and device.address and device.address.lower() == target_address.lower():
            return device
        if target_name and device.name and device.name.lower() == target_name.lower():
            return device
    return None


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan for the skeleton BLE device and generate a profile.")
    parser.add_argument("--device-name", help="Target device name to profile once discovered.")
    parser.add_argument(
        "--mac-address",
        help="Target device MAC address (or BLE address). Overrides the device name if provided.",
    )
    parser.add_argument(
        "--scan-output",
        type=Path,
        default=DEFAULT_SCAN_OUTPUT_PATH,
        help="Path to write the discovery results JSON (default: %(default)s).",
    )
    parser.add_argument(
        "--profile-output",
        type=Path,
        default=DEFAULT_PROFILE_OUTPUT_PATH,
        help="Path to write the generated device profile JSON when profiling (default: %(default)s).",
    )
    parser.add_argument(
        "--scan-duration",
        type=float,
        default=DEFAULT_SCAN_DURATION,
        help="Seconds to wait while gathering BLE advertisements (default: %(default)s).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (can be specified multiple times).",
    )
    parser.add_argument(
        "--adapter",
        help="Bluetooth adapter to use (e.g., 'hci0' for Raspberry Pi). Auto-detected if not specified.",
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
    devices = await scan_devices(args.scan_duration, adapter=args.adapter)
    write_scan_results(devices, args.scan_output, args.scan_duration)

    if not args.device_name and not args.mac_address:
        logging.info("No target specified; skipping device profiling.")
        return

    target_device = select_device(devices, args.device_name, args.mac_address)
    if not target_device:
        identifier = args.mac_address or args.device_name
        raise SystemExit(
            "No device matching %s was found. Review %s to pick a candidate."
            % (identifier, args.scan_output)
        )

    profile = await build_profile(target_device)
    write_profile(profile, args.profile_output)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    configure_logging(args.verbose)

    try:
        asyncio.run(async_main(args))
    except KeyboardInterrupt:
        raise SystemExit("Scan cancelled by user.")
    except SystemExit:
        raise  # Re-raise SystemExit to preserve error messages
    except Exception as exc:
        if "No powered Bluetooth adapters found" in str(exc):
            raise SystemExit(
                f"Bluetooth adapter error: {exc}\n\n"
                "For Raspberry Pi Zero W 2 troubleshooting, see the README."
            ) from exc
        raise


if __name__ == "__main__":
    main()
