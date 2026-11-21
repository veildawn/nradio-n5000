"""Install the N5000's TF-only upgrade path in the Filogic platform script."""

BOARD = "nradio,n5000"


def patch_platform_upgrade(text: str) -> str:
    upgrade_anchor = '\tcase "$board" in\n'
    upgrade_start = text.index("platform_do_upgrade() {")
    index = text.index(upgrade_anchor, upgrade_start) + len(upgrade_anchor)
    upgrade = f"""\t{BOARD})
\t\t# The TF kernel and DTB are installed by the factory flasher.
\t\t# emmc_do_upgrade and emmc_copy_config share the TF rootdisk tail.
\t\t[ -b /dev/mmcblk0p4 ] || return 1
\t\texport EMMC_ROOT_DEV=/dev/mmcblk0p4
\t\temmc_do_upgrade "$1"
\t\t;;
"""
    if not text.startswith(upgrade, index):
        end = text.index("\n}", index)
        if f"\t{BOARD})\n" in text[index:end]:
            raise ValueError("Use a clean Filogic platform.sh for this board port.")
        text = text[:index] + upgrade + text[index:]

    for function, anchor in (
        ("platform_check_image", "\tnradio,c8-668gl)"),
        ("platform_copy_config", "\tnradio,c8-668gl|\\\n"),
    ):
        start = text.index(f"{function}() {{")
        index = text.index(anchor, start)
        entry = f"\t{BOARD}|\\\n"
        if not text[:index].endswith(entry):
            text = text[:index] + entry + text[index:]

    return text
