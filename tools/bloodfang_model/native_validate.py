"""Read-only DirectX .x validation using the installed Microsoft D3DX9 runtime.

COM signatures and slots follow Microsoft's D3DX9Xof.h, obtained from its
Microsoft.DXSDK.D3DX 9.29.952.8 NuGet package. The source hash and header are
recorded in artifacts/bloodfang-original-pet-20260914/d3dx-header-source.json.
native_validator_templates.bin contains Microsoft's standard D3DRM schema from
the local DirectX SDK rmxftmpl.h; it contains no mesh, rig, or animation data.
This checks actual native parsing and every non-reference data object's Lock,
not rendering or animation playback. No D3D device or window is created.
Optional texture inspection uses the documented D3DXGetImageInfoFromFileInMemory
signature and D3DXIMAGE_INFO layout from Microsoft Learn's D3dx9tex.h reference.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import uuid

PTR = C.c_void_p
SIZE = C.c_size_t
UINT = C.c_uint32
HRESULT = C.c_int32
PPTR = C.POINTER(PTR)
PSIZE = C.POINTER(SIZE)


class MemorySource(C.Structure):
    _fields_ = [("lpMemory", PTR), ("dSize", SIZE)]


class ImageInfo(C.Structure):
    _fields_ = [(field, UINT) for field in
                ("Width", "Height", "Depth", "MipLevels", "Format",
                 "ResourceType", "ImageFileFormat")]


def native_runtime():
    if os.name != "nt" or C.sizeof(PTR) != 8:
        raise OSError("Native validation requires 64-bit Python on Windows")
    path = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/d3dx9_31.dll"
    return path, C.WinDLL(str(path))


def validate_texture(path: Path) -> dict:
    """Read native image metadata; does not create or upload a D3D texture.

    API: https://learn.microsoft.com/en-us/windows/win32/direct3d9/
         d3dxgetimageinfofromfileinmemory
    Layout: https://learn.microsoft.com/en-us/windows/win32/direct3d9/d3dximage-info
    """
    encoded = path.read_bytes()
    if not encoded or len(encoded) > 256 * 1024 * 1024:
        raise ValueError("Texture input must be between one byte and 256 MiB")
    dll_path, library = native_runtime()
    inspect = library.D3DXGetImageInfoFromFileInMemory
    inspect.argtypes, inspect.restype = [PTR, UINT, C.POINTER(ImageInfo)], HRESULT
    buffer = C.create_string_buffer(encoded)
    info = ImageInfo()
    check(inspect(buffer, len(encoded), C.byref(info)),
          "D3DXGetImageInfoFromFileInMemory")
    return {"label": str(path), "sha256": hashlib.sha256(encoded).hexdigest(),
            "runtime": str(dll_path), "native_image_info_succeeded": True,
            "width": info.Width, "height": info.Height, "depth": info.Depth,
            "mip_levels": info.MipLevels, "d3d_format": info.Format,
            "resource_type": info.ResourceType,
            "image_file_format": info.ImageFileFormat,
            "image_file_format_name": "TGA" if info.ImageFileFormat == 2 else None}


def method(pointer: PTR, slot: int, result, *arguments):
    table = C.cast(pointer, C.POINTER(C.POINTER(PTR))).contents
    return C.WINFUNCTYPE(result, PTR, *arguments)(table[slot])


def check(value: int, operation: str) -> None:
    if value < 0:
        raise ValueError(f"{operation} failed HRESULT 0x{value & 0xffffffff:08x}")


def release(pointer: PTR) -> None:
    if pointer.value:
        method(pointer, 2, UINT)(pointer)


def data_name(pointer: PTR) -> str:
    count = SIZE()
    get_name = method(pointer, 4, HRESULT, PTR, PSIZE)
    check(get_name(pointer, None, C.byref(count)), "GetName(size)")
    if count.value == 0:
        return ""
    if count.value > 1048576:
        raise ValueError("Native object name exceeds one MiB")
    buffer = C.create_string_buffer(count.value)
    check(get_name(pointer, buffer, C.byref(count)), "GetName")
    return buffer.value.decode("ascii", "backslashreplace")


def validate_bytes(encoded: bytes, *, label: str = "memory",
                   templates: Path | None = None) -> dict:
    templates = templates or Path(__file__).with_name("native_validator_templates.bin")
    schema = templates.read_bytes()
    dll_path, library = native_runtime()
    create = library.D3DXFileCreate
    create.argtypes, create.restype = [PPTR], HRESULT
    file_pointer, enum_pointer = PTR(), PTR()
    result = {"label": label, "sha256": hashlib.sha256(encoded).hexdigest(),
              "runtime": str(dll_path), "native_parse_succeeded": False,
              "objects": 0, "references": 0, "locked_bytes": 0,
              "types": {}, "names_by_type": {}}
    types = Counter()
    names = defaultdict(set)

    def walk(pointer: PTR, depth: int) -> None:
        if depth > 256 or result["objects"] > 100000:
            raise ValueError("Native hierarchy exceeds bounded inspection limits")
        result["objects"] += 1
        name = data_name(pointer)
        guid = (C.c_ubyte * 16)()
        check(method(pointer, 8, HRESULT, PTR)(pointer, guid), "GetType")
        type_id = str(uuid.UUID(bytes_le=bytes(guid)))
        types[type_id] += 1
        reference = bool(method(pointer, 9, C.c_int32)(pointer))
        if name:
            names[type_id].add(name)
        if reference:
            result["references"] += 1
            return
        size, payload = SIZE(), PTR()
        check(method(pointer, 6, HRESULT, PSIZE, PPTR)(
            pointer, C.byref(size), C.byref(payload)), "Lock")
        try:
            if size.value > 256 * 1024 * 1024:
                raise ValueError("Native data object exceeds 256 MiB")
            if size.value and not payload.value:
                raise ValueError("Native Lock returned a null nonempty payload")
            result["locked_bytes"] += size.value
        finally:
            check(method(pointer, 7, HRESULT)(pointer), "Unlock")
        children = SIZE()
        check(method(pointer, 10, HRESULT, PSIZE)(pointer, C.byref(children)),
              "Data.GetChildren")
        for index in range(children.value):
            child = PTR()
            check(method(pointer, 11, HRESULT, SIZE, PPTR)(
                pointer, index, C.byref(child)), "Data.GetChild")
            try:
                walk(child, depth + 1)
            finally:
                release(child)

    try:
        check(create(C.byref(file_pointer)), "D3DXFileCreate")
        schema_buffer = C.create_string_buffer(schema)
        check(method(file_pointer, 5, HRESULT, PTR, SIZE)(
            file_pointer, schema_buffer, len(schema)), "RegisterTemplates")
        model_buffer = C.create_string_buffer(encoded)
        source = MemorySource(C.cast(model_buffer, PTR), len(encoded))
        check(method(file_pointer, 3, HRESULT, PTR, UINT, PPTR)(
            file_pointer, C.byref(source), 3, C.byref(enum_pointer)),
            "CreateEnumObject")
        children = SIZE()
        check(method(enum_pointer, 4, HRESULT, PSIZE)(
            enum_pointer, C.byref(children)), "Enum.GetChildren")
        result["root_objects"] = children.value
        for index in range(children.value):
            child = PTR()
            check(method(enum_pointer, 5, HRESULT, SIZE, PPTR)(
                enum_pointer, index, C.byref(child)), "Enum.GetChild")
            try:
                walk(child, 0)
            finally:
                release(child)
        result["native_parse_succeeded"] = True
        result["types"] = dict(types)
        result["names_by_type"] = {key: sorted(value) for key, value in names.items()}
        return result
    finally:
        release(enum_pointer)
        release(file_pointer)


def validate(path: Path) -> dict:
    return validate_bytes(path.read_bytes(), label=str(path))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    parser.add_argument("--texture", type=Path,
                        help="Inspect the supplied image using native D3DX9")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = validate(args.model)
    if args.texture:
        result["texture"] = validate_texture(args.texture)
    if args.report:
        args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "names_by_type"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
