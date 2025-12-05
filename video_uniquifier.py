#!/usr/bin/env python3
"""
Video Uniquifier for YNTOYG
Generates unique video copies with realistic, randomized metadata
"""

import uuid
import random
import subprocess
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Optional
import json

# ============ REALISTIC DATA POOLS ============

CREATOR_TOOLS = [
    # Adobe Premiere Pro - verified versions (2024-2025)
    "Adobe Premiere Pro 2025.0 (Windows)",
    "Adobe Premiere Pro 2025.1 (Windows)",
    "Adobe Premiere Pro 2024.2 (Windows)",
    "Adobe Premiere Pro 2024.1 (Windows)",
    "Adobe Premiere Pro 2024.0 (Windows)",
    "Adobe Premiere Pro 2025.0 (Mac OS)",
    "Adobe Premiere Pro 2024.2 (Mac OS)",
    # Adobe After Effects - verified versions (24.x = 2024, 25.x = 2025)
    "Adobe After Effects 2025 25.1 (Windows)",
    "Adobe After Effects 2025 25.0 (Windows)",
    "Adobe After Effects 2024 24.4 (Windows)",
    "Adobe After Effects 2024 24.2 (Windows)",
    "Adobe After Effects 2025 25.0 (Mac OS)",
    # Final Cut Pro - verified versions (macOS only)
    "Final Cut Pro 11.0",
    "Final Cut Pro 10.8.1",
    "Final Cut Pro 10.8",
    "Final Cut Pro 10.7.1",
    # Apple iMovie - verified versions
    "iMovie 10.4.3",
    "iMovie 10.4.2",
    "iMovie 10.4.1",
    "iMovie 10.4",
    # DaVinci Resolve - verified versions (18.x, 19.x, 20.x)
    "DaVinci Resolve 20.3",
    "DaVinci Resolve 20.0",
    "DaVinci Resolve 19.1.2",
    "DaVinci Resolve 19.0",
    "DaVinci Resolve 18.6.6",
    "DaVinci Resolve 18.6",
    # VEGAS Pro - verified versions (owned by MAGIX, formerly Sony)
    "VEGAS Pro 22.0",
    "VEGAS Pro 21.0",
    "VEGAS Pro 20.0",
    # CapCut - verified versions (7.x as of late 2024/2025)
    "CapCut 7.5.0",
    "CapCut 7.4.0",
    "CapCut 7.3.0",
    "CapCut 7.1.0",
    # Wondershare Filmora - verified versions (14.x, 15.x)
    "Wondershare Filmora 15.0",
    "Wondershare Filmora 14.5",
    "Wondershare Filmora 14.0",
    "Wondershare Filmora 13.6",
]

XMP_TOOLKITS = [
    "Adobe XMP Core 9.1-c002 79.a1cd12f, 2024/11/11-19:08:46",
    "Adobe XMP Core 9.0-c001 79.f5e1b7a, 2024/06/03-18:12:44",
    "Adobe XMP Core 8.0-c001 79.8b19e16, 2023/05/09-09:30:00",
    "XMP Core 6.0.0",
    "Apple XMP Core 4.1",
]

# Generic source file names - mimics real device/export naming patterns
SOURCE_FILE_NAMES = [
    # Generic numbered exports (most common)
    "video_001.mp4",
    "video_002.mp4",
    "video_final.mp4",
    "clip_001.mp4",
    "clip_final.mov",
    "content_001.mp4",
    "content_v2.mp4",
    "export_001.mp4",
    "export_final.mp4",
    "render_001.mp4",
    "render_v2.mp4",
    "edit_final.mp4",
    "sequence_01.mp4",
    "timeline_export.mp4",
    # iPhone style (IMG_XXXX.MOV)
    "IMG_0001.MOV",
    "IMG_1234.MOV",
    "IMG_2847.MOV",
    "IMG_3921.MOV",
    "IMG_5629.MOV",
    # Android style (VID_YYYYMMDD_HHMMSS.mp4)
    "VID_20241105_143022.mp4",
    "VID_20241201_091547.mp4",
    "VID_20240915_182033.mp4",
    # Canon/DSLR style (MVI_XXXX.MOV)
    "MVI_0012.MOV",
    "MVI_1847.MOV",
    "MVI_2391.MOV",
    # GoPro style (GOPRXXXX.MP4 or GHXXXXXX.MP4)
    "GOPR0001.MP4",
    "GOPR1234.MP4",
    "GH010847.MP4",
    "GX010293.MP4",
    # DJI Drone style (DJI_XXXX.MP4)
    "DJI_0001.MP4",
    "DJI_0234.MP4",
    "DJI_0891.MP4",
    # Sony style (C0001.MP4)
    "C0001.MP4",
    "C0023.MP4",
    # Screen recordings
    "Screen Recording.mp4",
    "Recording_001.mp4",
    "Capture_001.mp4",
    # Generic simple names
    "untitled.mp4",
    "new_project.mp4",
    "video.mp4",
    "final.mp4",
    "output.mp4",
]

