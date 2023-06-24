import {
  ButtonItem,
  definePlugin,
  DialogButton,
  Menu,
  MenuItem,
  PanelSection,
  PanelSectionRow,
  Router,
  ServerAPI,
  showContextMenu,
  staticClasses,
  ToggleField,
} from "decky-frontend-lib";
import { VFC, useState, useEffect } from "react";
import { FaShip } from "react-icons/fa";
import logo from "../assets/logo.png";

// interface AddMethodArgs {
//   left: number;
//   right: number;
// }

const Content: VFC<{ serverAPI: ServerAPI }> = ({ serverAPI }) => {
  // const [result, setResult] = useState<number | undefined>();

  // const onClick = async () => {
  //   const result = await serverAPI.callPluginMethod<AddMethodArgs, number>(
  //     "add",
  //     {
  //       left: 2,
  //       right: 2,
  //     }
  //   );
  //   if (result.success) {
  //     setResult(result.result);
  //   }
  // };

  const [usbDevices, setUsbDevices] = useState<any[]>([]);

  useEffect(() => {
    fetchUsbDevices();
  }, []);

  const fetchUsbDevices = async () => {
    const data = await serverAPI.callPluginMethod("get_usb_devices", {});
    console.log(data.result)
    if (Array.isArray(data.result)){
      setUsbDevices(data.result);
    }
  };

  async function toggleUsbDeviceState(input: boolean, usbDevice: any): Promise<void> {
    if (input) {
      try {
        await serverAPI.callPluginMethod("mount_usb", {
          device_path: usbDevice.device_path,
          mount_point: usbDevice.mount_point,
          filesystem: usbDevice.filesystem
        });
  
        const isSteamLibrary = await serverAPI.callPluginMethod("verify_steam_library_path", {
          mount_point: usbDevice.mount_point
        });
    
        if (isSteamLibrary.result) {
          await serverAPI.callPluginMethod("add_libraryfolder", {
            mount_point: usbDevice.mount_point
          });
          console.log("StartRestart() called"); // Debugging
          SteamClient.User.StartRestart();
        } else {
          serverAPI.toaster.toast({ title: "USB Mount Error", body: "Not a valid steam library!" });
        }
      } catch (error) {
        console.error("Error mounting USB:", error); // Error handling
        serverAPI.toaster.toast({ title: "USB Mount Error", body: "Failed to mount USB device" });
      }
    } else {
      try {
        await serverAPI.callPluginMethod("unmount_usb", {
          device_path: usbDevice.device_path,
          mount_point: usbDevice.mount_point
        });
  
        serverAPI.toaster.toast({ title: "USB Disconnected", body: "USB device disconnected" });
      } catch (error) {
        console.error("Error unmounting USB:", error); // Error handling
        serverAPI.toaster.toast({ title: "USB Unmount Error", body: "Failed to unmount USB device" });
      }
    }
  }

  return (
    <PanelSection title="Devices">
      {/* <PanelSectionRow>
        <ButtonItem
          layout="below"
          onClick={(e) =>
            showContextMenu(
              <Menu label="Menu" cancelText="CAAAANCEL" onCancel={() => {}}>
                <MenuItem onSelected={() => {}}>Item #1</MenuItem>
                <MenuItem onSelected={() => {}}>Item #2</MenuItem>
                <MenuItem onSelected={() => {}}>Item #3</MenuItem>
              </Menu>,
              e.currentTarget ?? window
            )
          }
        >
          Server says yolo
        </ButtonItem>
      </PanelSectionRow> */}

      {/* <PanelSectionRow>
        <div style={{ display: "flex", justifyContent: "center" }}>
          <img src={logo} />
        </div>
      </PanelSectionRow> */}

      {/* <PanelSectionRow>
        <ButtonItem
          layout="below"
          onClick={() => {
            Router.CloseSideMenus();
            Router.Navigate("/decky-plugin-test");
          }}
        >
          Router
        </ButtonItem>
      </PanelSectionRow> */}

      {usbDevices.map((usbDevice, index) => (
        <PanelSectionRow key={index}>
          <ToggleField checked={usbDevice.is_mounted} label={usbDevice.serial_number} description={`Filesystem: ${usbDevice.filesystem}`} onChange={(event) => toggleUsbDeviceState(event, usbDevice)}></ToggleField>
          {/* Display testing data obtained from backend */}
          {/* <div>
            <h3>USB Device {index + 1}</h3>
            <p>Serial Number: {usbDevice.serial_number}</p>
            <p>Is Mounted: {usbDevice.is_mounted.toString()}</p>
            <p>Device Path: {usbDevice.device_path}</p>
            <p>Mount Point: {usbDevice.mount_point}</p>
            <p>Filesystem: {usbDevice.filesystem}</p>
          </div> */}
        </PanelSectionRow>
      ))}
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          onClick={() => {
            fetchUsbDevices()
          }}
        >
          Refresh
        </ButtonItem>
      </PanelSectionRow>
    </PanelSection>
  );
};

const DeckyPluginRouterTest: VFC = () => {
  return (
    <div style={{ marginTop: "50px", color: "white" }}>
      Hello World!
      <DialogButton onClick={() => Router.NavigateToLibraryTab()}>
        Go to Library
      </DialogButton>
    </div>
  );
};

export default definePlugin((serverApi: ServerAPI) => {
  serverApi.routerHook.addRoute("/decky-plugin-test", DeckyPluginRouterTest, {
    exact: true,
  });

  return {
    title: <div className={staticClasses.Title}>Example Plugin</div>,
    content: <Content serverAPI={serverApi} />,
    icon: <FaShip />,
    onDismount() {
      serverApi.routerHook.removeRoute("/decky-plugin-test");
    },
  };
});