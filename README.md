# MKUltraSkelly

Enhanced control program for the Grave & Bones Ultra Skele.

## BLE device discovery

To capture the Bluetooth Low Energy (BLE) services that power the skeleton, run the interactive scanner provided in this repository. The tool requires the [`bleak`](https://github.com/hbldh/bleak) library and Python 3.8+.

```bash
pip install bleak
```

Run the scanner from the project root:

```bash
python tools/scan_ble.py [--device-name "MKUltra Skeleton"] [--mac-address AA:BB:CC:DD:EE:FF] [-v|-vv]
```

* `--device-name` – friendly name to match during discovery. Defaults to `MKUltra Skeleton` when a MAC address is not provided.
* `--mac-address` – explicit BLE address (overrides the device name search).
* `-v` / `-vv` – increase logging verbosity. The default log level only shows warnings.
* `--output` – override the destination JSON file (defaults to `config/device_profile.json`).

The script scans for the matching device, connects, enumerates every service, characteristic, and descriptor, and then writes a structured profile to the output JSON file. This file becomes the canonical reference for later tooling that needs UUIDs or characteristic properties.

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



## Boot Strap

Prepare a fresh workstation with the bootstrap script before working on the
project. The helper installs system dependencies, enables Bluetooth support, and
creates a Python virtual environment so the application can be developed or run
immediately:

```bash
./scripts/bootstrap.sh
```

> **Tip:** Run the script from the repository root. Administrative privileges
> (either as `root` or via `sudo`) are required so that apt operations and
> service configuration succeed.

The script performs the following actions:

1. Updates the apt package index and upgrades installed packages.
2. Installs Bluetooth and Python build dependencies (`bluez`, `bluez-tools`,
   `bluetooth`, `python3-venv`, and related packages).
3. Enables and starts the `bluetooth` service when `systemd` is available on the
   host.
4. Clones the repository (when `REPO_URL` is provided) or updates the existing
   checkout.
5. Provisions a `.venv` virtual environment and, when `requirements.txt` is
   present, installs the listed Python dependencies.

### Customisation

Tweak the workflow by exporting any of the following environment variables
before running the script:

| Variable     | Purpose |
|--------------|---------|
| `REPO_URL`   | Source URL used when cloning into an empty directory. |
| `REPO_DIR`   | Target directory for the checkout (defaults to the repository root). |
| `PYTHON_BIN` | Python interpreter used for the virtual environment (`python3` by default). |
| `VENV_PATH`  | Location where the virtual environment should be created (defaults to `<repo>/.venv`). |

### After bootstrapping

Activate the environment whenever you work on the project:

```bash
source .venv/bin/activate
```

You can then run project-specific tooling, install additional dependencies, or
execute scripts in an isolated context. When finished, deactivate the
environment with `deactivate`.


