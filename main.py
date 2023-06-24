import os
import re
import shutil
import asyncio
import subprocess

# The decky plugin module is located at decky-loader/plugin
# For easy intellisense checkout the decky-loader code one directory up
# or add the `decky-loader/plugin` path to `python.analysis.extraPaths` in `.vscode/settings.json`
import decky_plugin

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
    
def get_device_property(device_path, property_name):
    command = f"udevadm info -q property -n {device_path}"
    output = subprocess.check_output(command, shell=True, text=True).strip()
    properties = dict(line.split("=") for line in output.split("\n"))
    return properties.get(property_name)

def read_libraryfolder(library_folder, index):
    with open(library_folder + "/libraryfolder.vdf", 'r') as file:
        contents = file.read()

    # Find the start and end positions of "libraryfolder" section
    start_pos = contents.find('"libraryfolder"')
    end_pos = contents.find('}', start_pos)

    if start_pos == -1 or end_pos == -1:
        raise ValueError('Invalid libraryfolder.vdf file format.')

    # Create the modified content with the index
    modified_content = '\t"' + str(index) + '"' + contents[start_pos + 15: end_pos].replace('\n', '\n\t') + '\t"path"\t\t"' + library_folder + '"\n\t}\n'

    return modified_content

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
    
    async def mount_usb(self, device_path, mount_point, filesystem):
        try:
            primary_partition = get_primary_partition('/dev/' + device_path)
            command = f'mount -t {filesystem} /dev/{primary_partition} {mount_point}'
            subprocess.run(command, shell=True, check=True)
            decky_plugin.logger.info(f"USB mounted: {device_path} -> {mount_point}")
        except subprocess.CalledProcessError as e:
            decky_plugin.logger.error(f"Error mounting USB: {device_path} -> {mount_point} - {e}")

    async def unmount_usb(self, device_path, mount_point):
        try:
            command = f'umount --lazy {mount_point}'
            subprocess.run(command, shell=True, check=True)
            shutil.rmtree(mount_point)
            decky_plugin.logger.info(f"USB unmounted: {device_path}")
        except subprocess.CalledProcessError as e:
            decky_plugin.logger.error(f"Error unmounting USB: {device_path} - {e}")
    
    # Provides mountpoint to steam client
    async def add_libraryfolder(self, mount_point):
        # Read the existing contents of the libraryfolders.vdf file
        with open(decky_plugin.DECKY_USER_HOME + "/.steam/steam/steamapps/libraryfolders.vdf", 'r') as file:
            contents = file.read()

        # Find the position of the last closing brace '}' in the contents
        last_brace_pos = contents.rfind('}')

        if last_brace_pos == -1:
            raise ValueError('Invalid libraryfolders.vdf file format.')

        # Find the last index used in the libraryfolders.vdf file
        last_index = 0

        for line in contents.split('\n'):
            if line.startswith('\t"') and line.strip().endswith('"'):
                temp = line.strip()
                temp = temp.replace('"', '')
                last_index = int(temp)
        
        # Increment the last index to get the new index for the added library folder
        new_index = last_index + 1

        # Log the new index for debugging
        decky_plugin.logger.error(f"New Index: {new_index}")

        # Get the modified content from read_libraryfolder function using the new index
        modified_content = read_libraryfolder(mount_point + "/SteamLibrary", new_index)

        # Log the modified content for debugging
        decky_plugin.logger.error(f"Modified Content: {modified_content}")

        # Insert the modified content at the end of the libraryfolders.vdf file
        updated_contents = contents[:last_brace_pos].rstrip() + '\n' + modified_content + '\n}'

        # Log the updated contents for debugging
        decky_plugin.logger.error(f"Updated Contents: {updated_contents}")

        # Write the updated contents back to the libraryfolders.vdf file
        with open(decky_plugin.DECKY_USER_HOME + "/.steam/steam/steamapps/libraryfolders.vdf", 'w') as file:
            file.write(updated_contents)

    # Check if steam library exists on a given drive
    async def verify_steam_library_path(self, mount_point):
        file_path = mount_point + "/SteamLibrary/libraryfolder.vdf"
        return os.path.isfile(file_path)
    
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
