# MKUltraSkelly

Enhanced control program for the Grave & Bones Ultra Skele.

## BLE device discovery

To capture the Bluetooth Low Energy (BLE) services that power the skeleton, run the discovery tool in this repository. The tool requires the [`bleak`](https://github.com/hbldh/bleak) library and Python 3.8+.

### Quick start

Download the scanner script directly:

```bash
curl -o scan_ble.py https://raw.githubusercontent.com/YOUR_USERNAME/MKUltraSkelly/main/tools/scan_ble.py
```

Or using `wget`:

```bash
wget -O scan_ble.py https://raw.githubusercontent.com/YOUR_USERNAME/MKUltraSkelly/main/tools/scan_ble.py
```

### Installation

Install the required dependencies:

```bash
pip install bleak
```

On some systems (such as Raspberry Pi OS) you may need to install the package via apt if pip reports an "externally-managed-environment" error:

```bash
sudo apt install python3-bleak
```

Run the scanner from the project root:

```bash
python tools/scan_ble.py [--scan-duration 30] [--scan-output config/discovered_devices.json] \
    [--device-name "MKUltra Skeleton"] [--mac-address AA:BB:CC:DD:EE:FF] \
    [--profile-output config/device_profile.json] [--adapter hci0] [-v|-vv]
```

* `--scan-duration` – how long (in seconds) to listen for advertisements. Defaults to 30 seconds.
* `--scan-output` – path for the discovery results JSON file (defaults to `config/discovered_devices.json`).
* `--device-name` – friendly name to profile after discovery (optional).
* `--mac-address` – explicit BLE address to profile (overrides the device name when provided).
* `--profile-output` – path for the generated profile when a target device is provided (defaults to `config/device_profile.json`).
* `--adapter` – Bluetooth adapter to use (e.g., `hci0` for Raspberry Pi). Auto-detected if not specified.
* `-v` / `-vv` – increase logging verbosity. The default log level only shows warnings.

The script spends the requested time harvesting every BLE advertisement it can see and writes a JSON summary to the discovery output file. Review that file to determine which device entry represents the skeleton. Once you know the friendly name or MAC address, rerun the script with the appropriate flag to connect, enumerate services and characteristics, and write a full profile for downstream tooling.

### Understanding `config/device_profile.json`

The generated JSON document has the following structure:

```json
{
  "device": {
    "name": "MKUltra Skeleton",
    "address": "AA:BB:CC:DD:EE:FF",
    "rssi": -60,
    "manufacturer_data": {"0xFFFF": "..."},
    "metadata": {"...": "..."},
    "bleak_version": "0.21.1"
  },
  "services": [
    {
      "uuid": "00001800-0000-1000-8000-00805f9b34fb",
      "handle": 1,
      "description": "Generic Access",
      "characteristics": [
        {
          "uuid": "...",
          "handle": 3,
          "description": "Device Name",
          "properties": ["read"],
          "descriptors": [
            {"uuid": "...", "handle": 4, "description": "Characteristic User Description"}
          ]
        }
      ]
    }
  ]
}
```

Use the `services[].characteristics[].uuid` and `properties` fields to identify the handles to read, write, or subscribe to when building control flows. Logging with `-vv` will also print every discovered device, which is useful if the skeleton is advertising under a different name.

## Raspberry Pi Zero W 2 Bluetooth Setup

If you encounter `bleak.exc.BleakError: No powered Bluetooth adapters found` on Raspberry Pi Zero W 2, follow these steps:

### 1. Check Bluetooth Service Status

```bash
sudo systemctl status bluetooth
```

If not running, start and enable it:

```bash
sudo systemctl start bluetooth
sudo systemctl enable bluetooth
```

### 2. Verify Bluetooth is Not Disabled in Config

Check `/boot/config.txt` for any lines that disable Bluetooth:

```bash
sudo nano /boot/config.txt
```

Look for and comment out (add `#`) any line like:
```
dtoverlay=disable-bt
```

Should become:
```
#dtoverlay=disable-bt
```

Save and reboot if you made changes:
```bash
sudo reboot
```

### 3. Install Raspberry Pi Bluetooth Packages

```bash
sudo apt-get update
sudo apt-get install pi-bluetooth bluez
```

### 4. Add User to Bluetooth Group

Replace `pi` with your username if different:

```bash
sudo usermod -aG bluetooth pi
```

Log out and back in, or reboot for the group change to take effect.

### 5. Power On Bluetooth Adapter

```bash
# Check adapter status
hciconfig

# If it shows DOWN, bring it up
sudo hciconfig hci0 up

# Alternative: Use bluetoothctl
sudo bluetoothctl power on
sudo bluetoothctl show
```

### 6. Troubleshooting Additional Issues

If Bluetooth still isn't detected:

- **Wi-Fi interference**: Raspberry Pi Zero W 2 shares the same chip for Wi-Fi and Bluetooth. Temporarily disable Wi-Fi to test:
  ```bash
  sudo rfkill block wlan
  ```

- **Verify adapter exists**:
  ```bash
  lsusb | grep -i bluetooth
  dmesg | grep -i bluetooth
  ```

- **Restart Bluetooth service**:
  ```bash
  sudo systemctl restart bluetooth
  ```

Once Bluetooth is working, you should be able to run the scanner script normally:

```bash
python tools/scan_ble.py
```