# Realistic Windows usernames
WINDOWS_USERNAMES = [
    "Michael", "Sarah", "David", "Emily", "James", "Jessica", "John", "Ashley",
    "Robert", "Amanda", "William", "Stephanie", "Daniel", "Nicole", "Matthew",
    "Jennifer", "Christopher", "Elizabeth", "Andrew", "Michelle", "Ryan", "Lauren",
    "Brandon", "Megan", "Tyler", "Rachel", "Kevin", "Samantha", "Justin", "Amber",
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Jamie", "Chris", "Pat",
]

# Realistic project names
PROJECT_NAMES = [
    "summer_edit",
    "vacation_2024",
    "wedding_video",
    "birthday_compilation",
    "travel_vlog",
    "music_video_project",
    "youtube_upload",
    "instagram_reel",
    "tiktok_edit",
    "family_video",
    "school_project",
    "work_presentation",
    "drone_footage_edit",
    "car_content",
    "fitness_video",
    "cooking_channel",
    "gaming_montage",
    "dance_video",
    "podcast_video",
    "product_promo",
]

# Realistic folder paths
FOLDER_PATHS = [
    "Desktop",
    "Videos",
    "Documents\\Videos",
    "Videos\\Projects",
    "Videos\\Edits",
    "Desktop\\Video Projects",
    "Documents\\Adobe",
    "Documents\\Video Editing",
    "OneDrive\\Videos",
    "Downloads\\Video Projects",
]

HANDLER_NAMES_VIDEO = [
    "VideoHandler",
    "Mainconcept Video Media Handler",
    "Apple Video Media Handler",
    "GPAC ISO Video Handler",
    "L-SMASH Video Handler",
]

HANDLER_NAMES_AUDIO = [
    "SoundHandler",
    "Mainconcept MP4 Sound Media Handler",
    "#Mainconcept MP4 Sound Media Handler",
    "Apple Sound Media Handler",
    "GPAC ISO Audio Handler",
    "L-SMASH Audio Handler",
]

TIMEZONES = [
    "-05:00",  # EST
    "-06:00",  # CST
    "-07:00",  # MST
    "-08:00",  # PST
    "+00:00",  # UTC
    "+01:00",  # CET
    "+02:00",  # EET
    "+03:00",  # Moscow
    "+08:00",  # China/Singapore
    "+09:00",  # Japan/Korea
]


# ============ UUID GENERATORS ============
# Based on real Adobe Premiere Pro metadata patterns

def generate_xmp_uuid() -> str:
    """
    Generate standard XMP-style UUID (lowercase with dashes)
    Used for: xmp.iid: and xmp.did: prefixed IDs
    Example: 87e89982-659f-4846-9b1a-a06f08f8806c
    """
    return str(uuid.uuid4())

def generate_adobe_internal_id() -> str:
    """
    Generate Adobe internal ID format (used WITHOUT xmp.iid/xmp.did prefix)
    Pattern: {8hex}-{4hex}-{4hex}-{4hex}-{4hex}00000{3hex}

    Real examples from Adobe Premiere Pro:
    - 34ee5d21-1805-73d0-5741-d72100000078
    - f673fbd4-c2da-9aad-9374-df4100000080
    - 39e48885-b4b6-587c-d179-8ec10000004b
    - ee9fa432-e5b4-4ae2-76dd-04390000004b
    - 3580146e-547d-a31e-b238-c88400000078
    """
    u = uuid.uuid4()
    hex_str = u.hex
    # Last segment: 4 random hex + "00000" + 3 hex digits (0x000-0x0FF range typically)
    last_3_hex = format(random.randint(0x040, 0x0FF), '03x')  # Common range seen in real data
    return f"{hex_str[:8]}-{hex_str[8:12]}-{hex_str[12:16]}-{hex_str[16:20]}-{hex_str[20:24]}00000{last_3_hex}"

def generate_document_id() -> str:
    """
    Generate Adobe document ID (same format as internal ID, no prefix)
    Example: ee9fa432-e5b4-4ae2-76dd-04390000004b
    """
    return generate_adobe_internal_id()

