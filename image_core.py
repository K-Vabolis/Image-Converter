"""
image_core.py - turns DDS, TGA and BMP files into normal PNG images, pure Python.

DDS: DXT1/DXT3/DXT5 (also DXT2/DXT4), ATI1/ATI2 (BC4/BC5), the DX10 header
variants of those, and uncompressed RGB/RGBA/luminance/alpha. First mip level only.
TGA: indexed, true color and gray, plain or RLE, any origin.
BMP: 1, 4, 8, 16, 24 and 32 bit.
Anything else is handed to Pillow when it is installed (BC7, TIFF, WebP, PSD ...).
"""
import io
import os
import struct
import zlib

MAGIC = b"DDS "

DDPF_ALPHAPIXELS = 0x1
DDPF_ALPHA = 0x2
DDPF_FOURCC = 0x4
DDPF_RGB = 0x40
DDPF_YUV = 0x200
DDPF_LUMINANCE = 0x20000

DXGI_TO_FOURCC = {
    71: b"DXT1", 72: b"DXT1", 74: b"DXT3", 75: b"DXT3", 77: b"DXT5", 78: b"DXT5",
    80: b"ATI1", 81: b"ATI1", 83: b"ATI2", 84: b"ATI2",
}
DXGI_RAW = {
    28: (32, 0x000000FF, 0x0000FF00, 0x00FF0000, 0xFF000000),
    29: (32, 0x000000FF, 0x0000FF00, 0x00FF0000, 0xFF000000),
    87: (32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000),
    91: (32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000),
    88: (32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0),
    61: (8, 0xFF, 0, 0, 0),
    65: (8, 0, 0, 0, 0xFF),
}


class ImageError(Exception):
    pass


class Header:
    __slots__ = ("width", "height", "flags", "fourcc", "bits", "rmask", "gmask", "bmask",
                 "amask", "pf_flags", "data_offset", "dxgi", "mips")


def parse_header(data):
    if len(data) < 128 or data[:4] != MAGIC:
        raise ImageError("Not a DDS file")
    size, flags, height, width, _pitch, _depth, mips = struct.unpack_from("<7I", data, 4)
    if size != 124:
        raise ImageError("Unusual DDS header")
    pf = struct.unpack_from("<8I", data, 76)
    h = Header()
    h.width, h.height, h.flags, h.mips = width, height, flags, max(mips, 1)
    h.pf_flags = pf[1]
    h.fourcc = struct.pack("<I", pf[2]) if pf[1] & DDPF_FOURCC else b""
    h.bits, h.rmask, h.gmask, h.bmask, h.amask = pf[3], pf[4], pf[5], pf[6], pf[7]
    h.data_offset = 128
    h.dxgi = 0
    if h.fourcc == b"DX10":
        if len(data) < 148:
            raise ImageError("Truncated DX10 header")
        h.dxgi = struct.unpack_from("<I", data, 128)[0]
        h.data_offset = 148
        if h.dxgi in DXGI_TO_FOURCC:
            h.fourcc = DXGI_TO_FOURCC[h.dxgi]
        elif h.dxgi in DXGI_RAW:
            h.fourcc = b""
            h.pf_flags = DDPF_RGB | DDPF_ALPHAPIXELS
            h.bits, h.rmask, h.gmask, h.bmask, h.amask = DXGI_RAW[h.dxgi]
            if h.bits == 8:
                h.pf_flags = DDPF_ALPHA if h.amask else DDPF_LUMINANCE
        else:
            raise ImageError("Unsupported DX10 format %d" % h.dxgi)
    if width < 1 or height < 1 or width > 16384 or height > 16384:
        raise ImageError("Bad image size %dx%d" % (width, height))
    return h


def describe_dds(data):
    h = parse_header(data)
    if h.fourcc:
        kind = h.fourcc.decode("ascii", "replace")
    else:
        kind = "%d-bit" % h.bits
    return "%dx%d %s" % (h.width, h.height, kind)


