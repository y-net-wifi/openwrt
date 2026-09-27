#!/usr/bin/env python3
"""Patch OpenWrt source tree to add support for COMFAST CF-WA350."""

import os
import re

BASE = "openwrt"

NETWORK_FILE = (
    f"{BASE}/target/linux/ath79/generic/base-files/etc/board.d/02_network"
)
LEDS_FILE = (
    f"{BASE}/target/linux/ath79/generic/base-files/etc/board.d/01_leds"
)
GENERIC_MK = f"{BASE}/target/linux/ath79/image/generic.mk"
DTS_SRC = "dts/qca9563_comfast_cf-wa350.dts"
DTS_DST = f"{BASE}/target/linux/ath79/dts/qca9563_comfast_cf-wa350.dts"


# ---------------------------------------------------------------------------
# Regex that matches the previously-injected cf-wa350 LED block (anywhere)
# ---------------------------------------------------------------------------
LED_BLOCK_RE = re.compile(
    r'[\t ]*comfast,cf-wa350\)\n'
    r'[\t ]*ucidef_set_led_netdev "wan" "WAN" "red:wan" "wan"\n'
    r'[\t ]*ucidef_set_led_netdev "lan" "LAN" "green:lan" "lan"\n'
    r'[\t ]*ucidef_set_led_wlan "wlan5g" "WLAN5G" "blue:wlan5g" "phy0tpt"\n'
    r'[\t ]*;;\n?'
)


# ---------------------------------------------------------------------------
# 01_leds — line-based anchor injection after telco,t1) case
# ---------------------------------------------------------------------------
def patch_leds():
    if not os.path.exists(LEDS_FILE):
        print("!!! 01_leds not found")
        return

    with open(LEDS_FILE, "r") as f:
        content = f.read()

    # --- 1. Clean up any broken/previous cf-wa350 injection ---
    if LED_BLOCK_RE.search(content):
        content = LED_BLOCK_RE.sub('', content)
        # Remove any accidental double blank lines left behind
        content = re.sub(r'\n\n\n+', '\n\n', content)
        print(">>> 01_leds: removed previous cf-wa350 block")

    # --- 2. Locate anchor line: "telco,t1)" ---
    lines = content.split('\n')
    anchor_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == 'telco,t1)':
            anchor_idx = i
            break

    # --- 3. Prepare the injection block ---
    injection = [
        '\tcomfast,cf-wa350)',
        '\t\tucidef_set_led_netdev "wan" "WAN" "red:wan" "wan"',
        '\t\tucidef_set_led_netdev "lan" "LAN" "green:lan" "lan"',
        '\t\tucidef_set_led_wlan "wlan5g" "WLAN5G" "blue:wlan5g" "phy0tpt"',
        '\t\t;;',
    ]

    if anchor_idx != -1:
        # Find the ";;" that closes the telco case (first one after anchor)
        end_idx = -1
        for j in range(anchor_idx + 1, len(lines)):
            if lines[j].strip() == ';;':
                end_idx = j
                break

        if end_idx != -1:
            lines = lines[:end_idx + 1] + injection + lines[end_idx + 1:]
            with open(LEDS_FILE, "w") as f:
                f.write('\n'.join(lines))
            print(">>> 01_leds patched (anchor: telco,t1)")
            return
        else:
            print("!!! No ';;' found after telco,t1), falling back to esac")

    else:
        print("!!! 'telco,t1)' anchor not found, falling back to esac")

    # --- Fallback: inject just before the last 'esac' ---
    esac_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == 'esac':
            esac_idx = i
            break

    if esac_idx == -1:
        print("!!! No 'esac' found either, aborting")
        return

    lines = lines[:esac_idx] + injection + lines[esac_idx:]
    with open(LEDS_FILE, "w") as f:
        f.write('\n'.join(lines))
    print(">>> 01_leds patched (esac fallback)")