def generate_instance_id_adobe() -> str:
    """
    Generate Adobe instance ID (same format as internal ID, no prefix)
    Example: 3580146e-547d-a31e-b238-c88400000078
    """
    return generate_adobe_internal_id()


# ============ PATH GENERATORS ============

def generate_windows_project_path() -> str:
    """Generate realistic Windows project path"""
    username = random.choice(WINDOWS_USERNAMES)
    folder = random.choice(FOLDER_PATHS)
    project = random.choice(PROJECT_NAMES)

    # Add random suffix sometimes
    if random.random() > 0.5:
        project = f"{project}_{random.randint(1, 5)}"

    return f"\\\\?\\C:\\Users\\{username}\\{folder}\\{project}.prproj"

def generate_source_file_path() -> str:
    """Generate realistic source file name"""
    base_name = random.choice(SOURCE_FILE_NAMES)

    # Sometimes add version number
    if random.random() > 0.7:
        name, ext = os.path.splitext(base_name)
        base_name = f"{name}_v{random.randint(1, 5)}{ext}"

    return base_name


# ============ TIMESTAMP GENERATORS ============

def generate_realistic_timestamp(base_time: datetime = None, offset_minutes: int = None) -> str:
    """Generate realistic ISO timestamp with timezone"""
    if base_time is None:
        # Random time in the past 30 days
        days_ago = random.randint(0, 30)
        hours_ago = random.randint(0, 23)
        minutes_ago = random.randint(0, 59)
        base_time = datetime.now() - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)

    if offset_minutes:
        base_time = base_time + timedelta(minutes=offset_minutes)

    tz = random.choice(TIMEZONES)
    return base_time.strftime(f"%Y-%m-%dT%H:%M:%S{tz}")

def generate_creation_time_utc(base_time: datetime = None) -> str:
    """Generate UTC timestamp for creation_time tag"""
    if base_time is None:
        days_ago = random.randint(0, 30)
        hours_ago = random.randint(0, 23)
        base_time = datetime.now() - timedelta(days=days_ago, hours=hours_ago)

    return base_time.strftime("%Y-%m-%dT%H:%M:%S.000000Z")


# ============ COMPLETE METADATA GENERATOR ============

def generate_complete_fake_metadata() -> Dict:
    """Generate complete, realistic video metadata structure"""

    # Base timestamp for this "edit session"
    base_time = datetime.now() - timedelta(
        days=random.randint(0, 30),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59)
    )

    # Create timestamp is slightly before modify
    create_offset = -random.randint(5, 30)  # 5-30 seconds before

    creator_tool = random.choice(CREATOR_TOOLS)
    xmp_toolkit = random.choice(XMP_TOOLKITS)

    # Document IDs
    main_instance_id = f"xmp.iid:{generate_xmp_uuid()}"
    main_document_id = generate_document_id()
    original_document_id = f"xmp.did:{generate_xmp_uuid()}"

    # Source files (1-3 ingredients)
    num_ingredients = random.randint(1, 3)
    ingredients = []
    for i in range(num_ingredients):
        ingredients.append({
            "instanceID": generate_instance_id_adobe(),
            "documentID": generate_document_id(),
            "filePath": generate_source_file_path(),
            "fromPart": f"time:0d{random.randint(100000, 9999999)}00000f254016000000",
            "toPart": f"time:{random.randint(100000, 9999999)}00000f254016000000d{random.randint(100000, 9999999)}00000f254016000000",
            "maskMarkers": "None",
        })

    # History events (3-5 saves)
    num_history = random.randint(3, 5)
    history = []

    # First event is "created"
    history.append({
        "action": "created",
        "instanceID": f"xmp.iid:{generate_xmp_uuid()}",
        "when": generate_realistic_timestamp(base_time, offset_minutes=create_offset),
        "softwareAgent": creator_tool,
    })

    # Rest are "saved" events
    for i in range(num_history - 1):
        changed = random.choice(["/", "/metadata", "/"])
        history.append({
            "action": "saved",
            "instanceID": generate_instance_id_adobe() if random.random() > 0.5 else f"xmp.iid:{generate_xmp_uuid()}",
            "when": generate_realistic_timestamp(base_time, offset_minutes=i * random.randint(1, 10)),
            "softwareAgent": creator_tool,
            "changed": changed,
        })

    # Pantry (source file metadata)
    pantry = []
    for ing in ingredients:
        pantry_time = base_time - timedelta(minutes=random.randint(1, 120))
        pantry.append({
            "instanceID": ing["instanceID"],
            "documentID": ing["documentID"],
            "originalDocumentID": f"xmp.did:{generate_xmp_uuid()}",
            "metadataDate": generate_realistic_timestamp(pantry_time),
            "modifyDate": generate_realistic_timestamp(pantry_time),
            "createDate": "1904-01-01T00:00:00Z" if random.random() > 0.5 else generate_realistic_timestamp(pantry_time - timedelta(days=random.randint(1, 365))),
        })

    # DerivedFrom
    derived_from_id = f"xmp.iid:{generate_xmp_uuid()}"

    return {
        "xmpToolkit": xmp_toolkit,
        "creatorTool": creator_tool,
        "createDate": generate_realistic_timestamp(base_time, offset_minutes=create_offset),
        "modifyDate": generate_realistic_timestamp(base_time),
        "metadataDate": generate_realistic_timestamp(base_time),
        "instanceID": main_instance_id,
        "documentID": main_document_id,
        "originalDocumentID": original_document_id,
        "history": history,
        "ingredients": ingredients,
        "pantry": pantry,
        "derivedFrom": {
            "instanceID": derived_from_id,
            "documentID": derived_from_id.replace("iid", "did"),
            "originalDocumentID": derived_from_id.replace("iid", "did"),
        },
        "windowsAtom": {
            "extension": ".prproj",
            "invocationFlags": "/L",
            "uncProjectPath": generate_windows_project_path(),
        },
        "macAtom": {
            "applicationCode": str(random.choice([1347449455, 1347449456, 1094992453])),
            "invocationAppleEvent": str(random.choice([1129468018, 1129468019, 1096176756])),
        },
        "creationTimeUTC": generate_creation_time_utc(base_time),
        "handlerNameVideo": random.choice(HANDLER_NAMES_VIDEO),
        "handlerNameAudio": random.choice(HANDLER_NAMES_AUDIO),
    }