def _rgb565(c):
    r = (c >> 11) & 31
    g = (c >> 5) & 63
    b = c & 31
    return ((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2))


def _color_palette(c0, c1, four_color):
    r0, g0, b0 = _rgb565(c0)
    r1, g1, b1 = _rgb565(c1)
    p0 = bytes((r0, g0, b0, 255))
    p1 = bytes((r1, g1, b1, 255))
    if four_color:
        p2 = bytes(((2 * r0 + r1) // 3, (2 * g0 + g1) // 3, (2 * b0 + b1) // 3, 255))
        p3 = bytes(((r0 + 2 * r1) // 3, (g0 + 2 * g1) // 3, (b0 + 2 * b1) // 3, 255))
    else:
        p2 = bytes(((r0 + r1) // 2, (g0 + g1) // 2, (b0 + b1) // 2, 255))
        p3 = bytes((0, 0, 0, 0))
    return (p0, p1, p2, p3)


def _alpha_palette(a0, a1):
    if a0 > a1:
        return [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
    return [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]


def _decode_block_texture(data, h, mode):
    """mode: DXT1, DXT3, DXT5, ATI1, ATI2. Returns RGBA bytes."""
    w, ht = h.width, h.height
    bw, bh = (w + 3) // 4, (ht + 3) // 4
    block = 8 if mode in ("DXT1", "ATI1") else 16
    need = bw * bh * block
    src = data[h.data_offset:h.data_offset + need]
    if len(src) < need:
        raise ImageError("File is cut off (needs %d bytes, has %d)" % (need, len(src)))
    stride = bw * 16
    out = bytearray(stride * bh * 4)
    pal_cache = {}
    unpack = struct.unpack_from
    pos = 0
    for by in range(bh):
        row0 = by * 4 * stride
        for bx in range(bw):
            base = row0 + bx * 16
            if mode == "DXT1":
                c0, c1, bits = unpack("<HHI", src, pos)
                key = (c0, c1)
                pal = pal_cache.get(key)
                if pal is None:
                    pal = pal_cache[key] = _color_palette(c0, c1, c0 > c1)
                for y in range(4):
                    i = bits >> (y * 8)
                    o = base + y * stride
                    out[o:o + 16] = pal[i & 3] + pal[(i >> 2) & 3] + pal[(i >> 4) & 3] + pal[(i >> 6) & 3]
            elif mode in ("DXT3", "DXT5"):
                c0, c1, bits = unpack("<HHI", src, pos + 8)
                key = (c0, c1)
                pal = pal_cache.get(key)
                if pal is None:
                    pal = pal_cache[key] = _color_palette(c0, c1, True)
                if mode == "DXT3":
                    ab = unpack("<Q", src, pos)[0]
                    alphas = [((ab >> (4 * k)) & 15) * 17 for k in range(16)]
                else:
                    a0, a1 = src[pos], src[pos + 1]
                    ap = _alpha_palette(a0, a1)
                    ab = int.from_bytes(src[pos + 2:pos + 8], "little")
                    alphas = [ap[(ab >> (3 * k)) & 7] for k in range(16)]
                for y in range(4):
                    i = bits >> (y * 8)
                    o = base + y * stride
                    out[o:o + 16] = pal[i & 3] + pal[(i >> 2) & 3] + pal[(i >> 4) & 3] + pal[(i >> 6) & 3]
                    out[o + 3:o + 16:4] = bytes(alphas[y * 4:y * 4 + 4])
            else:
                chans = (0,) if mode == "ATI1" else (0, 1)
                vals = []
                for n in range(len(chans)):
                    p = pos + n * 8
                    ap = _alpha_palette(src[p], src[p + 1])
                    ab = int.from_bytes(src[p + 2:p + 8], "little")
                    vals.append([ap[(ab >> (3 * k)) & 7] for k in range(16)])
                for y in range(4):
                    o = base + y * stride
                    for x in range(4):
                        k = y * 4 + x
                        if mode == "ATI1":
                            v = vals[0][k]
                            px = (v, v, v, 255)
                        else:
                            px = (vals[0][k], vals[1][k], 0, 255)
                        out[o + x * 4:o + x * 4 + 4] = bytes(px)
            pos += block
    if bw * 4 == w and bh * 4 == ht:
        return bytes(out)
    rows = []
    for y in range(ht):
        rows.append(bytes(out[y * stride * 1:y * stride + w * 4]))
    return b"".join(rows)


def _shift_and_bits(mask):
    if not mask:
        return 0, 0
    shift = 0
    while not (mask >> shift) & 1:
        shift += 1
    bits = 0
    while (mask >> (shift + bits)) & 1:
        bits += 1
    return shift, bits


def _scale8(v, bits):
    if bits == 8:
        return v
    if bits == 0:
        return 0
    return (v * 255) // ((1 << bits) - 1)


def _decode_raw(data, h):
    w, ht = h.width, h.height
    bpp = h.bits // 8
    if bpp not in (1, 2, 3, 4):
        raise ImageError("Unsupported %d-bit format" % h.bits)
    need = w * ht * bpp
    src = data[h.data_offset:h.data_offset + need]
    if len(src) < need:
        raise ImageError("File is cut off")
    lum = bool(h.pf_flags & DDPF_LUMINANCE)
    only_alpha = bool(h.pf_flags & DDPF_ALPHA) and not h.rmask
    masks = []
    for m in (h.rmask, h.gmask, h.bmask, h.amask):
        masks.append(_shift_and_bits(m))
    has_alpha = bool(h.amask)
    out = bytearray(w * ht * 4)
    if bpp == 4 and [m[1] for m in masks[:3]] == [8, 8, 8] and (not has_alpha or masks[3][1] == 8):
        sr, sg, sb, sa = (m[0] // 8 for m in masks)
        for i in range(w * ht):
            p = i * 4
            out[p] = src[p + sr]
            out[p + 1] = src[p + sg]
            out[p + 2] = src[p + sb]
            out[p + 3] = src[p + sa] if has_alpha else 255
        return bytes(out)
    for i in range(w * ht):
        v = int.from_bytes(src[i * bpp:i * bpp + bpp], "little")
        p = i * 4
        if only_alpha:
            out[p:p + 4] = bytes((255, 255, 255, _scale8((v & h.amask) >> masks[3][0], masks[3][1])))
            continue
        if lum:
            l = _scale8((v & h.rmask) >> masks[0][0], masks[0][1])
            out[p:p + 3] = bytes((l, l, l))
        else:
            out[p] = _scale8((v & h.rmask) >> masks[0][0], masks[0][1])
            out[p + 1] = _scale8((v & h.gmask) >> masks[1][0], masks[1][1])
            out[p + 2] = _scale8((v & h.bmask) >> masks[2][0], masks[2][1])
        out[p + 3] = _scale8((v & h.amask) >> masks[3][0], masks[3][1]) if has_alpha else 255
    return bytes(out)


def _decode_with_pillow(data):
    try:
        from PIL import Image
    except Exception:
        raise ImageError("This format needs Pillow: run  python -m pip install pillow")
    try:
        im = Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception as ex:
        raise ImageError("Unsupported image format (%s)" % ex)
    return im.size[0], im.size[1], im.tobytes()


def decode_dds(data):
    h = parse_header(data)
    try:
        if h.fourcc in (b"DXT1",):
            return h.width, h.height, _decode_block_texture(data, h, "DXT1")
        if h.fourcc in (b"DXT2", b"DXT3"):
            return h.width, h.height, _decode_block_texture(data, h, "DXT3")
        if h.fourcc in (b"DXT4", b"DXT5"):
            return h.width, h.height, _decode_block_texture(data, h, "DXT5")
        if h.fourcc in (b"ATI1", b"BC4U"):
            return h.width, h.height, _decode_block_texture(data, h, "ATI1")
        if h.fourcc in (b"ATI2", b"BC5U"):
            return h.width, h.height, _decode_block_texture(data, h, "ATI2")
        if not h.fourcc and h.pf_flags & (DDPF_RGB | DDPF_LUMINANCE | DDPF_ALPHA):
            return h.width, h.height, _decode_raw(data, h)
    except ImageError:
        raise
    except Exception as ex:
        raise ImageError("Could not decode (%s)" % ex)
    return _decode_with_pillow(data)


def _flip_rows(rgba, w, h):
    stride = w * 4
    return b"".join(rgba[y * stride:(y + 1) * stride] for y in range(h - 1, -1, -1))


def _tga_unrle(src, pos, count, bpp):
    out = bytearray()
    need = count * bpp
    n = len(src)
    while len(out) < need and pos < n:
        head = src[pos]
        pos += 1
        run = (head & 0x7F) + 1
        if head & 0x80:
            out += src[pos:pos + bpp] * run
            pos += bpp
        else:
            out += src[pos:pos + run * bpp]
            pos += run * bpp
    if len(out) < need:
        raise ImageError("TGA data is cut off")
    return bytes(out[:need])


def _expand_16(px, alpha_bit):
    r = (px >> 10) & 31
    g = (px >> 5) & 31
    b = px & 31
    a = 255 if not alpha_bit else (255 if px & 0x8000 else 0)
    return ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2), a)


def decode_tga(data):
    if len(data) < 18:
        raise ImageError("Not a TGA file")
    idlen, cmtype, imtype, cm_first, cm_len, cm_bits, _xo, _yo, w, h, bpp, desc = struct.unpack(
        "<BBBHHBHHHHBB", data[:18])
    if imtype not in (1, 2, 3, 9, 10, 11) or w < 1 or h < 1 or bpp not in (8, 15, 16, 24, 32):
        raise ImageError("Not a TGA file")
    pos = 18 + idlen
    palette = []
    if cmtype == 1:
        cb = (cm_bits + 7) // 8
        raw = data[pos:pos + cm_len * cb]
        if len(raw) < cm_len * cb:
            raise ImageError("TGA palette is cut off")
        for i in range(cm_len):
            e = raw[i * cb:(i + 1) * cb]
            if cb == 2:
                palette.append(_expand_16(e[0] | (e[1] << 8), False)[:3] + (255,))
            elif cb == 3:
                palette.append((e[2], e[1], e[0], 255))
            else:
                palette.append((e[2], e[1], e[0], e[3]))
        pos += cm_len * cb
    bytes_pp = (bpp + 7) // 8
    count = w * h
    if imtype >= 9:
        px = _tga_unrle(data, pos, count, bytes_pp)
    else:
        px = data[pos:pos + count * bytes_pp]
        if len(px) < count * bytes_pp:
            raise ImageError("TGA data is cut off")
    out = bytearray(count * 4)
    alpha_bits = desc & 15
    if imtype in (1, 9):
        if not palette:
            raise ImageError("TGA has no palette")
        table = [bytes(p) for p in palette]
        blank = bytes(4)
        for i in range(count):
            idx = px[i] - cm_first
            out[i * 4:i * 4 + 4] = table[idx] if 0 <= idx < len(table) else blank
    elif imtype in (3, 11):
        if bytes_pp == 1:
            out[0::4] = out[1::4] = out[2::4] = px
            out[3::4] = b"\xff" * count
        else:
            out[0::4] = out[1::4] = out[2::4] = px[0::2]
            out[3::4] = px[1::2]
    elif bytes_pp == 3:
        out[0::4], out[1::4], out[2::4] = px[2::3], px[1::3], px[0::3]
        out[3::4] = b"\xff" * count
    elif bytes_pp == 4:
        out[0::4], out[1::4], out[2::4] = px[2::4], px[1::4], px[0::4]
        out[3::4] = px[3::4] if alpha_bits else b"\xff" * count
    else:
        for i in range(count):
            out[i * 4:i * 4 + 4] = bytes(_expand_16(px[i * 2] | (px[i * 2 + 1] << 8), bool(alpha_bits)))
    result = bytes(out)
    if desc & 0x10:
        rows = [result[y * w * 4:(y + 1) * w * 4] for y in range(h)]
        result = b"".join(b"".join(r[x * 4:x * 4 + 4] for x in range(w - 1, -1, -1)) for r in rows)
    if not desc & 0x20:
        result = _flip_rows(result, w, h)
    return w, h, result


def decode_bmp(data):
    if len(data) < 30 or data[:2] != b"BM":
        raise ImageError("Not a BMP file")
    off = struct.unpack_from("<I", data, 10)[0]
    hsize = struct.unpack_from("<I", data, 14)[0]
    if hsize == 12:
        w, h, _planes, bpp = struct.unpack_from("<HHHH", data, 18)
        comp, ncolors, entry = 0, 0, 3
    elif hsize >= 40:
        w, h, _planes, bpp, comp, _sz, _xp, _yp, ncolors = struct.unpack_from("<iiHHIIiiI", data, 18)
        entry = 4
    else:
        raise ImageError("Unsupported BMP header")
    top_down = h < 0
    h = abs(h)
    if comp not in (0, 3) or bpp not in (1, 4, 8, 16, 24, 32) or w < 1 or h < 1:
        raise ImageError("Unsupported BMP (compression %d, %d-bit)" % (comp, bpp))
    palette = []
    if bpp <= 8:
        n = ncolors or (1 << bpp)
        base = 14 + hsize
        for i in range(n):
            e = data[base + i * entry:base + i * entry + 3]
            palette.append(bytes((e[2], e[1], e[0], 255)) if len(e) == 3 else bytes(4))
    masks = (0x7C00, 0x03E0, 0x001F, 0) if bpp == 16 else (0x00FF0000, 0x0000FF00, 0x000000FF, 0)
    if comp == 3 and hsize >= 40 and bpp in (16, 32):
        masks = struct.unpack_from("<4I", data, 54) if hsize >= 56 else struct.unpack_from("<3I", data, 54) + (0,)
    row = ((w * bpp + 31) // 32) * 4
    out = bytearray(w * h * 4)
    for y in range(h):
        src_y = y if top_down else h - 1 - y
        line = data[off + src_y * row:off + src_y * row + row]
        if len(line) < row:
            raise ImageError("BMP data is cut off")
        o = y * w * 4
        if bpp == 24:
            out[o:o + w * 4:4], out[o + 1:o + w * 4:4], out[o + 2:o + w * 4:4] = line[2:w * 3:3], line[1:w * 3:3], line[0:w * 3:3]
            out[o + 3:o + w * 4:4] = b"\xff" * w
        elif bpp == 32 and masks[:3] == (0x00FF0000, 0x0000FF00, 0x000000FF):
            out[o:o + w * 4:4], out[o + 1:o + w * 4:4], out[o + 2:o + w * 4:4] = line[2:w * 4:4], line[1:w * 4:4], line[0:w * 4:4]
            alpha = line[3:w * 4:4]
            out[o + 3:o + w * 4:4] = alpha if masks[3] else b"\xff" * w
        elif bpp in (16, 32):
            shifts = [_shift_and_bits(m) for m in masks]
            for x in range(w):
                v = int.from_bytes(line[x * bpp // 8:(x + 1) * bpp // 8], "little")
                px = [_scale8((v & m) >> sh, bits) for m, (sh, bits) in zip(masks, shifts)]
                px[3] = px[3] if masks[3] else 255
                out[o + x * 4:o + x * 4 + 4] = bytes(px)
        else:
            per = 8 // bpp
            for x in range(w):
                byte = line[x // per]
                idx = (byte >> (8 - bpp * (x % per + 1))) & ((1 << bpp) - 1)
                out[o + x * 4:o + x * 4 + 4] = palette[idx] if idx < len(palette) else bytes(4)
    return w, h, bytes(out)


def kind_of(data, name=""):
    if data[:4] == MAGIC:
        return "DDS"
    if data[:2] == b"BM":
        return "BMP"
    low = name.lower()
    if low.endswith(".tga") or data[-18:-2] == b"TRUEVISION-XFILE":
        return "TGA"
    return "OTHER"


def decode(data, name=""):
    """Returns (width, height, rgba_bytes). The format comes from the file header."""
    kind = kind_of(data, name)
    try:
        if kind == "DDS":
            return decode_dds(data)
        if kind == "BMP":
            return decode_bmp(data)
        if kind == "TGA":
            return decode_tga(data)
    except ImageError:
        raise
    except Exception as ex:
        raise ImageError("Could not decode (%s)" % ex)
    return _decode_with_pillow(data)


def describe(data, name=""):
    """Short text such as '256x256 DXT5' for the info line."""
    kind = kind_of(data, name)
    try:
        if kind == "DDS":
            return describe_dds(data)
        w, h, _ = decode(data, name)
        return "%dx%d %s" % (w, h, kind if kind != "OTHER" else "image")
    except ImageError:
        return "unreadable image"


def _png_chunk(tag, body):
    return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF)


def png_bytes(width, height, rgba, level=6):
    """Encode RGBA as PNG, dropping the alpha channel when it is fully opaque."""
    opaque = rgba[3::4].count(255) == width * height
    rows = []
    if opaque:
        for y in range(height):
            row = rgba[y * width * 4:(y + 1) * width * 4]
            rgb = bytearray(width * 3)
            rgb[0::3], rgb[1::3], rgb[2::3] = row[0::4], row[1::4], row[2::4]
            rows.append(b"\x00" + bytes(rgb))
    else:
        for y in range(height):
            rows.append(b"\x00" + rgba[y * width * 4:(y + 1) * width * 4])
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2 if opaque else 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr)
            + _png_chunk(b"IDAT", zlib.compress(b"".join(rows), level)) + _png_chunk(b"IEND", b""))


def to_png(data, name=""):
    w, h, rgba = decode(data, name)
    return png_bytes(w, h, rgba)


def convert_file(path, outdir=None):
    """Writes name.png next to the source (or into outdir). Returns the new path."""
    with open(path, "rb") as f:
        png = to_png(f.read(), path)
    outdir = outdir or os.path.dirname(os.path.abspath(path))
    os.makedirs(outdir, exist_ok=True)
    dest = os.path.join(outdir, os.path.splitext(os.path.basename(path))[0] + ".png")
    with open(dest, "wb") as f:
        f.write(png)
    return dest


def preview_png(data, box=420, name=""):
    """PNG for the on-screen preview: scaled to fit the box, over a checkerboard."""
    w, h, rgba = decode(data, name)
    scale = min(box / w, box / h)
    if scale >= 1:
        scale = max(1, int(scale))
    tw, th = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    out = bytearray(tw * th * 4)
    xs = [min(w - 1, int(x / scale)) for x in range(tw)]
    for y in range(th):
        srow = min(h - 1, int(y / scale)) * w * 4
        orow = y * tw * 4
        for x in range(tw):
            p = srow + xs[x] * 4
            a = rgba[p + 3]
            if a == 255:
                out[orow + x * 4:orow + x * 4 + 3] = rgba[p:p + 3]
            else:
                bg = 200 if ((x // 8) + (y // 8)) % 2 else 150
                for c in range(3):
                    out[orow + x * 4 + c] = (rgba[p + c] * a + bg * (255 - a)) // 255
            out[orow + x * 4 + 3] = 255
    return png_bytes(tw, th, bytes(out), 1), "%dx%d" % (w, h)