# ---------------------------------------------------------------------------
# 02_network — interfaces:
#   Line-based anchor injection after the "tplink,tl-wdr6500-v2)" case.
# ---------------------------------------------------------------------------
def patch_network():
    if not os.path.exists(NETWORK_FILE):
        print("!!! 02_network not found")
        return

    with open(NETWORK_FILE, "r") as f:
        content = f.read()

    iface_func_pos = content.find("ath79_setup_interfaces")
    macs_func_pos = content.find("ath79_setup_macs")
    if iface_func_pos == -1 or macs_func_pos == -1:
        print("!!! ath79_setup_interfaces / ath79_setup_macs not found")
        return

    iface_block = content[iface_func_pos:macs_func_pos]

    if "comfast,cf-wa350)" in iface_block:
        print(">>> 02_network interfaces already patched")
        return

    # --- Prepare the injection block ---
    injection = [
        '\tcomfast,cf-wa350)',
        '\t\tucidef_set_interfaces_lan_wan "lan" "wan"',
        '\t\t;;',
    ]

    lines = iface_block.split('\n')

    # --- Locate the anchor line: "tplink,tl-wdr6500-v2)" ---
    anchor_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == 'tplink,tl-wdr6500-v2)':
            anchor_idx = i
            break

    if anchor_idx != -1:
        # Find the closing ';;' for this case
        end_idx = -1
        for j in range(anchor_idx + 1, len(lines)):
            if lines[j].strip() == ';;':
                end_idx = j
                break

        if end_idx != -1:
            lines = lines[:end_idx + 1] + injection + lines[end_idx + 1:]
            new_block = '\n'.join(lines)
            content = content[:iface_func_pos] + new_block + content[macs_func_pos:]
            with open(NETWORK_FILE, "w") as f:
                f.write(content)
            print(">>> 02_network interfaces patched (after tplink,tl-wdr6500-v2)")
            return
        else:
            print("!!! No ';;' found after tplink,tl-wdr6500-v2), falling back to esac")
    else:
        print("!!! 'tplink,tl-wdr6500-v2)' anchor not found, falling back to esac")

    # --- Fallback: inject before the last esac inside ath79_setup_interfaces ---
    esac_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == 'esac':
            esac_idx = i
            break

    if esac_idx == -1:
        print("!!! esac not found in ath79_setup_interfaces")
        return

    lines = lines[:esac_idx] + injection + lines[esac_idx:]
    new_block = '\n'.join(lines)
    content = content[:iface_func_pos] + new_block + content[macs_func_pos:]
    with open(NETWORK_FILE, "w") as f:
        f.write(content)
    print(">>> 02_network interfaces patched (esac fallback)")


# ---------------------------------------------------------------------------
# 02_network — MACs: extend comfast,cf-e375ac) to also cover cf-wa350
# ---------------------------------------------------------------------------
def patch_network_mac():
    if not os.path.exists(NETWORK_FILE):
        print("!!! 02_network not found for MAC")
        return

    with open(NETWORK_FILE, "r") as f:
        content = f.read()

    macs_pos = content.find("ath79_setup_macs")
    if macs_pos == -1:
        print("!!! ath79_setup_macs not found")
        return

    macs_block = content[macs_pos:]

    if "comfast,cf-wa350)" in macs_block:
        print(">>> 02_network MAC already patched")
        return

    old_entry = (
        '\tcomfast,cf-e375ac)\n'
        '\t\twan_mac=$(macaddr_add $(mtd_get_mac_binary art 0x0) 1)\n'
        '\t\t;;\n'
    )

    new_entry = (
        '\tcomfast,cf-e375ac|\\\n'
        '\tcomfast,cf-wa350)\n'
        '\t\twan_mac=$(macaddr_add $(mtd_get_mac_binary art 0x0) 1)\n'
        '\t\t;;\n'
    )

    if old_entry not in macs_block:
        print("!!! Target block 'comfast,cf-e375ac)' not found in ath79_setup_macs")
        return

    new_macs_block = macs_block.replace(old_entry, new_entry, 1)
    content = content[:macs_pos] + new_macs_block

    with open(NETWORK_FILE, "w") as f:
        f.write(content)
    print(">>> 02_network MAC patched")


# ---------------------------------------------------------------------------
# image/generic.mk — inject device definition after comfast_cf-ew72
# ---------------------------------------------------------------------------
def patch_generic_mk():
    if not os.path.exists(GENERIC_MK):
        print("!!! generic.mk not found")
        return

    with open(GENERIC_MK, "r") as f:
        content = f.read()

    if "comfast_cf-wa350" in content:
        print(">>> generic.mk already patched")
        return

    anchor = "TARGET_DEVICES += comfast_cf-ew72\n"

    injection = (
        '\n'
        'define Device/comfast_cf-wa350\n'
        '  SOC := qca9563\n'
        '  DEVICE_VENDOR := COMFAST\n'
        '  DEVICE_MODEL := CF-WA350\n'
        '  DEVICE_PACKAGES := kmod-ath10k-ct ath10k-firmware-qca9888-ct \\\n'
        '\tkmod-dsa-qca8k kmod-phy-qca83xx cfw-leds -swconfig -uboot-envtools\n'
        '  IMAGE_SIZE := 16000k\n'
        'endef\n'
        'TARGET_DEVICES += comfast_cf-wa350\n'
    )

    if anchor in content:
        content = content.replace(anchor, anchor + injection, 1)
        with open(GENERIC_MK, "w") as f:
            f.write(content)
        print(">>> generic.mk patched (anchor-based)")
        return

    # Fallback: append to end of file
    print("!!! Anchor 'TARGET_DEVICES += comfast_cf-ew72' not found, appending to EOF")
    with open(GENERIC_MK, "a") as f:
        f.write(injection)
    print(">>> generic.mk patched (EOF fallback)")


# ---------------------------------------------------------------------------
# Copy the custom DTS file
# ---------------------------------------------------------------------------
def copy_dts():
    if not os.path.exists(DTS_SRC):
        print("!!! DTS source not found")
        return

    os.makedirs(os.path.dirname(DTS_DST), exist_ok=True)
    with open(DTS_SRC, "r") as f:
        data = f.read()
    with open(DTS_DST, "w") as f:
        f.write(data)
    print(">>> DTS copied")


if __name__ == "__main__":
    copy_dts()
    patch_generic_mk()
    patch_leds()
    patch_network()
    patch_network_mac()
    print(">>> All patches applied!")