def generate_xmp_xml(metadata: Dict) -> str:
    """Generate complete XMP XML from metadata dict"""

    # Build history XML
    history_xml = ""
    for h in metadata["history"]:
        changed_attr = f'\n      stEvt:changed="{h.get("changed", "/")}"' if "changed" in h else ""
        history_xml += f'''     <rdf:li
      stEvt:action="{h["action"]}"
      stEvt:instanceID="{h["instanceID"]}"
      stEvt:when="{h["when"]}"
      stEvt:softwareAgent="{h["softwareAgent"]}"{changed_attr}/>
'''

    # Build ingredients XML
    ingredients_xml = ""
    for ing in metadata["ingredients"]:
        ingredients_xml += f'''     <rdf:li
      stRef:instanceID="{ing["instanceID"]}"
      stRef:documentID="{ing["documentID"]}"
      stRef:fromPart="{ing["fromPart"]}"
      stRef:toPart="{ing["toPart"]}"
      stRef:filePath="{ing["filePath"]}"
      stRef:maskMarkers="{ing["maskMarkers"]}"/>
'''

    # Build pantry XML
    pantry_xml = ""
    for p in metadata["pantry"]:
        pantry_xml += f'''     <rdf:li>
      <rdf:Description
       xmpMM:InstanceID="{p["instanceID"]}"
       xmpMM:DocumentID="{p["documentID"]}"
       xmpMM:OriginalDocumentID="{p["originalDocumentID"]}"
       xmp:MetadataDate="{p["metadataDate"]}"
       xmp:ModifyDate="{p["modifyDate"]}"
       xmp:CreateDate="{p["createDate"]}">
      <xmpMM:History>
       <rdf:Seq>
        <rdf:li
         stEvt:action="saved"
         stEvt:instanceID="{p["instanceID"]}"
         stEvt:when="{p["modifyDate"]}"
         stEvt:softwareAgent="{metadata["creatorTool"]}"
         stEvt:changed="/"/>
       </rdf:Seq>
      </xmpMM:History>
      </rdf:Description>
     </rdf:li>
'''

    xmp_xml = f'''<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="{metadata["xmpToolkit"]}">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:xmpDM="http://ns.adobe.com/xmp/1.0/DynamicMedia/"
    xmlns:stDim="http://ns.adobe.com/xap/1.0/sType/Dimensions#"
    xmlns:tiff="http://ns.adobe.com/tiff/1.0/"
    xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"
    xmlns:stEvt="http://ns.adobe.com/xap/1.0/sType/ResourceEvent#"
    xmlns:stRef="http://ns.adobe.com/xap/1.0/sType/ResourceRef#"
    xmlns:creatorAtom="http://ns.adobe.com/creatorAtom/1.0/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
   xmp:CreateDate="{metadata["createDate"]}"
   xmp:ModifyDate="{metadata["modifyDate"]}"
   xmp:MetadataDate="{metadata["metadataDate"]}"
   xmp:CreatorTool="{metadata["creatorTool"]}"
   xmpDM:videoFrameRate="24.000000"
   xmpDM:videoFieldOrder="Progressive"
   xmpDM:videoPixelAspectRatio="1/1"
   xmpDM:audioSampleRate="48000"
   xmpDM:audioSampleType="16Int"
   xmpDM:audioChannelType="Stereo"
   xmpDM:startTimeScale="24"
   xmpDM:startTimeSampleSize="1"
   tiff:Orientation="1"
   xmpMM:InstanceID="{metadata["instanceID"]}"
   xmpMM:DocumentID="{metadata["documentID"]}"
   xmpMM:OriginalDocumentID="{metadata["originalDocumentID"]}"
   dc:format="H.264">
   <xmpDM:duration
    xmpDM:value="1353600"
    xmpDM:scale="1/90000"/>
   <xmpDM:projectRef
    xmpDM:type="movie"/>
   <xmpDM:videoFrameSize
    stDim:w="1080"
    stDim:h="1920"
    stDim:unit="pixel"/>
   <xmpDM:startTimecode
    xmpDM:timeFormat="24Timecode"
    xmpDM:timeValue="00:00:00:00"/>
   <xmpDM:altTimecode
    xmpDM:timeValue="00:00:00:00"
    xmpDM:timeFormat="24Timecode"/>
   <xmpMM:History>
    <rdf:Seq>
{history_xml}    </rdf:Seq>
   </xmpMM:History>
   <xmpMM:Ingredients>
    <rdf:Bag>
{ingredients_xml}    </rdf:Bag>
   </xmpMM:Ingredients>
   <xmpMM:Pantry>
    <rdf:Bag>
{pantry_xml}    </rdf:Bag>
   </xmpMM:Pantry>
   <xmpMM:DerivedFrom
    stRef:instanceID="{metadata["derivedFrom"]["instanceID"]}"
    stRef:documentID="{metadata["derivedFrom"]["documentID"]}"
    stRef:originalDocumentID="{metadata["derivedFrom"]["originalDocumentID"]}"/>
   <creatorAtom:windowsAtom
    creatorAtom:extension="{metadata["windowsAtom"]["extension"]}"
    creatorAtom:invocationFlags="{metadata["windowsAtom"]["invocationFlags"]}"
    creatorAtom:uncProjectPath="{metadata["windowsAtom"]["uncProjectPath"]}"/>
   <creatorAtom:macAtom
    creatorAtom:applicationCode="{metadata["macAtom"]["applicationCode"]}"
    creatorAtom:invocationAppleEvent="{metadata["macAtom"]["invocationAppleEvent"]}"/>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>'''

    return xmp_xml


