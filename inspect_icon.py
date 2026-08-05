"""Inspect icon resources embedded in a Windows PE/EXE file.

Walks the Win32 resource directory to find RT_ICON groups and prints
their size and pixel dimensions (by parsing the BITMAPINFOHEADER or
embedded PNG of each icon image).
"""
import io
import struct
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None


def parse_pe(path: str):
    with open(path, "rb") as f:
        data = f.read()

    if data[:2] != b"MZ":
        raise SystemExit("Not an MZ/PE file")

    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_off:pe_off + 4] != b"PE\x00\x00":
        raise SystemExit("PE signature not found")

    coff = pe_off + 4
    _machine, num_sections, _, _, _, opt_hdr_size, _ = struct.unpack_from(
        "<HHIIIHH", data, coff
    )
    opt_off = coff + 20
    magic = struct.unpack_from("<H", data, opt_off)[0]
    is64 = magic == 0x20B

    num_dd = struct.unpack_from("<I", data, opt_off + (108 if is64 else 92))[0]
    dd_off = opt_off + (112 if is64 else 96)

    if num_dd < 3:
        raise SystemExit("No resource directory entries")
    rsrc_rva, rsrc_size = struct.unpack_from("<II", data, dd_off + 8 * 2)
    if rsrc_rva == 0:
        raise SystemExit("No resource directory")

    sec_off = opt_off + opt_hdr_size
    sections = []
    for i in range(num_sections):
        s = sec_off + 40 * i
        vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", data, s + 8)
        sections.append((vaddr, max(vsize, rsize), raddr))

    def rva_to_off(rva: int) -> int:
        for vaddr, vsize, raddr in sections:
            if vaddr <= rva < vaddr + vsize:
                return raddr + (rva - vaddr)
        raise ValueError(f"RVA 0x{rva:x} not found")

    rsrc_off = rva_to_off(rsrc_rva)
    return data, rsrc_off, rsrc_rva, rva_to_off


def walk_type(data, rsrc_off, type_id):
    """Yield (file_offset, size) for each resource of the given type id."""
    named, ids = struct.unpack_from("<HH", data, rsrc_off + 12)
    type_dir = None
    for i in range(named + ids):
        e = rsrc_off + 16 + i * 8
        tid, sub = struct.unpack_from("<II", data, e)
        if (tid & 0x7FFFFFFF) == type_id and (sub & 0x80000000):
            type_dir = rsrc_off + (sub & 0x7FFFFFFF)
            break
    if type_dir is None:
        return

    def walk(dir_off):
        n, i = struct.unpack_from("<HH", data, dir_off + 12)
        for idx in range(n + i):
            e = dir_off + 16 + idx * 8
            _nid, sub = struct.unpack_from("<II", data, e)
            if sub & 0x80000000:
                yield from walk(rsrc_off + (sub & 0x7FFFFFFF))
            else:
                leaf = rsrc_off + sub
                rva, size, _cp, _res = struct.unpack_from("<IIII", data, leaf)
                # data RVA is absolute RVA
                file_off = None
                # recompute via sections — caller passes helper? Use rva relative:
                # We only have rsrc_off; convert rva using difference from rsrc
                yield ("rva", rva, size)

    yield from walk(type_dir)


def describe_icon(blob):
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        if Image is None:
            return "PNG", "?", "?", "?"
        im = Image.open(io.BytesIO(blob)).convert("RGBA")
        w, h = im.size
        cx = im.getpixel((w // 2, h // 2))
        return "PNG", w, h, cx
    if len(blob) >= 40 and blob[:4] == b"\x28\x00\x00\x00":
        w, h = struct.unpack_from("<ii", blob, 4)
        if w == 0:
            w = 256
        if h == 0:
            h = 256
        # DIB icon height is double (XOR + AND mask)
        h = h // 2 if h >= 2 * w else h
        bpp = struct.unpack_from("<H", blob, 14)[0]
        return "BMP", w, h, bpp
    return "???", "?", "?", "?"


def main():
    default = Path(__file__).resolve().parent / "dist" / "VoxSlide AI.exe"
    path = sys.argv[1] if len(sys.argv) > 1 else str(default)
    data, rsrc_off, rsrc_rva, rva_to_off = parse_pe(path)

    print(f"File: {path}")
    RT_ICON, RT_GROUP_ICON = 3, 14

    def collect(type_id):
        results = []
        named, ids = struct.unpack_from("<HH", data, rsrc_off + 12)
        type_dir = None
        for i in range(named + ids):
            e = rsrc_off + 16 + i * 8
            tid, sub = struct.unpack_from("<II", data, e)
            if (tid & 0x7FFFFFFF) == type_id and (sub & 0x80000000):
                type_dir = rsrc_off + (sub & 0x7FFFFFFF)
                break
        if type_dir is None:
            return results

        def walk(dir_off):
            n, i = struct.unpack_from("<HH", data, dir_off + 12)
            for idx in range(n + i):
                e = dir_off + 16 + idx * 8
                _nid, sub = struct.unpack_from("<II", data, e)
                if sub & 0x80000000:
                    walk(rsrc_off + (sub & 0x7FFFFFFF))
                else:
                    leaf = rsrc_off + sub
                    rva, size, _cp, _res = struct.unpack_from("<IIII", data, leaf)
                    off = rva_to_off(rva)
                    results.append((off, size))

        walk(type_dir)
        return results

    icons = collect(RT_ICON)
    groups = collect(RT_GROUP_ICON)
    print(f"RT_GROUP_ICON entries: {len(groups)}")
    print(f"RT_ICON entries:       {len(icons)}")

    if not icons:
        raise SystemExit(2)

    print("\nRT_ICON images:")
    print(f"  {'#':>2}  {'offset':>10}  {'size':>8}  {'kind':>4}  {'WxH':>10}  detail")
    for i, (off, size) in enumerate(icons):
        blob = data[off:off + size]
        kind, a, b, c = describe_icon(blob)
        if kind == "PNG":
            print(f"  {i:>2}  0x{off:08x}  {size:>8}  PNG   {a}x{b:<5}  center={c}")
        else:
            print(f"  {i:>2}  0x{off:08x}  {size:>8}  {kind:>4}  {a}x{b:<5}  bpp/detail={c}")

    # Compare largest PNG/BMP center to source icon.ico if present
    src = Path(__file__).resolve().parent / "icon.ico"
    if src.is_file() and Image is not None:
        im = Image.open(src)
        for i in range(16):
            try:
                im.seek(i)
            except EOFError:
                break
            if im.size == (256, 256):
                rgba = im.convert("RGBA")
                print(f"\nSource icon.ico 256 center = {rgba.getpixel((128, 128))}")
                break


if __name__ == "__main__":
    main()
