import os
import re
import shutil
import asyncio
import subprocess

# The decky plugin module is located at decky-loader/plugin
# For easy intellisense checkout the decky-loader code one directory up
# or add the `decky-loader/plugin` path to `python.analysis.extraPaths` in `.vscode/settings.json`
import decky_plugin

def detect_and_mount_usb():
    devices = get_block_devices()

    for device in devices:
        if is_usb_device(device):
            device_path = device
            if not is_mounted(device_path):
                mount_point = get_mount_point(device)
                if mount_point:
                    filesystem = get_filesystem(device_path)
                    if filesystem:
                        mount_usb(device_path, mount_point, filesystem)

def get_block_devices():
    command = "lsblk -ndo NAME -e7,11"
    output = subprocess.check_output(command, shell=True, text=True).strip()
    devices = output.split("\n")
    return devices

def is_usb_device(device_path):
    command = f"udevadm info -q property -n {device_path}"
    try:
        output = subprocess.check_output(command, shell=True, text=True).strip()
        properties = dict(line.split("=") for line in output.split("\n"))
        if "ID_BUS" in properties and "usb" in properties["ID_BUS"]:
            if "ID_CDROM" in properties:
                return False
            return True
        return False
    except subprocess.CalledProcessError:
        return False

def is_mounted(device_path):
    with open('/proc/mounts', 'r') as f:
        for line in f.readlines():
            if device_path in line:
                return True
    return False

def get_mount_point(device):
    serial_number = get_device_property(device, "ID_SERIAL_SHORT")
    if serial_number:
        mount_point = f'/run/media/{serial_number}'
        os.makedirs(mount_point, exist_ok=True)
        return mount_point
    return None

def get_filesystem(device_path):
    command = f'lsblk -no FSTYPE /dev/{device_path}'
    output = subprocess.check_output(command, shell=True, text=True).strip()
    return output

def get_primary_partition(device_path):
    pattern = r'(\w+)\s+(\w+)'
    try:
        command = f'lsblk -lnpo NAME,TYPE {device_path}'
        output = subprocess.check_output(command, shell=True, text=True)
        lines = output.strip().split('\n')
        for line in lines:
            match = re.search(pattern, line)
            name = match.group(1)
            dev_type = match.group(2)
            if dev_type == 'part':
                return name
    except subprocess.CalledProcessError as e:
        raise ValueError(f"Error retrieving primary partition for device {device_path}") from e

def mount_usb(device_path, mount_point, filesystem):
    try:
        primary_partition = get_primary_partition('/dev/' + device_path)
        command = f'mount -t {filesystem} /dev/{primary_partition} {mount_point}'
        subprocess.run(command, shell=True, check=True)
        decky_plugin.logger.info(f"USB mounted: {device_path} -> {mount_point}")
    except subprocess.CalledProcessError as e:
        decky_plugin.logger.error(f"Error mounting USB: {device_path} -> {mount_point} - {e}")

def unmount_usb(device_path, mount_point):
    try:
        command = f'umount --lazy {mount_point}'
        subprocess.run(command, shell=True, check=True)
        shutil.rmtree(mount_point)
        decky_plugin.logger.info(f"USB unmounted: {device_path}")
    except subprocess.CalledProcessError as e:
        decky_plugin.logger.error(f"Error unmounting USB: {device_path} - {e}")

def get_device_property(device_path, property_name):
    command = f"udevadm info -q property -n {device_path}"
    output = subprocess.check_output(command, shell=True, text=True).strip()
    properties = dict(line.split("=") for line in output.split("\n"))
    return properties.get(property_name)

# Continuous function to check for usb device changes
async def monitor_usb():
    mounted_devices = {}

    while True:
        devices = get_block_devices()

        for device in devices:
            if device not in mounted_devices and is_usb_device(device):
                detect_and_mount_usb()
                mounted_devices[device] = get_mount_point(device)

        for device in list(mounted_devices.keys()):
            if not is_usb_device(device):
                mount_point = mounted_devices[device]
                unmount_usb(device, mount_point)
                del mounted_devices[device]

        await asyncio.sleep(1)  # Adjust the sleep duration as needed

class Plugin:

    # Returns every connected USB device's status for use in Frontend
    async def get_usb_devices(self):
        block_devices = get_block_devices()
        usb_devices = []
        for device_path in block_devices:
            if is_usb_device(device_path):
                serial_number = get_device_property(device_path, "ID_SERIAL_SHORT")
                mounted = is_mounted(device_path)  # Renamed variable
                mount_point = get_mount_point(device_path)
                filesystem = get_filesystem(device_path)
                usb_devices.append({
                    "serial_number": serial_number,
                    "is_mounted": mounted,  # Updated variable name
                    "device_path": device_path,
                    "mount_point": mount_point,
                    "filesystem": filesystem
                })
        return usb_devices
    
    # A normal method. It can be called from JavaScript using call_plugin_function("method_1", argument1, argument2)
    async def add(self, left, right):
        return left + right

    # Asyncio-compatible long-running code, executed in a task when the plugin is loaded
    async def _main(self):
        decky_plugin.logger.info("Hello World!")
        # decky_plugin.logger.info("Monitoring USB devices...")
        # await monitor_usb()

    # Function called first during the unload process, utilize this to handle your plugin being removed
    async def _unload(self):
        decky_plugin.logger.info("Goodbye World!")
        pass

    # Migrations that should be performed before entering `_main()`.
    async def _migration(self):
        decky_plugin.logger.info("Migrating")
        # Here's a migration example for logs:
        # - `~/.config/decky-template/template.log` will be migrated to `decky_plugin.DECKY_PLUGIN_LOG_DIR/template.log`
        decky_plugin.migrate_logs(os.path.join(decky_plugin.DECKY_USER_HOME,
                                               ".config", "decky-template", "template.log"))
        # Here's a migration example for settings:
        # - `~/homebrew/settings/template.json` is migrated to `decky_plugin.DECKY_PLUGIN_SETTINGS_DIR/template.json`
        # - `~/.config/decky-template/` all files and directories under this root are migrated to `decky_plugin.DECKY_PLUGIN_SETTINGS_DIR/`
        decky_plugin.migrate_settings(
            os.path.join(decky_plugin.DECKY_HOME, "settings", "template.json"),
            os.path.join(decky_plugin.DECKY_USER_HOME, ".config", "decky-template"))
        # Here's a migration example for runtime data:
        # - `~/homebrew/template/` all files and directories under this root are migrated to `decky_plugin.DECKY_PLUGIN_RUNTIME_DIR/`
        # - `~/.local/share/decky-template/` all files and directories under this root are migrated to `decky_plugin.DECKY_PLUGIN_RUNTIME_DIR/`
        decky_plugin.migrate_runtime(
            os.path.join(decky_plugin.DECKY_HOME, "template"),
            os.path.join(decky_plugin.DECKY_USER_HOME, ".local", "share", "decky-template"))