# ============ MAIN TEST ============

if __name__ == "__main__":
    print("=" * 60)
    print("VIDEO UNIQUIFIER - Fake Metadata Generator")
    print("=" * 60)

    # Generate sample metadata
    metadata = generate_complete_fake_metadata()

    print("\n📋 Generated Metadata Sample:")
    print(f"  Creator Tool: {metadata['creatorTool']}")
    print(f"  Create Date:  {metadata['createDate']}")
    print(f"  Instance ID:  {metadata['instanceID']}")
    print(f"  Document ID:  {metadata['documentID']}")
    print(f"  Project Path: {metadata['windowsAtom']['uncProjectPath']}")

    print(f"\n📁 Source Files ({len(metadata['ingredients'])}):")
    for ing in metadata["ingredients"]:
        print(f"  - {ing['filePath']}")

    print(f"\n📜 History ({len(metadata['history'])} events):")
    for h in metadata["history"]:
        print(f"  - [{h['action']}] {h['when']}")

    # Generate XMP XML
    xmp = generate_xmp_xml(metadata)

    print(f"\n✅ Generated XMP XML: {len(xmp)} characters")

    # Save sample
    with open("sample_xmp.xml", "w") as f:
        f.write(xmp)
    print("   Saved to: sample_xmp.xml")

    # Also save metadata as JSON for reference
    with open("sample_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print("   Saved to: sample_metadata.json")
