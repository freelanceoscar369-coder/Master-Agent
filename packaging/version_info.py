# PyInstaller Windows version resource — embeds real FileVersion/
# ProductVersion metadata into Kalpavriksha.exe (visible in Explorer's
# file Properties > Details tab). Referenced by kalpavriksha.spec.
VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(1, 0, 0, 0),
        prodvers=(1, 0, 0, 0),
        mask=0x3F,
        flags=0x0,
        OS=0x40004,   # VOS_NT_WINDOWS32
        fileType=0x1, # VFT_APP
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "Kalpavriksha"),
                        StringStruct("FileDescription", "Kalpavriksha Founder Edition"),
                        StringStruct("FileVersion", "1.0.0.0"),
                        StringStruct("InternalName", "Kalpavriksha"),
                        StringStruct("LegalCopyright", "Kalpavriksha"),
                        StringStruct("OriginalFilename", "Kalpavriksha.exe"),
                        StringStruct("ProductName", "Kalpavriksha Founder Edition"),
                        StringStruct("ProductVersion", "1.0.0.0"),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)
