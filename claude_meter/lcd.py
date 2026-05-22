import sys
from struct import pack, unpack

try:
    import usb.core
    import usb.util
except ImportError:
    sys.exit("Run: pip install pyusb")

try:
    import numpy as np
    _NUMPY_OK = True
except ImportError:
    np = None
    _NUMPY_OK = False

try:
    from PIL import Image
except ImportError:
    sys.exit("Run: pip install pillow")

import claude_meter.config as config


class AX206LCD:
    """Native AX206 LCD driver using SCSI commands."""

    def __init__(self, debug=False, flip_horizontal=True, flip_vertical=True):
        self.dev             = None
        self.width           = config.DISPLAY_W
        self.height          = config.DISPLAY_H
        self.debug           = debug
        self.flip_horizontal = flip_horizontal
        self.flip_vertical   = flip_vertical
        self._connect()

    def _connect(self):
        self.dev = usb.core.find(idVendor=config.AX206_VID, idProduct=config.AX206_PID)
        if self.dev is None:
            raise Exception(
                f"AX206 LCD not found (VID={config.AX206_VID:#06x} PID={config.AX206_PID:#06x})\n"
                "Make sure libusb-win32 driver is installed via Zadig"
            )
        print("[lcd] AX206 LCD found")
        try:
            self.dev.set_configuration()
            print("[lcd] Configuration set")
        except Exception as e:
            print(f"[lcd] Note: set_configuration: {e}")

        try:
            cmd = b'\xcd\x00\x00\x00\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            buf = bytearray(5)
            if self._scsi_command(cmd, buf, direction="IN"):
                w, h = unpack('<HH', buf[0:4])
                if w > 0 and h > 0:
                    self.width, self.height = w, h
                    print(f"[lcd] Detected dimensions: {self.width}x{self.height}")
        except Exception:
            print(f"[lcd] Using default dimensions: {self.width}x{self.height}")

        self.set_backlight(5)

    def _scsi_command(self, cmd, data=None, direction="OUT"):
        if self.dev is None:
            return False

        cbw = bytearray(b'USBC\xde\xad\xbe\xef\x00\x00\x00\x00\x00\x00\x10')
        cbw[14] = len(cmd)
        if data is not None and direction == "OUT":
            cbw[8:12] = pack("<L", len(data))

        try:
            self.dev.write(0x01, cbw + cmd, timeout=2000)
        except Exception as e:
            if self.debug:
                print(f"SCSI write failed: {e}")
            return False

        if data is not None:
            if direction == "OUT":
                try:
                    self.dev.write(0x01, data, timeout=5000)
                except Exception as e:
                    if self.debug:
                        print(f"Data write failed: {e}")
                    return False
            elif direction == "IN":
                try:
                    read_data = self.dev.read(0x81, len(data), timeout=5000)
                    data[:len(read_data)] = read_data
                except Exception as e:
                    if self.debug:
                        print(f"Data read failed: {e}")
                    return False

        try:
            csw = self.dev.read(0x81, 13, timeout=2000)
            return csw[12] == 0
        except Exception:
            return True

    def set_backlight(self, brightness=5):
        brightness = max(0, min(7, brightness))
        cmd = bytearray(
            b'\xcd\x00\x00\x00\x00\x06\x01\x01\x00\xff\x00\x00\x00\x00\x00\x00')
        cmd[9] = brightness
        self._scsi_command(cmd)
        print(f"[lcd] Backlight set to {brightness}")

    def rgb_to_rgb565(self, r, g, b):
        rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        return [(rgb565 >> 8) & 0xFF, rgb565 & 0xFF]

    def display_image(self, image):
        x_ratio  = self.width  / image.width
        y_ratio  = self.height / image.height
        ratio    = min(x_ratio, y_ratio)
        new_size = (int(image.width * ratio), int(image.height * ratio))
        image    = image.resize(new_size, Image.Resampling.LANCZOS)

        canvas = Image.new("RGB", (self.width, self.height), (0, 0, 0))
        canvas.paste(image,
                     ((self.width  - image.width)  // 2,
                      (self.height - image.height) // 2))

        if self.flip_horizontal:
            canvas = canvas.transpose(Image.FLIP_LEFT_RIGHT)
        if self.flip_vertical:
            canvas = canvas.transpose(Image.FLIP_TOP_BOTTOM)

        if _NUMPY_OK:
            arr       = np.array(canvas, dtype=np.uint16)
            r, g, b   = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            rgb565    = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            rgb565_be = ((rgb565 & 0xFF) << 8) | (rgb565 >> 8)
            out_data  = rgb565_be.flatten().astype(np.uint16).tobytes()
        else:
            pixels   = canvas.load()
            out_data = bytearray(self.width * self.height * 2)
            idx = 0
            for py in range(self.height):
                for px in range(self.width):
                    r, g, b  = pixels[px, py]
                    rgb565   = self.rgb_to_rgb565(r, g, b)
                    out_data[idx]     = rgb565[0]
                    out_data[idx + 1] = rgb565[1]
                    idx += 2

        cmd = bytearray(
            b'\xcd\x00\x00\x00\x00\x06\x12\xff\xff\xff\xff\xff\xff\xff\xff\x00')
        cmd[7:15] = pack("<HHHH", 0, 0, self.width - 1, self.height - 1)
        self._scsi_command(cmd, out_data)

    def clear(self):
        out_data = bytearray(self.width * self.height * 2)
        cmd = bytearray(
            b'\xcd\x00\x00\x00\x00\x06\x12\xff\xff\xff\xff\xff\xff\xff\xff\x00')
        cmd[7:15] = pack("<HHHH", 0, 0, self.width - 1, self.height - 1)
        self._scsi_command(cmd, out_data)

    def close(self):
        if self.dev:
            try:
                self.set_backlight(1)
            except Exception:
                pass
            usb.util.dispose_resources(self.dev)
            self.dev = None
